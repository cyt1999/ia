from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.channels.feishu.channel import FeishuChannel
from app.config.settings import Settings
from app.db.session import SessionLocal
from app.services.reminder_service import ReminderService
from app.services.user_service import UserService
from app.utils.timezone import now_utc


def create_scheduler(timezone: str, settings: Settings | None = None) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=timezone)
    if settings is not None:
        scheduler.add_job(
            send_due_reminders,
            "interval",
            seconds=30,
            args=[settings],
            id="send_due_reminders",
            max_instances=1,
            coalesce=True,
        )
    return scheduler


async def send_due_reminders(settings: Settings) -> int:
    with SessionLocal() as db:
        user = UserService(db, settings).current_user()
        chat_id = user.feishu_chat_id or settings.feishu_allowed_chat_id
        if not chat_id:
            return 0
        return await ReminderService(db).send_due(
            channel=FeishuChannel(settings),
            chat_id=chat_id,
            now=now_utc(),
            timezone=settings.app_timezone,
        )
