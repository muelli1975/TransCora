"""Conventional SDR display values at the RGB/video boundary.

sRGB photographs and ordinary BT.709/SMPTE170M SDR video use the same
encoded working values here. Matrix, primaries and range are still converted.
Do not use this policy to remove the linearization inside anaglyph methods.

Reference: Shotcut Native8Cpu / MLT avcolour_space (matrix/range conversion);
Chromium ColorSpace::GetTransferFunction groups BT709/SMPTE170M with sRGB.
See docs/SDR_COLOR_POLICY.md for scope and regression checks.
"""


def display_transfer(transfer: str) -> str:
    return "iec61966-2-1" if transfer in {"bt709", "smpte170m"} else transfer


def rgb_input(colors: dict) -> str:
    return (f"zscale=matrixin={colors['matrix']}:primariesin={colors['primaries']}:"
            f"transferin={display_transfer(colors['transfer'])}:"
            f"rangein={'full' if colors['range'] == 'pc' else 'limited'}:"
            "matrix=gbr:primaries=bt709:transfer=iec61966-2-1:range=full,format=gbrp16")


SDR_TAGS = "setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=limited"
