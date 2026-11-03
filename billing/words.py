"""Amounts in words, in the lakh and crore system used on Pakistani invoices."""

from decimal import ROUND_HALF_UP, Decimal

ONES = ("Zero One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve Thirteen Fourteen "
        "Fifteen Sixteen Seventeen Eighteen Nineteen").split()
TENS = "_ _ Twenty Thirty Forty Fifty Sixty Seventy Eighty Ninety".split()


def _under_thousand(n):
    parts = []
    if n >= 100:
        parts += [ONES[n // 100], "Hundred"]
        n %= 100
    if n >= 20:
        parts.append(TENS[n // 10])
        n %= 10
    if n:
        parts.append(ONES[n])
    return parts


def _number(n):
    if n == 0:
        return "Zero"
    parts = []
    for size, name in ((10_000_000, "Crore"), (100_000, "Lakh"), (1000, "Thousand")):
        if n >= size:
            parts += (_number(n // size).split() if name == "Crore" else _under_thousand(n // size)) + [name]
            n %= size
    return " ".join(parts + _under_thousand(n))


def amount_in_words(value) -> str:
    paisa_total = int((Decimal(value) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    rupees, paisa = divmod(abs(paisa_total), 100)
    text = f"Rupees {_number(rupees)}"
    if paisa:
        text += f" and {_number(paisa)} Paisa"
    return text + " Only"
