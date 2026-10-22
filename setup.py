from setuptools import setup

setup(
    name="microservice_chassis",
    version="0.3.2",
    packages=["my_chassis"],
    python_requires=">=3.10",
    install_requires=["fastapi~=0.114"],
)
