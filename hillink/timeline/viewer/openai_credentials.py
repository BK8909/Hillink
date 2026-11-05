"""Opt-in facade for the repository-owned private-file credential loader."""
from __future__ import annotations

import importlib
import os


class OpenAIConfigError(RuntimeError):
    pass


def _loader():
    try:
        name = f"{__package__}.openai_key_file" if __package__ else "openai_key_file"
        return importlib.import_module(name)
    except Exception:
        raise OpenAIConfigError("HILLINK repository OpenAI loader could not be imported") from None


def _call(name, *args, **kwargs):
    loader = _loader()
    try:
        return getattr(loader, name)(*args, **kwargs)
    except loader.OpenAIConfigError as exc:
        raise OpenAIConfigError(str(exc)) from None


def load_openai_api_key():
    _require_external_opt_in()
    return _call("load_openai_api_key")


def read_key_file(path):
    return _call("read_key_file", path)


def _require_external_opt_in():
    if os.environ.get("HILLINK_LLM_EXTERNAL_OPT_IN") != "1":
        raise OpenAIConfigError("외부 LLM 사용은 HILLINK_LLM_EXTERNAL_OPT_IN=1 설정이 필요합니다")


def verify_openai_auth(timeout=20.0):
    _require_external_opt_in()
    return _call("verify_openai_auth", timeout=timeout)


__all__ = ["OpenAIConfigError", "load_openai_api_key", "read_key_file", "verify_openai_auth"]
