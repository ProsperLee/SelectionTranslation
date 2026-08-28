"""从 icons/translate.svg 生成高清多尺寸 Windows .ico。

使用经典 32-bit BMP（非 PNG）条目，确保：
- 嵌入 EXE 后资源管理器 / 快捷方式能正确选用大图
- 桌面快捷方式通过独立 app.ico 显示清晰
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SVG_PATH = ROOT / "icons" / "translate.svg"
OUT_PATH = Path(__file__).resolve().parent / "app.ico"
COLOR = "#088fff"
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def _render_rgba(renderer, size: int, color: str):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter
    from PIL import Image

    qimg = QImage(size, size, QImage.Format.Format_ARGB32)
    qimg.fill(Qt.GlobalColor.transparent)
    painter = QPainter(qimg)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    pad = max(1, size // 16)
    renderer.render(painter, qimg.rect().adjusted(pad, pad, -pad, -pad))
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(qimg.rect(), QColor(color))
    painter.end()

    ptr = qimg.constBits()
    buf = bytes(memoryview(ptr))
    return Image.frombuffer("RGBA", (size, size), buf, "raw", "BGRA", 0, 1).copy()


def _rgba_to_ico_dib(img) -> bytes:
    """ICO 用 DIB：BITMAPINFOHEADER + 32bit XOR（底向上）+ 1bit AND mask。"""
    img = img.convert("RGBA")
    w, h = img.size
    pixels = list(img.getdata())

    xor = bytearray()
    for y in range(h - 1, -1, -1):
        row = y * w
        for x in range(w):
            r, g, b, a = pixels[row + x]
            xor += bytes((b, g, r, a))

    # AND mask：透明处为 1；每行补齐到 4 字节
    row_bytes = ((w + 31) // 32) * 4
    and_mask = bytearray()
    for y in range(h - 1, -1, -1):
        row = y * w
        bits = 0
        cur = 0
        line = bytearray()
        for x in range(w):
            a = pixels[row + x][3]
            cur = (cur << 1) | (1 if a < 128 else 0)
            bits += 1
            if bits == 8:
                line.append(cur)
                cur = 0
                bits = 0
        if bits:
            line.append(cur << (8 - bits))
        while len(line) < row_bytes:
            line.append(0)
        and_mask += line

    # biHeight = height * 2（XOR + AND）
    header = struct.pack(
        "<IIIHHIIIIII",
        40,  # biSize
        w,
        h * 2,
        1,  # planes
        32,  # bit count
        0,  # BI_RGB
        len(xor),
        0,
        0,
        0,
        0,
    )
    return header + xor + and_mask


def _write_bmp_ico(path: Path, images: dict[int, object]) -> None:
    sizes = sorted(images.keys())
    count = len(sizes)
    dibs = {s: _rgba_to_ico_dib(images[s]) for s in sizes}

    offset = 6 + 16 * count
    directory = bytearray()
    payload = bytearray()
    for size in sizes:
        data = dibs[size]
        w = 0 if size >= 256 else size
        h = 0 if size >= 256 else size
        directory += struct.pack(
            "<BBBBHHII",
            w,
            h,
            0,
            0,
            1,
            32,
            len(data),
            offset + len(payload),
        )
        payload += data

    header = struct.pack("<HHH", 0, 1, count)
    path.write_bytes(header + directory + payload)


def main() -> int:
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtSvg import QSvgRenderer

    _ = QGuiApplication.instance() or QGuiApplication(sys.argv)

    if not SVG_PATH.is_file():
        print(f"找不到图标: {SVG_PATH}", file=sys.stderr)
        return 1

    renderer = QSvgRenderer(str(SVG_PATH))
    if not renderer.isValid():
        print(f"无效 SVG: {SVG_PATH}", file=sys.stderr)
        return 1

    images = {}
    for size in SIZES:
        images[size] = _render_rgba(renderer, size, COLOR)
        print(f"  {size}x{size}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _write_bmp_ico(OUT_PATH, images)
    print(f"已生成 BMP-ICO: {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
