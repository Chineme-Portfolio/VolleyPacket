"""Public, signed QR/barcode image endpoint — referenced by email bodies.

Stateless: the image is generated on the fly from the URL params. An HMAC signature
(over SECRET_KEY) ties each URL to one our app produced, so this isn't an open
QR-for-anything generator and the params can't be tampered with.
"""

from fastapi import APIRouter, Query, Response, HTTPException

from app.services.codes import png, verify

router = APIRouter()

_CACHE = {"Cache-Control": "public, max-age=86400"}


@router.get("/qr")
def qr_code(data: str = Query(""), sig: str = Query("")):
    if not verify("qr", data, sig):
        raise HTTPException(status_code=403, detail="Invalid signature")
    return Response(content=png("qr", data), media_type="image/png", headers=_CACHE)


@router.get("/barcode")
def barcode_code(data: str = Query(""), sig: str = Query("")):
    if not verify("barcode", data, sig):
        raise HTTPException(status_code=403, detail="Invalid signature")
    return Response(content=png("barcode", data), media_type="image/png", headers=_CACHE)
