from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from core.config import config
from .authentication import AuthenticationMiddleware
from .responseFormatter import ResponseFormatterMiddleware


def include_middleware() -> list[Middleware]:
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=config.CORS_ALLOW_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        Middleware(AuthenticationMiddleware),
        Middleware(ResponseFormatterMiddleware),
    ]
    return middleware
