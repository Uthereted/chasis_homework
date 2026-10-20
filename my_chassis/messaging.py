import aio_pika


async def conectar_rabbitmq(url):
    return await aio_pika.connect_robust(url, timeout=5)


async def preparar_cola(channel, nombre_exchange, nombre_cola, tema):
    exchange = await channel.declare_exchange(
        nombre_exchange,
        aio_pika.ExchangeType.TOPIC,
        durable=True,
    )

    queue = await channel.declare_queue(
        nombre_cola,
        durable=True,
    )

    await queue.bind(exchange, routing_key=tema)

    return exchange, queue