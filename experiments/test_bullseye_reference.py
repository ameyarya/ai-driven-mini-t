"""Synthetic reference-matching regressions; run with .detector-venv/bin/python."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
import cv2
import numpy as np
from rover_detector import bullseye_candidates

class BullseyeReferenceTests(unittest.TestCase):
    def setUp(self):
        self.reference=np.full((96,96,3),180,np.uint8)
        cv2.circle(self.reference,(48,48),35,(15,15,15),9)
        cv2.circle(self.reference,(48,48),10,(15,15,15),-1)
        cv2.line(self.reference,(16,23),(27,19),(15,15,15),3)
    def scene(self,size=60,angle=0,second=False):
        frame=np.full((240,400,3),220,np.uint8)
        matrix=cv2.getRotationMatrix2D((48,48),angle,1)
        rotated=cv2.warpAffine(self.reference,matrix,(96,96),borderMode=cv2.BORDER_REPLICATE)
        patch=cv2.resize(rotated,(size,size));frame[90:90+size,60:60+size]=patch
        if second:frame[90:90+size,260:260+size]=patch
        return frame
    def test_scale_and_tilt(self):
        for size,angle in [(30,0),(60,-15),(96,15)]:
            with self.subTest(size=size,angle=angle):
                boxes=bullseye_candidates(self.scene(size,angle),self.reference)
                self.assertEqual(len(boxes),1)
                x1,y1,x2,y2=boxes[0]['bbox']
                self.assertLess(abs((x1+x2)/2-(60+size/2)/400*1000),25)
    def test_duplicates_remain_ambiguous(self):
        self.assertEqual(len(bullseye_candidates(self.scene(second=True),self.reference)),2)
    def test_absent_and_missing_reference(self):
        self.assertEqual(bullseye_candidates(np.full((240,400,3),220,np.uint8),self.reference),[])
        with self.assertRaises(ValueError):bullseye_candidates(self.scene(),None)

if __name__=='__main__':unittest.main()
