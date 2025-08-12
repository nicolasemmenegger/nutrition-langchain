from ..config import settings
from typing import Optional

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

_client = None

def has_openai() -> bool:
    return settings.openai_api_key is not None and OpenAI is not None

def client() -> Optional["OpenAI"]:
    global _client
    if not has_openai():
        return None
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client
