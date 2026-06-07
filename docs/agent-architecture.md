# Agent Architecture Notes

Date: 2026-06-07

## Current Direction

This project uses OpenAI through an `LLMProvider` abstraction. The first production path is:

```text
Feishu message
-> InteractionRouter
-> OpenAI Responses API structured output
-> TaskService / ReviewService
-> SQLite
-> NotificationChannel
-> Feishu reply
```

The model helps understand the user's Chinese message and produce typed output. The application still owns identity, authorization, database writes, transactions, reminder state, and Feishu delivery.

## Responses API

The Responses API is the model runtime interface we use to call OpenAI. In this project it is responsible for:

- Natural-language understanding.
- Structured JSON output for task intent parsing.
- Structured JSON output for evening review parsing.
- Later, tool calls such as `list_tasks`, `create_task`, `postpone_task`, and `add_review`.

It is not the business workflow engine. The API can request tool calls, but the application must still execute tools, validate arguments, handle failures, and persist state.

Official references:

- Responses API guide: https://developers.openai.com/api/docs/guides/responses
- Function calling and tools: https://developers.openai.com/api/docs/guides/function-calling

## Agent Framework

An agent framework is an application orchestration layer. It usually wraps model calls, tool execution, retries, tracing, handoffs, and long-running state management.

In this project, an agent framework is not required for the MVP because the first interaction flow is short and explicit:

```text
receive one message
-> parse intent
-> execute one service operation
-> send one reply
```

The project should consider a framework later if the assistant needs:

- Multi-step autonomous planning.
- Multiple agents with different responsibilities.
- Tool-call loops that are hard to keep explicit.
- Human approval gates.
- Rich tracing and debugging for model/tool decisions.
- Integration with many tools such as calendar, documents, email, browser, and task systems.

Official reference:

- Agents SDK guide: https://developers.openai.com/api/docs/guides/agents

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

If our code controls these steps, our application is doing the orchestration. If an agent framework controls the loop between model decisions and tool execution, the framework is doing more of the orchestration.

## What "State" Means

State is the information the assistant must remember to behave correctly. There are two important categories.

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
- Any tool calls requested by the model.
- Tool outputs.
- Whether the assistant is waiting for user clarification.
- Whether an operation already succeeded.

SQLite is the source of truth for business state. The model context is only a temporary input to a decision.

## Current Implementation Choice

The current implementation uses Responses API structured output first. This gives us a controlled and testable path:

```text
OpenAI returns ParsedIntent
-> InteractionRouter chooses the service method
-> service layer validates and writes SQLite
```

This is safer than letting the model directly "own" database behavior. Even after tools are added, the tool functions should call `TaskService`, `ReviewService`, and `ReminderService` instead of writing database rows directly.

## Tool Roadmap

The next step is to expose a small tool set behind the OpenAI provider while keeping service-layer validation:

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
- If OpenAI is unavailable, the assistant replies with `当前小助手失联了，请稍后再试。`

## Migration Path

The architecture should remain replaceable:

```text
LLMProvider
  OpenAIProvider now: Responses API structured output
  OpenAIProvider next: Responses API tools
  Future option: Agents SDK or another agent framework
```

Keeping `LLMProvider`, services, and notification channels separate means the project can adopt a heavier framework later without rewriting Feishu, SQLite, or reminder logic.
