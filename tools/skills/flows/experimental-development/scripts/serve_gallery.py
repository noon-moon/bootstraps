#!/usr/bin/env python3
"""Preview one artifact root on loopback; notify galleries of actual HTML changes."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from urllib.parse import unquote, urlsplit


def gallery_bytes(root):
    path = (root / 'galleries.html').resolve()
    if not path.is_relative_to(root):
        raise OSError('Gallery escapes preview root')
    data = path.read_bytes()
    return data, hashlib.sha256(data).hexdigest()


def handler_for(root):
    root = root.resolve(strict=True)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get('Host') not in {
                f'127.0.0.1:{self.server.server_port}',
                f'localhost:{self.server.server_port}',
            }:
                self.send_error(403)
                return
            name = unquote(urlsplit(self.path).path)
            if name == '/__gallery_version':
                try:
                    _, version = gallery_bytes(root)
                except OSError:
                    self.send_error(503)
                    return
                self.respond(json.dumps({'version': version}).encode(), 'application/json')
                return
            try:
                path = (root / (name.lstrip('/') or 'galleries.html')).resolve()
                if not path.is_relative_to(root) or not path.is_file():
                    self.send_error(404)
                    return
                if any(part.startswith('.') for part in path.relative_to(root).parts):
                    self.send_error(404)
                    return
                data = path.read_bytes()
            except (OSError, ValueError):
                self.send_error(404)
                return
            if path == root / 'galleries.html':
                version = hashlib.sha256(data).hexdigest()
                data = data.replace(b'const previewVersion=null;',
                                    ('const previewVersion=' + json.dumps(version) + ';').encode())
            self.respond(data, mimetypes.guess_type(path.name)[0] or 'application/octet-stream')

        def respond(self, data, content_type):
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    if not root.is_dir() or not (root / 'galleries.html').is_file():
        parser.error('root must contain a built galleries.html')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(root))
    print(f'http://127.0.0.1:{server.server_port}/galleries.html', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
