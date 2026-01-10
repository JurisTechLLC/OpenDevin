from http.server import BaseHTTPRequestHandler
import json

# Common LLM models available
MODELS = [
    "gpt-4",
    "gpt-4-turbo",
    "gpt-4-turbo-preview",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-3.5-turbo",
    "gpt-3.5-turbo-16k",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
    "claude-3-5-sonnet-20240620",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "gemini-pro",
    "gemini-1.5-pro",
    "gemini-1.5-flash"
]

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(MODELS).encode())
        return

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        return
