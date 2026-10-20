import json
from contextlib import asynccontextmanager

import aio_pika
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from my_chassis.messaging import conectar_rabbitmq, preparar_cola


RABBITMQ_URL = "amqp://manufacturing:manufacturing@localhost:5673/"


@asynccontextmanager
async def lifespan(app: FastAPI):
    connection = await conectar_rabbitmq(RABBITMQ_URL)

    async with connection:
        channel = await connection.channel(
            publisher_confirms=True,
            on_return_raises=True,
        )

        exchange, queue = await preparar_cola(
            channel,
            "manufacturing.events",
            "payment.events",
            "order.created",
        )

        app.state.exchange = exchange
        print("RabbitMQ conectado utilizando el chassis", flush=True)

        yield


app = FastAPI(
    title="Microservicio de pedidos con chassis",
    lifespan=lifespan,
)


class Pedido(BaseModel):
    order_id: int = Field(gt=0)
    client_id: int = Field(gt=0)
    amount: int = Field(gt=0)


@app.post("/pedidos", status_code=202)
async def crear_pedido(pedido: Pedido, request: Request):
    mensaje = aio_pika.Message(
        body=json.dumps(pedido.model_dump()).encode(),
        content_type="application/json",
        message_id=f"order.created:{pedido.order_id}",
        type="order.created",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )

    await request.app.state.exchange.publish(
        mensaje,
        routing_key="order.created",
        mandatory=True,
        timeout=5,
    )

    return {"mensaje": "Pedido enviado a RabbitMQ"}