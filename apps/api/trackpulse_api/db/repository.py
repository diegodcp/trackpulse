from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .models import RawOpenF1Event


class RawOpenF1EventRepository:
    async def insert_raw_event(
        self,
        session: AsyncSession,
        *,
        topic: str,
        payload: Mapping[str, Any],
        source_id: str | None = None,
        source_key: str | None = None,
        event_time: datetime | None = None,
    ) -> RawOpenF1Event:
        existing = None
        if source_id is not None:
            existing = await self._find_by_topic_and_source_id(session, topic=topic, source_id=source_id)
            if existing is not None:
                return existing

        event = RawOpenF1Event(
            topic=topic,
            source_id=source_id,
            source_key=source_key,
            event_time=event_time,
            payload=dict(payload),
        )

        try:
            async with session.begin_nested():
                session.add(event)
                await session.flush()
        except IntegrityError:
            if source_id is None:
                raise
            existing = await self._find_by_topic_and_source_id(session, topic=topic, source_id=source_id)
            if existing is not None:
                return existing
            raise

        return event

    async def _find_by_topic_and_source_id(
        self,
        session: AsyncSession,
        *,
        topic: str,
        source_id: str,
    ) -> RawOpenF1Event | None:
        stmt = select(RawOpenF1Event).where(
            RawOpenF1Event.topic == topic,
            RawOpenF1Event.source_id == source_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
