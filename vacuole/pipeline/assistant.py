"""The LangGraph pipeline behind the Telegram bot.

Flow: one fast model call that both routes the request and builds a search plan ->
a parallel product search -> one short model call for the human touch. Product
rendering is deterministic (see bot/formatting.py), so the model never has to restate
prices or links.

    understand -> search -> present -> END
              \\-> chat -> END

Every collaborator is injected, so the graph can be exercised with fakes.
"""

from __future__ import annotations

from typing import Any, Sequence, TypedDict

from langgraph.graph import END, StateGraph

from vacuole.domain.errors import ProviderError
from vacuole.domain.models import (
    AssistantReply,
    ChatTurn,
    SearchOutcome,
    SearchPlan,
    UserLocation,
)
from vacuole.pipeline.planner import QueryPlanner
from vacuole.pipeline.responders import (
    OFF_TOPIC_TEXT,
    ChatResponder,
    ResultNarrator,
    no_results_message,
)
from vacuole.ports import ProductSearch, ProgressReporter


class GraphState(TypedDict, total=False):
    history: Sequence[ChatTurn]
    user_input: str
    location: UserLocation
    progress: ProgressReporter | None
    intent: str
    plan: SearchPlan
    outcome: SearchOutcome
    reply: AssistantReply


class ShoppingAssistant:
    """Implements the `Assistant` port."""

    def __init__(
        self,
        planner: QueryPlanner,
        search: ProductSearch,
        narrator: ResultNarrator,
        responder: ChatResponder,
    ):
        self._planner = planner
        self._search = search
        self._narrator = narrator
        self._responder = responder
        self._graph = self._build_graph()

    # -- public API ---------------------------------------------------------

    async def reply(
        self,
        user_input: str,
        *,
        history: Sequence[ChatTurn],
        location: UserLocation,
        progress: ProgressReporter | None = None,
    ) -> AssistantReply:
        initial: GraphState = {
            "history": history,
            "user_input": user_input,
            "location": location,
            "progress": progress,
        }
        try:
            final = await self._graph.ainvoke(initial)
        except Exception as exc:
            print(f"[assistant] graph failed: {exc}")
            return AssistantReply(
                kind="text",
                text="Something went wrong while handling that. Please try again.",
                notice=str(exc),
            )
        return final.get("reply") or AssistantReply(
            kind="text", text="I couldn't put together a reply for that."
        )

    # -- graph --------------------------------------------------------------

    def _build_graph(self):
        graph = StateGraph(GraphState)
        graph.add_node("understand", self._understand)
        graph.add_node("search", self._run_search)
        graph.add_node("present", self._present)
        graph.add_node("chat", self._chat)
        graph.add_node("decline", self._decline)

        graph.set_entry_point("understand")
        graph.add_conditional_edges(
            "understand",
            self._route,
            {"search": "search", "chat": "chat", "decline": "decline"},
        )
        graph.add_edge("search", "present")
        graph.add_edge("present", END)
        graph.add_edge("chat", END)
        graph.add_edge("decline", END)
        return graph.compile()

    @staticmethod
    def _route(state: GraphState) -> str:
        intent = state.get("intent")
        if intent == "search":
            return "search"
        if intent == "off_topic":
            return "decline"
        return "chat"

    async def _decline(self, state: GraphState) -> dict[str, Any]:
        """Out-of-scope requests get a fixed reply; no model call can answer them."""
        return {"reply": AssistantReply(kind="text", text=OFF_TOPIC_TEXT)}

    @staticmethod
    async def _progress(state: GraphState, key: str, detail: str = "") -> None:
        tracker = state.get("progress")
        if tracker is not None:
            await tracker.step(key, detail)

    # -- nodes --------------------------------------------------------------

    async def _understand(self, state: GraphState) -> dict[str, Any]:
        await self._progress(state, "understanding")
        planned = await self._planner.plan(
            state.get("user_input", ""), state.get("history") or [], state["location"]
        )
        if planned.intent == "search":
            await self._progress(state, "planning", f"Searching for “{planned.plan.query[:48]}”…")
        return {"intent": planned.intent, "plan": planned.plan}

    async def _run_search(self, state: GraphState) -> dict[str, Any]:
        await self._progress(state, "searching")
        try:
            outcome = await self._search.search(state["plan"], state["location"])
        except ProviderError as exc:
            outcome = SearchOutcome(products=[], errors=[str(exc)])
        await self._progress(state, "comparing")
        return {"outcome": outcome}

    async def _present(self, state: GraphState) -> dict[str, Any]:
        """Cards are rendered deterministically; the model only adds one line."""
        await self._progress(state, "writing")
        plan, outcome = state["plan"], state["outcome"]

        if not outcome.products:
            return {
                "reply": AssistantReply(
                    kind="text",
                    text=no_results_message(plan, outcome),
                    query=plan.query,
                    notice="; ".join(outcome.errors),
                )
            }

        note = await self._narrator.note(
            plan.query or state.get("user_input", ""), outcome.products
        )
        return {
            "reply": AssistantReply(
                kind="products",
                text=note,
                products=outcome.products,
                query=plan.query,
                notice="; ".join(outcome.errors),
            )
        }

    async def _chat(self, state: GraphState) -> dict[str, Any]:
        await self._progress(state, "writing")
        text = await self._responder.respond(
            state.get("user_input", ""), state.get("history") or []
        )
        return {"reply": AssistantReply(kind="text", text=text)}
