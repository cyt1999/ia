import json

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent.intents import IntentType
from app.agent.openai_provider import OpenAIProvider
from app.channels.actions import ActionId
from app.channels.base import InboundInteraction, NotificationChannel
from app.config.settings import Settings
from app.models.inbound_message import InboundMessage
from app.services.authz_service import AuthzService
from app.services.message_renderer import MessageRenderer
from app.services.reminder_service import ReminderService
from app.services.task_service import TaskService
from app.services.user_service import UserService
from app.utils.timezone import now_utc


class InteractionRouter:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        channel: NotificationChannel | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.channel = channel
        self.authz = AuthzService(settings)
        self.llm = OpenAIProvider(settings)
        self.renderer = MessageRenderer()

    async def handle(self, interaction: InboundInteraction) -> None:
        if not self.authz.is_allowed(interaction):
            self._record(interaction, status="ignored")
            return
        user = UserService(self.db, self.settings).current_user()
        inbound = self._record(interaction, user_id=user.id)
        if inbound is None:
            return

        if interaction.action_id:
            await self._handle_action(interaction)
            inbound.status = "processed"
            self.db.commit()
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
            task = task_service.complete_most_relevant(user.id, parsed.target_title)
            if task:
                await self._reply(interaction, "已完成", f"我把「{task.title}」标记为完成了。")
            else:
                await self._reply(
                    interaction, "没找到任务", "我没找到要完成的任务，你可以说得具体一点。"
                )
        elif parsed.intent == IntentType.POSTPONE_TASK:
            task = task_service.postpone_most_relevant(user.id, parsed.target_title)
            if task:
                await self._reply(interaction, "已推迟", f"我先把「{task.title}」标记为推迟。")
            else:
                await self._reply(
                    interaction, "没找到任务", "我没找到要推迟的任务，你可以说得具体一点。"
                )
        elif parsed.intent == IntentType.CANCEL_TASK:
            task = task_service.cancel_most_relevant(user.id, parsed.target_title)
            if task:
                await self._reply(interaction, "已取消", f"我把「{task.title}」取消了。")
            else:
                await self._reply(
                    interaction, "没找到任务", "我没找到要取消的任务，你可以说得具体一点。"
                )
        elif parsed.intent == IntentType.CREATE_TASK and parsed.task:
            parsed.task.user_id = user.id
            task = task_service.create_task(parsed.task)
            parts = [f"我已安排「{task.title}」。"]
            if task.planned_date:
                parts.append(f"日期：{task.planned_date}")
            if task.planned_time:
                parts.append(f"时间：{task.planned_time.strftime('%H:%M')}")
            if task.estimated_minutes:
                parts.append(f"预计：{task.estimated_minutes} 分钟")
            await self._reply(interaction, "已安排", "\n".join(parts))
        elif parsed.intent == IntentType.ACKNOWLEDGE:
            await self._reply(interaction, "收到", "好，我记下了。")
        else:
            await self._reply(interaction, "收到", parsed.reply or "我收到了。")

        inbound.status = "processed"
        self.db.commit()

    async def _handle_action(self, interaction: InboundInteraction) -> None:
        reminder_id = interaction.action_payload.get("reminder_id")
        if not reminder_id:
            return
        reminders = ReminderService(self.db)
        if interaction.action_id == ActionId.ACK_REMINDER.value:
            reminders.ack(int(reminder_id))
            await self._reply(interaction, "收到", "好，我不再重复提醒这件事。")
        elif interaction.action_id == ActionId.SNOOZE_REMINDER.value:
            minutes = int(interaction.action_payload.get("minutes", 10))
            reminders.snooze(int(reminder_id), minutes, now_utc())
            await self._reply(interaction, "已推迟", f"我会在 {minutes} 分钟后再提醒你。")
        elif interaction.action_id == ActionId.SKIP_TODAY.value:
            reminders.ack(int(reminder_id))
            await self._reply(interaction, "今天跳过", "好，今天先不追这件事。")

    async def _reply(self, interaction: InboundInteraction, title: str, body: str) -> None:
        if self.channel is None or not interaction.chat_id:
            return
        await self.channel.send(interaction.chat_id, self.renderer.text(title=title, body=body))

    def _record(
        self, interaction: InboundInteraction, user_id: int | None = None, status: str = "received"
    ) -> InboundMessage | None:
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
            self.db.refresh(row)
            return row
        except IntegrityError:
            self.db.rollback()
            return None
