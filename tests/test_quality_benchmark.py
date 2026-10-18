import unittest
from fpl_radar.quality import benchmark_forecasts

class BenchmarkTests(unittest.TestCase):
    def test_no_hindsight_claim(self):
        data={'elements':[{'id':1,'web_name':'A','ep_next':'5.0'}, {'id':2,'web_name':'B','ep_next':None}]}
        results=benchmark_forecasts(data,{1:{'weeks':{8:4.0}}},8)
        self.assertEqual(results['n'],1)
        self.assertEqual(results['mean_absolute_disagreement'],1.0)
        self.assertIn('does not measure predictive accuracy', results['note'])
    def test_missing_inputs(self):
        self.assertIsNone(benchmark_forecasts({'elements':[]},{},8)['mean_absolute_disagreement'])
if __name__ == '__main__':
    unittest.main()
