import secrets
from functools import wraps
from fastapi import Request, HTTPException
from starlette.responses import RedirectResponse

SESSIONS = {}


def create_session(user):
    sid = secrets.token_hex(32)
    SESSIONS[sid] = {"id": user["id"], "username": user["username"], "role": user["role"]}
    return sid


def get_session(request: Request):
    sid = request.cookies.get("session_id")
    if sid and sid in SESSIONS:
        return SESSIONS[sid]
    return None


def _get_request_from_call(args, kwargs):
    request = kwargs.get("request")
    if request is not None:
        return request
    for arg in args:
        if isinstance(arg, Request):
            return arg
    return None


def _auth_fail(request: Request):
    if request and request.url.path.startswith("/api/"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return RedirectResponse("/login", status_code=303)


def require_login(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request = _get_request_from_call(args, kwargs)
        if not request or not get_session(request):
            return _auth_fail(request)
        return await func(*args, **kwargs)
    return wrapper


def require_role(*roles):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = _get_request_from_call(args, kwargs)
            session = get_session(request) if request else None
            if not session:
                return _auth_fail(request)
            if session["role"] not in roles:
                raise HTTPException(status_code=403, detail="Access denied")
            return await func(*args, **kwargs)
        return wrapper
    return decorator
