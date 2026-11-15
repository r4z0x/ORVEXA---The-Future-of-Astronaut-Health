import json
import tempfile
import unittest
from dataclasses import replace
from orvexa.domain import Metrics, validate_ai_analysis, sample_plan
from orvexa.ai import AIClient, AIConfig
from orvexa.storage import Repository

PLAN={'title':'Balanced Day','summary':'Considering short sleep and moderate fatigue.',
      'reasons':['Sleep 6,7 h'], 'plan':[{'name':'Mobility & Stretching','equipment':'Restraints','minutes':10,
      'description':'Gentle movements','steps':'Follow the mission protocol.','category':'Recovery'}]}

class DomainTests(unittest.TestCase):
    def test_invalid_and_nonfinite_metrics(self):
        for patch in [{'heart':float('nan')},{'spo2':101},{'temperature':True},{'sleep_hours':17},{'symptoms':'yes'}]:
            with self.subTest(patch=patch),self.assertRaises(ValueError):
                replace(Metrics(),**patch).validate()

    def test_guardrail_prevents_network_and_exercises(self):
        def forbidden(*args):
            self.fail('Network must not be called for concerning metrics')
        client=AIClient(AIConfig(api_key='test-only'),transport=forbidden)
        for patch in [{'heart':140},{'spo2':90},{'temperature':39},{'symptoms':True}]:
            m=replace(Metrics(),**patch)
            with self.subTest(patch=patch):
                self.assertEqual(client.analyze(m).plan,())
                self.assertEqual(sample_plan(m),())
                self.assertEqual(client.analyze(m).mode,'guardrail')
                self.assertIn('medical officer',client.chat(m,'What workload is appropriate?'))

    def test_reject_unreasonable_model_plan(self):
        for duration in [True,0,2,31,100]:
            with self.subTest(duration=duration),self.assertRaises(ValueError):
                validate_ai_analysis({**PLAN,'plan':[{**PLAN['plan'][0],'minutes':duration}]})
        with self.assertRaises(ValueError):
            validate_ai_analysis({**PLAN,'plan':[{**PLAN['plan'][0],'minutes':30}]*3})

class InferenceTests(unittest.TestCase):
    def test_openai_request_and_structured_response(self):
        calls=[]
        def transport(url,payload,headers):
            calls.append((url,payload,headers))
            return {'output':[{'content':[{'type':'output_text','text':json.dumps(PLAN,ensure_ascii=False)}]}]}
        result=AIClient(AIConfig(api_key='test-secret'),transport).analyze(Metrics())
        self.assertEqual(result.plan[0].minutes,10)
        self.assertEqual(result.mode,'ai')
        url,payload,headers=calls[0]
        self.assertEqual(url,'https://api.openai.com/v1/responses')
        self.assertFalse(payload['store'])
        self.assertTrue(payload['text']['format']['strict'])
        self.assertEqual(json.loads(payload['input'])['metrics']['heart'],68)
        self.assertEqual(headers['Authorization'],'Bearer test-secret')

    def test_ollama_request_and_local_restriction(self):
        calls=[]
        def transport(url,payload,headers):
            calls.append((url,payload,headers))
            return {'message':{'content':json.dumps(PLAN)}}
        result=AIClient(AIConfig('Ollama','qwen2.5:7b'),transport).analyze(Metrics())
        self.assertEqual(result.model,'qwen2.5:7b')
        self.assertEqual(calls[0][0],'http://127.0.0.1:11434/api/chat')
        self.assertFalse(calls[0][1]['stream'])
        with self.assertRaises(ValueError):
            AIClient(AIConfig('Ollama','model',ollama_url='https://external.test'),transport).analyze(Metrics())

    def test_missing_key_and_malformed_model_reply(self):
        with self.assertRaisesRegex(ValueError,'API key'):
            AIClient(AIConfig()).analyze(Metrics())
        transport=lambda *args:{'output':[{'content':[{'type':'output_text','text':'not JSON'}]}]}
        with self.assertRaisesRegex(ValueError,'unstructured'):
            AIClient(AIConfig(api_key='test'),transport).analyze(Metrics())

class PersistenceTests(unittest.TestCase):
    def test_measurements_plans_sessions_survive_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo=Repository(tmp)
            current=repo.add_measurement(Metrics())
            analysis=validate_ai_analysis(PLAN)
            repo.save_analysis(current,analysis)
            repo.add_session(127,1,analysis.plan,'ai')
            repo.close()
            repo=Repository(tmp)
            self.assertEqual(repo.measurements()[0]['metrics']['heart'],68)
            self.assertEqual(repo.latest_analysis(current).plan[0].name,'Mobility & Stretching')
            self.assertIsNone(repo.latest_analysis(current+1))
            self.assertEqual(repo.sessions()[0]['seconds'],127)
            self.assertEqual(repo.export()['sessions'][0]['mode'],'ai')
            with self.assertRaises(ValueError):
                repo.set_setting('api_key','should-not-persist')
            repo.close()

if __name__=='__main__':
    unittest.main()
