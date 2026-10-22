import json
import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from my_chassis.database import create_db_dependency
from my_chassis.messaging import publish_json_event
from my_chassis import messaging


class DatabaseDependencyTests(unittest.TestCase):
    def test_fastapi_closes_session_on_success_and_route_failure(self):
        calls = []
        session = object()

        @asynccontextmanager
        async def factory():
            calls.append('open')
            try:
                yield session
            finally:
                calls.append('close')

        get_db = create_db_dependency(factory)
        app = FastAPI()

        @app.get('/{fail}')
        async def route(fail: bool, db=Depends(get_db)):
            assert db is session
            if fail:
                raise RuntimeError('route failed')
            return {'ok': True}

        with TestClient(app, raise_server_exceptions=False) as client:
            self.assertEqual(client.get('/false').status_code, 200)
            self.assertEqual(client.get('/true').status_code, 500)
        self.assertEqual(calls, ['open', 'close', 'open', 'close'])

class PublicationTests(unittest.IsolatedAsyncioTestCase):
    async def test_confirmations_bindings_and_persistent_message(self):
        with patch.object(messaging.aio_pika, 'connect_robust', new=AsyncMock()) as connect:
            channel = connect.return_value.channel.return_value
            exchange = channel.declare_exchange.return_value
            queue = channel.declare_queue.return_value
            await publish_json_event('amqp://test', 'events', 'approved', 'results',
                                     {'id': 2}, 'approved:2', bindings=('approved', 'rejected'))
            connect.assert_awaited_once_with('amqp://test', timeout=5)
            connect.return_value.channel.assert_awaited_once_with(
                publisher_confirms=True, on_return_raises=True)
            channel.declare_exchange.assert_awaited_once_with(
                'events', messaging.aio_pika.ExchangeType.TOPIC, durable=True)
            channel.declare_queue.assert_awaited_once_with('results', durable=True)
            self.assertEqual([c.kwargs['routing_key'] for c in queue.bind.await_args_list],
                             ['approved', 'rejected'])
            message = exchange.publish.call_args.args[0]
            self.assertEqual(json.loads(message.body), {'id': 2})
            self.assertEqual(message.message_id, 'approved:2')
            self.assertEqual(message.type, 'approved')
            self.assertEqual(message.content_type, 'application/json')
            self.assertEqual(message.delivery_mode, messaging.aio_pika.DeliveryMode.PERSISTENT)
            self.assertEqual(exchange.publish.call_args.kwargs,
                             {'routing_key': 'approved', 'mandatory': True, 'timeout': 5})
            connect.return_value.__aexit__.assert_awaited_once()

    async def test_binding_failure_prevents_publication(self):
        with patch.object(messaging.aio_pika, 'connect_robust', new=AsyncMock()) as connect:
            channel = connect.return_value.channel.return_value
            channel.declare_queue.return_value.bind.side_effect = ConnectionError('cannot bind')
            with self.assertRaises(ConnectionError):
                await publish_json_event('amqp://test', 'events', 'created', 'orders', {}, '1')
            channel.declare_exchange.return_value.publish.assert_not_awaited()
            connect.return_value.__aexit__.assert_awaited_once()

    async def test_publication_failure_propagates_and_closes_connection(self):
        with patch.object(messaging.aio_pika, 'connect_robust', new=AsyncMock()) as connect:
            channel = connect.return_value.channel.return_value
            channel.declare_exchange.return_value.publish.side_effect = ConnectionError('offline')
            with self.assertRaises(ConnectionError):
                await publish_json_event('amqp://test', 'events', 'created', 'orders', {}, '1')
            channel.declare_queue.return_value.bind.assert_awaited_once_with(
                channel.declare_exchange.return_value, routing_key='created')
            connect.return_value.__aexit__.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
