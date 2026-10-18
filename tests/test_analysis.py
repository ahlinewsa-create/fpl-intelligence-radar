import unittest
from fpl_radar.analysis import ranked_players, current_event, assess_team

DATA = {'events': [{'id': 1, 'finished': True}, {'id': 2, 'is_next': True}],
        'teams': [{'id': 1, 'short_name': 'AAA'}],
        'element_types': [{'id': 3, 'singular_name_short': 'MID'}],
        'elements': [{'id': 12, 'web_name': 'Test', 'now_cost': 75, 'team': 1,
                      'element_type': 3, 'form': '6', 'ep_next': '5', 'minutes': 900,
                      'status': 'a', 'chance_of_playing_next_round': None}]}

class RadarTests(unittest.TestCase):
    def test_event(self):
        self.assertEqual(current_event(DATA)['id'], 2)
    def test_ranking(self):
        ranked = ranked_players(DATA, [{'event': 2, 'team_h': 1, 'team_a': 2, 'team_h_difficulty': 2}], 10)
        self.assertEqual(ranked[0]['name'], 'Test')
        self.assertGreater(ranked[0]['estimated_score'], 0)
    def test_team(self):
        candidates = ranked_players(DATA, [], 10)
        self.assertEqual(assess_team({'picks': [{'element': 12}]}, candidates)['matched_players'], 1)
    def test_unavailable(self):
        d = {**DATA, 'elements': [{**DATA['elements'][0], 'chance_of_playing_next_round': 0}]}
        self.assertEqual(ranked_players(d, [], 10)[0]['estimated_score'], 0)

if __name__ == '__main__':
    unittest.main()
