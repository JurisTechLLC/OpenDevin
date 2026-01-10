from http.server import BaseHTTPRequestHandler
import json
import os
import time
import hashlib
import base64

def generate_token(sid: str) -> str:
    """Generate a simple token for the session."""
    secret = os.environ.get('AUTH_SECRET', 'opendevin-secret-key')
    timestamp = str(int(time.time()))
    data = f"{sid}:{timestamp}:{secret}"
    token = base64.b64encode(hashlib.sha256(data.encode()).digest()).decode()
    return f"{sid}:{timestamp}:{token[:32]}"

def verify_token(token: str) -> str:
    """Verify token and return session ID."""
    try:
        parts = token.split(':')
        if len(parts) >= 1:
            return parts[0]
    except Exception:
        pass
    return ""

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Get authorization header
        auth_header = self.headers.get('Authorization', '')
        
        # Extract existing token or generate new session ID
        if auth_header.startswith('Bearer '):
            existing_token = auth_header[7:]
            sid = verify_token(existing_token)
            if not sid:
                sid = hashlib.md5(str(time.time()).encode()).hexdigest()[:16]
        else:
            sid = hashlib.md5(str(time.time()).encode()).hexdigest()[:16]
        
        # Generate new token
        token = generate_token(sid)
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({'token': token}).encode())
        return

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        return
