"""日志脱敏工具 — email/phone/IP 掩码。"""

import re

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{4,10}")
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

SENSITIVE_FIELDS = {"password", "password_hash", "token", "access_token",
                     "secret", "api_key", "authorization"}


def mask_email(text: str) -> str:
    return _EMAIL_RE.sub(lambda m: _mask_email_val(m.group(0)), text)


def mask_phone(text: str) -> str:
    return _PHONE_RE.sub(lambda m: m.group(0)[:3] + "****" + m.group(0)[-2:], text)


def mask_ip(text: str) -> str:
    return _IP_RE.sub(lambda m: ".".join(m.group(0).split(".")[:2]) + ".*.*", text)


def mask_dict(data: dict) -> dict:
    """递归脱敏字典，对敏感键值替换。"""
    result = {}
    for key, value in data.items():
        if key.lower() in SENSITIVE_FIELDS:
            result[key] = "***REDACTED***"
        elif isinstance(value, dict):
            result[key] = mask_dict(value)
        elif isinstance(value, list):
            result[key] = [mask_dict(v) if isinstance(v, dict) else v for v in value]
        elif isinstance(value, str):
            result[key] = mask_email(mask_phone(mask_ip(value)))
        else:
            result[key] = value
    return result


def mask_sensitive(text: str) -> str:
    """组合掩码：email + phone + IP。"""
    return mask_ip(mask_phone(mask_email(text)))


def _mask_email_val(email: str) -> str:
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        return f"{local[0]}***@{domain}"
    return f"{local[:2]}***{local[-1]}@{domain}"
