"""
MemoryVerse AI — FastAPI Application Entry Point
"""
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

load_dotenv()

# ─── DB INIT ──────────────────────────────────────────────────────────────────
from database.db import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    os.makedirs(os.getenv("UPLOAD_DIR", "uploads"), exist_ok=True)
    yield


# ─── APP INIT ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="MemoryVerse AI",
    description="AI-powered Digital Identity System — organize, connect, and retrieve your academic journey.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,       # Disable public docs
    redoc_url=None,      # Disable public redoc
    openapi_url=None,    # Disable public openapi.json
)

# ─── PROTECTED ADMIN API DOCS ──────────────────────────────────────────────────
import secrets
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security_basic = HTTPBasic(auto_error=False)
ADMIN_DOCS_USER = os.getenv("ADMIN_DOCS_USER", "admin")
ADMIN_DOCS_PASS = os.getenv("ADMIN_DOCS_PASS", "change_me_in_env")


def check_admin_auth(credentials: Optional[HTTPBasicCredentials] = Depends(security_basic)):
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin credentials required to view API documentation.",
            headers={"WWW-Authenticate": 'Basic realm="Admin API Documentation"'},
        )
    is_user_ok = secrets.compare_digest(credentials.username, ADMIN_DOCS_USER)
    is_pass_ok = secrets.compare_digest(credentials.password, ADMIN_DOCS_PASS)
    if not (is_user_ok and is_pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin credentials required to view API documentation.",
            headers={"WWW-Authenticate": 'Basic realm="Admin API Documentation"'},
        )
    return credentials.username


@app.get("/api/openapi.json", include_in_schema=False)
async def get_protected_openapi(username: str = Depends(check_admin_auth)):
    return get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )


@app.get("/api/docs", include_in_schema=False)
async def get_protected_docs(username: str = Depends(check_admin_auth)):
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title=app.title + " - Admin API Documentation",
    )


@app.get("/api/redoc", include_in_schema=False)
async def get_protected_redoc(username: str = Depends(check_admin_auth)):
    return get_redoc_html(
        openapi_url="/api/openapi.json",
        title=app.title + " - Admin ReDoc Documentation",
    )

# ─── SECURITY MIDDLEWARE ──────────────────────────────────────────────────────
from middleware.security import add_security_headers
app.middleware("http")(add_security_headers)

# ─── CORS ─────────────────────────────────────────────────────────────────────
allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
allowed_origins = [o.strip() for o in allowed_origins_raw.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# ─── EXCEPTION HANDLERS ───────────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []) if l != "body")
        errors.append(f"Field '{loc}': {err.get('msg', 'Invalid value')}")
    return JSONResponse(
        status_code=422,
        content={"error": "Validation Error", "details": errors},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    headers = getattr(exc, "headers", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
        headers=headers,
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    # Never leak stack traces or internal details to the client
    print(f"[ERROR] Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "An unexpected error occurred. Please try again."},
    )

# ─── ROUTES ───────────────────────────────────────────────────────────────────
from routes.auth import router as auth_router
from routes.upload import router as upload_router
from routes.documents import router as documents_router
from routes.search import router as search_router
from routes.timeline import router as timeline_router
from routes.graph import router as graph_router

app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(timeline_router)
app.include_router(graph_router)

# ─── SERVE FRONTEND ───────────────────────────────────────────────────────────
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/", include_in_schema=False)
    def serve_frontend():
        return FileResponse(os.path.join(frontend_dir, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
