"""Google Search Console MCP Server — FastAPI wrapper with OAuth and SSE transport."""
import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import Response
from starlette.middleware.sessions import SessionMiddleware

from server import mcp
from oauth.auth_routes import router as auth_router
from oauth.google_auth import current_user_email

BASE_URL = os.environ.get("BASE_URL", "")
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "dev-secret-change-me")

mcp_asgi_app = mcp.http_app(path="/")
app = FastAPI(lifespan=mcp_asgi_app.lifespan, redirect_slashes=False)

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)
app.include_router(auth_router, prefix="/auth")


@app.middleware("http")
async def require_login_for_mcp(request: Request, call_next):
    if request.url.path.startswith("/mcp"):
        email = request.query_params.get("user")
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
