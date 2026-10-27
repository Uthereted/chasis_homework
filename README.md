# Chasis compartido para FastAPI — 0.5.0

Librería de infraestructura reutilizable (Python >= 3.10). No contiene modelos
ni decisiones de negocio de pedidos, pagos, fabricación o entregas.

## Instalación

`pip install ".[auth,events,database]"` desde este repositorio.
El proyecto consumidor incluye una wheel 0.5.0 probada para construcciones Docker
reproducibles, sin depender de cambios posteriores en la rama main.

## Utilidades

- `my_chassis.auth.JWTVerifier`: verificación RS256, emisor/audiencia configurables,
  claims exp/iat/sub, caché de clave y recarga tras fallo de firma. Depende de una
  función asíncrona que proporciona la clave. Devuelve 401 o 503 según el caso.
- `my_chassis.keys`: validación RSA, carga desde el almacenamiento local y recepción
  de claves en la misma transacción que el inbox.
- `my_chassis.events.EventBus`: modelos de infraestructura Outbox/Inbox/SigningKey
  creados sobre la Base del servicio, publicación confirmada, deduplicación y
  consumo con reintentos. La sesión y las reglas de negocio pertenecen al servicio.
  La implementación de outbox/inbox utiliza actualmente SQLite.
- `my_chassis.messaging.TopicTransport`: conexión robusta, exchange topic y
  suscripciones locales. No conoce colas ni topología de otros servicios.
- `my_chassis.database.create_database` y `create_db_dependency`: motor/fábrica/Base
  por servicio y cierre de sesiones por petición.
- Logs, health y publicadores JSON anteriores se conservan por compatibilidad.

```python
from my_chassis.events import EventBus
from my_chassis.auth import JWTVerifier
from my_chassis.keys import database_public_key_loader

bus = EventBus(Base, SessionLocal, service_name="example-service",
               broker_url=broker_url, exchange_name="events")
verifier = JWTVerifier(
    key_loader=database_public_key_loader(SessionLocal, bus.SigningKey),
    issuer="expected-issuer", audience="expected-audience",
)
# FastAPI: token_payload = Depends(verifier.verify_jwt)
# Dentro de la transacción de negocio:
# await bus.record_event(db, "entity.created", data, "entity.created:123")
# await db.commit()
```

`record_event` y la recepción de claves no hacen commits propios. El consumidor
hace commit de estado, inbox y hechos derivados juntos. El publicador marca cada
hecho solo tras confirmación; una reentrega se deduplica por event_id. El envelope
incluye event_id, event_type, data y producer para auditoría independiente.

## Pruebas

`python -m unittest discover -s tests -v`

La CI ejecuta las pruebas de infraestructura y autenticación en Python 3.10 y 3.12.
