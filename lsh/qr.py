# lsh/qr.py
# ============================================================
# توليد QR — نفس الدالة
# ============================================================

import io
import qrcode


def generate_qr_code_bytes(deep_link_url):
    """★ توليد QR Code"""
    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=12,
            border=2,
        )
        qr.add_data(deep_link_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#000000", back_color="#ffffff")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        buf.name = "lsh_qr.png"
        return buf
    except Exception as e:
        print(f"[-] QR gen error: {e}")
        return io.BytesIO()
