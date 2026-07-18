"""Secret exclusion and redaction used by local absorb importers."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Keep these patterns in the same order as ts/src/absorb/secrets.ts. File names
# matching one of them are never read or uploaded.
SKIP_NAME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\.env(\..*)?$", re.IGNORECASE),
    re.compile(r"credentials", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"(^|[._-])tokens?([._-]|$)", re.IGNORECASE),
    re.compile(r"\.pem$", re.IGNORECASE),
    re.compile(r"\.key$", re.IGNORECASE),
    re.compile(r"id_rsa", re.IGNORECASE),
    re.compile(r"\.p12$", re.IGNORECASE),
    re.compile(r"\.pfx$", re.IGNORECASE),
)

# Keep these patterns in the same order as ts/src/absorb/secrets.ts. Specific
# patterns run before generic long-hex/base64 patterns so each match is counted
# consistently and prefixed keys are redacted as a whole.
REDACT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[opusr]_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bhbn_[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\b([Bb]earer\s+)[A-Za-z0-9._-]{20,}\b"),
    re.compile(r"\b([a-zA-Z][a-zA-Z0-9+.-]*://[^:@/\s]*:)[^@\s]{3,}(?=@)"),
    re.compile(r"\bsb_secret_[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\bsbp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\b[0-9a-fA-F]{40,}\b"),
    re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b"),
)

REDACTION_MARKER = "[REDACTED]"


@dataclass(frozen=True)
class RedactionResult:
    """Cleaned content and the number of token-shaped strings replaced."""

    content: str
    redacted_count: int


def should_skip_file(filename: str) -> bool:
    """Return whether a basename indicates a credential-bearing file."""
    base = re.split(r"[\\/]", filename)[-1]
    return any(pattern.search(base) is not None for pattern in SKIP_NAME_PATTERNS)


def redact_secrets(content: str) -> RedactionResult:
    """Redact token-shaped values while preserving contextual prefixes."""
    redacted_count = 0
    output = content

    for pattern in REDACT_PATTERNS:

        def replace(match: re.Match[str]) -> str:
            nonlocal redacted_count
            redacted_count += 1
            prefix = match.group(1) if match.lastindex else ""
            return f"{prefix}{REDACTION_MARKER}"

        output = pattern.sub(replace, output)

    return RedactionResult(content=output, redacted_count=redacted_count)
