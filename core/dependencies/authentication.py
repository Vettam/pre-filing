from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from core.responseTypes import Unauthorized


class AuthenticationRequired:
    def __init__(
        self,
        request: Request,
        token: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))
    ):
        if not token or not getattr(request.state, "sub", None) or not getattr(request.state, "token", None):
            raise Unauthorized()
