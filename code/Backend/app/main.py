"""FastAPI app factory, router mounting, CORS (PLAN.md §3).

Auth routes come entirely from fastapi-users' own router factories (§9) — there's no
routers/auth.py in the plan's project structure (§3 only lists nodes/pipeline/formula/data/
templates under routers/), so mounting them is main.py's job, not a dedicated router module's.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.auth.backend import auth_backend
from app.auth.dependencies import fastapi_users
from app.config import settings
from app.engine.registry import get_registry
from app.rate_limit import limiter
from app.routers import data, formula, nodes, pipeline, templates
from app.schemas.user import UserCreate, UserRead, UserUpdate


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_registry()  # build once at startup, not on the first request — fail fast on a bad node
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Flux", lifespan=lifespan)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/api/auth/jwt", tags=["auth"])
    app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/api/auth", tags=["auth"])
    users_router = fastapi_users.get_users_router(UserRead, UserUpdate)
    # Remove superuser admin endpoints (/{id}) which cannot be reached by standard users and are not part of Flux
    users_router.routes = [
        r for r in users_router.routes if not (hasattr(r, "path") and r.path.endswith("/{id}"))
    ]
    app.include_router(users_router, prefix="/api/users", tags=["users"])

    app.include_router(nodes.router)
    app.include_router(pipeline.router)
    app.include_router(formula.router)
    app.include_router(data.router)
    app.include_router(templates.router)

    # A root/health pair, so "is the backend up?" is answerable with a single curl instead of
    # having to know to ask for /docs or /api/nodes. (These lived in the old top-level main.py
    # stub, which is now just a re-export of this app.)
    @app.get("/", tags=["meta"])
    async def root() -> dict:
        return {"name": "FLUX", "status": "online", "docs": "/docs"}

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "online"}

    return app


app = create_app()
