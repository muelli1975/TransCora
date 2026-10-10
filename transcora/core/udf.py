"""Bounded reader for the UDF 2.50 subset emitted by pinned tsMuxeR 2.6.12.

ECMA-167 descriptor layouts. Read-only: rejects unsupported allocation/map types
rather than treating arbitrary ISO input as a disc. No extraction outside caller
chosen files; used only to verify a just-generated single-film Blu-ray ISO.
"""
import binascii
import struct
from pathlib import Path

BLOCK = 2048


def u16(data, offset):
    return struct.unpack_from('<H', data, offset)[0]


def u32(data, offset):
    return struct.unpack_from('<I', data, offset)[0]


def dstring(data):
    if not data:
        return ''
    if data[0] not in (8, 16):
        raise ValueError('BD-3D: Ungültiger UDF-Dateiname.')
    return data[1:].decode('latin1' if data[0] == 8 else 'utf-16-be')


def tag(data, expected=None):
    if len(data) < 16 or (sum(data[:16])-data[4]) % 256 != data[4]:
        raise ValueError('BD-3D: UDF-Prüfsumme ungültig.')
    length = u16(data, 10)
    if len(data) < 16+length or binascii.crc_hqx(data[16:16+length], 0) != u16(data, 8):
        raise ValueError('BD-3D: UDF-Deskriptor beschädigt.')
    kind = u16(data, 0)
    if expected is not None and kind != expected:
        raise ValueError('BD-3D: Unerwartete ISO-Struktur.')
    return kind


class Disc:
    def __init__(self, path: Path):
        self.path = path
        self.size = path.stat().st_size
        self.source = path.open('rb')
        self.maps = []
        try:
            anchor = self.block(256)
            tag(anchor, 2)
            length, start = struct.unpack_from('<II', anchor, 16)
            if length > 1024*BLOCK:
                raise ValueError('BD-3D: ISO-Deskriptorbereich ungültig.')
            partition = logical = None
            for n in range(start, start+(length+BLOCK-1)//BLOCK):
                data = self.block(n)
                kind = tag(data)
                if kind == 5:
                    partition = data
                elif kind == 6:
                    logical = data
                elif kind == 8:
                    break
            if partition is None or logical is None or u32(logical, 212) != BLOCK or u16(logical, 240) != 0x250:
                raise ValueError('BD-3D: UDF 2.50 fehlt.')
            self.label = dstring(logical[84:84+logical[211]]) if logical[211] else ''
            self.partition = u32(partition, 188)
            self.partition_blocks = u32(partition, 192)
            mapping = logical[440:440+u32(logical, 264)]
            if len(mapping) > 4096:
                raise ValueError('BD-3D: UDF-Partitionskarte ungültig.')
            while mapping:
                kind, length = mapping[:2]
                entry = mapping[:length]
                if kind == 1 and length == 6:
                    self.maps.append([(0, self.partition, self.partition_blocks*BLOCK)])
                elif kind == 2 and length == 64 and entry[5:28] == b'*UDF Metadata Partition':
                    meta = self.block(self.partition+u32(entry, 40))
                    size, extents = self.allocations(meta, 0)
                    if any(part != 0 or mode != 0 for _, _, part, mode in extents):
                        raise ValueError('BD-3D: UDF-Metadatenzuordnung ungültig.')
                    mapped, offset = [], 0
                    for count, pos, _, _ in extents:
                        mapped.append((offset, self.partition+pos, count))
                        offset += count//BLOCK
                    self.maps.append(mapped)
                else:
                    raise ValueError('BD-3D: Nicht unterstützte UDF-Partitionskarte.')
                mapping = mapping[length:]
            fsd = self.block(self.physical(u16(logical, 256), u32(logical, 252)))
            tag(fsd, 256)
            self.root = (u16(fsd, 408), u32(fsd, 404))
        except BaseException:
            self.source.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.source.close()

    def block(self, position):
        return self.read(position*BLOCK, BLOCK)

    def read(self, position, length):
        if position < 0 or length < 0 or position+length > self.size:
            raise ValueError('BD-3D: ISO-Datei abgeschnitten.')
        self.source.seek(position)
        result = self.source.read(length)
        if len(result) != length:
            raise ValueError('BD-3D: ISO-Datei nicht vollständig lesbar.')
        return result

    def physical(self, partition, position):
        if not 0 <= partition < len(self.maps):
            raise ValueError('BD-3D: Ungültige UDF-Partition.')
        for first, physical, count in self.maps[partition]:
            if first <= position < first+(count+BLOCK-1)//BLOCK:
                return physical+position-first
        raise ValueError('BD-3D: UDF-Adresse außerhalb der Partition.')

    def allocations(self, entry, partition):
        kind = tag(entry)
        if kind not in (261, 266):
            raise ValueError('BD-3D: Ungültiger UDF-Dateieintrag.')
        size = struct.unpack_from('<Q', entry, 56)[0]
        base = 176 if kind == 261 else 216
        extra, count = struct.unpack_from('<II', entry, base-8)
        mode = u16(entry, 34)&7
        if mode not in (0, 1) or base+extra+count > len(entry):
            raise ValueError('BD-3D: Nicht unterstützte UDF-Dateiallokation.')
        result = []
        visited = set()
        data = entry[base+extra:base+extra+count]
        width = 8 if mode == 0 else 16
        if len(data) % width:
            raise ValueError('BD-3D: Beschädigte UDF-Dateiallokation.')
        def parse(data):
            if len(data) % width:
                raise ValueError('BD-3D: Beschädigte UDF-Dateiallokation.')
            for pos in range(0, len(data), width):
                length, block = struct.unpack_from('<II', data, pos)
                part = partition if mode == 0 else u16(data, pos+8)
                if length >> 30 == 3:
                    if (part, block) in visited or len(visited) >= 1024:
                        raise ValueError('BD-3D: Ungültige UDF-Allokationsfortsetzung.')
                    visited.add((part, block))
                    continuation = self.block(self.physical(part, block))
                    tag(continuation, 258)
                    count = u32(continuation, 20)
                    if count > BLOCK-24:
                        raise ValueError('BD-3D: Zu große UDF-Allokationsfortsetzung.')
                    parse(continuation[24:24+count])
                else:
                    result.append((length&0x3fffffff, block, part, length>>30))
        parse(data)
        return size, result

    def chunks(self, address, cancel=None):
        part, pos = address
        size, extents = self.allocations(self.block(self.physical(part, pos)), part)
        remaining = size
        for length, block, partition, mode in extents:
            if mode != 0:
                raise ValueError('BD-3D: Nicht unterstützte UDF-Fortsetzungsallokation.')
            offset = 0
            while offset < length and remaining:
                if cancel:
                    cancel()
                # Extents may cross metadata-map segments; bound each read to a block.
                n = min(1024*1024, length-offset, remaining)
                for first, _, mapped_length in self.maps[partition]:
                    current = block+offset//BLOCK
                    if first <= current < first+(mapped_length+BLOCK-1)//BLOCK:
                        n = min(n, mapped_length-(current-first)*BLOCK)
                        break
                yield self.read(self.physical(partition, block+offset//BLOCK)*BLOCK, n)
                remaining -= n
                offset += n
            if not remaining:
                break
        if remaining:
            raise ValueError('BD-3D: UDF-Dateidaten fehlen.')

    def directory(self, address):
        size, _ = self.allocations(self.block(self.physical(*address)), address[0])
        if size > 1024*1024:
            raise ValueError('BD-3D: UDF-Verzeichnis zu groß.')
        data = b''.join(self.chunks(address))
        result, pos = {}, 0
        while pos < len(data):
            entry = data[pos:]
            if len(entry) < 38:
                raise ValueError('BD-3D: UDF-Verzeichnis abgeschnitten.')
            name_len, use_len = entry[19], u16(entry, 36)
            length = (38+use_len+name_len+3)//4*4
            tag(entry[:length], 257)
            if not entry[18]&12:
                name = dstring(entry[38+use_len:38+use_len+name_len])
                result[name] = (u16(entry, 28), u32(entry, 24))
            pos += length
        return result

    def locate(self, path):
        address = self.root
        for name in path.split('/'):
            entries = self.directory(address)
            if name not in entries:
                raise ValueError('BD-3D: In der ISO fehlt ' + path)
            address = entries[name]
        return address

    def extract(self, path, destination, cancel=None):
        with destination.open('xb') as out:
            for chunk in self.chunks(self.locate(path), cancel):
                out.write(chunk)


def label_field(value, width, shorten=False):
    """OSTA compressed Unicode d-string; the final byte includes compression ID."""
    encoding = 'latin1' if all(ord(c) <= 255 for c in value) else 'utf-16-be'
    identifier = 8 if encoding == 'latin1' else 16
    if shorten:
        while len(value.encode(encoding)) > width-2:
            value = value[:-1]
    data = bytes([identifier])+value.encode(encoding)
    if len(data) >= width:
        raise ValueError('BD-3D: Disc-Titel ist für das UDF-Feld zu lang.')
    return data+b'\x00'*(width-len(data)-1)+bytes([len(data)])


def write_label(path: Path, value: str):
    """Normalize legacy muxer's label fields, including backup VDS and metadata.

    Only descriptor label bytes/CRCs change. Stream extents and coded pictures are
    untouched. Primary Volume Identifier is a shorter identifier; logical-volume
    and file-set labels retain the complete user title.
    """
    updates = {}
    with Disc(path) as disc:
        anchor = disc.block(256)
        logical = None
        for offset in (16, 24):
            length, start = struct.unpack_from('<II', anchor, offset)
            if length > 1024*BLOCK:
                raise ValueError('BD-3D: ISO-Deskriptorbereich ungültig.')
            for position in range(start, start+(length+BLOCK-1)//BLOCK):
                data = disc.block(position)
                kind = tag(data)
                if kind == 8:
                    break
                if kind == 1:
                    updates[position] = (24, label_field(value, 32, shorten=True))
                elif kind == 4 and data[21:33] == b'*UDF LV Info':
                    updates[position] = (116, label_field(value, 128))
                elif kind == 6:
                    updates[position] = (84, label_field(value, 128))
                    logical = data
        if logical is None:
            raise ValueError('BD-3D: ISO-Beschriftungsstruktur fehlt.')
        fsd_position, fsd_partition = u32(logical, 252), u16(logical, 256)
        updates[disc.physical(fsd_partition, fsd_position)] = (112, label_field(value, 128))
        # The metadata mirror repeats the file-set descriptor. Update that copy too.
        maps = logical[440:440+u32(logical, 264)]
        index = 0
        while maps:
            length = maps[1]
            entry = maps[:length]
            if index == fsd_partition and entry[0] == 2:
                mirror_location = u32(entry, 44)
                if mirror_location != 0xffffffff:
                    mirror = disc.block(disc.partition+mirror_location)
                    _, extents = disc.allocations(mirror, 0)
                    offset = fsd_position
                    for count, block, part, mode in extents:
                        if part != 0 or mode != 0:
                            raise ValueError('BD-3D: UDF-Metadatenspiegel ungültig.')
                        if offset < (count+BLOCK-1)//BLOCK:
                            position = disc.partition+block+offset
                            tag(disc.block(position), 256)
                            updates[position] = (112, label_field(value, 128))
                            break
                        offset -= (count+BLOCK-1)//BLOCK
                    else:
                        raise ValueError('BD-3D: UDF-Metadatenspiegel unvollständig.')
            maps = maps[length:]
            index += 1
        # Read and validate before changing any descriptor.
        descriptors = {}
        for position, (offset, field) in updates.items():
            data = bytearray(disc.block(position))
            tag(data)
            data[offset:offset+len(field)] = field
            crc_length = u16(data, 10)
            struct.pack_into('<H', data, 8, binascii.crc_hqx(data[16:16+crc_length], 0))
            data[4] = (sum(data[:16])-data[4]) % 256
            tag(data)
            descriptors[position] = data
    with path.open('r+b') as out:
        for position, data in descriptors.items():
            out.seek(position*BLOCK)
            out.write(data)
