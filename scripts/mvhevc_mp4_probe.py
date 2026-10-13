"""Development remux: separate hvcC/lhvC, preserving all media bytes.

Reference: Apple HEVC Stereo Video Interoperability Profile (hvc1, hvcC/lhvC).
The file API keeps only the movie metadata in memory. It is not yet connected to
TransCora exports.
"""
import os
from pathlib import Path
import struct
import tempfile


def box(kind, payload):
    return struct.pack('>I4s', len(payload)+8, kind)+payload


def boxes(data):
    offset = 0
    while offset < len(data):
        if len(data)-offset < 8:
            raise ValueError('Truncated MP4 box')
        size, kind = struct.unpack_from('>I4s', data, offset)
        header = 8
        if size == 1:
            if len(data)-offset < 16:
                raise ValueError('Truncated extended MP4 box')
            size = struct.unpack_from('>Q', data, offset+8)[0]; header = 16
        elif size == 0:
            size = len(data)-offset
        if size < header or offset+size > len(data):
            raise ValueError('Invalid MP4 box size')
        yield offset, kind, data[offset+header:offset+size]
        offset += size


def arrays(data):
    if len(data) < 23 or data[0] != 1:
        raise ValueError('Expected version-one hvcC')
    offset = 23; result = []
    for _ in range(data[22]):
        if offset+3 > len(data): raise ValueError('Truncated configuration array')
        flag, count = struct.unpack_from('>BH', data, offset); offset += 3
        for _ in range(count):
            if offset+2 > len(data): raise ValueError('Truncated configuration NAL')
            size = struct.unpack_from('>H', data, offset)[0]; offset += 2
            nal = data[offset:offset+size]; offset += size
            if len(nal) != size or len(nal) < 2: raise ValueError('Invalid configuration NAL')
            result.append((flag, nal))
    if offset != len(data): raise ValueError('Unexpected configuration trailing bytes')
    return result


def pack_arrays(items):
    grouped = {}
    for flag, nal in items:
        values = grouped.setdefault(flag, [])
        if nal not in values: values.append(nal)
    return bytes([len(grouped)])+b''.join(struct.pack('>BH',flag,len(values))+
        b''.join(struct.pack('>H',len(nal))+nal for nal in values) for flag,values in grouped.items())


def split_configuration(data, sei, secondary_nals=()):
    from mvhevc_probe_tools import layer
    items = arrays(data)
    base = [(flag, nal) for flag,nal in items if layer(nal) == 0]
    secondary = [(flag, nal) for flag,nal in items if layer(nal) == 1]
    secondary.extend((128|((nal[0]>>1)&63),nal) for nal in secondary_nals
                     if layer(nal)==1 and (nal[0]>>1)&63 in (33,34))
    if not {32,33,34}.issubset({flag&63 for flag,_ in base}) or not {33,34}.issubset({flag&63 for flag,_ in secondary}):
        raise ValueError('Both layers need their parameter sets')
    if any(layer(nal) not in (0,1) for _,nal in items):
        raise ValueError('This probe handles exactly two layers')
    sps = next(nal for flag,nal in base if flag&63 == 33)
    rbsp = sps[2:].replace(b'\0\0\3',b'\0\0')
    if len(rbsp) < 13: raise ValueError('Truncated base SPS profile')
    # hvcC describes the base SPS, rather than the highest profile of both layers.
    header = bytearray(data[:22]); header[1:13] = rbsp[1:13]
    base = [(flag,nal) for flag,nal in base if (flag&63)!=39 or nal!=sei]
    base.append((39,sei))
    hvcc = bytes(header)+pack_arrays(base)
    # LHEVCDecoderConfigurationRecord omits the base profile/chroma/depth fields.
    lhvc = bytes([1])+data[13:16]+bytes([data[21]|192])+pack_arrays(secondary)
    return hvcc, lhvc


def _configured_moov(old_moov, old_size, old_end, sei, secondary_nals=()):
    containers = {b'moov',b'trak',b'mdia',b'minf',b'stbl',b'dinf'}
    changed = 0
    def rewrite(kind, payload, delta=0):
        nonlocal changed
        if kind in containers:
            return box(kind,b''.join(rewrite(k,p,delta) for _,k,p in boxes(payload)))
        if kind == b'stsd':
            return box(kind,payload[:8]+b''.join(rewrite(k,p,delta) for _,k,p in boxes(payload[8:])))
        if kind == b'hvc1':
            children=[]
            for _,k,p in boxes(payload[78:]):
                if k==b'hvcC':
                    hvcc,lhvc=split_configuration(p,sei,secondary_nals)
                    children.extend([box(k,hvcc),box(b'lhvC',lhvc)]); changed+=1
                elif k!=b'lhvC': children.append(box(k,p))
            return box(kind,payload[:78]+b''.join(children))
        if kind in (b'stco',b'co64') and delta:
            size = 4 if kind==b'stco' else 8
            count = struct.unpack_from('>I',payload,4)[0]
            if len(payload)!=8+count*size: raise ValueError('Invalid chunk-offset table')
            values=[int.from_bytes(payload[8+i*size:8+(i+1)*size],'big') for i in range(count)]
            values=[v+delta if v>=old_end else v for v in values]
            if any(v < 0 for v in values): raise ValueError('Negative chunk offset')
            if kind==b'stco' and any(v>0xffffffff for v in values):
                kind=b'co64'; size=8
            return box(kind,payload[:8]+b''.join(v.to_bytes(size,'big') for v in values))
        return box(kind,payload)
    first = rewrite(b'moov',old_moov)
    if changed!=1: raise ValueError('This probe expects one hvc1 sample entry')
    delta=len(first)-old_size
    for _ in range(4):
        changed=0; new_moov=rewrite(b'moov',old_moov,delta)
        if changed!=1: raise ValueError('This probe expects one hvc1 sample entry')
        new_delta=len(new_moov)-old_size
        if new_delta==delta: return new_moov
        delta=new_delta
    raise ValueError('Chunk-offset rewrite did not stabilize')


def _root_boxes(data):
    roots=list(boxes(data))
    if sum(kind==b'moov' for _,kind,_ in roots)!=1:
        raise ValueError('Expected exactly one movie box')
    result=[]
    for index,(offset,kind,payload) in enumerate(roots):
        end=roots[index+1][0] if index+1<len(roots) else len(data)
        result.append((offset,end-offset,kind,payload))
    return result


def configure_stereo_mp4(data, sei, secondary_nals=()):
    roots=_root_boxes(data)
    moov_offset,old_size,_,old_moov=next(item for item in roots if item[2]==b'moov')
    new_moov=_configured_moov(old_moov,old_size,moov_offset+old_size,sei,secondary_nals)
    return b''.join(new_moov if kind==b'moov' else data[offset:offset+size]
                    for offset,size,kind,_ in roots)


def _file_boxes(handle):
    handle.seek(0,os.SEEK_END); total=handle.tell(); offset=0
    while offset<total:
        handle.seek(offset); header=handle.read(8)
        if len(header)!=8: raise ValueError('Truncated MP4 box')
        size,kind=struct.unpack('>I4s',header); header_size=8
        if size==1:
            extra=handle.read(8)
            if len(extra)!=8: raise ValueError('Truncated extended MP4 box')
            size=struct.unpack('>Q',extra)[0]; header_size=16
        elif size==0:
            size=total-offset
        if size<header_size or offset+size>total:
            raise ValueError('Invalid MP4 box size')
        yield offset,size,kind,header_size
        offset+=size


def _copy_range(source,target,offset,size,chunk_size):
    source.seek(offset)
    while size:
        block=source.read(min(size,chunk_size))
        if not block: raise ValueError('Truncated MP4 while copying')
        target.write(block); size-=len(block)


def configure_stereo_mp4_file(source, destination, sei, secondary_nals=(), chunk_size=1024*1024):
    """Rewrite one MP4 atomically while streaming every non-metadata box."""
    if chunk_size<1: raise ValueError('chunk_size must be positive')
    source=Path(source); destination=Path(destination)
    with source.open('rb') as handle:
        roots=list(_file_boxes(handle))
        movies=[item for item in roots if item[2]==b'moov']
        if len(movies)!=1: raise ValueError('Expected exactly one movie box')
        moov_offset,old_size,_,header_size=movies[0]
        handle.seek(moov_offset+header_size)
        old_moov=handle.read(old_size-header_size)
        if len(old_moov)!=old_size-header_size: raise ValueError('Truncated movie box')
        new_moov=_configured_moov(old_moov,old_size,moov_offset+old_size,sei,secondary_nals)
    destination.parent.mkdir(parents=True,exist_ok=True)
    fd,temporary=tempfile.mkstemp(prefix=destination.name+'.',suffix='.tmp',dir=destination.parent)
    try:
        with source.open('rb') as input_file,os.fdopen(fd,'wb') as output_file:
            fd=-1
            for offset,size,kind,_ in roots:
                if kind==b'moov': output_file.write(new_moov)
                else: _copy_range(input_file,output_file,offset,size,chunk_size)
            output_file.flush(); os.fsync(output_file.fileno())
        os.replace(temporary,destination)
    except Exception:
        if fd>=0: os.close(fd)
        try: os.unlink(temporary)
        except FileNotFoundError: pass
        raise

