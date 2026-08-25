"""Login único e interativo do Telethon — corre isto TU MESMO num terminal teu.

Vai pedir o teu número de telemóvel, depois o código que o Telegram te envia
(por mensagem, no próprio Telegram) e, se tiveres verificação em dois passos,
a password. Depois disto, fica guardado um ficheiro de sessão em data/, e as
próximas execuções (incluindo a tarefa agendada) não voltam a pedir nada.

Uso:
    python telethon_login.py
"""

from telethon.sync import TelegramClient

from config import TELETHON_API_HASH, TELETHON_API_ID, TELETHON_CHANNEL_USERNAME, TELETHON_SESSION_PATH

if __name__ == "__main__":
    if not TELETHON_API_ID or not TELETHON_API_HASH:
        raise SystemExit("TELETHON_API_ID / TELETHON_API_HASH em falta no .env")

    with TelegramClient(TELETHON_SESSION_PATH, int(TELETHON_API_ID), TELETHON_API_HASH) as client:
        me = client.get_me()
        print(f"Sessão criada com sucesso, autenticado como: {me.first_name} (@{me.username})")

        try:
            entity = client.get_entity(TELETHON_CHANNEL_USERNAME)
            print(f"Canal encontrado: {entity.title} (@{TELETHON_CHANNEL_USERNAME})")
        except Exception as e:
            print(f"Aviso: não consegui aceder a @{TELETHON_CHANNEL_USERNAME}: {e}")
