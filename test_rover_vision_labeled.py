import base64
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import rover_vision
from rover_detector import progress


class LabeledInputTests(unittest.TestCase):
    def test_labeled_bytes_not_raw_are_sent_and_published(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)/'frame-test.jpg'
            labeled = Path(directory)/'frame-test-labeled.jpg'
            raw.write_bytes(b'original camera bytes')
            labeled.write_bytes(b'detector labeled bytes with numeric measurements')
            measurement = {'target_visible':True,'target_bbox':[200,200,400,500],
                           'target_x':30.0,'target_height':30.0,'target_clipped':False,
                           'target_confidence':.8,'candidate_count':1,'source':'YOLO-World'}
            history = [{'action':'left','duration_ms':50,'target_x_before':29.9,'target_height_before':30}]
            prepared = {'model_frame':str(labeled),'measurement':measurement,'movement_feedback':progress(measurement,history)}
            decision = {'suggested_action':'left','duration_ms':250,'goal_achieved':False,'reason':'Increase ineffective turn','uncertainties':[]}
            def respond(url, body=None, timeout=5):
                self.assertEqual(base64.b64decode(body['messages'][0]['images'][0]),labeled.read_bytes())
                prompt=body['messages'][0]['content']
                self.assertIn('CURRENT MEASUREMENTS',prompt)
                self.assertIn('center_change_percent',prompt)
                self.assertIn('increase the duration',prompt)
                self.assertEqual(rover_vision.input_snapshot()['state'],'analyzing')
                return {'message':{'content':json.dumps(decision)},'model':'test','done_reason':'stop'}
            with patch.object(rover_vision,'prepare_detector_image',return_value=prepared),patch.object(rover_vision,'read_json',side_effect=respond):
                assessment,_,_,timings=rover_vision.analyze_image('position can in center',raw,True,history)
            self.assertEqual(assessment['duration_ms'],250)
            self.assertEqual(assessment['target_bbox'],measurement['target_bbox'])
            self.assertEqual(timings['input_sha256'],hashlib.sha256(labeled.read_bytes()).hexdigest())
            self.assertEqual(rover_vision.input_snapshot()['result']['input_sha256'],timings['input_sha256'])
            self.assertEqual(rover_vision.input_snapshot()['state'],'done')

    def test_centering_progress_is_not_uncertainty(self):
        observation={'target_visible':True,'target_x':29.25,
                     'uncertainties':['Target is not centered; continue adjusting.']}
        decision=rover_vision.centering_decision(observation)
        self.assertEqual(decision['suggested_action'],'left')
        self.assertEqual(decision['uncertainties'],[])
        self.assertFalse(decision['goal_achieved'])
        observation['uncertainties'].append('Target partially hidden; location unclear')
        decision=rover_vision.centering_decision(observation)
        self.assertEqual(decision['suggested_action'],'stop')
        self.assertEqual(decision['uncertainties'],['Target partially hidden; location unclear'])

    def test_feedback_measures_actual_change(self):
        feedback=progress({'target_x':34.1,'target_height':25},[{'action':'left','duration_ms':50,'target_x_before':34,'target_height_before':24}])
        self.assertEqual(feedback['center_change_percent'],.1)
        self.assertEqual(feedback['height_change_percent'],1)
        self.assertIsNone(progress({'target_x':None},[]) )


if __name__=='__main__':unittest.main()
