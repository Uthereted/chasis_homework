# Microservice Chassis con RabbitMQ

## Descripción

Este proyecto contiene un paquete de Python llamado `my_chassis` con funciones comunes de RabbitMQ y un microservicio de pedidos que las utiliza.

Se han extraído y adaptado las operaciones de conexión y configuración de RabbitMQ del proyecto grupal:

https://github.com/Uthereted/EjercicioMonolitico

El microservicio de ejemplo recibe un pedido mediante una API y envía sus datos a RabbitMQ. Es una versión simplificada, sin base de datos ni procesamiento de pagos.

Repositorio de esta entrega: AÑADIR_ENLACE_DEL_REPOSITORIO

## Funcionalidades del chassis

| Función | Qué hace | Microservicio que la utiliza |
|---|---|---|
| `conectar_rabbitmq(url)` | Abre una conexión con RabbitMQ. | Microservicio de pedidos |
| `preparar_cola(channel, nombre_exchange, nombre_cola, tema)` | Declara un exchange de tipo topic, crea una cola y la vincula con el tema indicado. | Microservicio de pedidos |

Estas funciones están en `my_chassis/messaging.py`.

El microservicio las importa desde el paquete, evitando tener que incluir su implementación en `pedido/main.py`.

## Archivos principales

| Archivo | Contenido |
|---|---|
| `setup.py` | Configuración y dependencias del paquete. |
| `my_chassis/__init__.py` | Identifica el paquete de Python. |
| `my_chassis/messaging.py` | Funciones comunes de RabbitMQ. |
| `pedido/main.py` | API de pedidos que utiliza el chassis. |

## Requisitos

- Python 3.10 o superior.
- Docker Desktop instalado y arrancado.
- PowerShell para ejecutar los comandos siguientes.

## Instalación

Abre PowerShell en la raíz del repositorio, donde se encuentra `setup.py`.

Crea y activa un entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instala el chassis y las dependencias del microservicio:

```powershell
python -m pip install -e .
python -m pip install fastapi "uvicorn[standard]"
```

El parámetro `-e` instala el chassis en modo editable.

Comprueba que sus funciones se pueden importar:

```powershell
python -c "from my_chassis.messaging import conectar_rabbitmq, preparar_cola; print('Chassis importado correctamente')"
```

## Arrancar RabbitMQ

La primera vez, crea el contenedor:

```powershell
docker run -d --name chassis-rabbitmq -p 127.0.0.1:5673:5672 -p 127.0.0.1:15673:15672 -e RABBITMQ_DEFAULT_USER=manufacturing -e RABBITMQ_DEFAULT_PASS=manufacturing rabbitmq:4-management
```

Si el contenedor ya existe, arráncalo con:

```powershell
docker start chassis-rabbitmq
```

Comprueba que está preparado:

```powershell
docker exec chassis-rabbitmq rabbitmq-diagnostics -q ping
```

Debe aparecer `Ping succeeded`. Si todavía está arrancando, repite la comprobación cuando termine.

La dirección de conexión utilizada por el microservicio es:

```text
amqp://manufacturing:manufacturing@localhost:5673/
```

Estas credenciales se utilizan para la demostración local.

## Arrancar el microservicio

Desde la raíz del repositorio, con el entorno virtual activado:

```powershell
python -m uvicorn main:app --app-dir pedido --port 8001
```

Durante el arranque, el microservicio llama al chassis para conectarse a RabbitMQ y preparar:

- Exchange: `manufacturing.events`.
- Cola: `payment.events`.
- Routing key: `order.created`.

Abre la documentación de la API:

http://localhost:8001/docs

## Enviar un pedido

En la documentación de la API:

1. Despliega `POST /pedidos`.
2. Pulsa `Try it out`.
3. Introduce este JSON:

```json
{
  "order_id": 1,
  "client_id": 1,
  "amount": 100
}
```

4. Pulsa `Execute`.

La respuesta esperada es un código HTTP `202` con:

```json
{
  "mensaje": "Pedido enviado a RabbitMQ"
}
```

## Comprobar el mensaje

Abre el panel de RabbitMQ:

http://localhost:15673

Usuario: `manufacturing`  
Contraseña: `manufacturing`

1. Entra en `Queues and Streams`.
2. Selecciona `payment.events`.
3. Abre `Get messages`.
4. Pulsa `Get Message(s)`.

Debe aparecer el JSON enviado desde la API.

Esta comprobación demuestra que el microservicio utiliza las funciones del chassis y publica el mensaje en RabbitMQ. No hay un consumidor de pagos en este ejemplo.

## Detener y volver a ejecutar

Para detener el microservicio, pulsa `Ctrl + C` en su terminal.

Para detener RabbitMQ y salir del entorno virtual:

```powershell
docker stop chassis-rabbitmq
deactivate
```

Para volver a ejecutar, abre PowerShell en la raíz del repositorio:

```powershell
.\.venv\Scripts\Activate.ps1
docker start chassis-rabbitmq
docker exec chassis-rabbitmq rabbitmq-diagnostics -q ping
```

Cuando RabbitMQ esté preparado:

```powershell
python -m uvicorn main:app --app-dir pedido --port 8001
```

## Alcance

El chassis se instala localmente mediante `pip install -e .`. Esta versión no incluye la publicación del paquete en un registro privado.