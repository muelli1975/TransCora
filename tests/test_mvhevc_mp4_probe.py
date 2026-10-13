"""Separate layer configs preserve media and adjust fast-start chunk addresses."""
import sys,struct,tempfile
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mvhevc_probe_tools import stereo_sei,layer
from mvhevc_mp4_probe import (box,boxes,pack_arrays,arrays,split_configuration,
    configure_stereo_mp4,configure_stereo_mp4_file)


def configuration():
    profile=bytes([1])+b'\x60\0\0\0'+b'\x90\0\0\0\0\0'+bytes([120])
    base_sps=b'\x42\x01\x01'+profile+b'extra'
    secondary=[b'\x42\x09secondary',b'\x44\x09secondary']
    header=bytearray(22); header[0]=1;header[1]=6;header[21]=15
    data=bytes(header)+pack_arrays([(160,b'\x40\x01vps'),(161,base_sps),(162,b'\x44\x01pps')])
    return data,secondary,profile


def find(data,kind):
    for _,name,payload in boxes(data):
        if name==kind:return payload
        if name in {b'moov',b'trak',b'mdia',b'minf',b'stbl'}:
            value=find(payload,kind)
            if value is not None:return value
    return None


class MP4ProbeTests(unittest.TestCase):
    def test_configs_describe_their_own_layers_and_base_profile(self):
        data,secondary,profile=configuration()
        base,enhancement=split_configuration(data,stereo_sei(),secondary)
        self.assertEqual(base[1:13],profile)
        self.assertTrue(all(layer(n)==0 for _,n in arrays(base)))
        self.assertEqual(enhancement[:5],b'\1'+data[13:16]+bytes([data[21]|192]))
        # Parse lhvC array section using an independent hvcC header for the table.
        parts=arrays(bytes(bytearray([1])+bytearray(21))+enhancement[5:])
        self.assertEqual({flag&63 for flag,_ in parts},{33,34})
        self.assertTrue(all(layer(n)==1 for _,n in parts))

    def movie(self,fast_start=True,wide=False,payload=b'VIDEO-AUDIO-PAYLOAD'):
        cfg,secondary,_=configuration()
        entry=box(b'hvc1',b'\0'*78+box(b'hvcC',cfg))
        stsd=box(b'stsd',b'\0'*4+struct.pack('>I',1)+entry)
        ftyp=box(b'ftyp',b'isom'+b'\0'*4)
        media=box(b'mdat',payload)
        def moov(address):
            table=box(b'co64' if wide else b'stco',b'\0'*4+struct.pack('>I',1)+address.to_bytes(8 if wide else 4,'big'))
            inner=box(b'stbl',stsd+table)
            for kind in (b'minf',b'mdia',b'trak',b'moov'):inner=box(kind,inner)
            return inner
        movie=moov(0)
        address=len(ftyp)+(len(movie) if fast_start else 0)+8
        movie=moov(address)
        return ftyp+movie+media if fast_start else ftyp+media+movie,secondary,address

    def test_fast_start_and_trailing_moov_preserve_media_and_offsets(self):
        for fast_start in (True,False):
            for wide in (True,False):
                before,secondary,address=self.movie(fast_start,wide)
                after=configure_stereo_mp4(before,stereo_sei(),secondary)
                media_before=next(p for _,k,p in boxes(before) if k==b'mdat')
                media_after=next(p for _,k,p in boxes(after) if k==b'mdat')
                self.assertEqual(media_before,media_after)
                table=find(after,b'co64' if wide else b'stco')
                actual=int.from_bytes(table[8:],'big')
                self.assertEqual(actual,address+(len(after)-len(before) if fast_start else 0))
                self.assertEqual(after[actual:actual+len(media_before)],media_before)
                self.assertIn(b'lhvC',after)

    def test_file_writer_matches_memory_writer_and_supports_in_place_update(self):
        before,secondary,_=self.movie(payload=b'large-media-block-'*200000)
        expected=configure_stereo_mp4(before,stereo_sei(),secondary)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            source=Path(folder)/'source.mp4'; target=Path(folder)/'target.mp4'
            source.write_bytes(before)
            configure_stereo_mp4_file(source,target,stereo_sei(),secondary,chunk_size=97)
            self.assertEqual(target.read_bytes(),expected)
            self.assertEqual(source.read_bytes(),before)
            configure_stereo_mp4_file(source,source,stereo_sei(),secondary,chunk_size=101)
            self.assertEqual(source.read_bytes(),expected)

    def test_stco_is_promoted_when_adjusted_offset_exceeds_32_bits(self):
        before,secondary,address=self.movie()
        near_limit=0xfffffff0
        before=before.replace(address.to_bytes(4,'big'),near_limit.to_bytes(4,'big'),1)
        after=configure_stereo_mp4(before,stereo_sei(),secondary)
        table=find(after,b'co64')
        self.assertIsNotNone(table)
        self.assertGreater(int.from_bytes(table[8:],'big'),0xffffffff)

    def test_missing_layer_configuration_is_reported(self):
        data,_,_=configuration()
        with self.assertRaises(ValueError):split_configuration(data,stereo_sei())

