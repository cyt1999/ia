# Debugging Guide

Date: 2026-06-07

## Goal

Use a layered debugging path. Verify local behavior first, then OpenAI, then Feishu.

The recommended order is:

```text
tests
-> health check
-> database migration
-> no-key assistant behavior
-> OpenAI structured parsing
-> Feishu long connection
-> real Feishu message
```

This avoids mixing model, database, and Feishu transport problems in one test.

## 1. Run Local Checks

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .
UV_CACHE_DIR=/tmp/uv-cache uv run pytest
```

Expected result:

```text
All checks passed
tests passed
```

## 2. Apply Database Migrations

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head
```

SQLite data is stored under `./data` by default.

## 3. Start The Service

For health-only startup, use test mode to avoid opening the Feishu long connection:

```bash
APP_ENV=test UV_CACHE_DIR=/tmp/uv-cache uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/healthz
```

Expected result:

```json
{"status":"ok"}
```

## 4. Verify No-Key Behavior

If `OPENAI_API_KEY` is empty, any normal user message should not be parsed by fallback rules.

Expected assistant reply:

```text
当前小助手失联了，请稍后再试。
```

Expected database behavior:

- No task is created.
- No task is completed.
- No task is postponed.
- The inbound message can still be recorded as processed.

This confirms the app is not silently using local hard-coded parsing.

## 5. Configure OpenAI

Set the following in `.env`:

```bash
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
```

Do not commit `.env`.

The current OpenAI provider uses Responses API structured output with JSON Schema:

- `parsed_intent` for normal user messages.
- `review_update` for evening reviews.

If OpenAI is unavailable, times out, or returns invalid output, the assistant should still reply:

```text
当前小助手失联了，请稍后再试。
```

## 6. Verify Feishu Long Connection

The default mode is:

```bash
FEISHU_EVENT_MODE=long_connection
```

In this mode, the app uses Feishu SDK WebSocket events and does not need a public event subscription callback URL.

Start the app, then send a private message to the bot in Feishu.

Useful test messages:

```text
你好
明天上午 9 点做客户报价，比较重要，大概 2 小时。
明天要去健身
客户报价做完了
```

Expected behavior with a valid OpenAI key:

- Task creation messages should create a task and reply with a structured confirmation.
- Completion messages should update the most relevant task if it can be matched.
- Ambiguous messages should get a natural clarification or small-talk reply from the model.

Expected behavior without a valid OpenAI key:

- All normal user messages should return the unified assistant-offline reply.

## 7. Check Feishu Endpoint Connectivity

If long connection does not start, test Feishu endpoint connectivity from the same runtime environment:

```bash
curl -v --connect-timeout 15 \
  -H "Content-Type: application/json" \
  -H "locale: zh" \
  -d '{"AppID":"<app_id>","AppSecret":"<app_secret>"}' \
  https://open.feishu.cn/callback/ws/endpoint
```

Expected result:

```text
HTTP/2 200
{"code":0,...,"URL":"wss://..."}
```

If this works in the host shell but not inside the service process or container, the problem is likely runtime network configuration rather than Feishu app credentials.

## 8. Debugging Boundaries

Common boundaries:

- Feishu SDK connection problem: no inbound event reaches `FeishuLongConnectionRunner`.
- Authorization problem: inbound event is ignored because sender/chat does not match allowed IDs.
- OpenAI problem: inbound event is processed but replies with the assistant-offline message.
- Parsing problem: OpenAI returns JSON that does not validate against the schema.
- Service problem: parsed intent is valid but task/review state changes are wrong.
- Channel rendering problem: service result is correct but Feishu message rendering is wrong.

Keep logs and tests aligned to these boundaries.

## 9. Next Manual Test

After adding a real `OPENAI_API_KEY`, run the app and send:

```text
明天上午 9 点做客户报价，比较重要，大概 2 小时。
```

Expected reply:

```text
已安排

我已安排「客户报价」。
日期：2026-06-08
时间：09:00
预计：120 分钟
```

The exact natural-language wording can vary later, but the task fields should be stable.
