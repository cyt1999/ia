from datetime import date

from app.models.enums import GoalDirection, GoalProgressKind, GoalStatus
from app.models.goal import GoalProgressEntry
from app.schemas.goals import GoalCreate, GoalProgressUpdate
from app.services.goal_service import GoalService


def test_create_goal_and_record_progress_history(db_session, user) -> None:
    service = GoalService(db_session)
    goal = service.create_goal(
        GoalCreate(
            user_id=user.id,
            title="存钱",
            metric_name="存款",
            unit="元",
            direction=GoalDirection.INCREASE,
            target_value=10000,
            start_date=date(2026, 6, 9),
        )
    )

    updated, entry = service.update_progress(
        user.id,
        GoalProgressUpdate(
            goal_title="存钱",
            kind=GoalProgressKind.CURRENT_VALUE,
            value=2300,
            raw_text="我现在存了 2300",
        ),
    )
    snapshot = service.status_for(updated)

    assert goal.id == updated.id
    assert updated.start_date == date(2026, 6, 9)
    assert updated.current_value == 2300
    assert entry.value == 2300
    assert snapshot.percent == 23
    assert snapshot.remaining_text == "还差 7700 元"
    assert db_session.query(GoalProgressEntry).count() == 1


def test_weight_loss_goal_uses_first_progress_as_baseline(db_session, user) -> None:
    service = GoalService(db_session)
    goal = service.create_goal(
        GoalCreate(
            user_id=user.id,
            title="减肥",
            metric_name="减重",
            unit="斤",
            direction=GoalDirection.DECREASE,
            target_delta=30,
        )
    )

    service.update_progress(
        user.id,
        GoalProgressUpdate(
            goal_title="减肥",
            kind=GoalProgressKind.CURRENT_VALUE,
            value=180,
            raw_text="我现在 180 斤",
        ),
    )
    updated, _entry = service.update_progress(
        user.id,
        GoalProgressUpdate(
            goal_title="减肥",
            kind=GoalProgressKind.CURRENT_VALUE,
            value=176,
            raw_text="今天 176 斤",
        ),
    )
    snapshot = service.status_for(updated)

    assert goal.baseline_value == 180
    assert updated.current_value == 176
    assert snapshot.percent == 13.333333333333334
    assert snapshot.remaining_text == "还差 26 斤"


def test_goal_is_completed_when_target_is_reached(db_session, user) -> None:
    service = GoalService(db_session)
    service.create_goal(
        GoalCreate(
            user_id=user.id,
            title="存钱",
            metric_name="存款",
            unit="元",
            direction=GoalDirection.INCREASE,
            target_value=10000,
        )
    )

    goal, _entry = service.update_progress(
        user.id,
        GoalProgressUpdate(
            goal_title="存钱",
            kind=GoalProgressKind.CURRENT_VALUE,
            value=10000,
        ),
    )

    assert goal.status == GoalStatus.COMPLETED.value
