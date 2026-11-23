"""Reusable transactional SQLite event bus. Business models and policies stay in services."""
import asyncio
import json
import logging
import aio_pika
from pydantic import ValidationError
from sqlalchemy import Boolean, Column, Integer, String, Text, select, update
from sqlalchemy.dialects.sqlite import insert
from .messaging import TopicTransport
from .keys import store_public_key

logger = logging.getLogger(__name__)


class RetryEvent(Exception):
    """A causal prerequisite is pending; retry without committing the inbox."""


def decode_event(body, routing_key):
    envelope = json.loads(body)
    if (not isinstance(envelope, dict) or not isinstance(envelope.get("event_id"), str)
            or not envelope["event_id"] or envelope.get("event_type") != routing_key
            or not isinstance(envelope.get("data"), dict)):
        raise ValueError("Invalid event envelope")
    return envelope


def create_event_models(base):
    existing = base.__dict__.get("_chassis_event_models")
    if existing is not None:
        return existing

    class Outbox(base):
        __tablename__ = "event_outbox"
        id = Column(Integer, primary_key=True)
        event_id = Column(String(200), unique=True, nullable=False)
        event_type = Column(String(100), nullable=False)
        payload = Column(Text, nullable=False)
        published = Column(Boolean, nullable=False, default=False)

    class Inbox(base):
        __tablename__ = "event_inbox"
        event_id = Column(String(200), primary_key=True)

    class SigningKey(base):
        __tablename__ = "event_signing_key"
        id = Column(Integer, primary_key=True)
        pem = Column(Text, nullable=False)

    base._chassis_event_models = (Outbox, Inbox, SigningKey)
    return base._chassis_event_models


class EventBus:
    def __init__(self, base, session_factory, *, service_name, broker_url, exchange_name,
                 key_event_type="auth.signing-key.published"):
        self.session_factory = session_factory
        self.service_name = service_name
        self.key_event_type = key_event_type
        self.transport = TopicTransport(broker_url, exchange_name)
        self._publisher_link = None
        self._consumer_links = {}
        self.Outbox, self.Inbox, self.SigningKey = create_event_models(base)

    @property
    def available(self):
        def connected(link):
            return link is not None and not link[0].is_closed and not link[1].is_closed
        return connected(self._publisher_link) and all(
            connected(link) for link in self._consumer_links.values()
        )

    async def provision(self, channel):
        return await self.transport.provision(channel)

    async def subscribe(self, channel, queue_name, topics):
        return await self.transport.subscribe(channel, queue_name, topics)

    async def record_event(self, db, event_type, payload, event_id):
        await db.execute(insert(self.Outbox).values(
            event_id=event_id, event_type=event_type, payload=json.dumps(payload), published=False,
        ).on_conflict_do_nothing(index_elements=["event_id"]))

    async def flush_outbox(self, exchange):
        async with self.session_factory() as db:
            pending = list((await db.execute(select(self.Outbox.id, self.Outbox.event_id, self.Outbox.event_type, self.Outbox.payload).where(
                self.Outbox.published.is_(False)).order_by(self.Outbox.id).limit(100))).all())
            for event in pending:
                await exchange.publish(aio_pika.Message(
                    body=json.dumps({"event_id": event.event_id, "event_type": event.event_type,
                                     "data": json.loads(event.payload), "producer": self.service_name}).encode(),
                    content_type="application/json", type=event.event_type, message_id=event.event_id,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ), routing_key=event.event_type, mandatory=True, timeout=5)
                await db.execute(update(self.Outbox).where(self.Outbox.id == event.id).values(published=True))
                await db.commit()

    async def publish_pending_events(self):
        while True:
            try:
                connection = await self.transport.connect()
                async with connection:
                    channel = await connection.channel(publisher_confirms=True, on_return_raises=True)
                    exchange = await self.provision(channel)
                    self._publisher_link = (connection, channel)
                    while True:
                        await self.flush_outbox(exchange)
                        await asyncio.sleep(0.25)
            except Exception:
                logger.exception("Event outbox publication pending; retrying")
                await asyncio.sleep(2)
            finally:
                self._publisher_link = None

    async def dispatch(self, event_id, event_type, data, handler):
        async with self.session_factory() as db:
            claimed = await db.execute(insert(self.Inbox).values(event_id=event_id).on_conflict_do_nothing())
            if claimed.rowcount == 0:
                await db.rollback()
                return
            if event_type == self.key_event_type:
                await store_public_key(db, self.SigningKey, data["public_key"])
            else:
                await handler(db, event_type, data)
            await db.commit()

    async def process_event(self, message, handler):
        try:
            envelope = decode_event(message.body, message.routing_key)
            await self.dispatch(envelope["event_id"], envelope["event_type"], envelope["data"], handler)
        except (ValidationError, ValueError, KeyError, TypeError):
            logger.exception("Invalid domain event; rejecting")
            await message.reject(requeue=False)
        except Exception:
            logger.exception("Domain event pending; retrying")
            await asyncio.sleep(1)
            await message.nack(requeue=True)
        else:
            await message.ack()

    async def consume_events(self, queue_name, handler, *, topics):
        self._consumer_links[queue_name] = None
        while True:
            try:
                connection = await self.transport.connect()
                async with connection:
                    channel = await connection.channel()
                    await channel.set_qos(prefetch_count=1)
                    queue = await self.subscribe(channel, queue_name, topics)
                    async with queue.iterator() as messages:
                        self._consumer_links[queue_name] = (connection, channel)
                        async for message in messages:
                            await self.process_event(message, handler)
            except Exception:
                logger.exception("Domain event consumer unavailable; retrying")
                await asyncio.sleep(2)
            finally:
                self._consumer_links[queue_name] = None
