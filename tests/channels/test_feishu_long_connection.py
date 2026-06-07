from dataclasses import dataclass
from types import SimpleNamespace

from sqlalchemy.orm import Session, sessionmaker

from app.channels.feishu.long_connection import FeishuLongConnectionRunner
from app.config.settings import Settings
from app.models.inbound_message import InboundMessage


class FakeSdkChannel:
    def __init__(self) -> None:
        self.handlers = {}
        self.started = False
        self.stopped = False
        self.sent = []

    def on(self, name, handler):
        self.handlers[name] = handler

    def start(self):
        self.started = True

    async def disconnect(self):
        self.stopped = True

    async def send(self, chat_id, payload):
        self.sent.append((chat_id, payload))
        return SimpleNamespace(success=True, message_id="om_reply", error=None)


@dataclass
class FakeMessage:
    message_id: str = "om_1"
    sender_id: str = "ou_user"
    chat_id: str = "oc_chat"
    content_text: str = "知道了"


def _session_factory(db_session: Session):
    bind = db_session.get_bind()
    SessionLocal = sessionmaker(bind=bind, expire_on_commit=False)
    return SessionLocal


async def test_runner_normalizes_message_event(db_session: Session) -> None:
    sdk_channel = FakeSdkChannel()
    settings = Settings(
        FEISHU_APP_ID="cli",
        FEISHU_APP_SECRET="secret",
        FEISHU_ALLOWED_OPEN_ID="ou_user",
        FEISHU_ALLOWED_CHAT_ID="oc_chat",
    )
    runner = FeishuLongConnectionRunner(
        settings,
        session_factory=_session_factory(db_session),
        sdk_channel=sdk_channel,
    )

    await runner.start()
    await sdk_channel.handlers["message"](FakeMessage())

    row = db_session.query(InboundMessage).one()
    assert sdk_channel.started
    assert row.channel_message_id == "om_1"
    assert row.sender_id == "ou_user"
    assert row.chat_id == "oc_chat"
    assert sdk_channel.sent


async def test_runner_normalizes_card_action_event(db_session: Session) -> None:
    sdk_channel = FakeSdkChannel()
    settings = Settings(
        FEISHU_APP_ID="cli",
        FEISHU_APP_SECRET="secret",
        FEISHU_ALLOWED_OPEN_ID="ou_user",
        FEISHU_ALLOWED_CHAT_ID="oc_chat",
    )
    FeishuLongConnectionRunner(
        settings,
        session_factory=_session_factory(db_session),
        sdk_channel=sdk_channel,
    )
    event = SimpleNamespace(
        message_id="om_card",
        chat_id="oc_chat",
        operator=SimpleNamespace(open_id="ou_user"),
        action=SimpleNamespace(
            value={"action_id": "ack_reminder", "payload": {"reminder_id": 1}}
        ),
    )

    await sdk_channel.handlers["cardAction"](event)

    row = db_session.query(InboundMessage).one()
    assert row.action_id == "ack_reminder"
    assert '"reminder_id": 1' in row.action_payload
    assert sdk_channel.sent
