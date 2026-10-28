"""Minimal HTTP wrapper around the OddsHarvester CLI (runs it as a subprocess)."""
import json
import os
import re
import subprocess
import sys

from flask import Flask, jsonify, request

app = Flask(__name__)
TIMEOUT = int(os.getenv("SCRAPE_TIMEOUT", "600"))


def _proxy_args():
    url = os.getenv("PROXY_URL", "")
    # ignore the placeholder until a real proxy URL is configured
    if re.match(r"^(https?|socks5)://[^/:\s]+:\d+/?$", url):
        return ["--proxy-url", url]
    return []


@app.get("/")
def health():
    return jsonify({"status": "ok"})


@app.get("/odds")
def odds():
    """GET /odds?league=england-premier-league&sport=football&date=20261101&market=1x2"""
    a = request.args
    cmd = [sys.executable, "-m", "oddsharvester", "upcoming",
           "--sport", a.get("sport", "football"), "--headless", "--stream-ndjson"]
    for key, flag in (("league", "--league"), ("date", "--date"), ("market", "--market")):
        if a.get(key):
            cmd += [flag, a[key]]
    if not (a.get("league") or a.get("date")):
        return jsonify({"error": "league or date is required"}), 400
    cmd += _proxy_args()
    env = dict(os.environ, OH_REQUEST_DELAY=os.getenv("SCRAPY_DELAY", "2"))
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT, env=env)
    except subprocess.TimeoutExpired:
        return jsonify({"error": "scrape timed out"}), 504
    rows = []
    for line in p.stdout.splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    if p.returncode != 0 and not rows:
        return jsonify({"error": "scrape failed", "detail": p.stderr[-2000:]}), 502
    return jsonify({"count": len(rows), "matches": rows})
