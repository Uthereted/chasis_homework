from setuptools import setup

setup(
    name="microservice_chassis",
    version="0.4.0",
    packages=["my_chassis"],
    python_requires=">=3.10",
    extras_require={
        "messaging": ["aio-pika~=9.4"],
    },
    install_requires=["fastapi~=0.114"],
)
