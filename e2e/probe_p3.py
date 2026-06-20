from utils.api import login_client, csrf_token, auth_headers, page_q
import json
import sys

for ver, base in [("4.1", "http://localhost:18088"), ("6.0", "http://localhost:18089")]:
    c, t = login_client(base)
    try:
        r = c.get("/api/v1/users/?q=" + page_q(0, 5), headers=auth_headers(t))
        sys.stdout.write(f"{ver} users: {r.status_code} {len(r.json().get('result', []))}\n")
    except Exception as e:
        sys.stdout.write(f"{ver} users ERR: {e} text={r.text[:100]}\n")
    try:
        r2 = c.get("/api/v1/roles/?q=" + page_q(0, 10), headers=auth_headers(t))
        sys.stdout.write(f"{ver} roles: {r2.status_code} {len(r2.json().get('result', []))}\n")
    except Exception as e:
        sys.stdout.write(f"{ver} roles ERR: {e} text={r2.text[:100]}\n")
    try:
        r3 = c.get("/api/v1/me/", headers=auth_headers(t))
        sys.stdout.write(f"{ver} me: {r3.status_code} {r3.text[:80]}\n")
    except Exception as e:
        sys.stdout.write(f"{ver} me ERR: {e} text={r3.text[:100]}\n")
    try:
        r5 = c.post("/api/v1/chart/", json={"slice_name": "x"})
        sys.stdout.write(f"{ver} no-csrf POST: {r5.status_code} {r5.text[:80]}\n")
    except Exception as e:
        sys.stdout.write(f"{ver} no-csrf POST ERR: {e}\n")
    c.close()
sys.stdout.flush()
