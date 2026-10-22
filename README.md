# Chasis compartido para FastAPI

Librería de infraestructura reutilizable. Versión **0.4.0**, Python 3.10 o superior.

- [Repositorio del chasis](https://github.com/Uthereted/chasis_homework).
- [Proyecto consumidor](https://github.com/Uthereted/EjercicioMonolitico).

## Utilidades y servicios que las usan

| Utilidad | Servicios del proyecto |
| --- | --- |
| `configure_logging` | order y payment |
| `create_health_router` | order y payment |
| `create_db_dependency` | client, delivery, order y payment |
| `publish_json_event` | order, payment y delivery |
| `create_json_message` | Publicador de eventos pendientes de order |

La verificación JWT se mantiene en el proyecto consumidor. El chasis no conoce
los modelos, esquemas, nombres de colas ni reglas de negocio de los servicios.

## Instalación

```bash
pip install "microservice_chassis @ git+https://github.com/Uthereted/chasis_homework.git@main"
```

Los servicios que publican eventos instalan el extra opcional `messaging`:

```bash
pip install "microservice_chassis[messaging] @ git+https://github.com/Uthereted/chasis_homework.git@main"
```

Git debe estar instalado, también dentro de las imágenes Docker que lo consuman.
`database` no añade SQLAlchemy como dependencia: recibe la fábrica del servicio.

## Logs y health

```python
from fastapi import FastAPI
from my_chassis import configure_logging, create_health_router

configure_logging("order-service")
app = FastAPI()
app.include_router(create_health_router("order-service"))
```

`GET /health` devuelve `{"status": "ok", "service": "order-service"}`.
Comprueba que el servicio responde; no comprueba la base de datos ni RabbitMQ.

## Sesiones por petición

```python
from fastapi import Depends
from my_chassis.database import create_db_dependency
from .sql.database import SessionLocal

get_db = create_db_dependency(SessionLocal)

@app.get("/example")
async def example(db=Depends(get_db)):
    ...  # Usar la sesión del servicio.
```

La dependencia abre una sesión mediante su contexto asíncrono y la cierra al
finalizar, también si la petición falla. Cada servicio conserva su motor,
configuración, modelos y decisiones de `commit`/`rollback`.

## Publicación de eventos RabbitMQ

```python
from my_chassis.messaging import publish_json_event

await publish_json_event(
    rabbitmq_url="amqp://guest:guest@localhost/",
    exchange_name="events",
    routing_key="example.created",
    queue_name="example.events",
    payload={"id": 42},
    message_id="example.created:42",
)
```

La función abre una conexión robusta, declara un exchange `topic` duradero y
una cola duradera, la enlaza antes de enviar y publica un mensaje JSON persistente
con confirmación y `mandatory=True`. Usa un timeout de cinco segundos para conectar
y publicar. Cierra la conexión al terminar y propaga los errores al servicio.

`bindings=("example.approved", "example.rejected")` permite preparar varios enlaces
para la misma cola; por defecto se enlaza la clave del mensaje publicado.

Los reintentos y el estado de publicación permanecen en el servicio: marcar un
evento como publicado solo después de que la llamada termine correctamente.
Las confirmaciones no eliminan posibles duplicados; los consumidores deben seguir
siendo idempotentes.

Si el servicio ya mantiene una conexión abierta, puede construir solo el mensaje:

```python
from my_chassis.messaging import create_json_message

message = create_json_message({"id": 42}, "example.created", "example.created:42")
await exchange.publish(message, routing_key="example.created", mandatory=True, timeout=5)
```

## Pruebas

```bash
pip install -e ".[messaging]" "httpx~=0.28"
python -m unittest discover -s tests -v
```

Las pruebas comprueban el cierre de sesiones en peticiones correctas y fallidas,
mensajes persistentes, confirmaciones, enlaces y propagación de errores de RabbitMQ.
No requieren un broker ni una base de datos en ejecución.
