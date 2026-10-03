import hashlib
import json
from pathlib import Path
import tempfile
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

    def test_bad_review_cannot_discard_requested_search(self):
        with self.assertRaises(ValueError):
            p.validate_label(dict(mode='center',target='can',height_percent=0,reason='OK',uncertainties=[]), 'Find the red can by doing a 360 turn')
        with self.assertRaises(ValueError):
            p.review('../secret', {})


if __name__ == '__main__':
    unittest.main()
