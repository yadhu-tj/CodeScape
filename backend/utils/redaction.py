import re

_PRIVATE_KEY = re.compile(r"-----BEGIN ([A-Z0-9 ]*PRIVATE KEY)-----.*?-----END \1-----", re.S)
_BEARER = re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/=-]+")
_TOKEN = re.compile(
    r"\b(?:AIza[A-Za-z0-9_-]{35}|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}"
    r"|(?:AKIA|ASIA)[A-Z0-9]{16}|sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{15,})\b"
)
_SECRET_NAME = r"[A-Z0-9_-]*(?:secret|password|passwd|api[_-]?key|token|credential|database_url|redis_url)[A-Z0-9_-]*"
_SECRET_KEY = re.compile(_SECRET_NAME, re.I)
# Source excerpts can end inside a triple-quoted secret, so consume through EOF if needed.
_SECRET_ASSIGNMENT = re.compile(
    rf"(?i)(\b{_SECRET_NAME}['\"]?[ \t]*[:=][ \t]*)"
    r"(?:[rubft]{0,2}(?:(?P<triple>\"{3}|'{3})"
    r"(?:\\[\s\S]|(?!(?P=triple))[^\\])*(?:(?P=triple)|\\?\Z)"
    r"|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')|[^\s,;}\]\"']+)"
)
_URL_CREDENTIALS = re.compile(r"(\b[a-zA-Z][a-zA-Z0-9+.-]*://)[^\s/@]+:[^\s/@]+@")


def redact_code_excerpt(text: str) -> str:
    text = _PRIVATE_KEY.sub("[REDACTED PRIVATE KEY]", text)
    text = _BEARER.sub(r"\1[REDACTED]", text)
    text = _TOKEN.sub("[REDACTED]", text)
    text = _SECRET_ASSIGNMENT.sub(r'\1"[REDACTED]"', text)
    return _URL_CREDENTIALS.sub(r"\1[REDACTED]@", text)


def redact_context(value):
    """Redact structured excerpts before serialization escapes quotes and line breaks."""
    if isinstance(value, str):
        return redact_code_excerpt(value)
    if isinstance(value, dict):
        return {
            redact_code_excerpt(key): "[REDACTED]" if _SECRET_KEY.fullmatch(key) else redact_context(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_context(item) for item in value]
    return value
