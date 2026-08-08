import os
import re
import string
import hashlib
import secrets
from pathlib import Path

from nonebot.log import logger

ERROR_CODE_PREFIX = "KSM"
_ERROR_CODE_CHARS = string.ascii_uppercase + string.digits
_ERROR_CODE_LENGTH = 6

_LOG_DIR_DEFAULT = "logs"
_LOG_RETENTION_DAYS = 30

_TOKEN_RE = re.compile(
    r"(?i)(\b(?:auth_)?token\b\s*[=:]\s*['\"]?)([^'\"\s,\]\}]+)"
)
_MESSAGE_ID_RE = re.compile(r"ROBOT1\.0_[^\s'\"]+")
_OPAQUE_QQ_ID_RE = re.compile(r"\b[A-F0-9]{32}\b")


def persistent_log_filter(record: dict) -> bool:
    """Drop message bodies and redact credentials from persistent logs."""

    message = str(record["message"])
    if "[message-created]" in message:
        return False

    message = _TOKEN_RE.sub(r"\1<redacted>", message)
    message = _MESSAGE_ID_RE.sub("<message-id>", message)
    message = _OPAQUE_QQ_ID_RE.sub("<qq-id>", message)
    record["message"] = message
    return True


def _user_reference(user_id: str) -> str:
    """Return a stable, non-reversible identifier for log correlation."""

    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
    return f"user_hash={digest}"


def setup_logging() -> None:
    """Configure persistent log file output.

    Adds a loguru file sink to ``logs/kasumi-{date}.log`` with daily
    rotation and 30-day retention.  The log directory is created if it
    does not exist.  The default stdout handler configured by NoneBot is
    left intact.
    """
    log_dir = Path(os.getenv("LOG_DIR", _LOG_DIR_DEFAULT))
    log_level = os.getenv("LOG_FILE_LEVEL", "INFO")

    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        str(log_dir / "kasumi-{time:YYYY-MM-DD}.log"),
        level=log_level,
        rotation="00:00",
        retention=f"{_LOG_RETENTION_DAYS} days",
        encoding="utf-8",
        enqueue=True,
        compression="gz",
        backtrace=False,
        diagnose=False,
        filter=persistent_log_filter,
        format="[{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<7} | {name}] {message}",
    )


def generate_error_code() -> str:
    """Return a unique error code like ``KSM-X9F2K1``."""
    body = "".join(secrets.choice(_ERROR_CODE_CHARS) for _ in range(_ERROR_CODE_LENGTH))
    return f"{ERROR_CODE_PREFIX}-{body}"


def log_error(
    error_code: str,
    exception: Exception,
    context: str = "",
    user_id: str = "",
) -> None:
    """Log a structured error entry with full traceback.

    The emitted log line uses the error code as a structured tag so that
    operators can grep the log file for it::

        [KSM-A1B2C3] mines | user=123456789 | <message>
        Traceback (most recent call last):
        ...
    """
    parts = [f"[{error_code}]"]
    if context:
        parts.append(context)
    if user_id:
        parts.append(_user_reference(user_id))
    parts.append(str(exception))

    logger.opt(exception=exception).error(" | ".join(parts))


def handle_error(
    exception: Exception,
    context: str = "",
    user_id: str = "",
) -> str:
    """Convenience: generate an error code, log the error, return the code.

    The caller is responsible for any cleanup (refunds, state reset)
    **before** calling this function.

    Returns the error code string (e.g. ``KSM-A1B2C3``) so the caller can
    include it in the user-facing message.
    """
    error_code = generate_error_code()
    log_error(error_code, exception, context, user_id)
    return error_code


class AppError(Exception):
    """Base exception for Kasumi application errors.

    Subclass this for domain-specific errors.  Currently a placeholder;
    concrete subclasses can be added later without changing the rest of
    the system.
    """

    pass
