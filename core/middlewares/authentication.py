import jwt
from jwt import PyJWKClient
from functools import lru_cache
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from core.config import config


@lru_cache(maxsize=1)
def get_jwks_client():
    """Get cached JWKS client for token verification"""
    # Ensure URL has trailing slash
    base_url = config.SUPABASE_PROJECT_URL.rstrip("/") + "/"
    jwks_url = f"{base_url}auth/v1/.well-known/jwks.json"
    print(f"[JWT] JWKS URL: {jwks_url}")
    return PyJWKClient(jwks_url)


class AuthenticationMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        authorization = request.headers.get("Authorization")

        if authorization is None:
            response = await call_next(request)
            return response

        try:
            scheme, token = authorization.split(" ")
            if scheme.lower() != "bearer" or not token:
                response = await call_next(request)
                return response

        except ValueError:
            response = await call_next(request)
            return response

        try:
            # Get the signing key from JWKS
            jwks_client = get_jwks_client()
            print(f"[JWT] client: {jwks_client}")
            print(f"[JWT] Received token: {token}")

            # Decode token header to check kid
            unverified_header = jwt.get_unverified_header(token)
            print(f"[JWT] Token header: {unverified_header}")

            signing_key = jwks_client.get_signing_key_from_jwt(token)

            # Verify token with the signing key
            payload = jwt.decode(
                jwt=token,
                key=signing_key.key,
                algorithms=[config.JWT_ALGORITHM],
                audience=config.JWT_AUDIENCE,
            )

        except jwt.ExpiredSignatureError:
            response = await call_next(request)
            return response

        except (jwt.InvalidTokenError, jwt.PyJWKClientError) as e:
            print(f"Invalid token error: {repr(e)}")
            response = await call_next(request)
            return response

        except Exception as e:
            print(f"Token verification error: {repr(e)}")
            response = await call_next(request)
            return response

        request.state.sub = payload.get("sub")
        request.state.token = token
        request.state.email = payload.get("email")

        response = await call_next(request)
        return response
