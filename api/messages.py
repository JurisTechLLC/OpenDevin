from http.server import BaseHTTPRequestHandler
import json

# In-memory message storage (will reset on cold starts)
# For production, use a database like Vercel KV or Postgres
messages_store = {}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Get session ID from authorization header
        auth_header = self.headers.get('Authorization', '')
        sid = ""
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            parts = token.split(':')
            if parts:
                sid = parts[0]
        
        messages = messages_store.get(sid, [])
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({'messages': messages}).encode())
        return

    def do_DELETE(self):
        auth_header = self.headers.get('Authorization', '')
        sid = ""
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            parts = token.split(':')
            if parts:
                sid = parts[0]
        
        if sid in messages_store:
            del messages_store[sid]
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({'ok': True}).encode())
        return

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        return
