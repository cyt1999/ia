from apscheduler.schedulers.asyncio import AsyncIOScheduler


def create_scheduler(timezone: str) -> AsyncIOScheduler:
    return AsyncIOScheduler(timezone=timezone)

