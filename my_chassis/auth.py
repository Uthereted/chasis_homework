"""Configurable RS256 access-token verification for FastAPI."""
import logging
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from .keys import validate_public_key

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


class JWTVerifier:
    def __init__(self, *, key_loader, issuer, audience):
        self.key_loader = key_loader
        self.issuer = issuer
        self.audience = audience
        self._public_key = None

    async def fetch_public_key(self):
        try:
            key = await self.key_loader()
            if key is None:
                return False
            self._public_key = validate_public_key(key)
            return True
        except Exception:
            logger.warning("Public key refresh unavailable")
            return False

    async def verify_jwt(self, credentials: HTTPAuthorizationCredentials = Depends(security)):
        if credentials is None:
            raise HTTPException(401, "Bearer token required", headers={"WWW-Authenticate": "Bearer"})
        if self._public_key is None and not await self.fetch_public_key():
            raise HTTPException(503, "Auth service is unavailable")
        for attempt in range(2):
            try:
                return jwt.decode(credentials.credentials, self._public_key, algorithms=["RS256"],
                                  issuer=self.issuer, audience=self.audience,
                                  options={"require": ["exp", "iat", "sub"]})
            except jwt.InvalidSignatureError:
                if attempt == 0 and await self.fetch_public_key():
                    continue
                break
            except jwt.InvalidTokenError:
                break
        raise HTTPException(401, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
