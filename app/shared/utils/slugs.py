from __future__ import annotations

import re
import secrets
import string

_SLUG_SUFFIX_ALPHABET = string.ascii_lowercase + string.digits


def slugify(value: str, *, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or fallback


def random_slug_suffix(length: int = 6) -> str:
    return "".join(secrets.choice(_SLUG_SUFFIX_ALPHABET) for _ in range(length))


def generate_unique_slug(
    value: str,
    used_slugs: set[str],
    *,
    fallback: str = "item",
    suffix_length: int = 6,
) -> str:
    base_slug = slugify(value, fallback=fallback)
    candidate = base_slug
    while candidate in used_slugs:
        candidate = f"{base_slug}-{random_slug_suffix(suffix_length)}"
    used_slugs.add(candidate)
    return candidate
