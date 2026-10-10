"""Names describe output. Method suffixes are exactly AnaglyphBatch suffixes."""
from pathlib import Path
import re

from .model import Options


_HINTS = {"lr": ("full_sbs", False), "lrh": ("half_sbs", False), "lrq": ("half_sbs", False),
          "rl": ("full_sbs", True), "rlh": ("half_sbs", True), "rlq": ("half_sbs", True),
          "tb": ("full_ou", False), "ab": ("full_ou", False),
          "tbh": ("half_ou", False), "abq": ("half_ou", False),
          "bt": ("full_ou", True), "ba": ("full_ou", True),
          "bth": ("half_ou", True), "baq": ("half_ou", True)}


def filename_layout(stem: str) -> tuple[str, bool] | None:
    match = re.search(r"-(lrh|rlh|lrq|rlq|tbh|bth|abq|baq|lr|rl|tb|bt|ab|ba)$", stem, re.I)
    hint = _HINTS[match[1].lower()] if match else None
    kodi = re.search(r"(?:^|[-. _])3d[-. _]+(hsbs|htab|sbs|tab)(?=$|[-. _])", stem, re.I)
    if kodi:
        other = {"hsbs": "half_sbs", "htab": "half_ou", "sbs": "full_sbs", "tab": "full_ou"}[kodi[1].lower()]
        if hint and other != hint[0]:
            raise ValueError("Widersprüchliche Stereo-Kürzel im Dateinamen. Namen beziehungsweise Quelllayout klären.")
        return hint or (other, False)
    return hint


def clean_stem(stem: str) -> str:
    # Remove recognized compound markers only; preserve ordinary words containing '3D'.
    stem = re.sub(r"(?:[-. _])3d[-. _]+h?(?:sbs|tab)(?=$|[-. _])", "", stem, flags=re.I)
    stem = re.sub(r"-(?:lrh|rlh|lrq|rlq|tbh|bth|abq|baq|lr|rl|tb|bt|ab|ba|2d)$", "", stem, flags=re.I)
    stem = re.sub(r"_(?:full_sbs|half_sbs|full_ou|half_ou|mono_l)$", "", stem, flags=re.I)
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).strip(" ._-") or "Video"
    if re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", stem, re.I):
        stem = "_" + stem
    return stem[:180].rstrip(" .")


def output_parts(source: Path, options: Options, method_suffix: str) -> tuple[str, str]:
    base = clean_stem(source.stem)
    if options.target == "anaglyph":
        return base, "_" + method_suffix  # No forced anaglyph, 2d or bit-depth suffix.
    if options.naming == "original":
        return base, ""
    if options.naming == "layout":
        return base, "_" + ("mono_l" if options.target == "mono" else options.target)
    return base, {"half_sbs": ".3D.HSBS-lrh", "half_ou": ".3D.HTAB-tbh", "mono": "_mono_l-2d"}[options.target]


def reserve_output(source: Path, folder: Path, options: Options, method_suffix: str,
                   reserved: set[str]) -> Path:
    base, suffix = output_parts(source, options, method_suffix)
    number = 1
    while True:
        middle = "" if number == 1 else f"_{number}"
        path = folder / f"{base}{middle}{suffix}.{options.container}"
        key = str(path.resolve()).casefold()
        # Windows name matching is applied on every host.
        existing = folder.is_dir() and any(p.name.casefold() == path.name.casefold() for p in folder.iterdir())
        if key not in reserved and not existing and path.resolve() != source.resolve():
            reserved.add(key)
            return path
        number += 1
