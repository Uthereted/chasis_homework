# Microservice Chassis con RabbitMQ

## Qué se ha hecho

Se ha creado un paquete de Python llamado **my_chassis** con funciones de RabbitMQ, extraídas y adaptadas del proyecto grupal:

https://github.com/Uthereted/EjercicioMonolitico

También se ha creado un microservicio sencillo de pedidos que utiliza el chassis para conectarse a RabbitMQ y preparar la cola. Recibe un pedido por una API y envía sus datos como mensaje.

Repositorio de esta entrega:
https://github.com/Uthereted/chasis_homework

## Funciones del chassis

**conectar_rabbitmq(url)** abre la conexión con RabbitMQ.

**preparar_cola(...)** crea el exchange, la cola y el enlace con el tema indicado.

Las dos funciones están en **my_chassis/messaging.py** y las utiliza el microservicio de pedidos desde **pedido/main.py**.

## Cómo instalarlo

Necesitas Python 3.10 o superior y Docker Desktop arrancado.

Abre PowerShell en la carpeta donde está **setup.py** y ejecuta:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pip install fastapi "uvicorn[standard]"
```

## Cómo ejecutarlo

La primera vez, crea el contenedor de RabbitMQ:

```powershell
docker run -d --name chassis-rabbitmq -p 127.0.0.1:5673:5672 -p 127.0.0.1:15673:15672 -e RABBITMQ_DEFAULT_USER=manufacturing -e RABBITMQ_DEFAULT_PASS=manufacturing rabbitmq:4-management
```

Si ya está creado, solo tienes que arrancarlo:

```powershell
docker start chassis-rabbitmq
```

Comprueba que funciona:

```powershell
docker exec chassis-rabbitmq rabbitmq-diagnostics -q ping
```

Cuando aparezca **Ping succeeded**, ejecuta el microservicio:

```powershell
python -m uvicorn main:app --app-dir pedido --port 8001
```

## Cómo comprobarlo

Abre http://localhost:8001/docs y envía un pedido desde **POST /pedidos**, por ejemplo:

```json
{
  "order_id": 1,
  "client_id": 1,
  "amount": 100
}
```

Debe responder con el código **202**.

Puedes ver el mensaje en http://localhost:15673. El usuario y la contraseña son **manufacturing**. Entra en la cola **payment.events** y pulsa **Get messages**.

## Cómo cerrarlo

Pulsa **Ctrl + C** en la terminal del microservicio y ejecuta:

```powershell
docker stop chassis-rabbitmq
deactivate
```

Para volver a arrancarlo, activa el entorno con `.\.venv\Scripts\Activate.ps1` y repite los pasos de ejecución.

## Aclaración

El chassis está instalado de forma local. No se ha publicado en un registro privado. El microservicio es una versión sencilla para demostrar su uso, sin base de datos ni pagos.