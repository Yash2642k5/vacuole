"""Firestore-backed stores. The SDK is blocking, so every call runs off the event loop."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

import firebase_admin
from firebase_admin import credentials, firestore

from vacuole.domain.models import ChatTurn, UserLocation

T = TypeVar("T")

_USERS = "users"
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def create_firestore_client(service_account: dict[str, Any]):
    """Initialise the Admin SDK once and return a Firestore client. Raises on bad credentials."""
    try:
        firebase_admin.get_app()
    except ValueError:  # not initialised yet
        firebase_admin.initialize_app(credentials.Certificate(service_account))
    return firestore.client()


class _UserDocuments:
    """Shared plumbing: one document per user under `users/`."""

    def __init__(self, db: Any):
        self._db = db

    def _doc(self, user_id: str | int):
        return self._db.collection(_USERS).document(str(user_id))

    @staticmethod
    async def _run(func: Callable[[], T]) -> T:
        return await asyncio.to_thread(func)


class FirestoreChatHistory(_UserDocuments):
    async def append(self, user_id: str | int, role: str, content: str) -> None:
        def write() -> None:
            self._doc(user_id).set(
                {
                    "chats": firestore.ArrayUnion(
                        [{"role": role, "content": content, "timestamp": datetime.now(timezone.utc)}]
                    )
                },
                merge=True,
            )

        try:
            await self._run(write)
        except Exception as exc:
            print(f"[db] could not append message for {user_id}: {exc}")

    async def recent(self, user_id: str | int, limit: int) -> list[ChatTurn]:
        def read() -> list[dict[str, Any]]:
            snapshot = self._doc(user_id).get()
            if not snapshot.exists:
                return []
            chats = (snapshot.to_dict() or {}).get("chats", [])
            ordered = sorted(chats, key=lambda msg: msg.get("timestamp") or _EPOCH)
            return ordered[-limit:]

        try:
            rows = await self._run(read)
        except Exception as exc:
            print(f"[db] could not read history for {user_id}: {exc}")
            return []

        return [
            ChatTurn(role=row["role"], content=row["content"])
            for row in rows
            if row.get("content") and row.get("role") in ("user", "assistant")
        ]


class FirestoreLocationStore(_UserDocuments):
    async def save(self, user_id: str | int, location: UserLocation) -> None:
        def write() -> None:
            self._doc(user_id).set({"location": location.to_dict()}, merge=True)

        try:
            await self._run(write)
        except Exception as exc:  # persistence is best effort
            print(f"[location] could not save location for {user_id}: {exc}")

    async def load(self, user_id: str | int) -> UserLocation | None:
        def read() -> dict[str, Any] | None:
            snapshot = self._doc(user_id).get()
            if not snapshot.exists:
                return None
            return (snapshot.to_dict() or {}).get("location")

        try:
            stored = await self._run(read)
        except Exception as exc:  # persistence is best effort
            print(f"[location] could not load location for {user_id}: {exc}")
            return None
        return UserLocation.from_dict(stored)
