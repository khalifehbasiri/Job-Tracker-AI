"""Convert the generated PNG artwork into a multi-size Windows ICO resource."""

import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / "src/job_tracker/assets/logo.png"
    image = QImage(str(source))
    if image.isNull():
        raise SystemExit("Logo PNG could not be loaded.")
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = []
    for size in sizes:
        scaled = image.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        if not scaled.save(buffer, "PNG"):
            raise SystemExit("Could not encode icon resource.")
        images.append(bytes(buffer.data()))
    offset = 6 + 16 * len(sizes)
    entries = []
    for size, data in zip(sizes, images, strict=True):
        entries.append(
            struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        )
        offset += len(data)
    source.with_suffix(".ico").write_bytes(
        struct.pack("<HHH", 0, 1, len(sizes)) + b"".join(entries) + b"".join(images)
    )


if __name__ == "__main__":
    main()
