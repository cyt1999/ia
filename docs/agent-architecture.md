# Agent Architecture Notes

Date: 2026-06-07

## Current Direction

This project uses DeepSeek through the OpenAI Python SDK compatibility layer. The first production path is:

```text
Feishu message
-> InteractionRouter
-> DeepSeek chat.completions JSON Output
-> TaskService / ReviewService
-> SQLite
-> NotificationChannel
-> Feishu reply
```

The model helps understand the user's Chinese message and produce typed JSON. The application still owns identity, authorization, database writes, transactions, reminder state, and Feishu delivery.

## DeepSeek API Shape

DeepSeek is used through:

```python
AsyncOpenAI(
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url,
)
```

Current defaults:

```text
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_REASONING_EFFORT=high
DEEPSEEK_THINKING_ENABLED=true
```

Important distinction: this project does not use OpenAI Responses API. DeepSeek's documented JSON Output, Tool Calls, multi-round chat, and thinking mode all use the Chat Completions style API.

Official references:

- JSON Output: https://api-docs.deepseek.com/zh-cn/guides/json_mode
- Tool Calls: https://api-docs.deepseek.com/zh-cn/guides/tool_calls
- Multi-round chat: https://api-docs.deepseek.com/zh-cn/guides/multi_round_chat
- Thinking mode: https://api-docs.deepseek.com/zh-cn/guides/thinking_mode

## JSON Output

For structured parsing, the provider calls:

```python
client.chat.completions.create(
    model="deepseek-v4-pro",
    messages=[...],
    response_format={"type": "json_object"},
    reasoning_effort="high",
    extra_body={"thinking": {"type": "enabled"}},
)
```

DeepSeek JSON Output requires the prompt to mention JSON and include an example JSON output. The application still validates the returned JSON with Pydantic models:

- `ParsedIntent` for normal user messages.
- `ReviewParsedUpdate` for evening reviews.

If DeepSeek is unavailable, returns empty content, or returns invalid JSON, the assistant replies:

```text
当前小助手失联了，请稍后再试。
```

The application must not silently fall back to local hard-coded task parsing.

## What "Orchestration" Means

Orchestration means deciding and executing the next step in a multi-step process.

Example user request:

```text
明天上午帮我安排客户报价，如果今天还有没做完的报价相关任务，就顺便推迟到明天。
```

This can require:

```text
1. Parse the request.
2. List unfinished tasks.
3. Match quote-related tasks.
4. Postpone old tasks.
5. Create the new task.
6. Summarize what changed.
```

If our code controls these steps, our application is doing the orchestration. If a model/tool loop controls the sequence, the agent layer is doing more of the orchestration.

## What "State" Means

State is the information the assistant must remember to behave correctly.

Business state:

- Current user identity.
- Tasks and task statuses.
- Reminder confirmation status.
- Review records.
- Missed reminder attempts.
- Quiet-time rules.

Conversation and execution state:

- The current user message.
- The model's parsed intent.
- Tool calls requested by the model.
- Tool outputs.
- Whether the assistant is waiting for user clarification.
- Whether an operation already succeeded.

SQLite is the source of truth for business state. DeepSeek chat completions are stateless, so multi-round context must be assembled and sent by the application when needed.

## Current Implementation Choice

The current implementation uses DeepSeek JSON Output first. This gives us a controlled and testable path:

```text
DeepSeek returns ParsedIntent JSON
-> InteractionRouter chooses the service method
-> service layer validates and writes SQLite
```

This is safer than letting the model directly control database behavior. Even after Tool Calls are added, the tool functions should call `TaskService`, `ReviewService`, and `ReminderService` instead of writing database rows directly.

## Tool Roadmap

The next step is to expose a small DeepSeek Tool Calls set while keeping service-layer validation:

- `list_tasks`: read current or planned tasks.
- `create_task`: create a task through `TaskService`.
- `complete_task`: mark a task completed through `TaskService`.
- `postpone_task`: mark a task postponed through `TaskService`.
- `cancel_task`: cancel a task through `TaskService`.
- `add_review`: save structured review information through `ReviewService`.

Rules:

- Tools must be typed.
- Tools must not bypass authz or service-layer validation.
- Tools must return compact, model-readable results.
- Tool failures should not create partial task changes.
- If DeepSeek is unavailable, the assistant replies with `当前小助手失联了，请稍后再试。`

DeepSeek Tool Calls are model decisions only. The model returns a tool call; our Python code executes the function and sends the tool result back to the model.

## Future Agent Framework

An agent framework is not required for the MVP because the first interaction flow is short and explicit:

```text
receive one message
-> parse intent
-> execute one service operation
-> send one reply
```

Consider a framework later if the assistant needs:

- Multi-step autonomous planning.
- Multiple agents with different responsibilities.
- Tool-call loops that are hard to keep explicit.
- Human approval gates.
- Rich tracing and debugging for model/tool decisions.
- Integration with many tools such as calendar, documents, email, browser, and task systems.

The architecture should remain replaceable:

```text
LLMProvider
  now: DeepSeek JSON Output
  next: DeepSeek Tool Calls
  future option: a heavier agent framework
```

Keeping `LLMProvider`, services, and notification channels separate means the project can adopt a heavier framework later without rewriting Feishu, SQLite, or reminder logic.
