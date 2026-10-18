import unittest
from fpl_radar.quality import audit_report

class QualityTests(unittest.TestCase):
    def test_missing_personal(self):
        out=audit_report({'multiweek_top':[]})
        self.assertEqual(out['status'],'review')
    def test_no_transfer_explanation(self):
        report={'team':{'matched_players':15,'manager':{'bank':0,'selling_prices_available':False}},
                'decision_desk':{'starting':[str(i) for i in range(11)],
                'bench':[str(i) for i in range(11,15)],'transfers':[]}}
        out=audit_report(report)
        self.assertEqual(out['status'],'ok')
        self.assertIn('أسعار البيع',report['decision_desk']['transfer_explanation'])
    def test_detect_minutes(self):
        report={'multiweek_top':[{'minutes_estimate':125}]}
        self.assertEqual(audit_report(report)['status'],'review')
    def test_chip_duplicate(self):
        report={'chip_strategy':{'history_verified':True,'recommendations':[{'chip':'wildcard'},{'chip':'wildcard'}]}}
        self.assertTrue(any('Duplicate chip' in msg for msg in audit_report(report)['warnings']))
if __name__=='__main__': unittest.main()
