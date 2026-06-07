from datetime import date, time

from sqlalchemy.orm import Session

from app.models.enums import Importance, TaskStatus
from app.schemas.tasks import TaskCreate
from app.services.task_service import TaskService


def test_create_and_complete_task(db_session: Session, user) -> None:
    service = TaskService(db_session)
    task = service.create_task(
        TaskCreate(
            user_id=user.id,
            title="客户报价",
            importance=Importance.HIGH,
            planned_date=date(2026, 6, 7),
            planned_time=time(9, 0),
        )
    )

    completed = service.complete_most_relevant(user.id, "客户")

    assert task.id == completed.id
    assert completed.status == TaskStatus.COMPLETED.value
    assert completed.actual_completed_at is not None

