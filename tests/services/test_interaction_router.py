from datetime import date, time

from sqlalchemy.orm import Session

from app.agent.deepseek_provider import AI_UNAVAILABLE_MESSAGE
from app.agent.intents import IntentType, ParsedIntent
from app.channels.base import InboundInteraction, SendResult
from app.config.settings import Settings
from app.models.enums import (
    GoalDirection,
    GoalProgressKind,
    Importance,
    RecurrenceRule,
    TaskActionKey,
    TaskSource,
    TaskType,
)
from app.models.goal import Goal, GoalProgressEntry
from app.models.inbound_message import InboundMessage
from app.models.reminder import Reminder
from app.models.task import Task
from app.schemas.goals import GoalCreate, GoalProgressUpdate
from app.schemas.reviews import ReviewParsedUpdate
from app.schemas.tasks import TaskCreate
from app.services.interaction_router import InteractionRouter
from app.services.task_service import TaskService


class FakeChannel:
    def __init__(self) -> None:
        self.sent = []

    async def send(self, chat_id, message):
        self.sent.append((chat_id, message))
        return SendResult(provider_message_id="reply_1")


class FakeLLM:
    async def parse_intent(self, *, user_id: int, text: str, timezone: str) -> ParsedIntent:
        return ParsedIntent(
            intent=IntentType.CREATE_TASK,
            task=TaskCreate(
                user_id=user_id,
                title="客户报价",
                importance=Importance.HIGH,
                planned_date=date(2026, 6, 8),
                planned_time=time(9, 0),
                estimated_minutes=120,
            ),
            confidence=0.9,
        )

    async def parse_review(self, *, text: str) -> ReviewParsedUpdate:
        return ReviewParsedUpdate()

    async def reminder_copy(self, *, title: str, kind: str, context: str | None = None) -> str:
        return title


class BrokenLLM(FakeLLM):
    async def parse_intent(self, *, user_id: int, text: str, timezone: str) -> ParsedIntent:
        raise RuntimeError("openai unavailable")


class ListTasksLLM(FakeLLM):
    async def parse_intent(self, *, user_id: int, text: str, timezone: str) -> ParsedIntent:
        return ParsedIntent(intent=IntentType.LIST_TASKS, confidence=0.9)


class RememberLLM(FakeLLM):
    async def parse_intent(self, *, user_id: int, text: str, timezone: str) -> ParsedIntent:
        return ParsedIntent(
            intent=IntentType.REMEMBER,
            memory="任务名要提炼真正要做的事。",
            confidence=0.9,
        )


class CreateTaskWithMemoryLLM(FakeLLM):
    async def parse_intent(self, *, user_id: int, text: str, timezone: str) -> ParsedIntent:
        return ParsedIntent(
            intent=IntentType.CREATE_TASK,
            task=TaskCreate(
                user_id=user_id,
                title="健身",
                importance=Importance.MEDIUM,
                planned_date=date(2026, 6, 9),
                planned_time=time(10, 0),
            ),
            memory="任务名应提炼真正要做的事。",
            confidence=0.9,
        )


class CreateDailyPlanningAndReviewTasksLLM(FakeLLM):
    async def parse_intent(self, *, user_id: int, text: str, timezone: str) -> ParsedIntent:
        return ParsedIntent(
            intent=IntentType.CREATE_TASK,
            tasks=[
                TaskCreate(
                    user_id=user_id,
                    title="查看当天任务和目标",
                    task_type=TaskType.WORK,
                    planned_date=date(2026, 6, 9),
                    planned_time=time(9, 0),
                    recurrence_rule=RecurrenceRule.DAILY,
                    action_key=TaskActionKey.DAILY_BRIEFING,
                    source=TaskSource.SYSTEM,
                ),
                TaskCreate(
                    user_id=user_id,
                    title="当日总结复盘",
                    task_type=TaskType.REVIEW,
                    planned_date=date(2026, 6, 9),
                    planned_time=time(23, 0),
                    recurrence_rule=RecurrenceRule.DAILY,
                    action_key=TaskActionKey.DAILY_REVIEW,
                    source=TaskSource.SYSTEM,
                ),
            ],
            confidence=0.9,
        )


class CreateGoalLLM(FakeLLM):
    async def parse_intent(self, *, user_id: int, text: str, timezone: str) -> ParsedIntent:
        return ParsedIntent(
            intent=IntentType.CREATE_GOAL,
            goal=GoalCreate(
                user_id=user_id,
                title="存钱",
                metric_name="存款",
                unit="元",
                direction=GoalDirection.INCREASE,
                target_value=10000,
                start_date=date(2026, 6, 9),
                deadline=date(2026, 8, 31),
            ),
            confidence=0.9,
        )


class UpdateGoalProgressLLM(FakeLLM):
    async def parse_intent(self, *, user_id: int, text: str, timezone: str) -> ParsedIntent:
        return ParsedIntent(
            intent=IntentType.UPDATE_GOAL_PROGRESS,
            goal_progress=GoalProgressUpdate(
                goal_title="存钱",
                kind=GoalProgressKind.CURRENT_VALUE,
                value=2300,
                raw_text=text,
            ),
            confidence=0.9,
        )


class ListGoalsLLM(FakeLLM):
    async def parse_intent(self, *, user_id: int, text: str, timezone: str) -> ParsedIntent:
        return ParsedIntent(intent=IntentType.LIST_GOALS, confidence=0.9)


class GoalStatusLLM(FakeLLM):
    async def parse_intent(self, *, user_id: int, text: str, timezone: str) -> ParsedIntent:
        return ParsedIntent(
            intent=IntentType.GOAL_STATUS,
            target_title="存钱",
            confidence=0.9,
        )


async def test_router_replies_after_creating_task(db_session: Session) -> None:
    channel = FakeChannel()
    settings = Settings(
        DEEPSEEK_API_KEY="",
        FEISHU_ALLOWED_OPEN_ID="ou_user",
        FEISHU_ALLOWED_CHAT_ID="oc_chat",
    )
    interaction = InboundInteraction(
        channel="feishu",
        message_id="om_task",
        sender_id="ou_user",
        chat_id="oc_chat",
        text="明天上午做一下客户报价，比较重要，9 点开始，大概 2 小时。",
    )

    await InteractionRouter(db_session, settings, channel=channel, llm=FakeLLM()).handle(
        interaction
    )

    task = db_session.query(Task).one()
    reminder = db_session.query(Reminder).one()
    inbound = db_session.query(InboundMessage).one()
    assert task.title == "客户报价"
    assert reminder.task_id == task.id
    assert reminder.title == "客户报价"
    assert reminder.reminder_at == reminder.scheduled_start_at
    assert inbound.status == "processed"
    assert channel.sent[0][0] == "oc_chat"
    assert channel.sent[0][1].title == "已安排"
    assert "客户报价" in channel.sent[0][1].plain_text


async def test_router_replies_with_current_task_list(db_session: Session, user) -> None:
    service = TaskService(db_session)
    service.create_task(
        TaskCreate(
            user_id=user.id,
            title="客户报价",
            planned_date=date(2026, 6, 8),
            planned_time=time(9, 0),
        )
    )
    service.create_task(TaskCreate(user_id=user.id, title="健身"))
    service.create_task(
        TaskCreate(
            user_id=user.id,
            title="查看当天任务和目标",
            source=TaskSource.SYSTEM,
            action_key=TaskActionKey.DAILY_BRIEFING,
            recurrence_rule=RecurrenceRule.DAILY,
        )
    )
    service.create_task(
        TaskCreate(
            user_id=user.id,
            title="过期任务",
            planned_date=date(2000, 1, 1),
            planned_time=time(9, 0),
        )
    )
    service.complete_most_relevant(user.id, "客户")
    channel = FakeChannel()
    settings = Settings(
        DEEPSEEK_API_KEY="",
        FEISHU_ALLOWED_OPEN_ID="ou_user",
        FEISHU_ALLOWED_CHAT_ID="oc_chat",
    )
    interaction = InboundInteraction(
        channel="feishu",
        message_id="om_list",
        sender_id="ou_user",
        chat_id="oc_chat",
        text="目前有哪些任务",
    )

    await InteractionRouter(db_session, settings, channel=channel, llm=ListTasksLLM()).handle(
        interaction
    )

    assert channel.sent[0][1].title == "当前任务"
    assert "健身" in channel.sent[0][1].plain_text
    assert "查看当天任务和目标" not in channel.sent[0][1].plain_text
    assert "客户报价" not in channel.sent[0][1].plain_text
    assert "过期任务" not in channel.sent[0][1].plain_text


async def test_router_silently_remembers_preference_while_handling_task(
    db_session: Session, tmp_path
) -> None:
    channel = FakeChannel()
    memory_path = tmp_path / "memory.md"
    settings = Settings(
        DEEPSEEK_API_KEY="",
        FEISHU_ALLOWED_OPEN_ID="ou_user",
        FEISHU_ALLOWED_CHAT_ID="oc_chat",
        MEMORY_FILE_PATH=str(memory_path),
    )
    interaction = InboundInteraction(
        channel="feishu",
        message_id="om_task_memory",
        sender_id="ou_user",
        chat_id="oc_chat",
        text="明天10点提醒我去健身哦，这种任务名要叫健身。",
    )

    await InteractionRouter(
        db_session, settings, channel=channel, llm=CreateTaskWithMemoryLLM()
    ).handle(interaction)

    assert "任务名应提炼真正要做的事" in memory_path.read_text(encoding="utf-8")
    assert channel.sent[0][1].title == "已安排"
    assert "健身" in channel.sent[0][1].plain_text


async def test_router_confirms_multiple_recurring_task_rules(db_session: Session) -> None:
    channel = FakeChannel()
    settings = Settings(
        DEEPSEEK_API_KEY="",
        FEISHU_ALLOWED_OPEN_ID="ou_user",
        FEISHU_ALLOWED_CHAT_ID="oc_chat",
    )
    interaction = InboundInteraction(
        channel="feishu",
        message_id="om_daily_review",
        sender_id="ou_user",
        chat_id="oc_chat",
        text="每天晚上11点告诉我当天做了什么，做一个总结复盘。",
    )

    await InteractionRouter(
        db_session, settings, channel=channel, llm=CreateDailyPlanningAndReviewTasksLLM()
    ).handle(interaction)

    tasks = db_session.query(Task).order_by(Task.planned_time).all()
    assert [task.title for task in tasks] == ["查看当天任务和目标", "当日总结复盘"]
    assert [task.recurrence_rule for task in tasks] == ["daily", "daily"]
    assert [task.action_key for task in tasks] == ["daily_briefing", "daily_review"]
    assert [task.source for task in tasks] == ["system", "system"]
    assert db_session.query(Reminder).count() == 2
    assert channel.sent[0][1].title == "已安排"
    assert "我已安排 2 个任务" in channel.sent[0][1].plain_text
    assert "查看当天任务和目标" in channel.sent[0][1].plain_text
    assert "当日总结复盘" in channel.sent[0][1].plain_text
    assert "重复：每天" in channel.sent[0][1].plain_text


async def test_router_creates_goal(db_session: Session) -> None:
    channel = FakeChannel()
    settings = Settings(
        DEEPSEEK_API_KEY="",
        FEISHU_ALLOWED_OPEN_ID="ou_user",
        FEISHU_ALLOWED_CHAT_ID="oc_chat",
    )
    interaction = InboundInteraction(
        channel="feishu",
        message_id="om_goal",
        sender_id="ou_user",
        chat_id="oc_chat",
        text="我要存 1w 块钱",
    )

    await InteractionRouter(db_session, settings, channel=channel, llm=CreateGoalLLM()).handle(
        interaction
    )

    goal = db_session.query(Goal).one()
    assert goal.title == "存钱"
    assert goal.target_value == 10000
    assert goal.start_date == date(2026, 6, 9)
    assert goal.deadline == date(2026, 8, 31)
    assert channel.sent[0][1].title == "已创建目标"
    assert "周期：2026-06-09 至 2026-08-31" in channel.sent[0][1].plain_text
    assert "10000 元" in channel.sent[0][1].plain_text


async def test_router_updates_goal_progress_and_keeps_history(
    db_session: Session, user
) -> None:
    db_session.add(
        Goal(
            user_id=user.id,
            title="存钱",
            metric_name="存款",
            unit="元",
            direction="increase",
            target_value=10000,
            start_date=date(2026, 6, 9),
            deadline=date(2026, 8, 31),
            status="active",
        )
    )
    db_session.commit()
    channel = FakeChannel()
    settings = Settings(
        DEEPSEEK_API_KEY="",
        FEISHU_ALLOWED_OPEN_ID="ou_user",
        FEISHU_ALLOWED_CHAT_ID="oc_chat",
    )
    interaction = InboundInteraction(
        channel="feishu",
        message_id="om_goal_progress",
        sender_id="ou_user",
        chat_id="oc_chat",
        text="我现在存了 2300",
    )

    await InteractionRouter(
        db_session, settings, channel=channel, llm=UpdateGoalProgressLLM()
    ).handle(interaction)

    goal = db_session.query(Goal).one()
    entry = db_session.query(GoalProgressEntry).one()
    assert goal.current_value == 2300
    assert entry.raw_text == "我现在存了 2300"
    assert channel.sent[0][1].title == "已记录进度"
    assert "完成度：23%" in channel.sent[0][1].plain_text
    assert "进度记录" in channel.sent[0][1].plain_text


async def test_router_lists_and_reports_goal_status(db_session: Session, user) -> None:
    goal = Goal(
        user_id=user.id,
        title="存钱",
        metric_name="存款",
        unit="元",
            direction="increase",
            current_value=2300,
            target_value=10000,
            start_date=date(2026, 6, 9),
            deadline=date(2026, 8, 31),
            status="active",
        )
    db_session.add(goal)
    db_session.flush()
    db_session.add(
        GoalProgressEntry(
            goal_id=goal.id,
            user_id=user.id,
            kind="current_value",
            value=2300,
            raw_text="我现在存了 2300",
        )
    )
    db_session.commit()
    settings = Settings(
        DEEPSEEK_API_KEY="",
        FEISHU_ALLOWED_OPEN_ID="ou_user",
        FEISHU_ALLOWED_CHAT_ID="oc_chat",
    )
    list_channel = FakeChannel()
    status_channel = FakeChannel()

    await InteractionRouter(
        db_session, settings, channel=list_channel, llm=ListGoalsLLM()
    ).handle(
        InboundInteraction(
            channel="feishu",
            message_id="om_goal_list",
            sender_id="ou_user",
            chat_id="oc_chat",
            text="我有哪些目标",
        )
    )
    await InteractionRouter(
        db_session, settings, channel=status_channel, llm=GoalStatusLLM()
    ).handle(
        InboundInteraction(
            channel="feishu",
            message_id="om_goal_status",
            sender_id="ou_user",
            chat_id="oc_chat",
            text="我的存钱目标怎么样了",
        )
    )

    assert list_channel.sent[0][1].title == "当前目标"
    assert "存钱" in list_channel.sent[0][1].plain_text
    assert "23%" in list_channel.sent[0][1].plain_text
    assert status_channel.sent[0][1].title == "目标进度"
    assert "还差 7700 元" in status_channel.sent[0][1].plain_text
    assert "周期：2026-06-09 至 2026-08-31" in status_channel.sent[0][1].plain_text


async def test_router_remembers_user_preference(db_session: Session, tmp_path) -> None:
    channel = FakeChannel()
    memory_path = tmp_path / "memory.md"
    settings = Settings(
        DEEPSEEK_API_KEY="",
        FEISHU_ALLOWED_OPEN_ID="ou_user",
        FEISHU_ALLOWED_CHAT_ID="oc_chat",
        MEMORY_FILE_PATH=str(memory_path),
    )
    interaction = InboundInteraction(
        channel="feishu",
        message_id="om_remember",
        sender_id="ou_user",
        chat_id="oc_chat",
        text="记住任务名要提炼真正要做的事。",
    )

    await InteractionRouter(db_session, settings, channel=channel, llm=RememberLLM()).handle(
        interaction
    )

    assert "任务名要提炼真正要做的事" in memory_path.read_text(encoding="utf-8")
    assert channel.sent[0][1].title == "已记住"


async def test_router_replies_unavailable_without_ai(db_session: Session) -> None:
    channel = FakeChannel()
    settings = Settings(
        DEEPSEEK_API_KEY="",
        FEISHU_ALLOWED_OPEN_ID="ou_user",
        FEISHU_ALLOWED_CHAT_ID="oc_chat",
    )
    interaction = InboundInteraction(
        channel="feishu",
        message_id="om_hi",
        sender_id="ou_user",
        chat_id="oc_chat",
        text="你好",
    )

    await InteractionRouter(db_session, settings, channel=channel).handle(interaction)

    assert db_session.query(Task).count() == 0
    assert channel.sent[0][1].title == "小助手失联"
    assert AI_UNAVAILABLE_MESSAGE in channel.sent[0][1].plain_text


async def test_router_replies_unavailable_when_llm_raises(db_session: Session) -> None:
    channel = FakeChannel()
    settings = Settings(
        DEEPSEEK_API_KEY="",
        FEISHU_ALLOWED_OPEN_ID="ou_user",
        FEISHU_ALLOWED_CHAT_ID="oc_chat",
    )
    interaction = InboundInteraction(
        channel="feishu",
        message_id="om_broken",
        sender_id="ou_user",
        chat_id="oc_chat",
        text="明天要去健身",
    )

    await InteractionRouter(db_session, settings, channel=channel, llm=BrokenLLM()).handle(
        interaction
    )

    assert db_session.query(Task).count() == 0
    assert channel.sent[0][1].title == "小助手失联"
    assert AI_UNAVAILABLE_MESSAGE in channel.sent[0][1].plain_text
