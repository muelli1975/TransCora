"""Names describe output. Method suffixes are exactly AnaglyphBatch suffixes."""
from pathlib import Path
import re

from .video import requested_rate
from .model import Options, frame_rate


_HINTS = {"lr": ("full_sbs", False), "lrh": ("half_sbs", False), "lrq": ("half_sbs", False),
          "sbs": ("full_sbs", False), "hsbs": ("half_sbs", False), "hou": ("half_ou", False),
          "half-sbs": ("half_sbs", False), "half-ou": ("half_ou", False),
          "rl": ("full_sbs", True), "rlh": ("half_sbs", True), "rlq": ("half_sbs", True),
          "tb": ("full_ou", False), "ab": ("full_ou", False),
          "tbh": ("half_ou", False), "abq": ("half_ou", False),
          "bt": ("full_ou", True), "ba": ("full_ou", True),
          "bth": ("half_ou", True), "baq": ("half_ou", True)}


def filename_layout(stem: str) -> tuple[str, bool] | None:
    if re.search(r"-dual$", stem, re.I):
        return "dual", False
    match = re.search(r"-(half-sbs|half-ou|hsbs|hou|sbs|lrh|rlh|lrq|rlq|tbh|bth|abq|baq|lr|rl|tb|bt|ab|ba)$", stem, re.I)
    hint = _HINTS[match[1].lower()] if match else None
    own = re.search(r"_(full_sbs|half_sbs|full_ou|half_ou)$", stem, re.I)
    if own:
        if hint and hint[0] != own[1].lower():
            raise ValueError("Widersprüchliche Stereo-Kürzel im Dateinamen.")
        hint = hint or (own[1].lower(), False)
    rows = re.search(r"_rows_(lr|rl)$", stem, re.I)
    if rows:
        hint = ('row_interleaved', rows[1].lower() == 'rl')
    sequential = re.search(r"_seq_(lr|rl)$", stem, re.I)
    if sequential:
        hint = ('frame_sequential', sequential[1].lower() == 'rl')
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
    stem = re.sub(r"-(?:half-sbs|half-ou|hsbs|hou|sbs|lrh|rlh|lrq|rlq|tbh|bth|abq|baq|lr|rl|tb|bt|ab|ba|2d|dual)$", "", stem, flags=re.I)
    stem = re.sub(r"_(?:full_sbs|half_sbs|full_ou|half_ou|mono_[lr]|rows_[lr]{2}|seq_[lr]{2})$", "", stem, flags=re.I)
    stem = re.sub(r"_\d+(?:\.\d+)?(?:_\d+)?fps$", "", stem, flags=re.I)
    stem = re.sub(r"_fps\d+(?:\.\d+)?(?:_\d+)?$", "", stem, flags=re.I)
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).strip(" ._-") or "Video"
    if re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", stem, re.I):
        stem = "_" + stem
    return stem[:180].rstrip(" .")


def default_disc_title(source: Path) -> str:
    title = clean_stem(source.stem)
    while len(title.encode('utf-16-be')) > 124:
        title = title[:-1]
    return title.rstrip(' .') or 'Video'


def fps_suffix(value: str) -> str:
    rate = frame_rate(value)
    labels = {'24000/1001': '23.976', '30000/1001': '29.97', '60000/1001': '59.94'}
    label = labels.get(str(rate), str(rate).replace('/', '_'))
    return '_' + label + 'fps'


def suffix_choices(options: Options, method_suffix: str, layout: str | None = None, swap: bool = False) -> list[str]:
    target = layout if options.target == "framerate" else options.target
    if target == "dual": return ["-dual", "Keiner"]
    if target == "cross_sbs": return ["-rl", "Keiner"]
    if target == "row_interleaved": return ['_rows_' + ('rl' if (swap if options.target == 'framerate' else options.row_first == 'right') else 'lr'), 'Keiner']
    choices = {"half_sbs": ["_half_sbs", "-lrh", "-lrq", ".3D.HSBS"],
               "half_ou": ["_half_ou", "-tbh", "-abq", ".3D.HTAB"],
               "full_sbs": ["_full_sbs", "-lr", ".3D.SBS"], "full_ou": ["_full_ou", "-tb", "-ab", ".3D.TAB"],
               "mono": ["_mono_" + ('l' if options.mono_eye == 'left' else 'r'), "-2d"], "bd3d": [], "anaglyph": ["_" + method_suffix]}.get(target, [])
    if options.target == "framerate":
        if swap:
            choices = {"half_sbs": ["-rlh", "-rlq"], "full_sbs": ["-rl"],
                       "half_ou": ["-bth", "-baq"], "full_ou": ["-bt", "-ba"]}.get(target, [])
        if target == "mono":
            choices = []
        choices = ([fps_suffix(options.target_fps)] if requested_rate(options) else []) + choices
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
                  ("full_ou", True): "-bt", ("half_ou", True): "-bth",
                  ("row_interleaved", False): "_rows_lr", ("row_interleaved", True): "_rows_rl"}.get((layout, swap), "")
        return (fps_suffix(options.target_fps) if requested_rate(options) else "") + marker
    if options.target == "cross_sbs": return "-rl"
    if options.target == "row_interleaved": return '_rows_' + ('rl' if options.row_first == 'right' else 'lr')
    if options.target == "dual":
        return "" if options.naming == "original" else "-dual"
    if options.target == "bd3d":
        return ""
    if options.target == "anaglyph":
        return "_" + method_suffix
    if options.naming == "original":
        return ""
    if options.naming == "layout":
        return "_" + ("mono_" + ('l' if options.mono_eye == 'left' else 'r') if options.target == "mono" else options.target)
    return {"half_sbs": ".3D.HSBS", "half_ou": ".3D.HTAB", "full_sbs": ".3D.SBS",
            "full_ou": ".3D.TAB", "mono": "_mono_" + ('l' if options.mono_eye == 'left' else 'r') + "-2d"}[options.target]


def output_parts(source: Path, options: Options, method_suffix: str) -> tuple[str, str]:
    title = (options.disc_title or default_disc_title(source)) if options.target == "bd3d" else None
    return clean_stem(title or source.stem), effective_suffix(options, method_suffix, source)


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


_SUFFIX_PLAYERS = {
    '-lr': 'Bino/Stereoscopic Player', '-lrq': 'Bino/Stereoscopic Player',
    '-ab': 'Bino/Stereoscopic Player', '-abq': 'Bino/Stereoscopic Player',
    '-lrh': 'Bino', '-tbh': 'Bino', '-tb': 'Bino', '-bt': 'Bino',
    '-ba': 'Bino', '-bth': 'Bino', '-baq': 'Bino', '-rl': 'Bino',
    '-rlh': 'Bino', '-rlq': 'Bino', '-2d': 'Bino',
    '.3D.SBS': 'Kodi', '.3D.HSBS': 'Kodi', '.3D.TAB': 'Kodi', '.3D.HTAB': 'Kodi',
    '-dual': 'Dual-Kennung',
    '_half_sbs': 'TransCora', '_half_ou': 'TransCora',
    '_full_sbs': 'TransCora', '_full_ou': 'TransCora',
}


def suffix_player(suffix):
    return _SUFFIX_PLAYERS.get(suffix, '')


def suffix_label(suffix, translate=lambda text:text):
    player=suffix_player(suffix)
    return suffix+' ('+translate(player)+')' if player else translate(suffix) if suffix=='Keiner' else suffix


def suffix_value(label, translate=lambda text:text):
    # Decode only complete menu labels; custom suffix text remains literal.
    return next((suffix for suffix in _SUFFIX_PLAYERS if suffix_label(suffix,translate)==label),label)
