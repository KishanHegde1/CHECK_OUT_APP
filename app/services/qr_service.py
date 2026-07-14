"""QR token generation service.

The backend intentionally returns only an opaque token.  The Flutter client is
responsible for rendering that value as a QR image.
"""

from app.utils.qr_generator import generate_checkout_id, generate_qr_token

__all__ = ["generate_checkout_id", "generate_qr_token"]
