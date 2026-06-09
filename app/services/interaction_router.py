import json

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent.deepseek_provider import AI_UNAVAILABLE_MESSAGE, DeepSeekProvider, unavailable_intent
from app.agent.intents import IntentType
from app.agent.provider import LLMProvider
from app.channels.actions import ActionId
from app.channels.base import InboundInteraction, NotificationChannel
from app.channels.messages import OutboundMessage
from app.config.settings import Settings
from app.models.inbound_message import InboundMessage
from app.services.authz_service import AuthzService
from app.services.goal_service import GoalService
from app.services.memory_service import MemoryService
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
        llm: LLMProvider | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.channel = channel
        self.authz = AuthzService(settings)
        self.llm = llm or DeepSeekProvider(settings)
        self.renderer = MessageRenderer()
        self.logger = structlog.get_logger(__name__)

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
        try:
            parsed = await self.llm.parse_intent(
                user_id=user.id,
                text=interaction.text,
                timezone=self.settings.app_timezone,
            )
        except Exception:
            parsed = unavailable_intent()

        if parsed.reply == AI_UNAVAILABLE_MESSAGE:
            await self._reply(interaction, "小助手失联", AI_UNAVAILABLE_MESSAGE)
            inbound.status = "processed"
            self.db.commit()
            return

        if parsed.memory:
            MemoryService(self.settings).remember(parsed.memory)

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
        elif parsed.intent == IntentType.LIST_TASKS:
            tasks = task_service.current_tasks(user.id, user.timezone, include_system=True)
            await self._reply_message(
                interaction,
                self.renderer.task_list(title="当前任务", rows=self._task_rows(tasks)),
            )
        elif parsed.intent == IntentType.LIST_GOALS:
            goals = GoalService(self.db).active_goals(user.id)
            await self._reply_message(
                interaction,
                self.renderer.task_list(
                    title="当前目标",
                    rows=self._goal_rows(goals),
                    empty_text="现在还没有目标。",
                ),
            )
        elif parsed.intent == IntentType.GOAL_STATUS:
            goal_service = GoalService(self.db)
            goal = goal_service.target_goal(user.id, parsed.target_title)
            if goal:
                await self._reply(
                    interaction,
                    "目标进度",
                    self._goal_status_body(goal_service, goal),
                )
            else:
                await self._reply(
                    interaction,
                    "没找到目标",
                    "我没找到这个目标，你可以说得具体一点。",
                )
        elif parsed.intent == IntentType.CREATE_GOAL and parsed.goal:
            parsed.goal.user_id = user.id
            goal = GoalService(self.db).create_goal(parsed.goal, timezone=user.timezone)
            await self._reply(interaction, "已创建目标", self._goal_created_body(goal))
        elif parsed.intent == IntentType.UPDATE_GOAL_PROGRESS and parsed.goal_progress:
            try:
                goal, _entry = GoalService(self.db).update_progress(
                    user.id, parsed.goal_progress
                )
            except ValueError:
                await self._reply(
                    interaction,
                    "没找到目标",
                    "我没找到要更新的目标，你可以说得具体一点。",
                )
            else:
                await self._reply(
                    interaction,
                    "已记录进度",
                    self._goal_status_body(GoalService(self.db), goal),
                )
        elif parsed.intent == IntentType.REMEMBER and parsed.memory:
            await self._reply(interaction, "已记住", f"我会记住：{parsed.memory}")
        elif parsed.intent == IntentType.UPDATE_TASK and parsed.task_update:
            task = task_service.update_most_relevant(user.id, parsed.task_update)
            if task:
                ReminderService(self.db).reschedule_for_task(task=task, timezone=user.timezone)
                await self._reply(interaction, "已更新", self._task_updated_body(task))
            else:
                await self._reply(
                    interaction, "没找到任务", "我没找到要修改的任务，你可以说得具体一点。"
                )
        elif parsed.intent == IntentType.CREATE_TASK and (parsed.task or parsed.tasks):
            task_inputs = parsed.tasks or ([parsed.task] if parsed.task else [])
            tasks = []
            for task_input in task_inputs:
                task_input.user_id = user.id
                task = task_service.create_task(task_input)
                ReminderService(self.db).create_for_task(
                    user_id=user.id,
                    task_id=task.id,
                    title=task.title,
                    planned_date=task.planned_date,
                    planned_time=task.planned_time,
                    timezone=user.timezone,
                )
                tasks.append(task)
            await self._reply(interaction, "已安排", self._task_created_body(tasks))
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
        await self._reply_message(interaction, self.renderer.text(title=title, body=body))

    async def _reply_message(
        self, interaction: InboundInteraction, message: OutboundMessage
    ) -> None:
        if self.channel is None or not interaction.chat_id:
            self.logger.warning(
                "reply_skipped",
                reason="missing_channel_or_chat_id",
                has_channel=self.channel is not None,
                chat_id=interaction.chat_id,
                message_id=interaction.message_id,
            )
            return
        result = await self.channel.send(interaction.chat_id, message)
        log = self.logger.info if result.ok else self.logger.warning
        log(
            "reply_sent" if result.ok else "reply_send_failed",
            chat_id=interaction.chat_id,
            message_id=interaction.message_id,
            title=message.title,
            provider_message_id=result.provider_message_id,
            error=result.error_summary,
        )

    def _task_rows(self, tasks) -> list[str]:
        rows = []
        for task in tasks:
            when = None
            if task.planned_date and task.planned_time:
                when = f"{task.planned_date} {task.planned_time:%H:%M}"
            elif task.planned_date:
                when = str(task.planned_date)
            elif task.planned_time:
                when = task.planned_time.strftime("%H:%M")

            recurrence = self._recurrence_label(task.recurrence_rule)
            action = self._action_label(task.action_key)
            task_type = self._task_list_type_label(task)
            details = "，".join(part for part in [task_type, action, when, recurrence] if part)
            rows.append(f"- {task.title}（{details}）" if details else f"- {task.title}")
        return rows

    def _task_list_type_label(self, task) -> str:
        if task.source == "system" or task.action_key:
            return "系统任务"
        return "普通任务"

    def _recurrence_label(self, recurrence_rule: str | None) -> str | None:
        if recurrence_rule == "daily":
            return "每天"
        if recurrence_rule == "weekdays":
            return "每个工作日"
        return None

    def _task_created_body(self, tasks) -> str:
        if len(tasks) == 1:
            task = tasks[0]
            parts = [f"我已安排「{task.title}」。"]
            parts.extend(self._task_detail_lines(task))
            return "\n".join(parts)

        rows = [f"我已安排 {len(tasks)} 个任务。"]
        for task in tasks:
            rows.append(f"- {task.title}")
            rows.extend(f"  {line}" for line in self._task_detail_lines(task))
        return "\n".join(rows)

    def _task_updated_body(self, task) -> str:
        parts = [f"我已更新「{task.title}」。"]
        parts.extend(self._task_detail_lines(task, include_non_recurring=True))
        return "\n".join(parts)

    def _task_detail_lines(self, task, *, include_non_recurring: bool = False) -> list[str]:
        parts = []
        if task.source == "system":
            parts.append("类型：系统任务")
        action = self._action_label(task.action_key)
        if action:
            parts.append(f"执行：{action}")
        if task.planned_date:
            parts.append(f"日期：{task.planned_date}")
        if task.planned_time:
            parts.append(f"时间：{task.planned_time.strftime('%H:%M')}")
        recurrence = self._recurrence_label(task.recurrence_rule)
        if recurrence:
            parts.append(f"重复：{recurrence}")
        elif include_non_recurring:
            parts.append("重复：不重复")
        if task.estimated_minutes:
            parts.append(f"预计：{task.estimated_minutes} 分钟")
        return parts

    def _action_label(self, action_key: str | None) -> str | None:
        if action_key == "daily_briefing":
            return "每日任务和目标简报"
        if action_key == "daily_review":
            return "晚间总结复盘"
        return None

    def _goal_rows(self, goals) -> list[str]:
        service = GoalService(self.db)
        rows = []
        for goal in goals:
            snapshot = service.status_for(goal)
            percent = self._percent_label(snapshot.percent)
            period = self._goal_period(goal)
            details = "，".join(part for part in [percent, period] if part)
            rows.append(f"- {goal.title}：{snapshot.progress_text}（{details}）")
        return rows

    def _goal_created_body(self, goal) -> str:
        rows = [f"我会帮你跟踪「{goal.title}」。"]
        period = self._goal_period(goal)
        if period:
            rows.append(f"周期：{period}")
        if goal.target_value is not None:
            rows.append(f"目标：{self._format_number(goal.target_value)} {goal.unit}")
        elif goal.target_delta is not None:
            target_delta = self._format_number(goal.target_delta)
            rows.append(f"目标：{goal.metric_name} {target_delta} {goal.unit}")
        if goal.current_value is not None:
            rows.append(f"当前：{self._format_number(goal.current_value)} {goal.unit}")
        elif goal.direction == "decrease":
            rows.append("还需要你告诉我当前数值，我才能计算进度。")
        return "\n".join(rows)

    def _goal_status_body(self, goal_service: GoalService, goal) -> str:
        snapshot = goal_service.status_for(goal)
        rows = [
            f"「{goal.title}」",
            f"周期：{self._goal_period(goal) or '未设置'}",
            snapshot.progress_text,
            f"完成度：{self._percent_label(snapshot.percent)}",
        ]
        if snapshot.remaining_text:
            rows.append(snapshot.remaining_text)
        entries = goal_service.progress_entries(goal.id)
        if entries:
            rows.append("进度记录：")
            for entry in entries[-5:]:
                value = self._format_number(entry.value)
                rows.append(f"- {entry.recorded_at:%Y-%m-%d}：{value} {goal.unit}")
        return "\n".join(rows)

    def _percent_label(self, percent: float | None) -> str:
        if percent is None:
            return "暂无"
        return f"{self._format_number(percent)}%"

    def _goal_period(self, goal) -> str | None:
        if goal.start_date and goal.deadline:
            return f"{goal.start_date} 至 {goal.deadline}"
        if goal.start_date:
            return f"{goal.start_date} 开始"
        if goal.deadline:
            return f"截止 {goal.deadline}"
        return None

    def _format_number(self, value: float) -> str:
        if value == int(value):
            return str(int(value))
        return f"{value:.1f}".rstrip("0").rstrip(".")

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
