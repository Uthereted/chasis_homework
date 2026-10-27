"""RSA key validation and configurable local key providers."""
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key


def validate_public_key(pem):
    if not isinstance(pem, str) or not isinstance(load_pem_public_key(pem.encode()), RSAPublicKey):
        raise ValueError("Expected an RSA public key in PEM format")
    return pem


def database_public_key_loader(session_factory, signing_key_model):
    async def load():
        async with session_factory() as db:
            row = await db.get(signing_key_model, 1)
            return row.pem if row is not None else None
    return load


async def store_public_key(db, signing_key_model, pem):
    from sqlalchemy.dialects.sqlite import insert
    pem = validate_public_key(pem)
    await db.execute(insert(signing_key_model).values(id=1, pem=pem).on_conflict_do_update(
        index_elements=["id"], set_={"pem": pem}))
