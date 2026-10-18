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

if __name__ == '__main__':
    unittest.main()
