"""Multi-country phone normalization for SMS — parse raw cells to canonical E.164."""

import re

import phonenumbers


def _parse_one(p: str, default_region: str) -> str | None:
    """Parse a single phone string to E.164, or None if it isn't a valid number.

    Tries the number as-is against the default region first (handles local numbers
    like NG '0801…' and any '+CC…' international number, since phonenumbers ignores
    the region when a '+' is present). If that fails, retries assuming the bare digits
    already include a country code (handles '2348012345678' or '14155552671')."""
    digits = re.sub(r"\D", "", p)
    attempts = [(p, default_region)]
    if not p.startswith("+") and digits:
        attempts.append(("+" + digits, None))
    for candidate, region in attempts:
        try:
            num = phonenumbers.parse(candidate, region)
        except phonenumbers.NumberParseException:
            continue
        if phonenumbers.is_valid_number(num):
            return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
    return None


def to_e164(raw, default_region: str = "NG") -> list[str]:
    """Parse a raw phone cell (one or more numbers separated by , / ;) into a list of
    valid E.164 numbers (e.g. '+2348012345678'). Invalid/unparseable numbers are dropped.
    Replaces the old Nigeria-only normalize_phone; each provider formats E.164 for its API."""
    out: list[str] = []
    for part in re.split(r"[,/;]", str(raw or "")):
        p = part.strip()
        if not p:
            continue
        e164 = _parse_one(p, default_region or "NG")
        if e164:
            out.append(e164)
    return list(dict.fromkeys(out))  # dedupe, preserve order
