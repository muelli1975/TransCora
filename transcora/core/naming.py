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
    own = re.search(r"_(full_sbs|half_sbs|full_ou|half_ou)$", stem, re.I)
    if own:
        if hint and hint[0] != own[1].lower():
            raise ValueError("Widersprüchliche Stereo-Kürzel im Dateinamen.")
        hint = hint or (own[1].lower(), False)
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
    stem = re.sub(r"_fps\d+(?:\.\d+)?(?:_\d+)?$", "", stem, flags=re.I)
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).strip(" ._-") or "Video"
    if re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", stem, re.I):
        stem = "_" + stem
    return stem[:180].rstrip(" .")


def suffix_choices(options: Options, method_suffix: str, layout: str | None = None, swap: bool = False) -> list[str]:
    target = layout if options.target == "framerate" else options.target
    choices = {"half_sbs": ["_half_sbs", "-lrh", "-lrq", ".3D.HSBS", ".3D.HSBS-lrh"],
               "half_ou": ["_half_ou", "-tbh", "-abq", ".3D.HTAB", ".3D.HTAB-tbh"],
               "full_sbs": ["_full_sbs", "-lr"], "full_ou": ["_full_ou", "-tb", "-ab"],
               "mono": ["_mono_l", "-2d"], "anaglyph": ["_" + method_suffix]}.get(target, [])
    if options.target == "framerate":
        if swap:
            choices = {"half_sbs": ["-rlh", "-rlq"], "full_sbs": ["-rl"],
                       "half_ou": ["-bth", "-baq"], "full_ou": ["-bt", "-ba"]}.get(target, [])
        if target == "mono":
            choices = []
        choices = ["_fps" + options.target_fps.replace("/", "_").replace(",", ".")] + choices
    return choices + ["Keiner"]


def effective_suffix(options: Options, method_suffix: str, source: Path | None = None) -> str:
    if options.suffix is not None:
        return options.suffix
    if options.target == "framerate":
        # Keep source stereo hints and append the new hint at the final position.
        hint = filename_layout(source.stem) if source and options.layout == "auto" else None
        layout, swap = hint or (options.layout, options.swap)
        marker = {("full_sbs", False): "-lr", ("half_sbs", False): "-lrh",
                  ("full_ou", False): "-tb", ("half_ou", False): "-tbh",
                  ("full_sbs", True): "-rl", ("half_sbs", True): "-rlh",
                  ("full_ou", True): "-bt", ("half_ou", True): "-bth"}.get((layout, swap), "")
        return "_fps" + options.target_fps.replace("/", "_").replace(",", ".") + marker
    if options.target == "anaglyph":
        return "_" + method_suffix
    if options.naming == "original":
        return ""
    if options.naming == "layout":
        return "_" + ("mono_l" if options.target == "mono" else options.target)
    return {"half_sbs": ".3D.HSBS-lrh", "half_ou": ".3D.HTAB-tbh", "mono": "_mono_l-2d"}[options.target]


def output_parts(source: Path, options: Options, method_suffix: str) -> tuple[str, str]:
    return clean_stem(source.stem), effective_suffix(options, method_suffix, source)


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
