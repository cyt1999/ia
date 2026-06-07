from app.main import healthz


def test_healthz() -> None:
    assert healthz() == {"status": "ok"}
