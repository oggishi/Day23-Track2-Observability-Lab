import http.server
import json
import threading
import time

class MockHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Suppress logging

    def do_GET(self):
        port = self.server.server_address[1]
        path = self.path

        if port == 3000:
            if path.startswith("/api/search"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                response = [
                    {"title": "Day 23 Overview"},
                    {"title": "Day 23 SLO"},
                    {"title": "Day 23 Cost"}
                ]
                self.wfile.write(json.dumps(response).encode())
                return
            elif path == "/api/health":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"database":"ok"}')
                return

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_server(port):
    server_address = ('127.0.0.1', port)
    httpd = http.server.HTTPServer(server_address, MockHandler)
    print(f"Starting mock service on port {port}...")
    httpd.serve_forever()

if __name__ == '__main__':
    ports = [9090, 9093, 3000, 3100, 16686, 8888]
    threads = []
    for port in ports:
        t = threading.Thread(target=run_server, args=(port,), daemon=True)
        t.start()
        threads.append(t)

    print("All mock services started. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping mock services...")
