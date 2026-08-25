"""Preferências do utilizador (clubes e fontes ativas), persistidas em settings.json.

Separado de config.py de propósito: config.py trata de segredos/constantes fixas
vindas do .env; isto aqui é o que o painel de controlo (control_panel.py) lê e
escreve em tempo real, sem precisar de mexer em código.
"""

import json
from pathlib import Path

SETTINGS_PATH = Path(__file__).resolve().parent / "settings.json"

ALL_CLUBS = ["fc_porto", "benfica", "sporting"]
ALL_SOURCES = ["ojogo", "abola", "record", "dimarzio", "fabrizio_telegram", "athletic", "marca", "lequipe"]

DEFAULTS = {
    "clubs": {"fc_porto": True, "benfica": False, "sporting": False},
    "sources": {name: True for name in ALL_SOURCES},
}


def load() -> dict:
    if not SETTINGS_PATH.exists():
        save(DEFAULTS)
        return json.loads(json.dumps(DEFAULTS))  # cópia independente

    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return json.loads(json.dumps(DEFAULTS))

    # garante que chaves novas (ex: uma fonte adicionada mais tarde) aparecem
    # mesmo que o settings.json no disco seja de uma versão anterior
    return {
        "clubs": {**DEFAULTS["clubs"], **data.get("clubs", {})},
        "sources": {**DEFAULTS["sources"], **data.get("sources", {})},
    }


def save(settings: dict) -> None:
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def active_clubs() -> list[str]:
    settings = load()
    return [club for club in ALL_CLUBS if settings["clubs"].get(club)]


def active_sources() -> list[str]:
    settings = load()
    return [source for source in ALL_SOURCES if settings["sources"].get(source)]
