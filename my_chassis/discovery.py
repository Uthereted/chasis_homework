"""Consul registration, deregistration and healthy service discovery."""
import asyncio
from contextlib import asynccontextmanager
import json
import logging
import os
import socket
from urllib.request import Request, urlopen
from urllib.parse import quote


def _get(url):
    with urlopen(url, timeout=2) as response:
        return json.load(response)


async def get_service_url(name):
    consul_url = os.environ["CONSUL_URL"].rstrip("/")
    instances = await asyncio.to_thread(
        _get, f"{consul_url}/v1/health/service/{quote(name, safe='')}?passing=true"
    )
    if not instances:
        raise RuntimeError(f"No healthy instances of {name} in Consul")
    instance = instances[0]
    service = instance["Service"]
    address = service["Address"] or instance["Node"]["Address"]
    scheme = service.get("Meta", {}).get("scheme", "https")
    return f"{scheme}://{address}:{service['Port']}"


def _put(url, data=None):
    body = json.dumps(data).encode() if data is not None else None
    request = Request(url, data=body, method="PUT",
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=5) as response:
        response.read()


@asynccontextmanager
async def registered_service(name, *, port=8000, health_path='/service/health'):
    consul_url = os.getenv("CONSUL_URL")
    if not consul_url:
        yield
        return

    consul_url = consul_url.rstrip("/")
    hostname = socket.gethostname()
    address = socket.gethostbyname(hostname)
    service_id = f"{name}-{hostname}"
    scheme = os.getenv("API_SCHEME", "https")
    await asyncio.to_thread(_put, f"{consul_url}/v1/agent/service/register", {
        "ID": service_id,
        "Name": name,
        "Address": address,
        "Port": port,
        "Meta": {"scheme": scheme},
        "Check": {
            "HTTP": f"{scheme}://{address}:{port}{health_path}",
            "TLSServerName": name,
            "Interval": "10s",
            "Timeout": "2s",
        },
    })
    try:
        yield
    finally:
        try:
            await asyncio.to_thread(
                _put, f"{consul_url}/v1/agent/service/deregister/{service_id}"
            )
        except OSError:
            logging.getLogger(__name__).warning(
                "Could not deregister %s from Consul", service_id
            )


async def query_service(name, path, *, access_token):
    """Make an authenticated read through Consul discovery, directly to the service."""
    import ssl
    import httpx
    from fastapi import HTTPException

    try:
        url = await get_service_url(name)
        if not url.startswith('https://'):
            raise ValueError('Service queries require HTTPS')
        context = ssl.create_default_context(cafile=os.getenv('TLS_CA_FILE'))
        async with httpx.AsyncClient(verify=context, trust_env=False, timeout=5) as client:
            response = await client.get(
                f'{url}{path}', headers={'Authorization': f'Bearer {access_token}'},
                extensions={'sni_hostname': name},
            )
        if response.status_code in (401, 403, 404):
            raise HTTPException(
                response.status_code,
                'Resource not found' if response.status_code == 404 else 'Query not authorized',
                headers={'WWW-Authenticate': 'Bearer'} if response.status_code == 401 else None,
            )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, OSError, RuntimeError, ValueError, KeyError) as exc:
        raise HTTPException(503, 'Service query unavailable') from exc
