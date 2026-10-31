from __future__ import annotations

import re
import unicodedata


_LEGAL_SUFFIXES = (
    "private limited",
    "pvt ltd",
    "limited",
    "ltd",
    "corporation",
    "corp",
    "incorporated",
    "inc",
    "plc",
)


def normalize_company_name(value: str) -> str:
    """Return a deterministic comparison form without fuzzy matching."""
    if not isinstance(value, str):
        raise TypeError("Company name must be a string")
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for suffix in _LEGAL_SUFFIXES:
        if normalized == suffix:
            return ""
        if normalized.endswith(f" {suffix}"):
            normalized = normalized[: -(len(suffix) + 1)].rstrip()
            break
    return normalized
