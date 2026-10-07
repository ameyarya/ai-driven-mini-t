import unittest
from camera_orientation import video_filter, standoff_limit
from unittest.mock import patch
class OrientationTests(unittest.TestCase):
 def test_portrait_keeps_long_edge_at_640(self):
  self.assertEqual(video_filter(90),'transpose=1,scale=-2:640')
  self.assertEqual(video_filter(270),'transpose=2,scale=-2:640')
 def test_landscape_and_inverted(self):
  self.assertEqual(video_filter(0),'scale=640:-2')
  self.assertEqual(video_filter(180),'hflip,vflip,scale=640:-2')
 def test_rotation_preserves_short_edge_standoff(self):
  with patch('camera_orientation.rotation',return_value=90):self.assertEqual(standoff_limit(),11.25)
  with patch('camera_orientation.rotation',return_value=0):self.assertEqual(standoff_limit(),8.43)
 def test_invalid_rotation(self):
  with self.assertRaises(ValueError):video_filter(45)
