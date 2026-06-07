from datetime import date, time

from sqlalchemy.orm import Session

from app.agent.deepseek_provider import AI_UNAVAILABLE_MESSAGE
from app.agent.intents import IntentType, ParsedIntent
from app.channels.base import InboundInteraction, SendResult
from app.config.settings import Settings
from app.models.enums import Importance
from app.models.inbound_message import InboundMessage
from app.models.task import Task
from app.schemas.reviews import ReviewParsedUpdate
from app.schemas.tasks import TaskCreate
from app.services.interaction_router import InteractionRouter


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
    inbound = db_session.query(InboundMessage).one()
    assert task.title == "客户报价"
    assert inbound.status == "processed"
    assert channel.sent[0][0] == "oc_chat"
    assert channel.sent[0][1].title == "已安排"
    assert "客户报价" in channel.sent[0][1].plain_text


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
