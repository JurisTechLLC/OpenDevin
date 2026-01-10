from http.server import BaseHTTPRequestHandler
import json
import os

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}
        
        message = data.get('message', '')
        model = data.get('model', 'gpt-4')
        
        # Get API key from environment
        api_key = os.environ.get('OPENAI_API_KEY') or os.environ.get('ANTHROPIC_API_KEY')
        
        if not api_key:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'error': 'No API key configured. Please set OPENAI_API_KEY or ANTHROPIC_API_KEY in environment variables.'
            }).encode())
            return
        
        try:
            # Use litellm for unified API access
            import litellm
            
            response = litellm.completion(
                model=model,
                messages=[
                    {"role": "system", "content": "You are OpenDevin, an AI software engineer assistant. Help users with coding tasks, debugging, and software development questions."},
                    {"role": "user", "content": message}
                ],
                api_key=api_key
            )
            
            assistant_message = response.choices[0].message.content
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'response': assistant_message,
                'model': model
            }).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'error': str(e)
            }).encode())
        
        return

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        return
