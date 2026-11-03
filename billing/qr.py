"""The invoice QR code. It holds the IRN that FBR returned, as confirmed by the owner.

The PRAL spec fixes the size: version 2.0 (25x25), printed at 1x1 inch.
"""

import qrcode
from django.utils.safestring import mark_safe
from qrcode.exceptions import DataOverflowError


def irn_matrix(irn: str):
    """The 25x25 grid for this IRN, or None if it can't fit in version 2."""
    code = qrcode.QRCode(version=2, error_correction=qrcode.constants.ERROR_CORRECT_M, border=0)
    code.add_data(irn)
    try:
        code.make(fit=False)
    except DataOverflowError:
        return None
    return code.get_matrix()


def irn_svg(irn: str):
    """Inline SVG, so it prints sharply and needs no internet or image library."""
    matrix = irn_matrix(irn) if irn else None
    if matrix is None:
        return None
    size = len(matrix)
    cells = "".join(
        f"M{x} {y}h1v1h-1z"
        for y, row in enumerate(matrix)
        for x, dark in enumerate(row)
        if dark
    )
    return mark_safe(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" shape-rendering="crispEdges" '
        f'role="img" aria-label="QR code of the FBR invoice number"><path fill="#000" d="{cells}"/></svg>'
    )
