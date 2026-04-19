"""
Generate icon16.png and icon48.png for the Chrome extension.
Uses only Python stdlib + ctypes — no Pillow required.
Run: python generate_icons.py
"""
import struct
import zlib
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _png_chunk(name: bytes, data: bytes) -> bytes:
    c = struct.pack(">I", len(data)) + name + data
    return c + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)


def make_png(size: int, bg: tuple, fg: tuple) -> bytes:
    """Create a square PNG with a solid bg and a centred circle in fg."""
    r_bg, g_bg, b_bg = bg
    r_fg, g_fg, b_fg = fg
    cx = cy = size / 2
    radius = size * 0.38

    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filter byte
        for x in range(size):
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if dist <= radius:
                raw += bytes([r_fg, g_fg, b_fg])
            else:
                raw += bytes([r_bg, g_bg, b_bg])

    ihdr_data = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    idat_data = zlib.compress(bytes(raw))

    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr_data)
        + _png_chunk(b"IDAT", idat_data)
        + _png_chunk(b"IEND", b"")
    )
    return png


# Vinted teal: #09b1ba → (9, 177, 186), white circle
TEAL = (9, 177, 186)
WHITE = (255, 255, 255)

for size, name in [(16, "icon16.png"), (48, "icon48.png")]:
    path = os.path.join(HERE, name)
    with open(path, "wb") as f:
        f.write(make_png(size, TEAL, WHITE))
    print(f"Created {name} ({size}x{size})")
