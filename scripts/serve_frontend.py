#!/usr/bin/env python3

from __future__ import annotations

import argparse
import http.server
import os
import socketserver
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the current frontend locally.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    os.chdir(PROJECT_ROOT)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer((args.host, args.port), handler) as httpd:
        print(f"Serving {PROJECT_ROOT} at http://{args.host}:{args.port}")
        httpd.serve_forever()


if __name__ == "__main__":
    raise SystemExit(main())
