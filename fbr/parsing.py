"""Reads FBR's replies. A wrong "accepted" here would be a compliance failure, so it's strict.

The spec's own samples show an outer statusCode of "00" with status "invalid" and a
failed item, so the outer code alone can't be trusted, and status case varies.
"""

from dataclasses import dataclass, field

from .constants import ERROR_HELP

VALID, INVALID, UNCLEAR = "valid", "invalid", "unclear"


@dataclass
class Parsed:
    outcome: str
    irn: str = ""
    dated: str = ""
    errors: list = field(default_factory=list)
    item_numbers: dict = field(default_factory=dict)

    @property
    def error_code(self):
        return self.errors[0][0] if self.errors else ""

    @property
    def message(self):
        parts = []
        for code, text in self.errors:
            line = f"{code + ': ' if code else ''}{text}"
            if code in ERROR_HELP:
                line += f" {ERROR_HELP[code]}"
            parts.append(line)
        return " | ".join(parts)


def parse(data, *, needs_irn: bool) -> Parsed:
    if not isinstance(data, dict) or not isinstance(data.get("validationResponse"), dict):
        return Parsed(UNCLEAR)
    vr = data["validationResponse"]
    irn = data.get("invoiceNumber") or ""
    dated = str(data.get("dated") or "")
    statuses = vr.get("invoiceStatuses")
    outer_code = str(vr.get("statusCode") or "")
    outer_valid = outer_code == "00" and str(vr.get("status") or "").strip().lower() == "valid"

    errors, numbers, any_bad = [], {}, False
    if isinstance(statuses, list):
        for item in statuses:
            if not isinstance(item, dict):
                return Parsed(UNCLEAR, irn=irn, dated=dated)
            if str(item.get("statusCode")) == "00":
                numbers[str(item.get("itemSNo"))] = item.get("invoiceNo") or ""
            else:
                any_bad = True
                errors.append((str(item.get("errorCode") or ""), f"Item {item.get('itemSNo')}: {item.get('error') or 'Invalid'}"))
    elif statuses is not None:
        return Parsed(UNCLEAR, irn=irn, dated=dated)

    if outer_code == "01" or any_bad or (not outer_valid and outer_code == "00"):
        if vr.get("error") or vr.get("errorCode"):
            errors.insert(0, (str(vr.get("errorCode") or ""), str(vr.get("error") or "Invalid")))
        if not errors:
            errors.append(("", "FBR marked this invoice as invalid."))
        # An IRN alongside a failure is contradictory, so a person must check it.
        return Parsed(UNCLEAR if irn else INVALID, irn=irn, dated=dated, errors=errors)

    if outer_valid and statuses:
        if needs_irn and not irn:
            return Parsed(UNCLEAR, dated=dated)
        return Parsed(VALID, irn=irn, dated=dated, item_numbers=numbers)
    return Parsed(UNCLEAR, irn=irn, dated=dated)
