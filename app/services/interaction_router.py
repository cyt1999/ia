import json

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent.intents import IntentType
from app.agent.openai_provider import OpenAIProvider
from app.channels.actions import ActionId
from app.channels.base import InboundInteraction
from app.config.settings import Settings
from app.models.inbound_message import InboundMessage
from app.services.authz_service import AuthzService
from app.services.reminder_service import ReminderService
from app.services.task_service import TaskService
from app.services.user_service import UserService


class InteractionRouter:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.authz = AuthzService(settings)
        self.llm = OpenAIProvider(settings)

    async def handle(self, interaction: InboundInteraction) -> None:
        if not self.authz.is_allowed(interaction):
            self._record(interaction, status="ignored")
            return
        user = UserService(self.db, self.settings).current_user()
        if not self._record(interaction, user_id=user.id):
            return

        if interaction.action_id:
            self._handle_action(interaction)
            return

        if not interaction.text:
            return

        task_service = TaskService(self.db)
        parsed = await self.llm.parse_intent(
            user_id=user.id,
            text=interaction.text,
            timezone=self.settings.app_timezone,
        )
        if parsed.intent == IntentType.COMPLETE_TASK:
            task_service.complete_most_relevant(user.id, parsed.target_title)
        elif parsed.intent == IntentType.POSTPONE_TASK:
            task_service.postpone_most_relevant(user.id, parsed.target_title)
        elif parsed.intent == IntentType.CANCEL_TASK:
            task_service.cancel_most_relevant(user.id, parsed.target_title)
        elif parsed.intent == IntentType.CREATE_TASK and parsed.task:
            task_service.create_task(parsed.task)

    def _handle_action(self, interaction: InboundInteraction) -> None:
        reminder_id = interaction.action_payload.get("reminder_id")
        if not reminder_id:
            return
        reminders = ReminderService(self.db)
        if interaction.action_id == ActionId.ACK_REMINDER.value:
            reminders.ack(int(reminder_id))
        elif interaction.action_id == ActionId.SNOOZE_REMINDER.value:
            minutes = int(interaction.action_payload.get("minutes", 10))
            from app.utils.timezone import now_utc

            reminders.snooze(int(reminder_id), minutes, now_utc())
        elif interaction.action_id == ActionId.SKIP_TODAY.value:
            reminders.ack(int(reminder_id))

    def _record(
        self, interaction: InboundInteraction, user_id: int | None = None, status: str = "received"
    ) -> bool:
        row = InboundMessage(
            user_id=user_id,
            channel=interaction.channel,
            channel_message_id=interaction.message_id,
            sender_id=interaction.sender_id,
            chat_id=interaction.chat_id,
            text=interaction.text,
            action_id=interaction.action_id,
            action_payload=json.dumps(interaction.action_payload, ensure_ascii=False),
            status=status,
        )
        self.db.add(row)
        try:
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            return False

