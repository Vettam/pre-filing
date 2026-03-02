from fastapi import HTTPException, status
from fastapi.responses import JSONResponse


class CustomException(HTTPException):
    def __init__(self, error_code: str, status_code: int, message: str, data: dict | None = None):
        super().__init__(status_code=status_code, detail=message)
        self.error_code = error_code
        self.data = data

class Unauthorized(CustomException):
    def __init__(self):
        super().__init__(
            error_code="unauthorized",
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Unauthorized",
        )

class Forbidden(CustomException):
    def __init__(self, message: str = "Access Denied"):
        super().__init__(
            error_code="access-denied",
            status_code=status.HTTP_403_FORBIDDEN,
            message=message,
        )

class NotFound(CustomException):
    def __init__(self, message: str = "Not Found"):
        super().__init__(
            error_code="not-found",
            status_code=status.HTTP_404_NOT_FOUND,
            message=message,
        )


class BadRequest(CustomException):
    def __init__(self, message: str, error_code: str):
        super().__init__(
            error_code=error_code,
            status_code=status.HTTP_400_BAD_REQUEST,
            message=message,
        )

class Duplicate(CustomException):
    def __init__(self, message: str = "Resource already exists"):
        super().__init__(
            error_code="already-exists",
            status_code=status.HTTP_409_CONFLICT,
            message=message,
        )

class Success:
    def __new__(cls, message: str | None = None, data: dict | None = None):
        response = {
            "status": "success",
            "message": message,
            "data": data,
        }
        return JSONResponse(content=response, status_code=status.HTTP_200_OK)
