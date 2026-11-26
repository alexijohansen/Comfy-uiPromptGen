"""Minimal Ollama HTTP client (standard library only)."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

DEFAULT_URL = "http://localhost:11434"
MODEL_LIST_TIMEOUT = 1.0  # seconds; ComfyUI waits for this when it builds the node list
MODEL_LIST_CACHE_SECONDS = 10.0
GENERATE_TIMEOUT = 600

THINK_RE = re.compile(r"<think>.*?</think>|<\|channel>.*?<channel\|>", re.DOTALL)
THINK_END_MARKERS = ("</think>", "<channel|>")

_model_cache: dict[str, tuple[float, list[str]]] = {}


class OllamaError(RuntimeError):
    """Ollama answered with an error, or could not be reached. code is the HTTP status, if any."""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


def strip_thinking(text: str) -> str:
    """Remove reasoning sections some models put before the answer."""
    text = THINK_RE.sub("", text)
    for marker in THINK_END_MARKERS:  # end marker without a matching start
        if marker in text:
            text = text.rsplit(marker, 1)[1]
    return text.strip()


def list_models(url: str = DEFAULT_URL) -> list[str]:
    """Installed model names, or [] if Ollama can't be reached. Cached for a few seconds."""
    now = time.monotonic()
    cached = _model_cache.get(url)
    if cached and now - cached[0] < MODEL_LIST_CACHE_SECONDS:
        return cached[1]
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/tags", timeout=MODEL_LIST_TIMEOUT) as r:
            models = sorted(m["name"] for m in json.load(r).get("models", []))
    except (OSError, ValueError):
        models = []
    _model_cache[url] = (now, models)
    return models


def _post_json(url: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _request(endpoint: str, body: dict, timeout: float) -> dict:
    """POST body; turn HTTP and connection errors into OllamaError."""
    try:
        return _post_json(endpoint, body, timeout)
    except urllib.error.HTTPError as e:
        raise OllamaError(f"Ollama error {e.code}: {e.read().decode('utf-8', 'replace')}", e.code) from e
    except urllib.error.URLError as e:
        raise OllamaError(f"Could not reach Ollama at {endpoint}: {e.reason}") from e


def generate(url: str, model: str, instruction: str, prompt: str, seed: int,
             temperature: float, thinking: bool = False, timeout: float = GENERATE_TIMEOUT) -> str:
    """Rewrite prompt with model, using instruction as the system prompt. Returns the cleaned reply.

    'think' is always sent (false by default) because some models think unless told not to.
    Models or Ollama versions that reject the flag are retried once without it.
    """
    endpoint = url.rstrip("/") + "/api/generate"
    body = {
        "model": model,
        "system": instruction,
        "prompt": prompt,
        "stream": False,
        "think": bool(thinking),
        "options": {"seed": seed % (2**31), "temperature": temperature},
    }
    try:
        data = _request(endpoint, body, timeout)
    except OllamaError as e:
        if e.code != 400 or "think" not in str(e).lower():
            raise
        del body["think"]
        data = _request(endpoint, body, timeout)
    return strip_thinking(data.get("response", ""))
