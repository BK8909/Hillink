"""Repository-owned key loader; the key stays in the user's private config.

No secret is bundled, returned in diagnostics, or logged. The public credential
facade requires explicit external-call opt-in before load/authentication.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

KEY_FILE = Path.home() / ".config" / "hillink" / "openai.env"


class OpenAIConfigError(RuntimeError):
    pass


def read_key_file(path: str | Path) -> str:
    path = Path(path)
    try:
        if not path.is_file():
            raise OpenAIConfigError("OpenAI key file is missing: ~/.config/hillink/openai.env")
        if stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise OpenAIConfigError("OpenAI key file permissions must be 600 or stricter")
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        raise OpenAIConfigError("OpenAI key file cannot be read") from None
    values = [line.split("=", 1)[1].strip().strip(chr(34)).strip(chr(39))
              for line in lines if line.strip().startswith("OPENAI_API_KEY=")]
    if len(values) != 1:
        raise OpenAIConfigError("OpenAI key file must contain one OPENAI_API_KEY assignment")
    key = values[0]
    if not key or any(ch.isspace() for ch in key):
        raise OpenAIConfigError("OPENAI_API_KEY is empty or malformed")
    return key


def load_openai_api_key() -> str:
    # Keep the opt-in gate here too, so importing this implementation directly
    # cannot bypass the public facade's external-call gate.
    if os.environ.get("HILLINK_LLM_EXTERNAL_OPT_IN") != "1":
        raise OpenAIConfigError("외부 LLM 사용은 HILLINK_LLM_EXTERNAL_OPT_IN=1 설정이 필요합니다")
    key = read_key_file(KEY_FILE)
    os.environ["OPENAI_API_KEY"] = key
    return key


def verify_openai_auth(timeout: float = 20.0) -> str:
    key = load_openai_api_key()
    request = Request("https://api.openai.com/v1/models",
        headers={"Authorization": "Bearer " + key, "Accept": "application/json"}, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return "AUTHENTICATED" if response.status == 200 else f"HTTP_STATUS_{response.status}"
    except HTTPError as exc:
        return "INVALID_KEY_401" if exc.code == 401 else f"HTTP_STATUS_{exc.code}"
    except URLError:
        return "NETWORK_UNAVAILABLE"
    except TimeoutError:
        return "NETWORK_TIMEOUT"
