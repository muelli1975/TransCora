"""Keep packed-video st3d metadata separate from spatial-video extensions."""
import struct
from pathlib import Path


def packed_stereo_boxes(path: Path, *, normalize: bool = False) -> list[int]:
    """Read st3d modes; neutralize generated vexu boxes without moving any bytes.

    FFmpeg 9 also writes Apple spatial-video vexu/eyes metadata when writing
    st3d. On re-reading it, eyes overwrites the explicit SBS/OU type with
    'unspecified'. Packed SBS/OU exports use st3d and codec frame packing only.
    Renaming that optional box to free preserves all box sizes and chunk offsets.
    Only the application's temporary output is ever normalized.
    """
    modes = []
    with path.open("r+b" if normalize else "rb") as file:
        file.seek(0, 2)
        length = file.tell()

        def walk(start, end, depth=0):
            if depth > 8:
                raise ValueError("Ungültige MP4-Box-Verschachtelung.")
            pos = start
            while pos < end:
                file.seek(pos)
                header = file.read(8)
                if len(header) != 8:
                    raise ValueError("Unvollständige MP4-Box.")
                size, kind = struct.unpack(">I4s", header)
                header_size = 8
                if size == 1:
                    extended = file.read(8)
                    if len(extended) != 8:
                        raise ValueError("Unvollständige MP4-Box-Größe.")
                    size = struct.unpack(">Q", extended)[0]
                    header_size = 16
                elif size == 0:
                    size = end-pos
                if size < header_size or pos+size > end:
                    raise ValueError("Ungültige MP4-Box-Größe.")
                content, stop = pos+header_size, pos+size
                if kind in {b"moov", b"trak", b"mdia", b"minf", b"stbl"}:
                    walk(content, stop, depth+1)
                elif kind == b"stsd":
                    walk(content+8, stop, depth+1)  # FullBox header + entry count.
                elif kind in {b"avc1", b"avc3", b"hvc1", b"hev1"}:
                    walk(content+78, stop, depth+1)  # VisualSampleEntry header.
                elif kind == b"st3d":
                    file.seek(content)
                    data = file.read(5)
                    if len(data) != 5 or size != header_size+5 or data[:4] != b"\0\0\0\0":
                        raise ValueError("Ungültige MP4-st3d-Kennzeichnung.")
                    modes.append(data[4])
                elif kind == b"vexu" and normalize:
                    file.seek(pos+4)
                    file.write(b"free")
                pos = stop
        walk(0, length)
    return modes
