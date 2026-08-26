"""Geração de resumos curtos, em estilo de post para X, e classificação de
"nível bombástico" (0-10), usando o tier gratuito do Gemini."""

import json
import logging
import time

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_TIMEOUT_MS

logger = logging.getLogger(__name__)

_client = None

MAX_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 5

SYSTEM_INSTRUCTION = """Analisas notícias de futebol sobre o FC Porto, Benfica ou Sporting, \
para publicação como post no X (Twitter), e devolves um objeto JSON com dois campos: \
"summary" e "bombast_score".

Regras para "summary":
- Português de Portugal, direto e informativo, sem clickbait.
- Uma a três frases curtas, no máximo cerca de 280 caracteres.
- Baseia-te só na informação fornecida — nunca inventes factos, números ou declarações.
- Não incluas hashtags nem emojis.
- Não repitas o nome da fonte nem incluas o link — isso é adicionado à parte, depois.

Regras para "bombast_score" (inteiro de 0 a 10, "nível de notícia bombástica"):
- 0-2: rotina (opinião, análise tática, crónica normal de jogo, notas de imprensa).
- 3-5: relevante mas não surpreendente (rumor de mercado, declarações normais, resultado esperado).
- 6-8: notícia forte (transferência avançada/confirmada, declaração polémica, resultado surpreendente).
- 9-10: verdadeira bomba (transferência de topo confirmada de última hora, saída/despedimento de \
treinador, escândalo grave, decisão histórica).
- Usa só a informação fornecida para decidir — não exageres a pontuação por defeito."""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "bombast_score": {"type": "integer", "minimum": 0, "maximum": 10},
    },
    "required": ["summary", "bombast_score"],
}


def is_configured() -> bool:
    return bool(GEMINI_API_KEY)


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY, http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS))
    return _client


def _build_prompt(item) -> str:
    parts = [f"Clube: {item.club}", f"Título original: {item.title}"]
    if item.summary:
        parts.append(f"Resumo/lead original: {item.summary}")
    if item.body:
        parts.append(f"Texto do artigo (excerto): {item.body[:2000]}")
    if item.is_paywalled and not item.body:
        parts.append("(Nota: artigo é pago — só está disponível o título e o resumo acima.)")
    return "\n".join(parts)


def _generate(item) -> dict | None:
    client = _get_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=_build_prompt(item),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            max_output_tokens=400,
            temperature=0.3,
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
        ),
    )
    data = json.loads(response.text)
    summary = (data.get("summary") or "").strip()
    score = data.get("bombast_score")
    if not summary or not isinstance(score, int):
        logger.warning("Resposta do Gemini incompleta para: %s — %r", item.title, data)
        return None
    return {"summary": summary, "bombast_score": max(0, min(10, score))}


def summarize(item) -> dict | None:
    """Devolve {"summary": str, "bombast_score": int} ou None se falhar/não configurado.
    Tenta até MAX_ATTEMPTS vezes — os timeouts do Gemini (504) costumam ser passageiros
    e resolvem-se numa segunda tentativa."""
    if not is_configured():
        return None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return _generate(item)
        except Exception:
            if attempt < MAX_ATTEMPTS:
                logger.warning(
                    "Falha ao gerar resumo via Gemini para: %s (tentativa %d/%d) — a repetir",
                    item.title,
                    attempt,
                    MAX_ATTEMPTS,
                )
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                logger.exception("Falha ao gerar resumo via Gemini para: %s", item.title)
    return None
