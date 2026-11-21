import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import UTC
from typing import TypedDict

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select

if __package__ == "backend.services":
    from ..database import Database
    from ..models import ChaosRun, RunEvent
else:
    from database import Database
    from models import ChaosRun, RunEvent


class EventEnvelope(TypedDict):
    run_id: int
    seq: int
    event: str
    ts: str
    payload: dict


def envelope(record: RunEvent) -> EventEnvelope:
    return {
        "run_id": record.run_id,
        "seq": record.seq,
        "event": record.event,
        "ts": record.ts.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "payload": record.payload,
    }


class LogStreamBroker:
    """Wake subscribers via Redis or a local queue and deliver ordered events from PostgreSQL."""

    def __init__(self, database: Database, redis_url: str | None = None) -> None:
        self.database = database
        self.redis = Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=2) if redis_url else None
        self.subscribers: dict[int, set[asyncio.Queue[None]]] = defaultdict(set)

    async def close(self) -> None:
        if self.redis is not None:
            await self.redis.aclose()

    async def publish(self, run_id: int, event: str, payload: dict) -> EventEnvelope:
        async with self.database.sessions.begin() as session:
            # Lock the run so separate workers cannot allocate the same sequence number.
            run = await session.scalar(select(ChaosRun.id).where(ChaosRun.id == run_id).with_for_update())
            if run is None:
                raise LookupError(f"Run {run_id} does not exist")
            last_seq = await session.scalar(select(func.max(RunEvent.seq)).where(RunEvent.run_id == run_id))
            record = RunEvent(run_id=run_id, seq=(last_seq or 0) + 1, event=event, payload=payload)
            session.add(record)
            await session.flush()
            message = envelope(record)

        for subscriber in self.subscribers.get(run_id, ()):
            if not subscriber.full():
                subscriber.put_nowait(None)
        if self.redis is not None:
            try:
                await self.redis.publish(f"codescape:run:{run_id}", message["seq"])
            except RedisError:
                # Replay remains available when the live transport is down.
                pass
        return message

    async def subscribe(self, run_id: int, after_seq: int = 0) -> AsyncIterator[EventEnvelope]:
        """Replay events after the cursor, then continue yielding newly committed events."""
        # Register wakeups before the first read to cover events committed during replay.
        wakeup: asyncio.Queue[None] = asyncio.Queue(maxsize=1)
        self.subscribers[run_id].add(wakeup)
        pubsub = self.redis.pubsub() if self.redis is not None else None
        try:
            if pubsub is not None:
                try:
                    await pubsub.subscribe(f"codescape:run:{run_id}")
                except RedisError:
                    await pubsub.aclose()
                    pubsub = None

            cursor = after_seq
            while True:
                async with self.database.sessions() as session:
                    rows = await session.scalars(
                        select(RunEvent)
                        .where(RunEvent.run_id == run_id, RunEvent.seq > cursor)
                        .order_by(RunEvent.seq)
                        .limit(100)
                    )
                    messages = [envelope(row) for row in rows]

                if messages:
                    for message in messages:
                        cursor = message["seq"]
                        yield message
                    continue

                if pubsub is not None:
                    try:
                        await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
                    except RedisError:
                        await pubsub.aclose()
                        pubsub = None
                else:
                    try:
                        await asyncio.wait_for(wakeup.get(), timeout=1)
                    except TimeoutError:
                        # Periodically reconcile committed events even if their notification was lost.
                        pass
        finally:
            subscribers = self.subscribers[run_id]
            subscribers.remove(wakeup)
            if not subscribers:
                del self.subscribers[run_id]
            if pubsub is not None:
                await pubsub.aclose()
