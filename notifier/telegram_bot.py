"""Envio do resumo das notícias para os chats do Telegram inscritos, via Bot API."""

import html
import logging
import time

import requests

from config import TELEGRAM_BOT_TOKEN
from notifier import recipients as recipients_store

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}/{method}"
MAX_MESSAGE_LENGTH = 4096
SEND_DELAY_SECONDS = 1  # cortesia para não sermos rate-limited pela API do Telegram

WELCOME_MESSAGE = (
    "✅ Ficaste inscrito para receber notícias do FC Porto, Benfica e Sporting via NewsAI. "
    "Vais receber um resumo sempre que houver novidades."
)


def is_configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN)


def _post(method: str, payload: dict) -> dict | None:
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN não configurado — não é possível chamar %s", method)
        return None
    url = API_BASE.format(token=TELEGRAM_BOT_TOKEN, method=method)
    try:
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()
        if not data.get("ok"):
            logger.error("Telegram API devolveu erro em %s: %s", method, data)
            return None
        return data.get("result")
    except Exception:
        logger.exception("Falha ao chamar o método %s da Telegram Bot API", method)
        return None


def send_message(text: str, chat_id) -> bool:
    if not chat_id:
        logger.error("chat_id vazio — não é possível enviar mensagem")
        return False
    result = _post(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
    )
    return result is not None


def get_recent_chat_ids() -> list[dict]:
    """Usa getUpdates para descobrir chat_ids de quem já falou com o bot.
    Útil para a configuração inicial, antes de teres o TELEGRAM_CHAT_ID."""
    result = _post("getUpdates", {})
    if result is None:
        return []
    chats = {}
    for update in result:
        message = update.get("message") or update.get("channel_post")
        if not message:
            continue
        chat = message.get("chat", {})
        chats[chat.get("id")] = chat
    return list(chats.values())


def discover_new_recipients() -> list[dict]:
    """Verifica se alguém novo mandou mensagem ao bot desde a última vez e,
    se sim, adiciona-o automaticamente à lista de destinatários e envia-lhe
    uma confirmação. Devolve os novos destinatários encontrados nesta chamada."""
    offset = recipients_store.load_offset()
    result = _post("getUpdates", {"offset": offset, "timeout": 0})
    if not result:
        return []

    known = {str(r.get("chat_id")) for r in recipients_store.load_recipients()}
    newly_added = []
    max_update_id = offset - 1

    for update in result:
        max_update_id = max(max_update_id, update.get("update_id", max_update_id))
        message = update.get("message")
        if not message:
            continue
        chat = message.get("chat", {})
        if chat.get("type") != "private":
            continue  # só inscreve conversas privadas com o bot, não grupos/canais
        chat_id = chat.get("id")
        if chat_id is None or str(chat_id) in known:
            continue

        name = chat.get("first_name") or chat.get("username") or str(chat_id)
        recipients_store.add_recipient(chat_id, name)
        known.add(str(chat_id))
        send_message(WELCOME_MESSAGE, chat_id)
        newly_added.append({"chat_id": chat_id, "name": name})

    recipients_store.save_offset(max_update_id + 1)
    return newly_added


def _impact_tag(score: int) -> str | None:
    """Etiqueta editorial (estilo agência de notícias) a partir do nível 0-10.
    10 é caso especial ("BOMBA"); rotina (0-2) não leva etiqueta nenhuma."""
    if score >= 10:
        return "BOMBA"
    if score >= 9:
        return "URGENTE"
    if score >= 6:
        return "DESTAQUE"
    if score >= 3:
        return "RELEVANTE"
    return None


def _format_item(item) -> str:
    title = html.escape(item.title)
    url = html.escape(item.url, quote=True)
    tag = _impact_tag(item.bombast_score) if item.bombast_score is not None else None
    prefix = f"[{tag}] " if tag else ""
    lines = [f'▪️ <b>{prefix}<a href="{url}">{title}</a></b>']
    text = item.llm_summary or item.summary
    if text:
        lines.append(html.escape(text))
    premium_tag = "🔒 Premium" if item.is_paywalled else ""
    source_label = {
        "ojogo": "O Jogo",
        "abola": "A Bola",
        "record": "Record",
        "dimarzio": "Gianluca Di Marzio",
        "fabrizio_telegram": "Fabrizio Romano",
        "athletic": "The Athletic (David Ornstein)",
        "marca": "Marca",
        "lequipe": "L'Équipe",
    }.get(item.source, item.source)
    footer = f"Fonte: {source_label}"
    if premium_tag:
        footer += f" · {premium_tag}"
    lines.append(f"<i>{footer}</i>")
    return "\n".join(lines)


def _chunk_messages(header: str, item_blocks: list[str]) -> list[str]:
    """Agrupa blocos de notícia em mensagens que não excedam o limite do Telegram."""
    chunks = []
    current = header
    for block in item_blocks:
        candidate = current + "\n\n" + block
        if len(candidate) > MAX_MESSAGE_LENGTH:
            chunks.append(current)
            current = header + " (cont.)\n\n" + block
        else:
            current = candidate
    chunks.append(current)
    return chunks


def send_club_digest(club_display_name: str, items: list) -> int:
    """Envia as notícias de um clube, a todos os destinatários inscritos, agrupadas
    numa ou mais mensagens por destinatário. Devolve quantas mensagens foram enviadas."""
    if not items:
        return 0
    if not is_configured():
        logger.warning("Telegram não configurado (TELEGRAM_BOT_TOKEN em falta) — a saltar envio")
        return 0

    active_recipients = [r for r in recipients_store.load_recipients() if r.get("chat_id")]
    if not active_recipients:
        logger.warning("Sem destinatários inscritos — a saltar envio")
        return 0

    header = f"📰 <b>{html.escape(club_display_name)}</b>"
    blocks = [_format_item(item) for item in items]
    messages = _chunk_messages(header, blocks)

    sent = 0
    for recipient in active_recipients:
        for msg in messages:
            if send_message(msg, recipient["chat_id"]):
                sent += 1
            time.sleep(SEND_DELAY_SECONDS)
    return sent
