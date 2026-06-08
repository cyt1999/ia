from app.config.settings import Settings
from app.scheduler.app_scheduler import create_scheduler


def test_create_scheduler_registers_due_reminder_job() -> None:
    scheduler = create_scheduler("Asia/Shanghai", Settings())

    assert scheduler.get_job("send_due_reminders") is not None
