from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.channels.feishu.crypto import FeishuCrypto, FeishuCryptoError
from app.channels.feishu.events import normalize_event
from app.config.settings import Settings, get_settings
from app.db.session import get_db
from app.services.interaction_router import InteractionRouter

router = APIRouter()
SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[Session, Depends(get_db)]


@router.post("/webhooks/feishu")
async def feishu_webhook(
    request: Request,
    settings: SettingsDep,
    db: DbDep,
) -> dict[str, str]:
    body = await request.json()

    if body.get("type") == "url_verification":
        crypto = FeishuCrypto(settings.feishu_encrypt_key, settings.feishu_verification_token)
        crypto.verify_token(body.get("token"))
        return {"challenge": body.get("challenge", "")}

    try:
        crypto = FeishuCrypto(settings.feishu_encrypt_key, settings.feishu_verification_token)
        if "encrypt" in body:
            body = crypto.decrypt_event(body["encrypt"])
        token = body.get("token") or body.get("header", {}).get("token")
        if token:
            crypto.verify_token(token)
    except FeishuCryptoError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    interaction = normalize_event(body)
    if interaction is None:
        return {"status": "ignored"}

    router_service = InteractionRouter(db=db, settings=settings)
    await router_service.handle(interaction)
    return {"status": "ok"}
