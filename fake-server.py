"""Fake server if you don't have a real one running or whatever"""
import json
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer

from zeroconf import ServiceInfo, Zeroconf

HOSTNAME = "vacuula.local."
PORT = 80

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(("192.0.2.1", 80))
    ip = s.getsockname()[0]
finally:
    s.close()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/cert":
            self.do_cert()
        elif self.path == "/api/server":
            self.do_server()

    def do_server(self):
        data = json.dumps({
            "version": "1.0.0",
            "gen4_port": 3443,
            # "timezone": XXX, - not used by installer
            # "utc_offset_minutes": XXX, - not used by installer
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()

    def do_cert(self):
        data = b"FAKE-BEGIN CERTIFICATE-FAKE\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header(
            "Content-Disposition",
            'attachment; filename="cert.txt"',
        )
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()

httpd = HTTPServer(("0.0.0.0", PORT), Handler)


zc = Zeroconf()
SERVICE_TYPE = "_vacuula._tcp.local."
SERVICE_NAME = "Vacuula Server._vacuula._tcp.local."
MDNS_HOSTNAME = "vacuula.local."
PORT = 80
info = ServiceInfo(
    SERVICE_TYPE,
    SERVICE_NAME,
    addresses=[socket.inet_aton(ip)],
    server=MDNS_HOSTNAME,
    port=PORT,
    properties={
        "version": "1",
        "cert-path": "/api/cert",
        "protocol": "http",
        "url": "http://vacuula.local",
    },
)
zc.register_service(info)
print(f"Advertising {HOSTNAME} -> {ip}")

print(f"Download: http://vacuula.local:{PORT}/api/cert")

try:
    httpd.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    httpd.server_close()
    zc.unregister_service(info)
    zc.close()