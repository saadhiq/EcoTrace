import re

from app.bagcodes import ALPHABET, check_char, generate_code, is_valid_code


def test_generated_codes_have_expected_format_and_validate() -> None:
    for _ in range(500):
        code = generate_code()
        assert re.fullmatch(r"ECO-[A-Z2-9]{4}-[A-Z2-9]{2}", code)
        assert set(code.replace("ECO-", "").replace("-", "")) <= set(ALPHABET)
        assert is_valid_code(code)


def test_codes_are_not_sequential() -> None:
    codes = sorted(generate_code() for _ in range(1000))
    # ~24M possible codes: a rare duplicate among 1000 is expected (birthday
    # problem, ~2%), so allow a few; uniqueness in storage is enforced by create().
    assert len(set(codes)) >= 995
    payloads = sorted({c[4:8] + c[9] for c in codes})
    consecutive = sum(1 for a, b in zip(payloads, payloads[1:]) if a[:-1] == b[:-1])
    assert consecutive < 100  # spread out, not counting up


def test_rejects_malformed_codes() -> None:
    good = generate_code()
    for bad in ["", "ECO-", good.lower(), good.replace("ECO", "ECX"), good + "A", "ECO-0000-00"]:
        assert not is_valid_code(bad)


def _variants(code: str):  # noqa: ANN202
    chars = [i for i, ch in enumerate(code) if ch in ALPHABET and i >= 4]
    for i in chars:
        for ch in ALPHABET:
            if ch != code[i]:
                yield code[:i] + ch + code[i + 1 :]


def test_every_single_character_error_is_detected() -> None:
    for _ in range(50):
        code = generate_code()
        for variant in _variants(code):
            assert not is_valid_code(variant), variant


def test_adjacent_transpositions_are_detected() -> None:
    # Exhaustive over every adjacent pair position in the 6-char body.
    detected = total = 0
    for _ in range(300):
        body = generate_code().replace("ECO-", "").replace("-", "")
        for i in range(len(body) - 1):
            if body[i] == body[i + 1]:
                continue
            swapped = body[:i] + body[i + 1] + body[i] + body[i + 2 :]
            total += 1
            detected += check_char(swapped[:5]) != swapped[5]
    # Luhn mod-N misses only the rare pair whose doubled values coincide.
    assert detected / total > 0.97
