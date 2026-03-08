import http.server, json, sys

class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers['Content-Length'])
        body = self.rfile.read(length)
        data = json.loads(body)
        with open('hk_stocks_data_new.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        print(f"Saved {len(data.get('rows', []))} rows", flush=True)
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(b'OK')
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    def log_message(self, *a): pass

print("Server starting on port 9876", flush=True)
httpd = http.server.HTTPServer(('', 9876), Handler)
httpd.serve_forever()
