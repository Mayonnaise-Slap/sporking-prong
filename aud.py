#!/usr/bin/env python3
"""Quick API surface audit — checks common endpoints for unauthenticated access."""

import argparse
import requests
from urllib.parse import urljoin

COMMON_PATHS = [
    "/docs", "/redoc", "/swagger", "/swagger-ui", "/swagger-ui.html",
    "/openapi.json", "/swagger.json", "/api-docs", "/api/docs",
    "/graphql", "/graphiql", "/playground",
    "/health", "/healthz", "/status", "/ping",
    "/metrics", "/actuator", "/actuator/health", "/actuator/env",
    "/api", "/api/v1", "/api/v2", "/version", "/info",
    "/.env", "/config", "/debug", "/admin",
]

DOC_HINTS = ("swagger", "redoc", "openapi", "graphiql", "api-docs", "/docs", "playground")

def audit(base, timeout, verify):
    session = requests.Session()
    session.headers.update({"User-Agent": "api-audit/1.0"})
    findings = []

    for path in COMMON_PATHS:
        url = urljoin(base, path)
        try:
            r = session.get(url, timeout=timeout, verify=verify, allow_redirects=True)
        except requests.RequestException as e:
            print(f"  ..  {path:<22} ERROR {type(e).__name__}")
            continue

        ct = r.headers.get("content-type", "").split(";")[0]
        open_access = r.status_code == 200
        is_doc = any(h in path.lower() for h in DOC_HINTS) or "swagger" in r.text[:2000].lower() or "openapi" in r.text[:2000].lower()

        if open_access:
            tag = "🎯 BINGO (docs!)" if is_doc else "OPEN"
            print(f"  {'!!' if is_doc else '::'}  {path:<22} {r.status_code} {ct}  -> {tag}")
            findings.append((path, r.status_code, ct, is_doc))
        else:
            print(f"  --  {path:<22} {r.status_code}")

    return findings

def main():
    ap = argparse.ArgumentParser(description="Poke common API endpoints for unauth access.")
    ap.add_argument("targets", nargs="+", help="Base URL(s), e.g. https://student.example.com")
    ap.add_argument("-t", "--timeout", type=float, default=5.0)
    ap.add_argument("-k", "--insecure", action="store_true", help="Skip TLS verification")
    args = ap.parse_args()

    for base in args.targets:
        if not base.startswith(("http://", "https://")):
            base = "http://" + base
        print(f"\n=== {base} ===")
        found = audit(base, args.timeout, not args.insecure)
        docs = [f for f in found if f[3]]
        print(f"\n  Summary: {len(found)} open endpoint(s), {len(docs)} doc endpoint(s).")
        if docs:
            print("  🎯 Exposed docs:", ", ".join(f[0] for f in docs))

if __name__ == "__main__":
    main()