"""Image slots for the public profile: whether a file is present, and its real pixel size.

Pure Python on purpose. requirements.txt is flask + gunicorn only, so Pillow is not available on
the host. Sizes come from the file header: JPEG (SOFn marker), PNG (IHDR), WebP (VP8 / VP8L / VP8X).
"""
import os
import struct

# SOF0-SOF15, minus DHT (C4), JPG (C8) and DAC (CC), which share the range but carry no size.
_JPEG_SOF = {m for m in range(0xC0, 0xD0)} - {0xC4, 0xC8, 0xCC}


def _jpeg(f):
    f.seek(2)
    while True:
        b = f.read(1)
        if not b:
            return None
        if b != b"\xff":
            continue
        marker = f.read(1)
        while marker == b"\xff":  # fill bytes
            marker = f.read(1)
        if not marker:
            return None
        m = marker[0]
        if m in (0x01, 0xD8) or 0xD0 <= m <= 0xD7:  # standalone markers carry no length
            continue
        if m == 0xD9:
            return None
        seg = f.read(2)
        if len(seg) < 2:
            return None
        length = struct.unpack(">H", seg)[0]
        if m in _JPEG_SOF:
            data = f.read(5)
            if len(data) < 5:
                return None
            _precision, h, w = struct.unpack(">BHH", data)
            return (w, h) if w and h else None
        f.seek(length - 2, 1)


def _png(head):
    if head[12:16] != b"IHDR":
        return None
    w, h = struct.unpack(">II", head[16:24])
    return (w, h) if w and h else None


def _webp(head):
    kind = head[12:16]
    if kind == b"VP8 " and head[23:26] == b"\x9d\x01\x2a":
        w, h = struct.unpack("<HH", head[26:30])
        return (w & 0x3FFF, h & 0x3FFF)
    if kind == b"VP8L" and head[20:21] == b"\x2f":
        bits = struct.unpack("<I", head[21:25])[0]
        return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
    if kind == b"VP8X":
        w = int.from_bytes(head[24:27], "little") + 1
        h = int.from_bytes(head[27:30], "little") + 1
        return (w, h)
    return None


def image_size(static_folder, relpath):
    """(width, height) of static_folder/relpath, or None if it is missing or not a readable image."""
    path = os.path.join(static_folder, relpath)
    try:
        with open(path, "rb") as f:
            head = f.read(30)
            if head[:2] == b"\xff\xd8":
                return _jpeg(f)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                return _png(head)
            if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
                return _webp(head)
    except (OSError, struct.error):
        pass
    return None
