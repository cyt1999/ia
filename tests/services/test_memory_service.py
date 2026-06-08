from datetime import UTC, datetime

from app.config.settings import Settings
from app.services.memory_service import MemoryService


def test_memory_service_appends_markdown_entry(tmp_path) -> None:
    path = tmp_path / "memory.md"
    service = MemoryService(Settings(MEMORY_FILE_PATH=str(path)))

    service.remember("任务名要提炼真正要做的事。", now=datetime(2026, 6, 8, tzinfo=UTC))

    content = path.read_text(encoding="utf-8")
    assert "# 用户记忆" in content
    assert "- 2026-06-08：任务名要提炼真正要做的事。" in content


def test_memory_service_skips_duplicate_entry(tmp_path) -> None:
    path = tmp_path / "memory.md"
    service = MemoryService(Settings(MEMORY_FILE_PATH=str(path)))

    service.remember("任务名要提炼真正要做的事。", now=datetime(2026, 6, 8, tzinfo=UTC))
    service.remember("任务名要提炼真正要做的事。", now=datetime(2026, 6, 9, tzinfo=UTC))

    content = path.read_text(encoding="utf-8")
    assert content.count("任务名要提炼真正要做的事。") == 1


def test_missing_memory_file_reads_empty(tmp_path) -> None:
    service = MemoryService(Settings(MEMORY_FILE_PATH=str(tmp_path / "missing.md")))

    assert service.read() == ""
