# Chasis: logs y health

Librería compartida para microservicios FastAPI.

- **Repositorio del chasis:** [chasis_homework](https://github.com/Uthereted/chasis_homework).
- **Repositorio del proyecto:** [EjercicioMonolitico](https://github.com/Uthereted/EjercicioMonolitico).

## Utilidades

- **Logs (`configure_logging`):** configura los mensajes de consola con fecha, nivel y nombre del servicio.
- **Health (`create_health_router`):** añade `GET /health` para comprobar que el servicio responde e identificarlo. No comprueba la base de datos ni RabbitMQ.

## Uso en los microservicios

| Microservicio | Logs del chasis | Health del chasis |
| --- | --- | --- |
| order | Sí | Sí |
| payment | Sí | Sí |
| client | No | No |
| machine | No | No |
| delibery | No | No |

## Instalación

Requiere Python 3.10 o superior. Los requisitos de pedidos y pagos instalan el paquete desde GitHub.

```python
from my_chassis import configure_logging, create_health_router
```

Para comprobarlo con el proyecto arrancado:

- [Health de pedidos](http://localhost:13001/health).
- [Health de pagos](http://localhost:13006/health).
