import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fpl_radar.history import snapshot, evaluate

class HistoryTests(unittest.TestCase):
    def test_immutable(self):
        with tempfile.TemporaryDirectory() as folder:
            report={'gameweek':8,'player_forecasts_for_archive':{'10':5.25}}
            self.assertEqual(snapshot(report,folder)['status'],'saved')
            path=Path(folder)/'gw_08.json'
            self.assertEqual(json.loads(path.read_text())['predictions']['10'],5.25)
            report['player_forecasts_for_archive']['10']=100
            self.assertEqual(snapshot(report,folder)['status'],'already_saved')
            self.assertEqual(json.loads(path.read_text())['predictions']['10'],5.25)
    def test_only_finished(self):
        with tempfile.TemporaryDirectory() as folder:
            snapshot({'gameweek':8,'player_forecasts_for_archive':{'10':5}},folder)
            with patch('fpl_radar.history.get_json') as fetch:
                self.assertEqual(evaluate({'events':[{'id':8,'finished':False}]},folder)['evaluated_rounds'],0)
                fetch.assert_not_called()
    def test_accuracy_after_completed_round(self):
        with tempfile.TemporaryDirectory() as folder:
            snapshot({'gameweek':8,'player_forecasts_for_archive':{'10':5}},folder)
            with patch('fpl_radar.history.get_json',return_value={'elements':[{'id':10,'stats':{'total_points':3}}]}):
                rows=evaluate({'events':[{'id':8,'finished':True}]},folder)['rounds']
            self.assertEqual(rows[0]['mae'],2)
            self.assertEqual(rows[0]['bias'],2)

if __name__ == '__main__':
    unittest.main()
