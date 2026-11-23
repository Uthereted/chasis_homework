"""Confirmed, durable JSON publication for RabbitMQ topic exchanges."""
import json
import aio_pika


def create_json_message(payload, routing_key, message_id):
    return aio_pika.Message(
        body=json.dumps(payload).encode(), content_type="application/json",
        message_id=message_id, type=routing_key,
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )


async def publish_json_event(rabbitmq_url, exchange_name, routing_key,
                             queue_name, payload, message_id, *, bindings=None):
    """Bind the destination before publishing; propagate failures to callers.

    Publishers can safely keep their outbox event pending until this returns.
    No retry or database commit is performed by the chassis.
    """
    connection = await aio_pika.connect_robust(rabbitmq_url, timeout=5)
    async with connection:
        channel = await connection.channel(publisher_confirms=True, on_return_raises=True)
        exchange = await channel.declare_exchange(
            exchange_name, aio_pika.ExchangeType.TOPIC, durable=True,
        )
        queue = await channel.declare_queue(queue_name, durable=True)
        for binding in (bindings if bindings is not None else (routing_key,)):
            await queue.bind(exchange, routing_key=binding)
        await exchange.publish(
            create_json_message(payload, routing_key, message_id),
            routing_key=routing_key, mandatory=True, timeout=5,
        )


class ExchangeRouter:
    """Route facts, saga commands and replies through the existing outbox.

    Reply destinations must be explicitly provisioned by the application.
    Old outbox entries without response_exchange keep their original route.
    """

    def __init__(self, domain, saga, *, response_exchanges=None):
        self.domain = domain
        self.saga = saga
        self.response_exchanges = response_exchanges

    async def publish(self, message, *, routing_key, **kwargs):
        exchange = self.domain
        if routing_key.startswith("saga."):
            exchange = self.saga
            if self.response_exchanges is not None:
                payload = json.loads(message.body)["data"]
                if "response_exchange" in payload:
                    requested = payload["response_exchange"]
                    if not isinstance(requested, str) or requested not in self.response_exchanges:
                        raise ValueError("Unsupported saga response exchange")
                    exchange = self.response_exchanges[requested]
        return await exchange.publish(message, routing_key=routing_key, **kwargs)


class TopicTransport:
    """Connection, exchange and local subscription setup without peer topology."""
    def __init__(self, broker_url, exchange_name):
        self.broker_url = broker_url
        self.exchange_name = exchange_name

    async def connect(self):
        return await aio_pika.connect_robust(self.broker_url, timeout=5)

    async def provision(self, channel):
        return await channel.declare_exchange(self.exchange_name, aio_pika.ExchangeType.TOPIC, durable=True)

    async def subscribe(self, channel, queue_name, topics):
        exchange = await self.provision(channel)
        queue = await channel.declare_queue(queue_name, durable=True)
        for topic in topics:
            await queue.bind(exchange, routing_key=topic)
        return queue
