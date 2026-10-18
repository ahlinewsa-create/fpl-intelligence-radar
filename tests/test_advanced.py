import unittest
from fpl_radar.advanced import player_forecasts, blank_double, manager_snapshot, transfers_with_prices, backtest, injury_watch, ownership_differentials

DATA={'elements':[{'id':1,'team':10,'status':'a','minutes':900,'starts':10,'form':'5','ep_next':'7','points_per_game':'4','expected_goals':'2.1','expected_assists':'1.5','selected_by_percent':'5.0','web_name':'Player A'}]}
FIX=[{'event':8,'team_h':10,'team_a':11,'team_h_difficulty':2},{'event':9,'team_h':10,'team_a':12,'team_h_difficulty':4}]
class AdvancedTests(unittest.TestCase):
    def test_per_week_differs(self):
        f=player_forecasts(DATA,FIX,8,2)[1]
        self.assertNotEqual(f['weeks'][8],f['weeks'][9])
    def test_blank_double(self):
        games=[{'event':8,'team_h':10,'team_a':11},{'event':8,'team_h':10,'team_a':12},{'event':9,'team_h':11,'team_a':12}]
        self.assertIn(10,blank_double(games,8,2)[0]['double_team_ids'])
    def test_bank(self):
        m=manager_snapshot({}, {'entry_history':{'bank':23,'value':1000},'picks':[]})
        self.assertEqual(m['bank'],2.3)
    def test_transfer_no_bank(self):
        self.assertEqual(transfers_with_prices([],[],{},None)['status'],'missing_bank')
    def test_backtest(self):
        self.assertEqual(backtest({'1':5},{'1':3})['mae'],2)
    def test_injury(self):
        self.assertEqual(len(injury_watch(DATA)),0)
    def test_differentials(self):
        self.assertEqual(ownership_differentials(DATA,player_forecasts(DATA,FIX,8,2))[0]['name'],'Player A')
if __name__ == '__main__':unittest.main()
