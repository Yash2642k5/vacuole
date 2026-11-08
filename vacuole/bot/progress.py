"""A live progress bar that edits one Telegram message in place."""

from __future__ import annotations

import time

from telegram.constants import ParseMode
from telegram.error import BadRequest, RetryAfter, TimedOut

from vacuole.bot.formatting import clip, esc

BAR_SEGMENTS = 10
BAR_FILLED = "▰"
BAR_EMPTY = "▱"

# Telegram throttles rapid edits of one message. The whole search takes a few
# seconds, so the window has to stay small or the bar would never visibly move.
MIN_EDIT_INTERVAL = 0.35

STEPS: dict[str, tuple[int, str]] = {
    "received": (5, "Reading your request…"),
    "understanding": (18, "Working out what you need…"),
    "planning": (32, "Building the search…"),
    "searching": (55, "Searching stores near you…"),
    "comparing": (78, "Comparing prices and ratings…"),
    "writing": (92, "Putting the results together…"),
}


def render_bar(percent: int) -> str:
    percent = max(0, min(100, int(percent)))
    filled = round(BAR_SEGMENTS * percent / 100)
    return f"{BAR_FILLED * filled}{BAR_EMPTY * (BAR_SEGMENTS - filled)}  {percent}%"


class ProgressTracker:
    """Owns one Telegram message and edits it in place as the work advances.

    Satisfies the `ProgressReporter` port. Every failure mode here is swallowed:
    progress cosmetics must never break a search.
    """

    def __init__(self, message=None, title: str = "", *, enabled: bool = True):
        self._message = message
        self._title = title
        self._enabled = enabled
        self._percent = 0
        self._label = ""
        # What is actually on screen, as opposed to what we want on screen. The two
        # diverge whenever an update is throttled.
        self._rendered: tuple[int, str] = (-1, "")
        self._last_edit = 0.0
        self._closed = False

    @classmethod
    async def start(cls, update, title: str = "Working on it") -> "ProgressTracker":
        """Post the initial progress card."""
        tracker = cls(title=title)
        try:
            tracker._message = await update.message.reply_text(
                tracker._render(5, STEPS["received"][1]),
                parse_mode=ParseMode.HTML,
            )
            tracker._percent = 5
            tracker._label = STEPS["received"][1]
            tracker._rendered = (5, tracker._label)
            tracker._last_edit = time.monotonic()
        except (BadRequest, RetryAfter, TimedOut) as exc:
            print(f"[progress] could not start tracker: {exc}")
            tracker._enabled = False
        return tracker

    def _render(self, percent: int, label: str) -> str:
        head = f"🔎 <b>{esc(clip(self._title, 90))}</b>\n\n" if self._title else ""
        return f"{head}<code>{render_bar(percent)}</code>\n<i>{esc(label)}</i>"

    async def step(self, key: str, detail: str = "") -> None:
        """Advance to a named milestone.

        Each milestone fires at most once per request, so these always render: at six
        edits per search there is no flood to guard against, and throttling them would
        strand the last step inside the window.
        """
        percent, label = STEPS.get(key, (self._percent, key))
        await self.set(percent, detail or label, force=True)

    async def set(self, percent: int, label: str, *, force: bool = False) -> None:
        if not self._enabled or self._closed or self._message is None:
            return

        # Never move the bar backwards; the graph can revisit nodes.
        self._percent = max(percent, self._percent)
        self._label = label

        # Already on screen, nothing to do. `force` skips the throttle below, never
        # this check: Telegram rejects an unchanged edit anyway.
        if self._rendered == (self._percent, self._label):
            return

        # Inside the throttle window: leave the target pending. Because we compare
        # against what was rendered rather than against the target, the next step
        # still carries this one through instead of silently dropping it.
        now = time.monotonic()
        if not force and now - self._last_edit < MIN_EDIT_INTERVAL and self._percent < 100:
            return

        self._rendered = (self._percent, self._label)
        await self._edit(self._render(self._percent, self._label))

    async def _edit(self, text: str, reply_markup=None) -> None:
        try:
            await self._message.edit_text(
                text, parse_mode=ParseMode.HTML, reply_markup=reply_markup
            )
            self._last_edit = time.monotonic()
        except BadRequest as exc:
            # "Message is not modified" is expected and harmless.
            if "not modified" not in str(exc).lower():
                print(f"[progress] edit failed: {exc}")
        except (RetryAfter, TimedOut) as exc:
            print(f"[progress] edit throttled: {exc}")

    async def finish(self, summary: str = "") -> None:
        """Replace the bar with a closing line, or delete it if nothing to say."""
        if not self._enabled or self._closed or self._message is None:
            self._closed = True
            return
        self._closed = True
        if summary:
            await self._edit(summary)
        else:
            try:
                await self._message.delete()
            except (BadRequest, RetryAfter, TimedOut):
                await self._edit("✅ <i>Done</i>")
