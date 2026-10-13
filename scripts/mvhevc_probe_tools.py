"""Development-only MV-HEVC signalling; never changes coded picture payloads.

Apple HEVC Stereo Video Interoperability Profile, section 6 (3D Reference
Displays Info): use width 0/unspecified, no viewing distance or camera metadata.
https://developer.apple.com/av-foundation/HEVC-Stereo-Video-Profile.pdf
"""
import re
from collections import Counter


def annexb_nals(data):
    starts = list(re.finditer(b'\x00\x00\x00?\x01', data))
    if not starts or starts[0].start() != 0:
        raise ValueError('Expected an Annex B HEVC stream')
    result = []
    for i, start in enumerate(starts):
        end = starts[i+1].start() if i+1 < len(starts) else len(data)
        nal = data[start.end():end]
        if len(nal) < 2 or nal[0] & 128 or not nal[1] & 7:
            raise ValueError('Invalid HEVC NAL header')
        result.append(nal)
    return result


def layer(nal):
    return ((nal[0] & 1) << 5) | (nal[1] >> 3)


def picture_counts(data):
    counts = Counter()
    for nal in annexb_nals(data):
        # Count first_slice_segment_in_pic_flag, not one picture per slice.
        if (nal[0] >> 1) & 63 < 32 and len(nal) < 3:
            raise ValueError('Truncated picture NAL')
        if (nal[0] >> 1) & 63 < 32 and nal[2] & 128:
            counts[str(layer(nal))] += 1
    return dict(counts)


def ue(value):
    bits = bin(value+1)[2:]
    return '0'*(len(bits)-1)+bits


def stereo_sei(left=0, right=1):
    if any(type(v) is not int or not 0 <= v < 65536 for v in (left, right)) or left == right:
        raise ValueError('Two different view IDs are required')
    # prec_ref_display_width=31, distance absent, one display, L/R IDs,
    # exponent/mantissa width=0, no sample shift, no extension.
    bits = ue(31)+'0'+ue(0)+ue(left)+ue(right)+'000000'+'0'+'0'+'0'
    if len(bits) % 8:
        bits += '1'+'0'*((7-len(bits)) % 8)
    payload = bytes(int(bits[i:i+8], 2) for i in range(0, len(bits), 8))
    rbsp = bytes([176, len(payload)])+payload+b'\x80'
    escaped = bytearray()
    zeros = 0
    for value in rbsp:
        if zeros >= 2 and value <= 3:
            escaped.append(3); zeros = 0
        escaped.append(value)
        zeros = zeros+1 if value == 0 else 0
    return b'\x4e\x01'+bytes(escaped)


def signal_stereo(data, left=0, right=1):
    nals = annexb_nals(data)
    first_picture = next((i for i, n in enumerate(nals) if (n[0] >> 1) & 63 < 32), None)
    if first_picture is None:
        raise ValueError('No coded pictures')
    nals.insert(first_picture, stereo_sei(left, right))
    return b''.join(b'\x00\x00\x00\x01'+n for n in nals)


def consolidate_headers(data):
    """Remove identical repeated base headers between the two pictures of an AU.

    The x265 multiview CLI repeats the complete prefix before each eye's IDR.
    A layer-0 prefix after the base picture signals the next AU to FFmpeg, even
    though the following secondary picture belongs to that same stereo pair.
    Only byte-identical prefix NALs are removed; coded slices stay untouched.
    """
    output, prefix, between = [], [], []
    base_open = False
    for nal in annexb_nals(data):
        kind = (nal[0] >> 1) & 63
        picture = kind < 32
        if base_open and not picture:
            between.append(nal)
            continue
        if base_open and picture:
            if layer(nal) == 1 and between and between == prefix:
                between.clear()
            output.extend(between); between.clear()
            base_open = False
        if picture and layer(nal) == 0 and nal[2] & 128:
            base_open = True
        elif not picture:
            if output and (output[-1][0] >> 1) & 63 < 32:
                prefix = []
            prefix.append(nal)
        output.append(nal)
    output.extend(between)
    return b''.join(b'\0\0\0\1'+nal for nal in output)
