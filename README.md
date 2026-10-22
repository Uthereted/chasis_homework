# Chasis: logs y health

Librería compartida por pedidos y pagos de `EjercicioMonolitico`.
Requiere Python 3.10 o superior.

- `configure_logging(nombre)`: configura los logs con el nombre del servicio.
- `create_health_router(nombre)`: añade GET `/health`, que devuelve
  `{"status":"ok","service":"nombre"}`. No comprueba la base de datos ni RabbitMQ.

Instalar desde esta carpeta:

```bash
python -m pip install .
```

Uso:

```python
from fastapi import FastAPI
from my_chassis import configure_logging, create_health_router

configure_logging("order-service")
app = FastAPI()
app.include_router(create_health_router("order-service"))
```

Mantener este repositorio junto a `EjercicioMonolitico`. Docker Compose lo
instala al construir pedidos y pagos. Para aplicar cambios, desde ese proyecto:

```bash
docker compose up -d --build order-service paymentservice
```

Comprobar http://localhost:13001/health y http://localhost:13006/health.
