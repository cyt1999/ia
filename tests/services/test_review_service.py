from datetime import date

from sqlalchemy.orm import Session

from app.schemas.reviews import ReviewCreate, ReviewParsedUpdate
from app.schemas.tasks import TaskCreate
from app.services.review_service import ReviewService
from app.services.task_service import TaskService


def test_save_review_updates_tasks_and_persists_review(db_session: Session, user) -> None:
    task_service = TaskService(db_session)
    task_service.create_task(TaskCreate(user_id=user.id, title="客户报价"))

    review = ReviewService(db_session).save_review(
        ReviewCreate(
            user_id=user.id,
            review_date=date(2026, 6, 7),
            raw_response="客户报价做完了，明天继续改方案。",
            parsed=ReviewParsedUpdate(
                completed_task_titles=["客户报价"],
                tomorrow_tasks=["改方案"],
                completed_summary="客户报价做完了",
                tomorrow_plan="改方案",
            ),
        )
    )

    assert review.id is not None
    tasks = task_service.active_tasks(user.id)
    assert [task.title for task in tasks] == ["改方案"]

