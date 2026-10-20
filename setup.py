from setuptools import setup, find_packages

setup(
    name="microservice_chassis",
    version="0.2.1",
    packages=find_packages(),
    install_requires=["aio-pika~=9.4"],
    author="Alain Perez",
    author_email="aperez@mondragon.edu",
    description="A reusable library for microservices",
    url="https://gitlab.com/macc_ci_cd/aas/chassis",
)
