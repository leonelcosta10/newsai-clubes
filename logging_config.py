import logging
import sys
from logging.handlers import RotatingFileHandler

from config import LOG_DIR


def setup_logging(level=logging.INFO):
    root = logging.getLogger()
    if root.handlers:
        return root  # já configurado (evita handlers duplicados em reimportações)

    root.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # quando corre via pythonw.exe (sem consola, ex: tarefa agendada) sys.stdout/stderr
    # podem não existir — só se adiciona o handler de consola se houver um stream real
    if sys.stderr is not None:
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        root.addHandler(console)

    file_handler = RotatingFileHandler(
        LOG_DIR / "newsai.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # aviso benigno e repetitivo do SDK do Gemini (recomenda usar Chat em vez de
    # generate_content direto) — não é acionável neste caso de uso, só ruído
    logging.getLogger("google_genai.models").setLevel(logging.ERROR)

    return root
