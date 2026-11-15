"""Exercise the real HTTP adapter on loopback; no external API or key required."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import threading
import unittest
from orvexa.ai import AIClient,AIConfig

class Handler(BaseHTTPRequestHandler):
    received=[]
    def log_message(self,*args):
        pass
    def do_POST(self):
        body=self.rfile.read(int(self.headers['Content-Length']))
        self.received.append(json.loads(body))
        if self.path=='/redirect':
            self.send_response(302);self.send_header('Location','http://127.0.0.1:1/should-not-follow');self.end_headers();return
        if self.path=='/unauthorized':
            self.send_response(401);self.end_headers();return
        self.send_response(200);self.end_headers()
        payload={'/ok':b'{"message":{"content":"reply"}}','/invalid':b'<html>error</html>',
                 '/list':b'[]','/large':b'x'*2_000_001}.get(self.path,b'{}')
        self.wfile.write(payload)

class HTTPAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=2)

    def test_real_post_and_json_decode(self):
        data=AIClient(AIConfig())._request(self.base+'/ok',{'question':'Sleep'}, {})
        self.assertEqual(data['message']['content'],'reply')
        self.assertEqual(Handler.received[-1],{'question':'Sleep'})

    def test_bad_server_responses_have_readable_errors(self):
        for path,expected in [('/unauthorized','API key'),('/invalid','JSON'),('/list','format'),('/large','large')]:
            with self.subTest(path=path),self.assertRaisesRegex(ValueError,expected):
                AIClient(AIConfig())._request(self.base+path,{}, {})

    def test_redirect_is_not_followed(self):
        with self.assertRaisesRegex(ValueError,'302'):
            AIClient(AIConfig())._request(self.base+'/redirect',{}, {})

if __name__=='__main__':
    unittest.main()
