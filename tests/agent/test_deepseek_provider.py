import json

from app.agent.deepseek_provider import AI_UNAVAILABLE_MESSAGE, DeepSeekProvider
from app.agent.intents import IntentType
from app.config.settings import Settings


async def test_no_deepseek_key_returns_unavailable_intent() -> None:
    provider = DeepSeekProvider(Settings(DEEPSEEK_API_KEY=""))

    parsed = await provider.parse_intent(
        user_id=1,
        text="明天上午做一下客户报价，比较重要，9 点开始，大概 2 小时。",
        timezone="Asia/Shanghai",
    )

    assert parsed.intent == IntentType.UNKNOWN
    assert parsed.reply == AI_UNAVAILABLE_MESSAGE
    assert parsed.task is None


async def test_deepseek_json_output_intent_is_used() -> None:
    provider = DeepSeekProvider(
        Settings(
            DEEPSEEK_API_KEY="test-key",
            DEEPSEEK_MODEL="deepseek-v4-pro",
            DEEPSEEK_REASONING_EFFORT="high",
            DEEPSEEK_THINKING_ENABLED=True,
        )
    )
    provider.client = FakeDeepSeekClient(
        output={
            "intent": "create_task",
            "task": {
                "user_id": 1,
                "title": "客户报价",
                "importance": "high",
                "task_type": "work",
                "planned_date": "2026-06-08",
                "planned_time": "09:00:00",
                "estimated_minutes": 120,
                "recurrence_rule": None,
                "source": "user",
                "notes": None,
            },
            "target_title": None,
            "reply": None,
            "confidence": 0.92,
        }
    )

    parsed = await provider.parse_intent(
        user_id=1,
        text="明天上午 9 点做客户报价，比较重要，大概 2 小时。",
        timezone="Asia/Shanghai",
    )

    kwargs = provider.client.chat.completions.last_kwargs
    assert parsed.intent == IntentType.CREATE_TASK
    assert parsed.task is not None
    assert parsed.task.title == "客户报价"
    assert parsed.task.planned_time.hour == 9
    assert kwargs["model"] == "deepseek-v4-pro"
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["reasoning_effort"] == "high"
    assert kwargs["extra_body"] == {"thinking": {"type": "enabled"}}
    assert "json" in kwargs["messages"][0]["content"].lower()
    assert "EXAMPLE JSON OUTPUT" in kwargs["messages"][0]["content"]
    assert "today=" in kwargs["messages"][1]["content"]
    assert "now=" in kwargs["messages"][1]["content"]
    assert "明天10点提醒我去健身哦" in kwargs["messages"][0]["content"]
    assert "memory 可在任何 intent 中填写" in kwargs["messages"][0]["content"]


async def test_deepseek_json_output_review_is_used() -> None:
    provider = DeepSeekProvider(Settings(DEEPSEEK_API_KEY="test-key"))
    provider.client = FakeDeepSeekClient(
        output={
            "completed_task_titles": ["客户报价"],
            "postponed_task_titles": [],
            "cancelled_task_titles": [],
            "tomorrow_tasks": ["整理方案"],
            "completed_summary": "完成了客户报价。",
            "unfinished_summary": None,
            "tomorrow_plan": "继续整理方案。",
            "state_note": "状态还可以。",
        }
    )

    parsed = await provider.parse_review(text="今天完成客户报价，明天整理方案。")

    kwargs = provider.client.chat.completions.last_kwargs
    assert parsed.completed_task_titles == ["客户报价"]
    assert parsed.tomorrow_tasks == ["整理方案"]
    assert kwargs["response_format"] == {"type": "json_object"}
    assert "review_update" in kwargs["messages"][0]["content"]


async def test_deepseek_json_output_list_tasks_intent_is_used() -> None:
    provider = DeepSeekProvider(Settings(DEEPSEEK_API_KEY="test-key"))
    provider.client = FakeDeepSeekClient(
        output={
            "intent": "list_tasks",
            "task": None,
            "target_title": None,
            "reply": None,
            "confidence": 0.9,
        }
    )

    parsed = await provider.parse_intent(
        user_id=1,
        text="目前有哪些任务",
        timezone="Asia/Shanghai",
    )

    kwargs = provider.client.chat.completions.last_kwargs
    assert parsed.intent == IntentType.LIST_TASKS
    assert parsed.task is None
    assert "list_tasks" in kwargs["messages"][0]["content"]


async def test_deepseek_json_output_accepts_null_tasks() -> None:
    provider = DeepSeekProvider(Settings(DEEPSEEK_API_KEY="test-key"))
    provider.client = FakeDeepSeekClient(
        output={
            "intent": "small_talk",
            "task": None,
            "tasks": None,
            "goal": None,
            "goal_progress": None,
            "target_title": None,
            "memory": None,
            "reply": "你好呀",
            "confidence": 0.9,
        }
    )

    parsed = await provider.parse_intent(
        user_id=1,
        text="你好呀",
        timezone="Asia/Shanghai",
    )

    assert parsed.intent == IntentType.SMALL_TALK
    assert parsed.tasks is None
    assert parsed.reply == "你好呀"


async def test_deepseek_json_output_recurring_task_is_used() -> None:
    provider = DeepSeekProvider(Settings(DEEPSEEK_API_KEY="test-key"))
    provider.client = FakeDeepSeekClient(
        output={
            "intent": "create_task",
            "task": {
                "user_id": 1,
                "title": "开始工作",
                "importance": "medium",
                "task_type": "work",
                "planned_date": "2026-06-09",
                "planned_time": "09:00:00",
                "estimated_minutes": None,
                "recurrence_rule": "weekdays",
                "source": "user",
                "notes": None,
            },
            "target_title": None,
            "reply": None,
            "confidence": 0.9,
        }
    )

    parsed = await provider.parse_intent(
        user_id=1,
        text="以后每个工作日早上9点提醒我开始工作",
        timezone="Asia/Shanghai",
    )

    kwargs = provider.client.chat.completions.last_kwargs
    assert parsed.task is not None
    assert parsed.task.recurrence_rule == "weekdays"
    assert "每天早上9点告诉我当天要做的事情" in kwargs["messages"][0]["content"]
    assert "不要把“每天几点提醒/告诉我做什么”写进 memory" in kwargs["messages"][0]["content"]


async def test_deepseek_json_output_multiple_recurring_tasks_is_used() -> None:
    provider = DeepSeekProvider(Settings(DEEPSEEK_API_KEY="test-key"))
    provider.client = FakeDeepSeekClient(
        output={
            "intent": "create_task",
            "task": None,
            "tasks": [
                {
                    "user_id": 1,
                    "title": "查看当天任务和目标",
                    "importance": "medium",
                    "task_type": "work",
                    "planned_date": "2026-06-09",
                    "planned_time": "09:00:00",
                    "estimated_minutes": None,
                    "recurrence_rule": "daily",
                    "action_key": "daily_briefing",
                    "source": "system",
                    "notes": None,
                },
                {
                    "user_id": 1,
                    "title": "当日总结复盘",
                    "importance": "medium",
                    "task_type": "review",
                    "planned_date": "2026-06-09",
                    "planned_time": "23:00:00",
                    "estimated_minutes": None,
                    "recurrence_rule": "daily",
                    "action_key": "daily_review",
                    "source": "system",
                    "notes": None,
                },
            ],
            "goal": None,
            "goal_progress": None,
            "target_title": None,
            "memory": None,
            "reply": None,
            "confidence": 0.9,
        }
    )

    parsed = await provider.parse_intent(
        user_id=1,
        text="每天早上9点告诉我当天要做的事情，还有当前的目标。每天晚上11点总结复盘。",
        timezone="Asia/Shanghai",
    )

    assert parsed.intent == IntentType.CREATE_TASK
    assert parsed.task is None
    assert len(parsed.tasks) == 2
    assert parsed.tasks[0].title == "查看当天任务和目标"
    assert parsed.tasks[0].action_key == "daily_briefing"
    assert parsed.tasks[0].source == "system"
    assert parsed.tasks[1].title == "当日总结复盘"
    assert parsed.tasks[1].action_key == "daily_review"
    assert parsed.tasks[1].source == "system"


async def test_deepseek_json_output_goal_is_used() -> None:
    provider = DeepSeekProvider(Settings(DEEPSEEK_API_KEY="test-key"))
    provider.client = FakeDeepSeekClient(
        output={
            "intent": "create_goal",
            "task": None,
            "goal": {
                "user_id": 1,
                "title": "存钱",
                "metric_name": "存款",
                "unit": "元",
                "direction": "increase",
                "baseline_value": None,
                "current_value": None,
                "target_value": 10000,
                "target_delta": None,
                "start_date": None,
                "deadline": None,
                "notes": None,
            },
            "goal_progress": None,
            "target_title": None,
            "memory": None,
            "reply": None,
            "confidence": 0.9,
        }
    )

    parsed = await provider.parse_intent(
        user_id=1,
        text="我要存 1w 块钱",
        timezone="Asia/Shanghai",
    )

    kwargs = provider.client.chat.completions.last_kwargs
    assert parsed.intent == IntentType.CREATE_GOAL
    assert parsed.goal is not None
    assert parsed.goal.target_value == 10000
    assert "create_goal" in kwargs["messages"][0]["content"]


async def test_deepseek_json_output_goal_progress_is_used() -> None:
    provider = DeepSeekProvider(Settings(DEEPSEEK_API_KEY="test-key"))
    provider.client = FakeDeepSeekClient(
        output={
            "intent": "update_goal_progress",
            "task": None,
            "goal": None,
            "goal_progress": {
                "goal_title": "存钱",
                "kind": "current_value",
                "value": 2300,
                "note": None,
                "raw_text": "我现在存了 2300",
            },
            "target_title": None,
            "memory": None,
            "reply": None,
            "confidence": 0.9,
        }
    )

    parsed = await provider.parse_intent(
        user_id=1,
        text="我现在存了 2300",
        timezone="Asia/Shanghai",
    )

    assert parsed.intent == IntentType.UPDATE_GOAL_PROGRESS
    assert parsed.goal_progress is not None
    assert parsed.goal_progress.value == 2300


async def test_deepseek_prompt_includes_markdown_memory(tmp_path) -> None:
    memory_path = tmp_path / "memory.md"
    memory_path.write_text("## 回复偏好\n\n- 任务名要提炼真正要做的事。", encoding="utf-8")
    provider = DeepSeekProvider(
        Settings(DEEPSEEK_API_KEY="test-key", MEMORY_FILE_PATH=str(memory_path))
    )
    provider.client = FakeDeepSeekClient(
        output={
            "intent": "list_tasks",
            "task": None,
            "target_title": None,
            "memory": None,
            "reply": None,
            "confidence": 0.9,
        }
    )

    await provider.parse_intent(user_id=1, text="当前有哪些待办？", timezone="Asia/Shanghai")

    kwargs = provider.client.chat.completions.last_kwargs
    assert "长期记忆" in kwargs["messages"][0]["content"]
    assert "任务名要提炼真正要做的事" in kwargs["messages"][0]["content"]


class FakeDeepSeekClient:
    def __init__(self, *, output: dict | str) -> None:
        self.chat = FakeChat(output=output)


class FakeChat:
    def __init__(self, *, output: dict | str) -> None:
        self.completions = FakeCompletions(output=output)


class FakeCompletions:
    def __init__(self, *, output: dict | str) -> None:
        self.output = output
        self.last_kwargs = {}

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        output_text = self.output if isinstance(self.output, str) else json.dumps(self.output)
        return FakeResponse(content=output_text)


class FakeResponse:
    def __init__(self, *, content: str) -> None:
        self.choices = [FakeChoice(content=content)]


class FakeChoice:
    def __init__(self, *, content: str) -> None:
        self.message = FakeMessage(content=content)


class FakeMessage:
    def __init__(self, *, content: str) -> None:
        self.content = content
