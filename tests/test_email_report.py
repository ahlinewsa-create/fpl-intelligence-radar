import unittest
from email.message import EmailMessage
from unittest.mock import patch
from fpl_radar.email_report import render, send

class EmailReportTests(unittest.TestCase):
    def setUp(self):
        self.report = {'gameweek': 8, 'top_players': [{'name':'Test <Player>', 'team':'ABC', 'position':'MID', 'price':7.0, 'estimated_score':5.2}], 'captain_candidates':[{'name':'Test', 'projected_double_points':10.4, 'availability':1.0}], 'value_picks':[], 'suggested_squad':{'status':'infeasible'}, 'fixture_difficulty_next_5':{}}
    def test_rtl_and_escape(self):
        html = render(self.report)
        self.assertIn('dir="rtl"', html)
        self.assertIn('Test &lt;Player&gt;', html)
        self.assertNotIn('Test <Player>', html)
    def test_without_team(self):
        self.assertIn('تعذر الحصول', render(self.report))
    def test_missing_secrets_fails(self):
        with self.assertRaises(ValueError):
            send(self.report, smtp_host='smtp.gmail.com', smtp_port=465, username='', password='', recipient='')
    def test_unsafe_port_fails(self):
        with self.assertRaises(ValueError):
            send(self.report, smtp_host='smtp.gmail.com', smtp_port=25, username='a', password='b', recipient='c')


    def test_mobile_transfer_cards(self):
        from fpl_radar.email_report import transfer_cards
        html=transfer_cards([{'sell':'Szoboszlai','buy':'Henderson','sell_id':368,'buy_id':101,'sell_team':'LIV','buy_team':'CHE','sell_position':'MID','buy_position':'MID','old_5gw':3.75,'new_5gw':38.5,'team_gain_5gw':29.66}],provisional=True)
        self.assertIn('transfer-card',html)
        self.assertIn('#101',html)
        self.assertIn('29.66',html)
        self.assertNotIn('<table',html)

if __name__ == '__main__':
    unittest.main()
