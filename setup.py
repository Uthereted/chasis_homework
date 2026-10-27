from setuptools import setup

setup(
    name="microservice_chassis",
    version="0.5.0",
    packages=["my_chassis"],
    python_requires=">=3.10",
    extras_require={
        "messaging": ["aio-pika~=9.4"],
        "auth": ["PyJWT[crypto]~=2.9"],
        "database": ["SQLAlchemy[asyncio]~=2.0", "aiosqlite~=0.20"],
        "events": ["aio-pika~=9.4", "SQLAlchemy[asyncio]~=2.0", "aiosqlite~=0.20", "PyJWT[crypto]~=2.9"],
    },
    install_requires=["fastapi~=0.114"],
)
