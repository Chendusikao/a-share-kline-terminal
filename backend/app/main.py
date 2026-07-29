from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


def create_app(static_dir: Path | None = None) -> FastAPI:
    application = FastAPI(
        title="A 股 K 线终端",
        docs_url=None,
        redoc_url=None,
    )

    @application.get("/api/v1/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    frontend_dist = static_dir or Path(__file__).parents[2] / "frontend" / "dist"
    if frontend_dist.is_dir():
        application.mount(
            "/",
            StaticFiles(directory=frontend_dist, html=True),
            name="frontend",
        )

    return application


app = create_app()
