"""Lista de destinatários do Telegram (quem recebe os digests) + acompanhamento
de que mensagens do bot já foram vistas, para a deteção automática de novos
destinatários não reprocessar sempre as mesmas."""

import json

from config import DATA_DIR, TELEGRAM_CHAT_ID

RECIPIENTS_PATH = DATA_DIR / "recipients.json"
OFFSET_PATH = DATA_DIR / "telegram_update_offset.txt"


def load_recipients() -> list[dict]:
    if not RECIPIENTS_PATH.exists():
        seed = [{"chat_id": TELEGRAM_CHAT_ID, "name": "dono"}] if TELEGRAM_CHAT_ID else []
        save_recipients(seed)
        return seed
    try:
        with open(RECIPIENTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_recipients(recipients: list[dict]) -> None:
    with open(RECIPIENTS_PATH, "w", encoding="utf-8") as f:
        json.dump(recipients, f, indent=2, ensure_ascii=False)


def add_recipient(chat_id, name: str | None = None) -> None:
    recipients = load_recipients()
    if any(str(r.get("chat_id")) == str(chat_id) for r in recipients):
        return
    recipients.append({"chat_id": chat_id, "name": name or ""})
    save_recipients(recipients)


def load_offset() -> int:
    if OFFSET_PATH.exists():
        try:
            return int(OFFSET_PATH.read_text().strip() or 0)
        except ValueError:
            return 0
    return 0


def save_offset(offset: int) -> None:
    OFFSET_PATH.write_text(str(offset), encoding="utf-8")
