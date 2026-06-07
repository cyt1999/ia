
from sqlalchemy.orm import Session

from app.agent.provider import LLMProvider
from app.models.review import Review
from app.models.task import Task
from app.schemas.reviews import ReviewCreate, ReviewParsedUpdate
from app.schemas.tasks import TaskCreate
from app.services.message_renderer import MessageRenderer
from app.services.task_service import TaskService


class ReviewService:
    def __init__(
        self,
        db: Session,
        parser: LLMProvider | None = None,
        renderer: MessageRenderer | None = None,
    ) -> None:
        self.db = db
        self.parser = parser
        self.renderer = renderer or MessageRenderer()

    def prompt(self, tasks: list[Task], missed_notes: list[str] | None = None):
        task_lines = [f"- {task.title}（{task.status}）" for task in tasks] or [
            "- 今天还没有任务记录"
        ]
        body = "今天完成了什么？\n还有什么没完成？\n明天有什么安排？\n\n" + "\n".join(task_lines)
        return self.renderer.review_prompt(body=body, missed_notes=missed_notes)

    async def parse_and_save(self, data: ReviewCreate) -> Review:
        return self.save_review(data)

    def save_review(self, data: ReviewCreate) -> Review:
        task_service = TaskService(self.db)
        for title in data.parsed.completed_task_titles:
            task_service.complete_most_relevant(data.user_id, title)
        for title in data.parsed.postponed_task_titles:
            task_service.postpone_most_relevant(data.user_id, title)
        for title in data.parsed.cancelled_task_titles:
            task_service.cancel_most_relevant(data.user_id, title)
        for title in data.parsed.tomorrow_tasks:
            task_service.create_task(TaskCreate(user_id=data.user_id, title=title))

        review = Review(
            user_id=data.user_id,
            review_date=data.review_date,
            completed_summary=data.parsed.completed_summary,
            unfinished_summary=data.parsed.unfinished_summary,
            tomorrow_plan=data.parsed.tomorrow_plan,
            state_note=data.parsed.state_note,
            missed_reminder_notes=data.missed_reminder_notes,
            raw_response=data.raw_response,
            structured_output=data.parsed.model_dump_json(),
        )
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review

    async def parse_response(self, text: str) -> ReviewParsedUpdate:
        if self.parser is None:
            return ReviewParsedUpdate(completed_summary=text)
        return await self.parser.parse_review(text=text)
