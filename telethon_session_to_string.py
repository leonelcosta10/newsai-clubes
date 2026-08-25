"""Converte a sessão local do Telethon (ficheiro) numa StringSession e guarda-a
diretamente como secret do GitHub — a string nunca é impressa no terminal.

Uso:
    python telethon_session_to_string.py <owner/repo>
"""

import subprocess
import sys

from telethon.sessions import StringSession
from telethon.sync import TelegramClient

from config import TELETHON_API_HASH, TELETHON_API_ID, TELETHON_SESSION_PATH

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python telethon_session_to_string.py <owner/repo>")
    repo = sys.argv[1]

    with TelegramClient(TELETHON_SESSION_PATH, int(TELETHON_API_ID), TELETHON_API_HASH) as client:
        new_session = StringSession()
        new_session.set_dc(client.session.dc_id, client.session.server_address, client.session.port)
        new_session.auth_key = client.session.auth_key
        string_session = new_session.save()

    result = subprocess.run(
        ["gh", "secret", "set", "TELETHON_STRING_SESSION", "--repo", repo, "--body", string_session],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("Secret TELETHON_STRING_SESSION criado com sucesso no repositório", repo)
    else:
        print("Falha ao criar o secret:", result.stderr)
