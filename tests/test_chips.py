import unittest
from fpl_radar.chips import recommend_chips

class ChipTests(unittest.TestCase):
    def test_first_half_deadline(self):
        r = recommend_chips(18, [], [], {'picks': []}, [])
        self.assertEqual(r['chip_deadline_gameweek'], 19)
    def test_second_half_reset(self):
        r = recommend_chips(20, [], [], {'picks': []}, [{'name': 'wildcard', 'event': 10}], True)
        self.assertNotIn('wildcard', r['used_chips'])
        self.assertEqual(r['chip_deadline_gameweek'], 38)
    def test_unverified_history(self):
        r = recommend_chips(7, [], [], {}, [], False)
        self.assertFalse(r['history_verified'])
    def test_one_chip_per_gameweek(self):
        r = recommend_chips(19, [], [], {}, [], True)
        weeks = [x['gameweek'] for x in r['recommendations']]
        self.assertEqual(len(weeks), len(set(weeks)))
    def test_no_wildcard_from_weak_count_only(self):
        players=[{'id':i,'team_id':i,'availability':1.0,'estimated_score':1.0,'position':('GKP' if i<=2 else 'DEF' if i<=7 else 'MID' if i<=12 else 'FWD')} for i in range(1,16)]
        picks={'picks':[{'element':i} for i in range(1,16)]}
        fixtures=[{'event':8,'team_h':1,'team_a':2}]
        result=recommend_chips(8,fixtures,players,picks,[],True)
        self.assertNotIn('wildcard',[x['chip'] for x in result['recommendations']])
    def test_used_not_recommended(self):
        r = recommend_chips(19, [], [], {}, [{'name':'freehit','event':7}], True)
        self.assertNotIn('freehit', [x['chip'] for x in r['recommendations']])

if __name__ == '__main__':
    unittest.main()
