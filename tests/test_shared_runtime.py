import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import HTTPException
from sqlalchemy import select, func

from my_chassis.auth import JWTVerifier
from my_chassis.database import create_database
from my_chassis.events import EventBus
from my_chassis.keys import database_public_key_loader
from fastapi.security import HTTPAuthorizationCredentials


def public(key):
    return key.public_key().public_bytes(serialization.Encoding.PEM,
                                       serialization.PublicFormat.SubjectPublicKeyInfo).decode()


class SharedAuthTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.loader = AsyncMock(return_value=public(self.key))
        self.verifier = JWTVerifier(key_loader=self.loader, issuer='custom-issuer', audience='custom-audience')

    def credentials(self, key=None, audience='custom-audience'):
        now = datetime.now(timezone.utc)
        token = jwt.encode({'sub': '42', 'iat': now, 'exp': now + timedelta(minutes=5),
                            'iss': 'custom-issuer', 'aud': audience}, key or self.key, algorithm='RS256')
        return HTTPAuthorizationCredentials(scheme='Bearer', credentials=token)

    async def test_custom_issuer_audience_and_cached_key(self):
        self.assertEqual((await self.verifier.verify_jwt(self.credentials()))['sub'], '42')
        await self.verifier.verify_jwt(self.credentials())
        self.loader.assert_awaited_once()

    async def test_rotation_loads_new_public_key(self):
        await self.verifier.verify_jwt(self.credentials())
        new_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.loader.return_value = public(new_key)
        await self.verifier.verify_jwt(self.credentials(key=new_key))
        self.assertEqual(self.loader.await_count, 2)

    async def test_missing_credentials_bad_audience_and_unavailable_key(self):
        for credentials in (None, self.credentials(audience='wrong')):
            with self.assertRaises(HTTPException) as error:
                await self.verifier.verify_jwt(credentials)
            self.assertEqual(error.exception.status_code, 401)
        self.verifier._public_key = None
        self.loader.return_value = None
        with self.assertRaises(HTTPException) as error:
            await self.verifier.verify_jwt(self.credentials())
        self.assertEqual(error.exception.status_code, 503)


class SharedEventTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine, self.sessions, self.base = create_database('sqlite+aiosqlite:///:memory:')
        self.bus = EventBus(self.base, self.sessions, service_name='custom-service',
                            broker_url='amqp://unused', exchange_name='custom-exchange')
        async with self.engine.begin() as connection:
            await connection.run_sync(self.base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_rebinding_same_base_reuses_infrastructure_models(self):
        other = EventBus(self.base, self.sessions, service_name='other',
                         broker_url='amqp://unused', exchange_name='custom-exchange')
        self.assertIs(other.Outbox, self.bus.Outbox)

    async def test_inbox_and_derived_outbox_roll_back_together(self):
        async def handler(db, kind, data):
            await self.bus.record_event(db, 'derived.fact', {}, 'derived:1')
            raise RuntimeError('abort transaction')
        with self.assertRaises(RuntimeError):
            await self.bus.dispatch('original:1', 'original.fact', {}, handler)
        async with self.sessions() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(self.bus.Inbox)), 0)
            self.assertEqual(await db.scalar(select(func.count()).select_from(self.bus.Outbox)), 0)

    async def test_public_key_receiving_and_loading_are_shared(self):
        key = public(rsa.generate_private_key(public_exponent=65537, key_size=2048))
        await self.bus.dispatch('key:1', 'auth.signing-key.published', {'public_key': key}, AsyncMock())
        loader = database_public_key_loader(self.sessions, self.bus.SigningKey)
        self.assertEqual(await loader(), key)

    async def test_shared_publisher_has_no_peer_queues_and_includes_producer(self):
        channel = AsyncMock()
        await self.bus.provision(channel)
        channel.declare_exchange.assert_awaited_once()
        channel.declare_queue.assert_not_awaited()
        async with self.sessions() as db:
            await self.bus.record_event(db, 'sample.fact', {}, 'fact:1')
            await db.commit()
        import json
        exchange = AsyncMock()
        await self.bus.flush_outbox(exchange)
        envelope = json.loads(exchange.publish.call_args.args[0].body)
        self.assertEqual(envelope['producer'], 'custom-service')


if __name__ == '__main__':
    unittest.main()
