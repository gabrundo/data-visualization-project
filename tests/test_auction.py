"""Auction arithmetic, fixed-window SQL and API contracts; isolated PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from project.etl.import_players import ROOT, database_engine
from project.etl.import_context import flatten, map_entry, import_snapshot
from project.web.app import create_app
from project.web.catalogue import evidence, resolved_context
from project.web.rules import team_summary, validate_purchase


def owned(gk=0, out=0, price=1):
    return [dict(role_group='goalkeeper',price=price) for _ in range(gk)]+[dict(role_group='outfield',price=price) for _ in range(out)]


class RuleTests(unittest.TestCase):
    def test_budget_and_reserve(self):
        self.assertEqual(team_summary([])['max_bid_goalkeeper'],478)
        validate_purchase([], 'outfield',478)
        with self.assertRaises(ValueError):validate_purchase([], 'outfield',479)
        for p in (0,-1,1.5,True,'4'):
            with self.assertRaises(ValueError):validate_purchase([], 'outfield',p)
        sales=owned(2,19);sales[0]['price']=478
        validate_purchase(sales,'goalkeeper',1)
        with self.assertRaises(ValueError):validate_purchase(sales,'goalkeeper',2)

    def test_role_boundaries_and_optional_reserve(self):
        validate_purchase(owned(2,20),'goalkeeper',478)
        validate_purchase(owned(3),'goalkeeper',1)
        validate_purchase(owned(3,19),'outfield',478)
        minimum=team_summary(owned(3,20))
        self.assertTrue(minimum['minimum_complete'])
        self.assertEqual(minimum['max_bid_outfield'],477)
        validate_purchase(owned(3,24),'outfield',473)
        validate_purchase(owned(3,25),'outfield',1)
        self.assertEqual(team_summary(owned(3,25))['max_bid_outfield'],472)
        validate_purchase(owned(10,40), 'goalkeeper', 450)
        validate_purchase(owned(10,40), 'outfield', 450)
        self.assertTrue(team_summary(owned(10,40))['minimum_complete'])
        with self.assertRaises(ValueError):validate_purchase(owned(10,40), 'outfield', 451)
        with self.assertRaises(ValueError):validate_purchase(owned(3,497), 'goalkeeper', 1)

    def test_optional_purchase_with_missing_goalkeepers(self):
        self.assertEqual(team_summary(owned(0,20))['max_bid_outfield'],477)
        validate_purchase(owned(0,20),'outfield',477)
        with self.assertRaises(ValueError):validate_purchase(owned(0,20),'outfield',478)

    def test_weights_missing_samples_newcomer(self):
        history=[dict(performance_season=2025,season_weighted_score=6,coverage_status='complete'),dict(performance_season=2024,season_weighted_score=4,coverage_status='complete'),dict(performance_season=2023,season_weighted_score=2,coverage_status='complete')]
        opening=dict(fv_matches=5,mean_fv=8,complete_matchdays=5)
        self.assertAlmostEqual(evidence(history,opening)['score'],.8*5+.2*8)
        self.assertFalse(evidence(history,opening)['provisional'])
        opening.update(fv_matches=1,complete_matchdays=2)
        self.assertIsNone(evidence([],opening)['score'])
        self.assertAlmostEqual(evidence(history[:1],opening)['score'],.8*.6*6)
        opening['fv_matches']=2
        self.assertAlmostEqual(evidence([],opening)['score'],.2*8*2/5)
        opening['fv_matches']=6
        self.assertIsNone(evidence([],opening)['score'])

    def test_mapping_and_precedence(self):
        p=[dict(player_id=1,player_name='Martinez Jo.',current_team='Inter'),dict(player_id=2,player_name='Martinez L.',current_team='Inter')]
        entry=dict(club='Inter',name='Martinez')
        self.assertEqual(map_entry(entry,p,{})[1],'unmatched')
        self.assertEqual(map_entry(entry,p,{'Inter|Martinez':1})[:2],(1,'matched'))
        self.assertEqual(map_entry(dict(club='Roma',name='Martinez Jo.'),p,{})[1],'club_conflict')
        self.assertEqual(map_entry(dict(club='Inter',name='Martinez Jo.'),p+[p[0]],{})[1],'ambiguous')
        at=datetime(2026,10,6,tzinfo=timezone.utc)
        entries=[dict(id=1,club='Inter',mapping_status='club',player_id=None,fields={'manager':'Expected','formation':'3-5-2'},verified=False,observed_at=None,retrieved_at=at,source_url='local'),dict(id=2,club='Inter',mapping_status='club',player_id=None,fields={'manager':'Verified'},verified=True,observed_at=at,retrieved_at=at,source_url='https://example.test')]
        result=resolved_context(entries,'Inter',1)
        self.assertEqual(result['manager']['value'],'Verified');self.assertFalse(result['formation']['verified'])
        entries.append(dict(entries[1],id=3,fields={'manager':None}))
        self.assertIsNone(resolved_context(entries,'Inter',1)['manager']['value'])
        self.assertEqual(len(flatten({'serie_a_2026_27':{'Inter':{'allenatore':'A','ruoli':{'portieri':[{'nome':'B','titolare':True}]},'rigoristi':['B'],'indisponibili':[{'nome':'B','motivo':'Test'}]}}})),2)


@unittest.skipUnless(os.environ.get('HISTORICAL_DB_TESTS')=='1','Set HISTORICAL_DB_TESTS=1 for isolated PostgreSQL tests')
class AuctionAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin=database_engine(ROOT/'.env');cls.schema='test_auction_'+uuid4().hex
        with cls.admin.begin() as conn:conn.execute(text(f'CREATE SCHEMA {cls.schema}'))
        cls.engine=create_engine(cls.admin.url,connect_args={'options':f'-csearch_path={cls.schema}'},hide_parameters=True)
        cls.addClassCleanup(cls.cleanup_schema)
        with cls.engine.connect() as conn:
            for f in ['001_schema.sql','002_player_metrics.sql','003_auction.sql','004_three_goalkeepers.sql','005_uncapped_squads.sql']:
                conn.exec_driver_sql((ROOT/'db/init'/f).read_text())
            conn.commit()
        cls.seed()

    @classmethod
    def cleanup_schema(cls):
        cls.engine.dispose()
        with cls.admin.begin() as c:c.execute(text(f'DROP SCHEMA {cls.schema} CASCADE'))
        cls.admin.dispose()

    @classmethod
    def seed(cls):
        with cls.engine.begin() as c:
            c.execute(text("INSERT INTO data_source(name) VALUES ('Fantacalcio.it')"))
            c.execute(text('INSERT INTO season VALUES (2023),(2024),(2025),(2026)'))
            c.execute(text("INSERT INTO collection_record(source_id,source_uri,status) VALUES (1,'https://example.test','parsed')"))
            c.execute(text("INSERT INTO team(name) VALUES ('Club'),('Other'),('Third')"))
            for i in range(1,101):
                name='Player '+str(i)
                c.execute(text('INSERT INTO player(name) VALUES (:name)'),dict(name=name))
                c.execute(text("INSERT INTO player_season_snapshot(player_id,season,source_id,snapshot_at,team_id,collection_id) VALUES (:i,2026,1,'2026-01-01',1,1)"),dict(i=i))
                c.execute(text('INSERT INTO player_snapshot_role VALUES (:i,:role)'),dict(i=i,role='Por' if i<=12 else 'M'))
            for year in range(2023,2027):
                for day in (1,2,6):
                    home,away=(1,2) if day==1 else (2,1) if day==2 else (1,3)
                    fid=c.execute(text("INSERT INTO fixture(season,matchday,home_team_id,away_team_id,home_goals,away_goals,status,collection_id) VALUES (:y,:d,:h,:a,1,0,'completed',1) RETURNING id"),dict(y=year,d=day,h=home,a=away)).scalar_one()
                    c.execute(text("""INSERT INTO player_fixture_performance(player_id,fixture_id,source_id,provider,team_id,collection_id,match_rating,fanta_voto,rating_status,goals,assists)
                     VALUES (13,:f,1,'Redazione Fantacalcio',1,1,6,:fv,'rated',:goals,0)"""),dict(f=fid,fv=100 if day==6 else 7,goals=10 if day==6 else 1))

    def setUp(self):
        with self.engine.begin() as c:
            c.execute(text('UPDATE auction_settings SET my_team_id=NULL, revision=0'))
            c.execute(text('TRUNCATE auction_sale,auction_request,fantasy_team RESTART IDENTITY CASCADE'))
            c.execute(text('INSERT INTO auction_settings(id) VALUES (1) ON CONFLICT DO NOTHING'))
        self.client=TestClient(create_app(self.engine));self.client.__enter__();self.addCleanup(self.client.__exit__,None,None,None)
        response=self.client.put('/api/settings',json={'teams':[{'name':'Mine'},{'name':'Other'}],'my_team_index':0})
        self.assertEqual(response.status_code,200,response.text)
        self.ids=[t['id'] for t in response.json()['teams']]

    def purchase(self,player=13,buyer=1,price=1,key=None):
        return self.client.post('/api/sales',json=dict(player_id=player,buyer_id=buyer,price=price,idempotency_key=key or str(uuid4())))

    def test_budget_invalid_prices_and_rollback(self):
        before=self.client.get('/api/state').json()
        self.assertEqual(self.purchase(price=479).status_code,409)
        for p in (0,1.5,True):self.assertEqual(self.purchase(price=p).status_code,422)
        self.assertEqual(before,self.client.get('/api/state').json())
        result=self.purchase(price=478);self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['teams'][0]['remaining_budget'],22)
        self.assertEqual(self.purchase(player=14,price=2).status_code,409)
        self.assertEqual(self.purchase(player=14).status_code,200)

    def test_idempotency_duplicates_delete_retry_and_payload_mismatch(self):
        key=str(uuid4());first=self.purchase(key=key);self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(self.purchase(key=key).json(),first.json())
        self.assertEqual(self.purchase().status_code,409)
        self.assertEqual(self.purchase(price=2,key=key).status_code,409)
        sid=first.json()['sales'][0]['id'];self.client.delete(f'/api/sales/{sid}')
        self.assertEqual(self.purchase(key=key).json()['sales'],[])
        self.assertEqual(self.purchase().status_code,200)

    def test_edit_transfer_refund_and_undo_newest_recorded(self):
        first=self.purchase(price=100).json()['sales'][0];second=self.purchase(player=14,price=10).json()['sales'][0]
        result=self.client.put(f"/api/sales/{first['id']}",json=dict(player_id=13,buyer_id=2,price=478))
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['teams'][0]['remaining_budget'],490)
        failed=self.client.put(f"/api/sales/{second['id']}",json=dict(player_id=14,buyer_id=2,price=2))
        self.assertEqual(failed.status_code,409)
        same=self.client.put(f"/api/sales/{first['id']}",json=dict(player_id=13,buyer_id=2,price=478));self.assertEqual(same.status_code,200)
        result=self.client.post('/api/undo').json();self.assertEqual([s['id'] for s in result['sales']],[first['id']])
        self.client.delete(f"/api/sales/{first['id']}")
        self.assertEqual(self.client.get('/api/state').json()['teams'][1]['remaining_budget'],500)
        self.assertEqual(self.client.post('/api/undo').status_code,409)

    def test_uncapped_role_groups(self):
        for p in range(1,4):self.assertEqual(self.purchase(player=p).status_code,200)
        self.assertEqual(self.purchase(player=4).status_code,200)
        for p in range(13,33):self.assertEqual(self.purchase(player=p).status_code,200)
        summary=self.client.get('/api/state').json()['teams'][0];self.assertTrue(summary['minimum_complete'])
        for p in range(33,38):self.assertEqual(self.purchase(player=p).status_code,200)
        self.assertEqual(self.purchase(player=38).status_code,200)
        self.assertTrue(self.client.get('/api/state').json()['teams'][0]['minimum_complete'])

    def test_transfer_beyond_former_cap_and_same_team_edit(self):
        for player in range(1,4):
            self.assertEqual(self.purchase(player=player,buyer=2).status_code,200)
        sale=self.purchase(player=4,buyer=1,price=10).json()['sales'][0]
        before=self.client.get('/api/state').json()
        result=self.client.put(f"/api/sales/{sale['id']}",json=dict(player_id=4,buyer_id=2,price=1))
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['teams'][1]['goalkeepers'],4)
        result=self.client.put(f"/api/sales/{sale['id']}",json=dict(player_id=4,buyer_id=1,price=478))
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['teams'][0]['remaining_budget'],22)
        other=self.client.put(f"/api/sales/{sale['id']}",json=dict(player_id=5,buyer_id=1,price=1))
        self.assertEqual(other.status_code,409)

    def test_concurrent_requests_serialize_budget_and_duplicates(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(lambda p:self.purchase(player=p,price=478).status_code,[13,14]))
        self.assertEqual(sorted(statuses),[200,409])
        self.client.post('/api/reset',json=dict(confirmation='RESET',revision=self.client.get('/api/state').json()['settings']['revision']))
        key=str(uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda _:self.purchase(key=key),range(2)))
        self.assertEqual([r.status_code for r in responses],[200,200])
        self.assertEqual(len(self.client.get('/api/state').json()['sales']),1)

    def test_settings_reset_export_and_reload(self):
        self.purchase(price=50)
        self.assertEqual(self.client.put('/api/settings',json=dict(teams=[dict(id=2,name='Other')],my_team_index=0)).status_code,409)
        changed=self.client.put('/api/settings',json=dict(teams=[dict(id=1,name='Other'),dict(id=2,name='Mine')],my_team_index=1))
        self.assertEqual(changed.status_code,200,changed.text)
        self.assertEqual(changed.json()['settings']['my_team_id'],2)
        for url in ['/api/export/sales.csv','/api/export/roster/1.csv']:
            r=self.client.get(url);self.assertEqual(r.status_code,200);self.assertIn('Player 13',r.text)
        with TestClient(create_app(self.engine)) as client:self.assertEqual(client.get('/api/state').json(),changed.json())
        self.assertEqual(self.client.post('/api/reset',json=dict(confirmation='RESET',revision=0)).status_code,409)
        self.assertEqual(self.client.post('/api/reset',json=dict(confirmation='no',revision=changed.json()['settings']['revision'])).status_code,409)
        self.assertEqual(self.client.post('/api/reset',json=dict(confirmation='RESET',revision=changed.json()['settings']['revision'])).json()['sales'],[])

    def test_catalogue_fixed_window_and_additive_repeat_install(self):
        catalogue=self.client.get('/api/catalogue');self.assertEqual(catalogue.status_code,200,catalogue.text)
        p=next(p for p in catalogue.json() if p['player_id']==13)
        self.assertEqual(p['opening']['mean_fv'],7);self.assertEqual(p['opening']['fv_matches'],2);self.assertEqual(p['opening']['goals'],2)
        self.assertEqual(p['opening']['imported_fixtures'],2);self.assertTrue(p['provisional'])
        self.assertIsNone(next(p for p in catalogue.json() if p['player_id']==14)['score'])
        with self.engine.connect() as c:
            before=c.execute(text('SELECT count(*) FROM player_fixture_performance')).scalar()
            c.exec_driver_sql((ROOT/'db/init/003_auction.sql').read_text());c.commit()
            self.assertEqual(c.execute(text('SELECT count(*) FROM player_fixture_performance')).scalar(),before)
            self.assertEqual(c.execute(text('SELECT count(*) FROM player')).scalar(),100)

    def test_existing_five_keeper_settings_upgrade_preserves_sales(self):
        self.purchase(player=1,price=10)
        before=self.client.get('/api/state').json()
        with self.engine.begin() as c:
            c.execute(text('ALTER TABLE auction_settings DROP CONSTRAINT auction_settings_goalkeeper_slots_check'))
            c.execute(text('UPDATE auction_settings SET goalkeeper_slots=5'))
            c.execute(text('ALTER TABLE auction_settings ADD CONSTRAINT auction_settings_goalkeeper_slots_check CHECK (goalkeeper_slots=5)'))
        with self.engine.connect() as c:
            c.exec_driver_sql((ROOT/'db/init/004_three_goalkeepers.sql').read_text());c.commit()
            c.exec_driver_sql((ROOT/'db/init/004_three_goalkeepers.sql').read_text());c.commit()
        after=self.client.get('/api/state').json()
        self.assertEqual(after['settings']['goalkeeper_slots'],3)
        self.assertEqual(after['settings']['revision'],before['settings']['revision']+1)
        self.assertEqual(after['sales'],before['sales'])
        self.assertEqual(after['teams'],before['teams'])

    def test_uncapped_migration_preserves_sales_and_is_repeatable(self):
        self.purchase(player=1,price=10)
        before=self.client.get('/api/state').json()
        with self.engine.begin() as c:
            c.execute(text('ALTER TABLE auction_settings DROP CONSTRAINT auction_settings_maximum_outfield_check'))
            c.execute(text('UPDATE auction_settings SET maximum_outfield=25'))
            c.execute(text('ALTER TABLE auction_settings ADD CONSTRAINT auction_settings_maximum_outfield_check CHECK (maximum_outfield=25)'))
        with self.engine.connect() as c:
            for _ in range(2):
                c.exec_driver_sql((ROOT/'db/init/005_uncapped_squads.sql').read_text());c.commit()
        after=self.client.get('/api/state').json()
        self.assertIsNone(after['settings']['maximum_outfield'])
        self.assertEqual(after['settings']['revision'],before['settings']['revision']+1)
        self.assertEqual(after['sales'],before['sales'])
        self.assertEqual(after['teams'],before['teams'])

    def test_context_preserved_and_unresolved_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'context.json';raw={'entries':[dict(club='Club',name='Alias',fields={'expected_starter':True}),dict(club='Club',name='Missing',fields={'availability':'doubtful'})]};path.write_text(json.dumps(raw))
            report=import_snapshot(self.engine,path,{'Club|Alias':13},retrieved_at=datetime.now(timezone.utc))
            self.assertEqual([r['status'] for r in report],['matched','unmatched'])
            with self.engine.connect() as c:
                self.assertEqual(c.execute(text('SELECT raw_values FROM context_snapshot ORDER BY id DESC LIMIT 1')).scalar(),raw)
            import_snapshot(self.engine,path,{'Club|Alias':13},retrieved_at=datetime.now(timezone.utc))
            with self.engine.connect() as c:self.assertEqual(c.execute(text('SELECT count(*) FROM context_snapshot WHERE raw_values=CAST(:r AS jsonb)'),dict(r=json.dumps(raw))).scalar(),1)

    def test_context_invalid_evidence_rolls_back_and_future_is_hidden(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'invalid.json'
            for fields,verified in [({'expected_starter':True},'false'),({'starter_percentage':101},False),({'expected_starter':'true'},False)]:
                path.write_text(json.dumps({'entries':[dict(club='Club',name='Player 13',fields=fields,verified=verified)]}))
                with self.assertRaises(ValueError):
                    import_snapshot(self.engine,path,{},retrieved_at=datetime.now(timezone.utc))
            path.write_text(json.dumps({'entries':[dict(club='Club',fields={'manager':'Future'},verified=True,source_url='https://example.test',observed_at='2099-01-01T00:00:00Z')]}))
            import_snapshot(self.engine,path,{},retrieved_at=datetime.now(timezone.utc))
            response=self.client.get('/api/catalogue')
            self.assertEqual(response.status_code,200,response.text)
            self.assertNotIn('Future',response.text)


if __name__=='__main__':unittest.main()
