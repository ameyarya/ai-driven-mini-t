import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch

import rover_playground as p


class PlaygroundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.frames = self.root / 'frames'
        self.frames.mkdir()
        (self.frames / 'raw.jpg').write_bytes(b'raw-image')
        (self.frames / 'label.jpg').write_bytes(b'labeled-image')
        self.record = dict(frame='/old/path/raw.jpg', model_frame='/old/path/label.jpg',
                           detector=dict(target_visible=True, target_x=30, target_height=10),
                           input_sha256=hashlib.sha256(b'labeled-image').hexdigest(), goal='Center the red can')
        (self.frames / 'old.controller.json').write_text(json.dumps(self.record))
        self.data_patch = patch.object(p, 'DATA', self.root / 'data')
        self.data_patch.start()

    def tearDown(self):
        self.data_patch.stop()
        self.temp.cleanup()

    def test_catalog_resolves_moved_paths_and_rejects_hash_mismatch(self):
        self.assertEqual(len(p.catalog(self.frames)), 1)
        (self.frames / 'label.jpg').write_bytes(b'changed')
        self.assertEqual(p.catalog(self.frames), {})

    def test_infer_preserves_originals_and_never_captures(self):
        item = next(iter(p.catalog(self.frames).values()))
        original = (self.frames / 'old.controller.json').read_bytes()
        response = dict(model='test', message=dict(content=json.dumps(dict(
            mode='center', target='red can', height_percent=0, reason='Center', uncertainties=[]))))
        with patch.object(p.navigation.vision, 'read_json', return_value=response) as request, \
                patch.object(p.navigation.vision, 'capture_frame', side_effect=AssertionError('Camera accessed')):
            result = p.infer(item, 'Center the red can')
        self.assertEqual(result['plan']['mode'], 'center')
        body = request.call_args.args[1]
        self.assertEqual(p.base64.b64decode(body['messages'][0]['images'][0]), b'labeled-image')
        self.assertIn('Translate this toy rover goal', result['prompt'])
        self.assertEqual((self.frames / 'old.controller.json').read_bytes(), original)
        self.assertFalse(result['motor_commands_sent'])
        self.assertFalse((self.frames / 'raw.plan.json').exists())

    def test_export_requires_review_and_uses_official_format(self):
        items = p.catalog(self.frames)
        item = next(iter(items.values()))
        run = p.DATA / 'runs' / ('a' * 32)
        run.mkdir(parents=True)
        result = dict(id=run.name, source=item['id'], image_sha256=item['sha256'],
                      goal='Center the red can', prompt='Test prompt')
        (run / 'result.json').write_text(json.dumps(result))
        self.assertEqual(p.export_dataset(items)['train'], 0)
        expected = dict(mode='center', target='red can', height_percent=0, reason='Center', uncertainties=[])
        p.review(run.name, expected)
        counts = p.export_dataset(items)
        self.assertEqual(counts['train'] + counts['validation'], 1)
        examples = json.loads((p.DATA / 'dataset/train.json').read_text()) + json.loads((p.DATA / 'dataset/validation.json').read_text())
        self.assertEqual(examples[0]['conversations'][0], {'from':'human','value':'<image>\nTest prompt'})
        self.assertEqual(json.loads(examples[0]['conversations'][1]['value']), expected)
        self.assertTrue((p.DATA / 'dataset' / examples[0]['image']).exists())

    def test_same_raw_frame_cannot_cross_splits(self):
        items = p.catalog(self.frames)
        item = next(iter(items.values()))
        for c in ('a', 'b'):
            run = p.DATA / 'runs' / (c * 32)
            run.mkdir(parents=True)
            (run / 'result.json').write_text(json.dumps(dict(id=run.name,source=item['id'],
                image_sha256=item['sha256'], goal='Center the red can', prompt='Test',
                expected=dict(mode='center', target='red can',height_percent=0,reason='OK',uncertainties=[]))))
        counts = p.export_dataset(items)
        self.assertIn(2, (counts['train'], counts['validation']))

    def test_concurrent_inferences_keep_prompts_isolated(self):
        item = next(iter(p.catalog(self.frames).values()))
        entered = threading.Event()
        release = threading.Event()
        goals = ['Center red can', 'Center soda can']
        calls = []

        def transport(url, body=None, timeout=5):
            calls.append(body['messages'][0]['content'])
            if len(calls) == 1:
                entered.set()
                self.assertTrue(release.wait(3))
            return dict(model='test', message=dict(content=json.dumps(dict(
                mode='center', target='red can', height_percent=0, reason='Center', uncertainties=[]))))

        with patch.object(p.navigation.vision, 'read_json', side_effect=transport), ThreadPoolExecutor(2) as pool:
            first = pool.submit(p.infer, item, goals[0])
            self.assertTrue(entered.wait(3))
            second = pool.submit(p.infer, item, goals[1])
            # Wait until the second request has created its private run and is
            # blocked on the first request, which still owns the patched globals.
            deadline = time.monotonic() + 3
            while len(list((p.DATA / 'runs').glob('*/frame.jpg'))) < 2 and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertEqual(len(list((p.DATA / 'runs').glob('*/frame.jpg'))), 2)
            release.set()
            results = [first.result(timeout=3), second.result(timeout=3)]
        for goal, result in zip(goals, results):
            self.assertNotIn('error', result)
            self.assertIn('Goal: ' + goal, result['prompt'])
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(results[0]['prompt'], results[1]['prompt'])

    def test_export_rejects_changed_reviewed_input(self):
        items = p.catalog(self.frames)
        item = next(iter(items.values()))
        run = p.DATA / 'runs' / ('a' * 32)
        run.mkdir(parents=True)
        (run / 'result.json').write_text(json.dumps(dict(source=item['id'],
            image_sha256='wrong', expected={}, id=run.name)))
        with self.assertRaisesRegex(ValueError, 'changed'):
            p.export_dataset(items)

    def test_invalid_review_values_are_rejected(self):
        valid = dict(mode='center',target='can',height_percent=0,reason='OK',uncertainties=[])
        for bad in [dict(valid,height_percent=True),dict(valid,height_percent=float('nan')),
                    dict(valid,uncertainties=[42]),dict(valid,reason='x'*121),dict(valid,extra='field')]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                p.validate_label(bad, 'Center can')

    def test_planner_cannot_convert_center_or_physical_distance_to_search(self):
        plan = dict(mode='find',target='red can',height_percent=0,reason='Search',uncertainties=[])
        for goal in ('Center the red can in the image, then stop.',
                     'Move within 20 centimeters of the red can.',
                     'Move within 20 cm of the red can.'):
            with self.subTest(goal=goal), self.assertRaises(ValueError):
                p.navigation.validate_plan(plan, goal)

    def test_bad_review_cannot_discard_requested_search(self):
        with self.assertRaises(ValueError):
            p.validate_label(dict(mode='center',target='can',height_percent=0,reason='OK',uncertainties=[]), 'Find the red can by doing a 360 turn')
        with self.assertRaises(ValueError):
            p.review('../secret', {})


if __name__ == '__main__':
    unittest.main()
