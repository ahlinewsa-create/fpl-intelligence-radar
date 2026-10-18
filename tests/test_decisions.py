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
    def test_provisional_watchlist(self):
        squad=self.squad()
        for p in squad:p.pop('selling_price')
        candidate={'id':99,'name':'Star','position':'MID','team_id':8,'estimated_score':8.0,'availability':1.0,'price':5.0}
        forecasts={p['id']:{'weeks':{g:2 for g in range(8,13)}} for p in squad}
        forecasts[99]={'weeks':{g:8 for g in range(8,13)}}
        result=decision_desk(squad,squad+[candidate],forecasts,0,8)
        self.assertFalse(result['transfers'])
        self.assertTrue(result['watchlist'])
        self.assertIsNone(result['best_transfer'])
    def test_injured_target_is_excluded(self):
        squad=self.squad()
        candidate={'id':99,'name':'Injured','position':'MID','team_id':8,'estimated_score':8,'availability':1,'fpl_status':'d','chance_of_playing_next_round':50,'price':5}
        forecasts={p['id']:{'weeks':{g:2 for g in range(8,13)}} for p in squad}
        forecasts[99]={'weeks':{g:8 for g in range(8,13)}}
        result=decision_desk(squad,squad+[candidate],forecasts,1,8)
        self.assertFalse(result['transfers'])
        self.assertFalse(result['watchlist'])
    def test_transfer_components_sum_to_gain(self):
        squad=self.squad()
        target={'id':99,'name':'Star','position':'MID','team_id':8,'estimated_score':8,'availability':1,'fpl_status':'a','price':5}
        forecasts={p['id']:{'weeks':{g:2 for g in range(8,13)}} for p in squad}
        forecasts[99]={'weeks':{g:8 for g in range(8,13)}}
        move=decision_desk(squad,squad+[target],forecasts,0,8)['transfers'][0]
        self.assertEqual(move['gain_5gw'],move['new_5gw']-move['old_5gw'])
    def test_low_baseline_is_quarantined(self):
        squad=self.squad()
        forecasts={p['id']:{'weeks':{g:0.5 for g in range(8,13)}} for p in squad}
        target={'id':99,'name':'Strong','position':'MID','team_id':8,'estimated_score':8,'availability':1,'fpl_status':'a','price':5}
        forecasts[99]={'weeks':{g:8 for g in range(8,13)}}
        result=decision_desk(squad,squad+[target],forecasts,0,8)
        self.assertFalse(result['transfers'])
        self.assertTrue(result['forecast_anomalies'])
    def test_team_gain_less_than_raw_gain_for_bench_swap(self):
        squad=self.squad()
        for p in squad: p['estimated_score']=4.0
        target={'id':99,'name':'Better','position':'MID','team_id':8,'estimated_score':4,'availability':1,'fpl_status':'a','price':5}
        forecasts={p['id']:{'weeks':{g:4 for g in range(8,13)}} for p in squad}
        forecasts[99]={'weeks':{g:6 for g in range(8,13)}}
        result=decision_desk(squad,squad+[target],forecasts,0,8)
        self.assertTrue(result['transfers'])
        self.assertLessEqual(result['transfers'][0]['team_gain_5gw'],result['transfers'][0]['gain_5gw'])
    def test_duplicate_anomaly_one_per_seller(self):
        squad=self.squad()
        forecasts={p['id']:{'weeks':{g:.5 for g in range(8,13)}} for p in squad}
        market=squad+[{'id':98,'name':'A','position':'MID','team_id':8,'estimated_score':8,'availability':1,'price':5},{'id':99,'name':'B','position':'MID','team_id':9,'estimated_score':8,'availability':1,'price':5}]
        forecasts[98]={'weeks':{g:8 for g in range(8,13)}}
        forecasts[99]={'weeks':{g:8 for g in range(8,13)}}
        result=decision_desk(squad,market,forecasts,0,8)
        ids=[x['player_id'] for x in result['forecast_anomalies']]
        self.assertEqual(len(ids),len(set(ids)))
    def test_transfer_identity_fields(self):
        squad=self.squad()
        candidate={'id':99,'name':'Duplicate','team':'XYZ','position':'MID','team_id':8,'estimated_score':8,'availability':1,'price':5}
        forecasts={p['id']:{'weeks':{g:2 for g in range(8,13)}} for p in squad}
        forecasts[99]={'weeks':{g:8 for g in range(8,13)}}
        result=decision_desk(squad,squad+[candidate],forecasts,0,8)
        move=result['transfers'][0]
        self.assertEqual(move['buy_id'],99)
        self.assertEqual(move['buy_team'],'XYZ')
        self.assertEqual(len(move['new_starters']),11)
    def test_email_decision_render(self):
        html=render({'gameweek':8,'decision_desk':{'action':'انتقال يستحق المراجعة','starting':['A'],'bench':['B']}})
        self.assertIn('انتقال يستحق المراجعة',html)
        self.assertIn('تشكيلتك الأساسية',html)

if __name__=='__main__':unittest.main()
