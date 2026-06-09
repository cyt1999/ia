from dataclasses import dataclass

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.enums import GoalDirection, GoalProgressKind, GoalStatus
from app.models.goal import Goal, GoalProgressEntry
from app.schemas.goals import GoalCreate, GoalProgressUpdate
from app.utils.timezone import from_utc, now_utc


@dataclass(frozen=True)
class GoalSnapshot:
    goal: Goal
    progress_text: str
    remaining_text: str | None
    percent: float | None


class GoalService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_goal(self, data: GoalCreate, *, timezone: str = "Asia/Shanghai") -> Goal:
        start_date = data.start_date or from_utc(now_utc(), timezone).date()
        goal = Goal(
            user_id=data.user_id,
            title=data.title,
            metric_name=data.metric_name,
            unit=data.unit,
            direction=data.direction.value,
            baseline_value=data.baseline_value,
            current_value=data.current_value,
            target_value=data.target_value,
            target_delta=data.target_delta,
            start_date=start_date,
            deadline=data.deadline,
            status=GoalStatus.ACTIVE.value,
            notes=data.notes,
        )
        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)
        return goal

    def update_progress(
        self, user_id: int, update: GoalProgressUpdate
    ) -> tuple[Goal, GoalProgressEntry]:
        goal = self._find_target(user_id, update.goal_title)
        if goal is None:
            raise ValueError("goal_not_found")

        if update.kind == GoalProgressKind.CURRENT_VALUE:
            goal.current_value = update.value
            if goal.baseline_value is None and goal.direction == GoalDirection.DECREASE.value:
                goal.baseline_value = update.value
        else:
            goal.current_value = (goal.current_value or 0) + update.value

        self._refresh_status(goal)
        entry = GoalProgressEntry(
            goal_id=goal.id,
            user_id=user_id,
            kind=update.kind.value,
            value=update.value,
            note=update.note,
            raw_text=update.raw_text,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(goal)
        self.db.refresh(entry)
        return goal, entry

    def active_goals(self, user_id: int) -> list[Goal]:
        stmt = (
            select(Goal)
            .where(and_(Goal.user_id == user_id, Goal.status == GoalStatus.ACTIVE.value))
            .order_by(Goal.deadline.is_(None), Goal.deadline, Goal.id)
        )
        return list(self.db.scalars(stmt))

    def target_goal(self, user_id: int, title: str | None = None) -> Goal | None:
        return self._find_target(user_id, title)

    def progress_entries(self, goal_id: int) -> list[GoalProgressEntry]:
        stmt = (
            select(GoalProgressEntry)
            .where(GoalProgressEntry.goal_id == goal_id)
            .order_by(GoalProgressEntry.recorded_at, GoalProgressEntry.id)
        )
        return list(self.db.scalars(stmt))

    def status_for(self, goal: Goal) -> GoalSnapshot:
        percent = self._percent(goal)
        progress_text = self._progress_text(goal)
        remaining_text = self._remaining_text(goal)
        return GoalSnapshot(
            goal=goal,
            progress_text=progress_text,
            remaining_text=remaining_text,
            percent=percent,
        )

    def _find_target(self, user_id: int, title: str | None = None) -> Goal | None:
        stmt = select(Goal).where(
            and_(Goal.user_id == user_id, Goal.status == GoalStatus.ACTIVE.value)
        )
        if title:
            stmt = stmt.where(Goal.title.contains(title))
        stmt = stmt.order_by(Goal.deadline.is_(None), Goal.deadline, Goal.id)
        return self.db.scalar(stmt)

    def _refresh_status(self, goal: Goal) -> None:
        percent = self._percent(goal)
        if percent is not None and percent >= 100:
            goal.status = GoalStatus.COMPLETED.value

    def _percent(self, goal: Goal) -> float | None:
        if goal.current_value is None:
            return None

        if goal.direction == GoalDirection.INCREASE.value:
            if not goal.target_value:
                return None
            return min(goal.current_value / goal.target_value * 100, 100)

        if goal.baseline_value is None:
            return None
        if goal.target_delta:
            completed = goal.baseline_value - goal.current_value
            return min(max(completed / goal.target_delta * 100, 0), 100)
        if goal.target_value is not None and goal.baseline_value > goal.target_value:
            completed = goal.baseline_value - goal.current_value
            total = goal.baseline_value - goal.target_value
            return min(max(completed / total * 100, 0), 100)
        return None

    def _progress_text(self, goal: Goal) -> str:
        if goal.current_value is None:
            return "还没有记录进度"
        return f"当前{goal.metric_name} {self._format_number(goal.current_value)} {goal.unit}"

    def _remaining_text(self, goal: Goal) -> str | None:
        if goal.current_value is None:
            return None

        if goal.direction == GoalDirection.INCREASE.value and goal.target_value is not None:
            remaining = max(goal.target_value - goal.current_value, 0)
            return f"还差 {self._format_number(remaining)} {goal.unit}"

        if goal.direction == GoalDirection.DECREASE.value:
            if goal.baseline_value is None:
                return None
            if goal.target_delta:
                completed = max(goal.baseline_value - goal.current_value, 0)
                remaining = max(goal.target_delta - completed, 0)
                return f"还差 {self._format_number(remaining)} {goal.unit}"
            if goal.target_value is not None:
                remaining = max(goal.current_value - goal.target_value, 0)
                return f"还差 {self._format_number(remaining)} {goal.unit}"
        return None

    def _format_number(self, value: float) -> str:
        if value == int(value):
            return str(int(value))
        return f"{value:.1f}".rstrip("0").rstrip(".")
