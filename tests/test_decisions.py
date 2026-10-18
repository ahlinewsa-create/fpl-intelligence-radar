import unittest
from fpl_radar.decisions import decision_desk
from fpl_radar.email_report import render

class DecisionTests(unittest.TestCase):
    def squad(self):
        players=[]
        i=0
        for role,n in [('GKP',2),('DEF',5),('MID',5),('FWD',3)]:
            for _ in range(n):
                i+=1
                players.append({'id':i,'name':str(i),'position':role,'team_id':i%7+1,
                                'estimated_score':3.0,'availability':1.0,'price':5.0,'selling_price':5.0})
        return players
    def test_no_impossible_transfer(self):
        squad=self.squad()
        data=decision_desk(squad,squad,{},0,8)
        self.assertEqual(data['action'],'الاحتفاظ بالانتقال مؤقتاً')
        self.assertEqual(len(data['starting']),11)
        self.assertEqual(len(data['bench']),4)
    def test_transfer_affordability(self):
        squad=self.squad()
        candidate={'id':99,'name':'Star','position':'MID','team_id':8,'estimated_score':8.0,'availability':1.0,'price':6.0}
        forecasts={p['id']:{'weeks':{g:2 for g in range(8,13)}} for p in squad}
        forecasts[99]={'weeks':{g:8 for g in range(8,13)}}
        self.assertFalse(decision_desk(squad,squad+[candidate],forecasts,0,8)['transfers'])
        result=decision_desk(squad,squad+[candidate],forecasts,1,8)
        self.assertTrue(result['transfers'])
        self.assertEqual(result['transfers'][0]['bank_after'],0)
    def test_email_decision_render(self):
        html=render({'gameweek':8,'decision_desk':{'action':'انتقال يستحق المراجعة','starting':['A'],'bench':['B']}})
        self.assertIn('انتقال يستحق المراجعة',html)
        self.assertIn('تشكيلتك الأساسية',html)

if __name__=='__main__':unittest.main()
