"""
QR code & barcode generation + the {QR:…} / {BARCODE:…} template tokens.

A token renders a per-recipient scannable code from row data:
  {QR:CouponNumber}              → QR of that row's CouponNumber value
  {QR:https://verify.me/{Code}}  → QR of a per-row URL
  {BARCODE:OrderID}              → Code128 barcode of OrderID's value

On the PDF / on-screen preview the image is embedded as a data: URI (reliable in
WeasyPrint). In email it points at the public, signed /codes endpoint, because
email clients (Gmail, etc.) block data: images.
"""

import base64
import hashlib
import hmac
import io
import re
import urllib.parse

from app import config

# {QR:payload} / {BARCODE:payload} — payload may contain one level of {Col} nesting.
CODE_TOKEN_RE = re.compile(r"\{(QR|BARCODE):((?:[^{}]|\{[^{}]*\})*)\}")

_BARE_COL_RE = re.compile(r"^[A-Za-z_]\w*$")


# ── Generation ──────────────────────────────────────────────────────────

def qr_png(data: str) -> bytes:
    import qrcode

    img = qrcode.make(data or " ")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def barcode_png(data: str) -> bytes:
    import barcode
    from barcode.writer import ImageWriter

    code = barcode.get("code128", data or " ", writer=ImageWriter())
    buf = io.BytesIO()
    code.write(buf, options={"module_height": 12.0, "quiet_zone": 2.0, "font_size": 8, "text_distance": 3.0})
    return buf.getvalue()


def png(kind: str, data: str) -> bytes:
    """PNG bytes for a code. kind is 'qr' or 'barcode'."""
    return barcode_png(data) if kind == "barcode" else qr_png(data)


def _data_uri(kind: str, data: str) -> str:
    return f"data:image/png;base64,{base64.b64encode(png(kind, data)).decode()}"


# ── Signing — so the public endpoint isn't an open generator ────────────

def sign(kind: str, data: str) -> str:
    mac = hmac.new(config.SECRET_KEY.encode(), f"{kind}:{data}".encode(), hashlib.sha256)
    return base64.urlsafe_b64encode(mac.digest()).decode().rstrip("=")[:24]


def verify(kind: str, data: str, sig: str) -> bool:
    return hmac.compare_digest(sign(kind, data), sig or "")


# ── Token resolution + expansion ────────────────────────────────────────

def _fill(payload: str, row: dict) -> str:
    """Substitute {Col} fields in a payload (same rule as template_renderer.fill_placeholders,
    inlined here so this module stays free of the WeasyPrint import)."""
    return re.sub(
        r"\{([^}]+)\}",
        lambda m: str(row[m.group(1)]) if m.group(1) in row else m.group(0),
        payload,
    )


def resolve_payload(payload: str, row: dict) -> str:
    """Resolve a token payload to the string to encode:
      - contains {Col} → fill per-row (URLs / templated strings)
      - bare column name present in row → that row's value
      - otherwise → literal
    """
    payload = payload.strip()
    if "{" in payload:
        return _fill(payload, row)
    if payload in row:
        return str(row[payload])
    return payload


def expand_codes(html: str, row: dict, *, mode: str = "datauri", base_url: str = None) -> str:
    """Replace {QR:…} / {BARCODE:…} tokens with <img> elements.

    mode="datauri": inline base64 PNG (PDF + on-screen preview).
    mode="url":     point at the signed public /codes endpoint (email). Falls back
                    to a data: URI if base_url is missing (logs a warning).
    """
    if "{QR:" not in html and "{BARCODE:" not in html:
        return html

    if mode == "url" and not base_url:
        import logging

        logging.getLogger(__name__).warning(
            "PUBLIC_API_URL is not set — embedding email QR/barcode as a data: URI "
            "(blocked by some email clients). Set PUBLIC_API_URL for reliable email codes."
        )

    def repl(m):
        kind = "barcode" if m.group(1) == "BARCODE" else "qr"
        data = resolve_payload(m.group(2), row)
        alt = "barcode" if kind == "barcode" else "QR code"
        if mode == "url" and base_url:
            q = urllib.parse.urlencode({"data": data, "sig": sign(kind, data)})
            src = f"{base_url.rstrip('/')}/codes/{kind}?{q}"
        else:
            src = _data_uri(kind, data)
        style = "max-width:100%;height:auto;" if kind == "barcode" else "width:140px;height:140px;"
        return f'<img src="{src}" alt="{alt}" style="{style}" />'

    return CODE_TOKEN_RE.sub(repl, html)


def referenced_columns(html: str) -> list[str]:
    """Bare column names referenced by {QR:Col}/{BARCODE:Col} so they get column-mapped.
    Templated payloads (with {Col}) are already covered by the normal placeholder extractor."""
    cols = []
    for m in CODE_TOKEN_RE.finditer(html):
        payload = m.group(2).strip()
        if "{" not in payload and _BARE_COL_RE.match(payload):
            cols.append(payload)
    return cols
