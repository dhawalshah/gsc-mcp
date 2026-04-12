"""Google Search Console MCP Server — FastAPI wrapper with OAuth and SSE transport."""
import logging
import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import Response
from starlette.middleware.sessions import SessionMiddleware

from server import mcp
from oauth.auth_routes import router as auth_router, ALLOWED_DOMAIN
from oauth.google_auth import current_user_email

logger = logging.getLogger(__name__)

BASE_URL = os.environ.get("BASE_URL", "")

_SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "")
_INSECURE_DEFAULT = "dev-secret-change-me"
if not _SESSION_SECRET_KEY or _SESSION_SECRET_KEY == _INSECURE_DEFAULT:
    if os.environ.get("GCP_PROJECT_ID"):
        # Running in Cloud Run / production — refuse to start with no/default secret
        raise RuntimeError(
            "SESSION_SECRET_KEY must be set to a strong random value in production. "
            "Generate one with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
        )
    else:
        # Local dev — warn only
        logger.warning("SESSION_SECRET_KEY not set — using insecure default. Set it for any shared deployment.")
        _SESSION_SECRET_KEY = _INSECURE_DEFAULT

mcp_asgi_app = mcp.http_app(path="/")
app = FastAPI(lifespan=mcp_asgi_app.lifespan, redirect_slashes=False)

app.add_middleware(SessionMiddleware, secret_key=_SESSION_SECRET_KEY)
app.include_router(auth_router, prefix="/auth")


@app.middleware("http")
async def require_login_for_mcp(request: Request, call_next):
    if request.url.path.startswith("/mcp"):
        email = request.query_params.get("user")
        # Validate ?user= email against the allowed domain before trusting it
        if email and ALLOWED_DOMAIN:
            domain_part = email.split("@")[-1].lower() if "@" in email else ""
            if domain_part != ALLOWED_DOMAIN.lower():
                return Response("Unauthorized: email domain not allowed.", status_code=403)
        if not email:
            email = request.session.get("user_email")
        if not email:
            return Response("Unauthorized. Visit /auth/login first.", status_code=401)
        current_user_email.set(email)
    return await call_next(request)


app.mount("/mcp", mcp_asgi_app)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
