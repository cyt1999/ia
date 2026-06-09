from enum import StrEnum


class Importance(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class TaskType(StrEnum):
    WORK = "work"
    LIFE = "life"
    REST = "rest"
    SLEEP = "sleep"
    REVIEW = "review"
    TEMP_REMINDER = "temp_reminder"


class TaskSource(StrEnum):
    USER = "user"
    REVIEW = "review"
    CARRY_OVER = "carry_over"
    SYSTEM = "system"


class TaskActionKey(StrEnum):
    DAILY_BRIEFING = "daily_briefing"
    DAILY_REVIEW = "daily_review"


class RecurrenceRule(StrEnum):
    DAILY = "daily"
    WEEKDAYS = "weekdays"


class GoalDirection(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"


class GoalStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class GoalProgressKind(StrEnum):
    CURRENT_VALUE = "current_value"
    DELTA = "delta"


class ReminderStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    ACKED = "acked"
    SNOOZED = "snoozed"
    EXHAUSTED = "exhausted"
    CANCELLED = "cancelled"


class ReminderKind(StrEnum):
    WORK_START = "work_start"
    REST_START = "rest_start"
    WORK_END = "work_end"
    REVIEW = "review"
    SLEEP_PREP = "sleep_prep"
    SLEEP = "sleep"
    TASK = "task"


class ChannelType(StrEnum):
    FEISHU = "feishu"


class NotificationStatus(StrEnum):
    SENT = "sent"
    FAILED = "failed"


class InboundStatus(StrEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    IGNORED = "ignored"
    FAILED = "failed"
