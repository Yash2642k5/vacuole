import unittest

from vacuole.domain.errors import ProviderError
from vacuole.domain.models import DEFAULT_LOCATION, ChatTurn, SearchOutcome
from vacuole.pipeline.assistant import ShoppingAssistant
from vacuole.pipeline.planner import (
    QueryPlanner,
    coerce_price,
    normalise_sort,
    parse_plan_json,
)
from vacuole.pipeline.responders import CHAT_FAILURE_TEXT, ChatResponder, ResultNarrator
from vacuole.adapters.llm import FallbackTextModel
from vacuole.services.product_search import ProductSearchService
from vacuole.tests.fakes import FakeEngine, FakeModel, RecordingProgress, product

SEARCH_JSON = (
    '```json\n{"intent": "search", "query": "earbuds", "max_price": "2k", '
    '"sort": "cheapest", "stores": ["Amazon"]}\n```'
)


class PlannerHelperTests(unittest.TestCase):
    def test_price_suffixes(self):
        self.assertEqual(coerce_price("20k"), 20_000)
        self.assertEqual(coerce_price("₹2,000"), 2_000)
        self.assertEqual(coerce_price("2 lakh"), 200_000)
        self.assertIsNone(coerce_price(None))
        self.assertIsNone(coerce_price(-5))

    def test_json_inside_prose_and_fences(self):
        self.assertEqual(parse_plan_json('Sure! {"a": 1} done')["a"], 1)
        self.assertEqual(parse_plan_json(SEARCH_JSON)["query"], "earbuds")
        self.assertEqual(parse_plan_json("no json"), {})

    def test_sort_aliases(self):
        self.assertEqual(normalise_sort("Cheapest"), "price_asc")
        self.assertEqual(normalise_sort("top_rated"), "rating")
        self.assertEqual(normalise_sort("???"), "relevance")


class PlannerTests(unittest.IsolatedAsyncioTestCase):
    async def test_builds_plan_from_model_json(self):
        planned = await QueryPlanner(FakeModel(SEARCH_JSON)).plan("earbuds under 2k", [], DEFAULT_LOCATION)
        self.assertEqual(planned.intent, "search")
        self.assertEqual(planned.plan.max_price, 2000)
        self.assertEqual(planned.plan.sort, "price_asc")
        self.assertEqual(planned.plan.stores, ["Amazon"])

    async def test_keyword_fallback_when_model_fails(self):
        planned = await QueryPlanner(FakeModel(RuntimeError("down"))).plan(
            "find cheap earbuds", [], DEFAULT_LOCATION
        )
        self.assertEqual((planned.intent, planned.plan.query), ("search", "find cheap earbuds"))

    async def test_greeting_routes_to_chat(self):
        planned = await QueryPlanner(FakeModel("not json")).plan("hello", [], DEFAULT_LOCATION)
        self.assertEqual(planned.intent, "chat")

    async def test_history_reaches_the_prompt(self):
        model = FakeModel("{}")
        await QueryPlanner(model).plan("it", [ChatTurn("user", "iphone 16")], DEFAULT_LOCATION)
        self.assertIn("User: iphone 16", model.prompts[0])


class ProductSearchServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_merges_engines_and_survives_one_failing(self):
        service = ProductSearchService(
            [
                FakeEngine("good", [product("A", 10)]),
                FakeEngine("bad", error=ProviderError("boom")),
            ]
        )
        from vacuole.domain.models import SearchPlan

        outcome = await service.search(SearchPlan(query="a"), DEFAULT_LOCATION)
        self.assertEqual([p.title for p in outcome.products], ["A"])
        self.assertEqual(outcome.engines_used, ["good"])
        self.assertEqual(outcome.errors, ["bad: boom"])

    async def test_engine_can_opt_out(self):
        from vacuole.domain.models import SearchPlan

        service = ProductSearchService([FakeEngine("skipped", [product("A")], applies=False)])
        outcome = await service.search(SearchPlan(query="a"), DEFAULT_LOCATION)
        self.assertEqual(outcome.products, [])

    async def test_empty_query_short_circuits(self):
        from vacuole.domain.models import SearchPlan

        outcome = await ProductSearchService([]).search(SearchPlan(query="  "), DEFAULT_LOCATION)
        self.assertEqual(outcome.errors, ["Empty search query."])


class _StubSearch:
    def __init__(self, outcome=None, error=None):
        self._outcome, self._error = outcome, error

    async def search(self, plan, location, limit=None):
        if self._error:
            raise self._error
        return self._outcome


def make_assistant(planner_reply, search, chat_reply="hi there", note="Best value."):
    return ShoppingAssistant(
        planner=QueryPlanner(FakeModel(planner_reply)),
        search=search,
        narrator=ResultNarrator(FakeModel(note)),
        responder=ChatResponder(FakeModel(chat_reply)),
    )


class AssistantGraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_path_returns_products_and_reports_progress(self):
        progress = RecordingProgress()
        assistant = make_assistant(
            SEARCH_JSON, _StubSearch(SearchOutcome(products=[product("Buds", 999)]))
        )
        reply = await assistant.reply(
            "earbuds", history=[], location=DEFAULT_LOCATION, progress=progress
        )
        self.assertEqual(reply.kind, "products")
        self.assertEqual(reply.query, "earbuds")
        self.assertEqual(reply.text, "Best value.")
        self.assertEqual(
            progress.steps, ["understanding", "planning", "searching", "comparing", "writing"]
        )

    async def test_chat_path_skips_search(self):
        assistant = make_assistant('{"intent": "chat"}', _StubSearch(error=AssertionError("no search")))
        reply = await assistant.reply("thanks!", history=[], location=DEFAULT_LOCATION)
        self.assertEqual((reply.kind, reply.text), ("text", "hi there"))

    async def test_provider_error_becomes_a_friendly_reply(self):
        assistant = make_assistant(SEARCH_JSON, _StubSearch(error=ProviderError("quota")))
        reply = await assistant.reply("earbuds", history=[], location=DEFAULT_LOCATION)
        self.assertEqual(reply.kind, "text")
        self.assertIn("couldn't reach", reply.text)
        self.assertEqual(reply.notice, "quota")

    async def test_no_results_message_mentions_budget(self):
        assistant = make_assistant(SEARCH_JSON, _StubSearch(SearchOutcome(products=[])))
        reply = await assistant.reply("earbuds", history=[], location=DEFAULT_LOCATION)
        self.assertIn("below 2,000", reply.text)


class ResponderTests(unittest.IsolatedAsyncioTestCase):
    async def test_fallback_model_used_when_primary_raises(self):
        model = FallbackTextModel(FakeModel(RuntimeError("x")), FakeModel("from fallback"))
        self.assertEqual(await ChatResponder(model).respond("hi", []), "from fallback")

    async def test_canned_text_when_everything_fails(self):
        model = FallbackTextModel(FakeModel(RuntimeError("a")), FakeModel(RuntimeError("b")))
        self.assertEqual(await ChatResponder(model).respond("hi", []), CHAT_FAILURE_TEXT)


if __name__ == "__main__":
    unittest.main()
