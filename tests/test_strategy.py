import unittest
from fpl_radar.strategy import fixture_matrix, team_strength, captains, starting_eleven, suggested_squad, transfer_ideas

def pool():
    result = []
    for pos, qty in [('GKP', 2), ('DEF', 5), ('MID', 5), ('FWD', 3)]:
        for i in range(qty + 3):
            idx = len(result) + 1
            price = 4.0 + i * .1
            score = 3 + i * .2
            result.append(dict(id=idx, name=str(idx), position=pos, price=price,
                               team_id=(idx % 8) + 1, estimated_score=score,
                               value=score / price, availability=1.0))
    return result

class StrategyTests(unittest.TestCase):
    def test_double_gameweek(self):
        games = [{'event': 10, 'team_h': 1, 'team_a': 2, 'team_h_difficulty': 2},
                 {'event': 10, 'team_h': 1, 'team_a': 3, 'team_h_difficulty': 4}]
        self.assertEqual(fixture_matrix(games, 10)['1']['10'], [2, 4])
    def test_captain(self):
        self.assertEqual(captains(pool(), 1)[0]['projected_double_points'], 8.8)
    def test_squad(self):
        selection = suggested_squad(pool())
        self.assertEqual(selection['status'], 'ok')
        self.assertLessEqual(selection['cost'], 100)
        self.assertEqual(len(selection['lineup']['starting_ids']), 11)
    def test_unaffordable(self):
        self.assertEqual(suggested_squad(pool(), 20)['status'], 'infeasible')
    def test_transfer_rules(self):
        ids = {x['id'] for x in suggested_squad(pool())['players']}
        current = [x for x in pool() if x['id'] in ids]
        for trade in transfer_ideas(current, pool()):
            old = next(x for x in pool() if x['id'] == trade['sell_id'])
            new = next(x for x in pool() if x['id'] == trade['buy_id'])
            self.assertEqual(old['position'], new['position'])
    def test_team_strength(self):
        self.assertEqual(team_strength({'teams': [{'id': 1, 'name': 'A', 'strength_attack_home': 120,
                              'strength_attack_away': 110}]})[0]['team'], 'A')

if __name__ == '__main__':
    unittest.main()
