"""Local text moderation for content the bot is about to send or retain.

The policy deliberately reports only a generic rejection.  Echoing the matched
term in an error response would recreate the exact platform-compliance issue
this module prevents.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import unicodedata


_LEXICON_DIRECTORY = Path(__file__).with_name("resources") / "sensitive_lexicon"
_LEXICON_FILES = ("politics.txt", "reactionary.txt")


class ContentSafetyError(ValueError):
    """Raised when user-controlled text must not be sent or stored."""

    def __init__(self) -> None:
        super().__init__("内容包含不符合平台规范的文字，请修改后重试。")


def normalize_text(text: str) -> str:
    """Normalize common evasion forms before exact-substring matching.

    Keeping letters and numbers joins text split by spaces or punctuation while
    preserving CJK characters.  This is intentionally deterministic: it is a
    safety net, not a claim to understand linguistic context.
    """

    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(
        character
        for character in normalized
        if unicodedata.category(character)[0] in {"L", "N"}
    )


@dataclass(frozen=True)
class SensitiveTextPolicy:
    """A small immutable lexicon with normalized substring matching."""

    terms: frozenset[str]

    @classmethod
    def from_terms(cls, terms: tuple[str, ...] | list[str]) -> "SensitiveTextPolicy":
        return cls(
            frozenset(
                normalized
                for term in terms
                if (normalized := normalize_text(term))
            )
        )

    @classmethod
    @lru_cache(maxsize=1)
    def default(cls) -> "SensitiveTextPolicy":
        terms: list[str] = []
        for filename in _LEXICON_FILES:
            lexicon_path = _LEXICON_DIRECTORY / filename
            terms.extend(lexicon_path.read_text(encoding="utf-8").splitlines())
        return cls.from_terms(terms)

    def contains(self, text: str) -> bool:
        normalized = normalize_text(text)
        return bool(normalized) and any(term in normalized for term in self.terms)


def ensure_safe_text(
    text: str, *, policy: SensitiveTextPolicy | None = None
) -> str:
    """Return safe text or raise a generic, non-echoing error."""

    active_policy = policy or SensitiveTextPolicy.default()
    if active_policy.contains(text):
        raise ContentSafetyError()
    return text


def safe_display_text(text: str | None, *, fallback: str = "") -> str:
    """Prevent pre-existing unsafe database values from reaching a reply."""

    if text is None or SensitiveTextPolicy.default().contains(text):
        return fallback
    return text
