import tempfile
import threading
import unittest
from pathlib import Path
from rover_elevation import ElevationCalibration

class ElevationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.c=ElevationCalibration(Path(self.temp.name)/'height.json')
 def shot(self,ident,height,position):
  return dict(id=ident,fire_command_sent=True,reset_acknowledged=True,elevation=dict(reference_confirmed=True,target='bullseye target',height_percent=height,position_ms=position))
 def points(self):
  self.c.confirm_reference();self.c.save_hit(self.shot('one',15,0));self.c.save_hit(self.shot('two',20,100))
 def test_requires_reference_and_one_successful_shot(self):
  with self.assertRaises(ValueError):self.c.enable()
  self.c.confirm_reference()
  with self.assertRaises(ValueError):self.c.enable()
  self.c.save_hit(self.shot('one',15,0))
  self.c.enable();self.assertTrue(self.c.enabled)
 def test_saved_distance_and_range_rejection(self):
  self.points();self.c.enable();self.assertEqual(self.c.desired(20),100)
  for height in (11,24,float('nan'),None):
   with self.assertRaises(ValueError):self.c.desired(height)
 def test_restart_retains_points_but_requires_reference(self):
  self.points();self.c.enable();new=ElevationCalibration(self.c.path)
  self.assertEqual(len(new.data['points']),2);self.assertIsNone(new.position);self.assertFalse(new.enabled)
  with self.assertRaises(ValueError):new.enable()
 def test_bounded_motion_stops(self):
  self.c.confirm_reference();calls=[];self.c.move(50,calls.append,threading.Event())
  self.assertEqual(self.c.position,50);self.assertEqual(calls,[-1,0,0])
  with self.assertRaises(ValueError):self.c.move(601,calls.append,threading.Event())
 def test_cancel_invalidates_reference(self):
  self.c.confirm_reference();token=threading.Event();token.set();calls=[]
  with self.assertRaises(ValueError):self.c.move(50,calls.append,token)
  self.assertEqual(calls,[0]);self.assertIsNone(self.c.position)
 def test_command_failure_invalidates(self):
  self.c.confirm_reference()
  def fail(value):
   if value:raise OSError('No acknowledgment')
  with self.assertRaises(OSError):self.c.move(50,fail,threading.Event())
  self.assertIsNone(self.c.position)
 def test_save_requires_acknowledged_shot_and_unique_id(self):
  self.points()
  self.c.save_hit(self.shot('one',15,0));self.assertEqual(self.c.desired(15),0)
  with self.assertRaises(ValueError):self.c.save_hit(dict(self.shot('bad',20,0),fire_command_sent=False))
  with self.assertRaises(ValueError):self.c.save_hit(dict(self.shot('bad',20,0),elevation={}))

if __name__=='__main__':unittest.main()
