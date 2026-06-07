from sqlalchemy.orm import Session

from app.channels.base import InboundInteraction, SendResult
from app.config.settings import Settings
from app.models.inbound_message import InboundMessage
from app.models.task import Task
from app.services.interaction_router import InteractionRouter


class FakeChannel:
    def __init__(self) -> None:
        self.sent = []

    async def send(self, chat_id, message):
        self.sent.append((chat_id, message))
        return SendResult(provider_message_id="reply_1")


async def test_router_replies_after_creating_task(db_session: Session) -> None:
    channel = FakeChannel()
    settings = Settings(
        OPENAI_API_KEY="",
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

    await InteractionRouter(db_session, settings, channel=channel).handle(interaction)

    task = db_session.query(Task).one()
    inbound = db_session.query(InboundMessage).one()
    assert task.title == "客户报价"
    assert inbound.status == "processed"
    assert channel.sent[0][0] == "oc_chat"
    assert channel.sent[0][1].title == "已安排"
    assert "客户报价" in channel.sent[0][1].plain_text


async def test_router_replies_to_small_talk(db_session: Session) -> None:
    channel = FakeChannel()
    settings = Settings(
        OPENAI_API_KEY="",
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

    assert channel.sent[0][1].title == "收到"
