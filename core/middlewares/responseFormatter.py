from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from core.logging import logger


class ResponseFormatterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response

        except Exception as e:
            import traceback
            
            logger.error("Unhandled exception occurred", exc_info=e)
            formatted_response = {
                "status": "failed",
                "message": "Internal Server Error",
                "error_code": "internal-server-error",
                "data": None,
            }
            return JSONResponse(content=formatted_response, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
