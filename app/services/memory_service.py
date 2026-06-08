from datetime import UTC, datetime
from pathlib import Path

from app.config.settings import Settings

DEFAULT_MEMORY = """# 用户记忆

## 用户画像

## 回复偏好

## 提醒偏好

## 固定节奏

## 行为观察

## 用户补充记忆
"""


class MemoryService:
    def __init__(self, settings: Settings) -> None:
        self.path = Path(settings.memory_file_path)

    def read(self) -> str:
        if not self.path.exists():
            return ""
        return self.path.read_text(encoding="utf-8").strip()

    def remember(self, text: str, *, now: datetime | None = None) -> bool:
        memory = text.strip()
        if not memory:
            return False
        if memory in self.read():
            return False
        self._ensure_file()
        timestamp = (now or datetime.now(UTC)).date().isoformat()
        with self.path.open("a", encoding="utf-8") as file:
            file.write(f"\n- {timestamp}：{memory}\n")
        return True

    def _ensure_file(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(DEFAULT_MEMORY, encoding="utf-8")
