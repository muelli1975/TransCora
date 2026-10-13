"""Stereo signalling preserves picture NALs and carries no invented geometry."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mvhevc_probe_tools import annexb_nals, picture_counts, signal_stereo, stereo_sei, consolidate_headers


class ProbeSignallingTests(unittest.TestCase):
    def test_duplicate_prefix_does_not_split_the_first_stereo_pair(self):
        header=[b'\x40\x01h',b'\x42\x01s',b'\x42\x09s',b'\x44\x01p',b'\x44\x09p']
        left,right=b'\x28\x01\x80left',b'\x28\x09\x80right'
        raw=b''.join(b'\0\0\1'+n for n in [*header,left,*header,right])
        result=consolidate_headers(raw)
        self.assertEqual(annexb_nals(result),[*header,left,right])
        self.assertEqual(picture_counts(result),{'0':1,'1':1})

    def test_different_prefix_is_never_silently_removed(self):
        nals=[b'\x40\x01h',b'\x28\x01\x80left',b'\x40\x01changed',b'\x28\x09\x80right']
        raw=b''.join(b'\0\0\1'+n for n in nals)
        self.assertEqual(annexb_nals(consolidate_headers(raw)),nals)

    def test_picture_data_and_layer_order_are_preserved(self):
        pictures=[b'\x28\x01\x80ab',b'\x28\x09\x80cd',b'\x02\x01\x80ef',b'\x02\x09\x80gh']
        raw=b''.join(b'\0\0\1'+n for n in [b'\x40\x01\xaa',*pictures])
        result=signal_stereo(raw)
        nals=annexb_nals(result)
        self.assertEqual(nals[2:],pictures)
        self.assertEqual(picture_counts(result),{'0':2,'1':2})
        self.assertEqual(nals[1],stereo_sei())

    def test_width_unspecified_and_only_left_right_ids_are_signalled(self):
        nal=stereo_sei()
        self.assertEqual(nal[:4],b'\x4e\x01\xb0\x04')
        payload=nal[4:-1].replace(b'\0\0\3',b'\0\0')
        bits=''.join(f'{v:08b}' for v in payload)
        def read_ue():
            nonlocal bits
            zeros=len(bits)-len(bits.lstrip('0'))
            value=int(bits[zeros:2*zeros+1],2)-1
            bits=bits[2*zeros+1:]
            return value
        self.assertEqual(read_ue(),31)
        self.assertEqual(bits[0],'0'); bits=bits[1:]
        self.assertEqual(read_ue(),0)
        self.assertEqual(read_ue(),0)
        self.assertEqual(read_ue(),1)
        self.assertEqual(bits[:9],'000000000')

    def test_multiple_slices_count_as_one_picture(self):
        self.assertEqual(picture_counts(b'\0\0\1\x02\x01\x80\0\0\1\x02\x01\x40'),{'0':1})

    def test_malformed_stream_and_equal_view_ids_are_rejected(self):
        for data in (b'',b'\0\0\1\x28',b'\0\0\1\x40\x01a'):
            with self.assertRaises(ValueError): signal_stereo(data)
        with self.assertRaises(ValueError): stereo_sei(0,0)
