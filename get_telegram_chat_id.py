"""Utilitário único: descobre o teu chat_id depois de enviares uma mensagem ao bot.

Uso:
  1. Cria o bot com o @BotFather e coloca o token em TELEGRAM_BOT_TOKEN no .env
  2. Abre o chat com o bot no Telegram e envia-lhe qualquer mensagem
  3. Corre este script — ele mostra o(s) chat_id(s) encontrados
  4. Copia o chat_id certo para TELEGRAM_CHAT_ID no .env
"""

from notifier.telegram_bot import get_recent_chat_ids

if __name__ == "__main__":
    chats = get_recent_chat_ids()
    if not chats:
        print("Nenhuma mensagem encontrada. Confirma que:")
        print("  - TELEGRAM_BOT_TOKEN está correto no .env")
        print("  - já enviaste pelo menos uma mensagem ao bot no Telegram")
        raise SystemExit(1)

    print("Chats encontrados:\n")
    for chat in chats:
        name = chat.get("username") or chat.get("first_name") or chat.get("title")
        print(f"  chat_id={chat.get('id')}  tipo={chat.get('type')}  nome={name}")
    print("\nCopia o chat_id correspondente a ti para TELEGRAM_CHAT_ID no .env")
