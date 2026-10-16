"""Human-readable, non-sequential bag codes with a check character.

Format: ECO-XXXX-XC. Five random characters plus one Luhn mod-N check
character, from an alphabet without look-alikes (no 0/O, 1/I/L, U).
30^5 ≈ 24 million codes. The check character catches any single wrong
character and any swap of two adjacent characters.
"""

import re
import secrets

ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
_N = len(ALPHABET)
_INDEX = {ch: i for i, ch in enumerate(ALPHABET)}
_PATTERN = re.compile(rf"^ECO-([{ALPHABET}]{{4}})-([{ALPHABET}])([{ALPHABET}])$")


def check_char(payload: str) -> str:
    """Luhn mod-N check character for `payload`."""
    factor = 2
    total = 0
    for ch in reversed(payload):
        addend = factor * _INDEX[ch]
        factor = 1 if factor == 2 else 2
        total += addend // _N + addend % _N
    return ALPHABET[(_N - total % _N) % _N]


def generate_code() -> str:
    payload = "".join(secrets.choice(ALPHABET) for _ in range(5))
    return f"ECO-{payload[:4]}-{payload[4]}{check_char(payload)}"


def is_valid_code(code: str) -> bool:
    match = _PATTERN.match(code)
    if not match:
        return False
    payload = match.group(1) + match.group(2)
    return check_char(payload) == match.group(3)
