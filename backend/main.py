import argparse
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException

if __package__:
    from .config import Settings
    from .database import Database
    from .routes.repos import router as repos_router
    from .schemas.common import api_response, error_response
    from .services.queue_service import LogStreamBroker
else:
    from config import Settings
    from database import Database
    from routes.repos import router as repos_router
    from schemas.common import api_response, error_response
    from services.queue_service import LogStreamBroker


def create_app(demo_mode: bool | None = None) -> FastAPI:
    """Use environment settings for ASGI startup and allow an explicit CLI override."""
    settings = Settings() if demo_mode is None else Settings(DEMO_MODE=demo_mode)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database = Database(settings)
        app.state.database = database
        try:
            await database.init_db()
            redis_url = settings.REDIS_URL.get_secret_value() if settings.REDIS_URL else None
            app.state.log_stream = LogStreamBroker(database, redis_url)
            try:
                yield
            finally:
                await app.state.log_stream.close()
        finally:
            await database.dispose()

    application = FastAPI(title="CodeScape", lifespan=lifespan)
    application.state.settings = settings
    application.include_router(repos_router)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @application.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException):
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        response = error_response(message, exc.status_code)
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @application.exception_handler(RequestValidationError)
    async def invalid_request(_: Request, __: RequestValidationError):
        return error_response("Request validation failed", 422)

    @application.get("/api/v1/health")
    async def health():
        return api_response({"status": "ok", "demo_mode": settings.DEMO_MODE})

    return application


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="Start the CodeScape API.")
    parser.add_argument("--demo", action="store_true", default=None)
    uvicorn.run(create_app(demo_mode=parser.parse_args().demo), host="127.0.0.1", port=8000)
else:
    app = create_app()
