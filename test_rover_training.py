import unittest
from experiments.prepare_planner_training import expected_plan, sessions
from experiments.train_planner_mlx import score
from rover_fast_navigation import planner_request


class TrainingDataTests(unittest.TestCase):
    def test_center_labels_do_not_become_search(self):
        m=dict(target_visible=True,candidate_count=1,target_clipped=False)
        p=expected_plan('center','Center the can',m)
        self.assertEqual(p['mode'],'center')
        self.assertEqual(p['height_percent'],0)
        self.assertEqual(p['uncertainties'],[])

    def test_missing_target_refusal_and_search_are_distinct(self):
        m=dict(target_visible=False,candidate_count=0)
        self.assertEqual(expected_plan('center','Center can',m)['mode'],'unsupported')
        self.assertEqual(expected_plan('approach_size','Approach to 50%',m)['mode'],'unsupported')
        self.assertEqual(expected_plan('find','Find can',m)['mode'],'find')
        self.assertEqual(expected_plan('find_approach_size','Find and approach to 50%',m)['mode'],'find_approach_size')

    def test_unsupported_labels_do_not_invent_capabilities(self):
        for kind in ('shoot','away','physical_distance'):
            self.assertEqual(expected_plan(kind,'Goal',dict(target_visible=True))['mode'],'unsupported')

    def test_clipped_approach_refuses_full_size_estimate(self):
        p=expected_plan('approach_size','Approach to 40%',dict(target_visible=True,candidate_count=1,target_clipped=True))
        self.assertEqual(p['mode'],'unsupported')
        self.assertTrue(p['uncertainties'])

    def test_sessions_group_adjacent_frames(self):
        items=[dict(id='frame-20261001-120000.controller.json'),dict(id='frame-20261001-120030.controller.json'),dict(id='frame-20261001-121000.controller.json')]
        self.assertEqual([len(x['items']) for x in sessions(items)],[2,1])

    def test_scoring_checks_schema_and_goal_without_matching_reason_text(self):
        expected=dict(mode='center',target='red soda can',height_percent=0,reason='Center',uncertainties=[])
        self.assertEqual(score(dict(expected,reason='Align the object.'),expected),[])
        self.assertTrue(score(dict(expected,mode='find'),expected))
        self.assertTrue(score(dict(expected,extra='unexpected'),expected))
        self.assertTrue(score(dict(expected,uncertainties=['unknown']),expected))

    def test_production_and_training_share_image_prompt(self):
        r=planner_request('Center red can',b'photo',dict(target_x=25))
        self.assertIn('Goal: Center red can',r['messages'][0]['content'])
        self.assertIn('"target_x": 25',r['messages'][0]['content'])
        self.assertEqual(r['messages'][0]['images'],['cGhvdG8='])


if __name__=='__main__':unittest.main()
