"""Verify Superset example data by querying datasets, charts, dashboards."""
import json
import os
import sys
import urllib.request
import urllib.error


def login(base, user, pwd):
    req = urllib.request.Request(
        f"{base}/api/v1/security/login",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": user, "password": pwd, "provider": "db", "refresh": True}).encode(),
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)["access_token"]


def get(base, token, path):
    req = urllib.request.Request(
        f"{base}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def main(base, label):
    print(f"\n========== {label} ({base}) ==========")
    try:
        token = login(base, "admin", "admin")
    except Exception as e:  # noqa: BLE001
        print(f"login FAILED: {e}")
        return 1
    print(f"token len: {len(token)}")

    ds = get(base, token, "/api/v1/dataset/?q=" + urllib.parse.quote(json.dumps({"page_size": 100})))
    print(f"datasets: {ds.get('count')}")
    schemas = {}
    for r in ds.get("result", []):
        s = r.get("schema") or "<None>"
        schemas[s] = schemas.get(s, 0) + 1
    for s, n in sorted(schemas.items(), key=lambda x: -x[1]):
        print(f"  schema={s!r:<10} count={n}")

    dboards = get(base, token, "/api/v1/dashboard/?q=" + urllib.parse.quote(json.dumps({"page_size": 100})))
    print(f"dashboards: {dboards.get('count')}")
    for r in dboards.get("result", [])[:8]:
        print(f"  - id={r['id']:>3}  slug={(r.get('slug') or '?')[:35]:<35}  title={r.get('dashboard_title')}")

    charts = get(base, token, "/api/v1/chart/?q=" + urllib.parse.quote(json.dumps({"page_size": 100})))
    print(f"charts: {charts.get('count')}")
    return 0


if __name__ == "__main__":
    import urllib.parse  # noqa: E402
    code = 0
    for base, label in [
        ("http://localhost:18088", "4.1"),
        ("http://localhost:18089", "6.0"),
    ]:
        try:
            code |= main(base, label)
        except Exception as e:  # noqa: BLE001
            print(f"{label} error: {e}")
            code |= 1
    sys.exit(code)
