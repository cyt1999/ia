from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api.routes.feishu import router as feishu_router
from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.scheduler.app_scheduler import create_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = structlog.get_logger(__name__)
    scheduler = create_scheduler(settings.app_timezone)
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("app_started", timezone=settings.app_timezone)
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        logger.info("app_stopped")


app = FastAPI(title="Personal Assistant Agent", lifespan=lifespan)
app.include_router(feishu_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}

