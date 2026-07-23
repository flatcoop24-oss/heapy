import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Optional


class LLMError(RuntimeError):
    pass


class GeminiFlashLiteClient:
    """Minimal Gemini generateContent REST adapter with JSON responses."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        opener: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.base_url = (base_url or os.getenv("GEMINI_API_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")).rstrip("/")
        self.timeout_seconds = timeout_seconds or float(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))
        self._opener = opener or urllib.request.urlopen

    def generate_json(self, system_instruction: str, prompt: str) -> Dict[str, Any]:
        if not self.api_key:
            raise LLMError("Gemini API is not configured")
        model = urllib.parse.quote(self.model, safe="-._")
        endpoint = "%s/models/%s:generateContent" % (self.base_url, model)
        payload = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1600,
                "responseMimeType": "application/json",
            },
        }
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                raw_response = response.read()
        except urllib.error.HTTPError as exc:
            raise LLMError("Gemini request was rejected (HTTP %s)" % exc.code) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise LLMError("Gemini API is unavailable") from exc
        try:
            response_payload = json.loads(raw_response.decode("utf-8"))
            parts = response_payload["candidates"][0]["content"]["parts"]
            text = "".join(str(part.get("text", "")) for part in parts).strip()
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("Gemini returned an invalid response") from exc
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError("Gemini did not return valid JSON") from exc
        if not isinstance(value, dict) or not str(value.get("answer", "")).strip():
            raise LLMError("Gemini response does not satisfy the answer contract")
        return value

