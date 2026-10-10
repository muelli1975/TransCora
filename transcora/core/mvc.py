"""Add explicit BT.709 VUI to generated AVC/MVC parameter sets, without changing slices.

SPS and subset SPS share seq_parameter_set_data (ITU-T H.264 7.3.2.1,
7.3.2.1.3 and Annex E). The MVC extension after it is kept byte-for-bit.
This adapter is deliberately restricted to FRIM's generated High/Stereo High.
"""
import re
import os
import uuid
from pathlib import Path


class Bits:
    def __init__(self, data: bytes):
        self.bits = ''.join(f'{b:08b}' for b in data)
        self.pos = 0

    def read(self, count=1):
        if self.pos+count > len(self.bits):
            raise ValueError('Truncated SPS')
        value = int(self.bits[self.pos:self.pos+count], 2)
        self.pos += count
        return value

    def ue(self):
        zeroes = 0
        while self.read() == 0:
            zeroes += 1
            if zeroes > 31:
                raise ValueError('Invalid Exp-Golomb SPS field')
        return (1 << zeroes)-1+(self.read(zeroes) if zeroes else 0)

    def se(self):
        code = self.ue()
        return (code+1)//2 if code%2 else -code//2


def unescape(data: bytes) -> bytes:
    return re.sub(b'\x00\x00\x03(?=[\x00-\x03])', b'\x00\x00', data)


def escape(data: bytes) -> bytes:
    out = bytearray()
    zeroes = 0
    for byte in data:
        if zeroes >= 2 and byte <= 3:
            out.append(3)
            zeroes = 0
        out.append(byte)
        zeroes = zeroes+1 if byte == 0 else 0
    return bytes(out)


def signal_bounds(data: bytes) -> tuple[Bits, int, int]:
    b = Bits(unescape(data))
    profile = b.read(8)
    if profile not in (100, 128):
        raise ValueError(f'Unexpected generated AVC/MVC profile: {profile}')
    b.read(16)  # constraints and level
    b.ue()  # sps_id
    chroma = b.ue()
    if chroma == 3:
        b.read()
    b.ue(); b.ue(); b.read()  # bit depths, transform bypass
    if b.read():
        for i in range(8 if chroma != 3 else 12):
            if b.read():
                last = following = 8
                for _ in range(16 if i < 6 else 64):
                    if following:
                        following = (last+b.se()+256)%256
                    last = following or last
    b.ue()  # frame_num
    order = b.ue()
    if order == 0:
        b.ue()
    elif order == 1:
        b.read(); b.se(); b.se()
        for _ in range(b.ue()):
            b.se()
    elif order != 2:
        raise ValueError('Unexpected POC type')
    b.ue(); b.read(); b.ue(); b.ue()  # refs, gaps, width, height
    progressive = b.read()
    if not progressive:
        b.read()
    b.read()  # direct8x8
    if b.read():
        for _ in range(4):
            b.ue()
    vui_at = b.pos
    if not b.read():
        raise ValueError('Generated FRIM SPS has no VUI; refusing an untested rewrite')
    if b.read():  # aspect ratio
        if b.read(8) == 255:
            b.read(32)
    if b.read():  # overscan
        b.read()
    start = b.pos
    if b.read():
        b.read(4)  # format, full range
        if b.read():
            b.read(24)
    return b, start, b.pos


def tag_sps(nal: bytes) -> bytes:
    if not nal or nal[0]&31 not in (7, 15):
        return nal
    b, start, end = signal_bounds(nal[1:])
    # video_signal_type_present=1, format=5, limited=0, description=1, 709 IDs=1.
    signal = '1'+'101'+'0'+'1'+('00000001'*3)
    bits = (b.bits[:start]+signal+b.bits[end:]).rstrip('0')
    bits += '0'*((-len(bits))%8)
    rbsp = int(bits, 2).to_bytes(len(bits)//8, 'big')
    return nal[:1]+escape(rbsp)


def annex_nals(source, check=None, chunk_size=1024*1024):
    """Keep at most one generated NAL plus a chunk in memory, never a whole film."""
    buffer = b''
    prefix = re.compile(b'\x00\x00\x00?\x01')
    first = True
    while True:
        if check:
            check()
        chunk = source.read(chunk_size)
        buffer += chunk
        starts = list(prefix.finditer(buffer))
        if first and starts:
            if starts[0].start() != 0:
                raise ValueError('Expected generated Annex-B stream')
            first = False
        for a, b in zip(starts, starts[1:]):
            yield a.group(), buffer[a.end():b.start()]
        if len(starts) > 1:
            buffer = buffer[starts[-1].start():]
        if len(buffer) > 64*1024*1024:
            raise ValueError('Unexpected oversized generated NAL')
        if not chunk:
            if first:
                raise ValueError('Expected generated Annex-B stream')
            match = prefix.match(buffer)
            if not match:
                raise ValueError('Invalid generated Annex-B stream')
            yield match.group(), buffer[match.end():]
            break


def tag_generated_stream(path: Path, check=None) -> int:
    temporary = path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tagged')
    count = 0
    try:
        with path.open('rb') as source, temporary.open('xb') as out:
            for prefix, nal in annex_nals(source, check):
                if nal and nal[0]&31 in (7, 15):
                    count += 1
                out.write(prefix)
                out.write(tag_sps(nal))
        if not count:
            raise ValueError('Generated stream contains no parameter set')
        if check:
            check()
        os.replace(temporary, path)
        return count
    finally:
        temporary.unlink(missing_ok=True)
