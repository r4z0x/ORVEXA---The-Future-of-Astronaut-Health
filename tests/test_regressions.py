"""Regression coverage for reported audit findings and upgrade compatibility."""
import csv
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from orvexa.ai import AIConfig, AIClient
from orvexa.charts import plot_samples
from orvexa.domain import Metrics, validate_ai_analysis
from orvexa.reports import save_report
from orvexa.storage import Repository
from tests.test_core import PLAN

class PlotTests(unittest.TestCase):
    def test_irregular_time_intervals_are_preserved(self):
        points=plot_samples([60,80,70],[0,1,100])
        self.assertEqual(points,[(0.0,60),(.01,80),(1.0,70)])

    def test_large_series_is_bounded_and_retains_extremes(self):
        values=[68]*10000
        values[4321]=110
        values[7890]=45
        points=plot_samples(values,list(range(len(values))))
        self.assertLessEqual(len(points),600)
        self.assertEqual(points[0],(0.0,68))
        self.assertEqual(points[-1],(1.0,68))
        self.assertIn(110,[p[1] for p in points])
        self.assertIn(45,[p[1] for p in points])

    def test_empty_series_has_no_invented_baseline_point(self):
        self.assertEqual(plot_samples([]),[])
        self.assertEqual(plot_samples([68],[123]),[(.5,68)])

class StorageUpgradeTests(unittest.TestCase):
    def test_old_database_migrates_without_losing_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=sqlite3.connect(Path(tmp)/'orvexa.sqlite3')
            db.executescript('CREATE TABLE measurements(id INTEGER PRIMARY KEY,at TEXT NOT NULL,data TEXT NOT NULL); CREATE TABLE analyses(id INTEGER PRIMARY KEY,measurement_id INTEGER,at TEXT NOT NULL,data TEXT NOT NULL);')
            at=datetime.now(timezone.utc).isoformat()
            db.execute('INSERT INTO measurements VALUES(1,?,?)',(at,json.dumps(Metrics().to_dict())))
            db.execute('INSERT INTO analyses VALUES(1,1,?,?)',(at,json.dumps(validate_ai_analysis(PLAN).to_dict())))
            db.commit();db.close()
            repo=Repository(tmp)
            self.assertEqual(len(repo.measurements()),1)
            self.assertIsNotNone(repo.latest_analysis(1,Metrics()))
            self.assertIsNone(repo.latest_analysis(1,replace(Metrics(),baseline_heart=65)))
            self.assertEqual(len(repo.export()['analyses']),1)
            repo.close()

    def test_profile_context_rejects_stale_analysis_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo=Repository(tmp)
            current=repo.add_measurement(Metrics())
            repo.save_analysis(current,validate_ai_analysis(PLAN),Metrics())
            repo.set_settings({'name':'Crew Member 04','baseline':65})
            self.assertEqual(repo.counts()[0],1)
            repo.close();repo=Repository(tmp)
            self.assertIsNone(repo.latest_analysis(current,replace(Metrics(),baseline_heart=65)))
            self.assertEqual(repo.measurements()[0]['metrics']['baseline_heart'],61)
            self.assertEqual(repo.export()['analyses'][0]['metrics']['baseline_heart'],61)
            repo.close()

    def test_pagination_and_range_keep_all_records_exportable(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo=Repository(tmp)
            now=datetime.now(timezone.utc)
            rows=[((now-timedelta(hours=401-i)).isoformat(),json.dumps(Metrics(heart=60+i%20).to_dict())) for i in range(401)]
            repo.db.executemany('INSERT INTO measurements(at,data) VALUES(?,?)',rows);repo.db.commit()
            pages=[repo.measurements(limit=200,offset=offset) for offset in [0,200,400]]
            self.assertEqual([len(page) for page in pages],[200,200,1])
            self.assertEqual(len({r['id'] for page in pages for r in page}),401)
            self.assertEqual(repo.counts()[0],401)
            self.assertEqual(len(repo.export()['measurements']),401)
            recent=repo.measurement_range(now-timedelta(days=1),now)
            self.assertTrue(all(datetime.fromisoformat(r['at'])>=now-timedelta(days=1) for r in recent))
            repo.close()

    def test_invalid_cached_analysis_does_not_break_startup(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo=Repository(tmp)
            current=repo.add_measurement(Metrics())
            repo.db.execute('INSERT INTO analyses(measurement_id,at,data,metrics) VALUES(?,?,?,?)',
                            (current,'now','not json',json.dumps(Metrics().to_dict())))
            repo.db.commit()
            self.assertIsNone(repo.latest_analysis(current,Metrics()))
            repo.close()

    def test_secret_rejection_is_atomic_for_multiple_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo=Repository(tmp)
            with self.assertRaises(ValueError):
                repo.set_settings({'model':'new-model','api_key':'must-not-save'})
            self.assertIsNone(repo.get_setting('model'))
            repo.close()

class ReportTests(unittest.TestCase):
    def report(self):
        return {'measurements':[{'at':'2026-11-15T00:00:00+00:00','metrics':Metrics().to_dict()}]}

    def test_csv_contains_bom_and_roundtrips_english_headings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'report.csv'
            save_report(path,self.report(),'csv')
            self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))
            with path.open(encoding='utf-8-sig',newline='') as stream:
                rows=list(csv.reader(stream,delimiter=';'))
            self.assertEqual(rows[0][0],'Date')
            self.assertEqual(rows[1][1],'68')

    def test_failed_write_keeps_previous_report_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'report.json'
            path.write_text('previous report',encoding='utf-8')
            with patch('orvexa.reports.json.dump',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    save_report(path,self.report())
            self.assertEqual(path.read_text(),'previous report')
            self.assertEqual([p.name for p in Path(tmp).iterdir()],['report.json'])

class AIResponseTests(unittest.TestCase):
    def test_incomplete_and_refused_responses_are_not_accepted(self):
        responses=[{'status':'incomplete','output':[{'content':[{'type':'output_text','text':json.dumps(PLAN)}]}]},
                   {'output':[{'content':[{'type':'refusal','refusal':'Refused'}]}]},
                   {'output':None}, {'error':{'message':'failed'}},
                   {'output':[None,{'content':None}]}]
        for response in responses:
            with self.subTest(response=response),self.assertRaises(ValueError):
                AIClient(AIConfig(api_key='test'),lambda *args:response).analyze(Metrics())

    def test_ollama_incomplete_and_error_responses_are_not_accepted(self):
        for response in [{'done':False,'message':{'content':json.dumps(PLAN)}},{'error':'model not loaded'},{'message':None}]:
            with self.subTest(response=response),self.assertRaises(ValueError):
                AIClient(AIConfig('Ollama','qwen2.5:7b'),lambda *args:response).analyze(Metrics())

    def test_chat_includes_bounded_prior_context(self):
        calls=[]
        def transport(url,payload,headers):
            calls.append(json.loads(payload['input']))
            return {'output':[{'content':[{'type':'output_text','text':'Context-aware reply'}]}]}
        history=[{'role':'user','content':f'Question {i}'} for i in range(20)]
        AIClient(AIConfig(api_key='test'),transport).chat(Metrics(),'What do you recommend?',history=history)
        self.assertEqual(len(calls[0]['history']),8)
        self.assertEqual(calls[0]['history'][-1]['content'],'Question 19')

    def test_invalid_config_is_rejected_before_network(self):
        for config in [AIConfig(model=''),AIConfig(api_key='bad\nkey'),AIConfig('Ollama','model',ollama_url='http://localhost:99999'),
                       AIConfig('Ollama','model',ollama_url='http://user@localhost:11434'),AIConfig('Ollama','model',ollama_url='http://localhost:11434/api')]:
            with self.subTest(config=config),self.assertRaises(ValueError):
                config.validate()
        self.assertNotIn('my-secret',repr(AIConfig(api_key='my-secret')))

if __name__=='__main__':
    unittest.main()
