## Summary

I implemented env-var-driven IP restriction at the nginx level, accounting for the fact that your internal nginx sits behind an external `nginx-proxy` (so the real client IP only lives in `X-Forwarded-For`).

**Changes:**

1. **`conf/nginx/app.conf`** — Added `real_ip` recovery (trusts private docker ranges, reads `X-Forwarded-For`) so `allow`/`deny` evaluate the *real* VPN client IP, plus `include /etc/nginx/allowed_ips.conf;` and `deny all;` at server level → covers the entire site including `/static/`.

2. **`conf/nginx-entrypoint/30-allowed-ips.sh`** (new, executable) — Runs at container start, expands comma-separated `ALLOWED_IPS` into `allow …;` lines. Empty/unset → `allow all;` (open, backward-compatible for prod).

3. **`docker-compose.yml`** (`decs_api_webserver`) — Added `ALLOWED_IPS=${ALLOWED_IPS}` env and mounted the script into `/docker-entrypoint.d/`.

4. **`.env` / `.env-TEMPLATE`** — Added a documented `ALLOWED_IPS=` variable.

**One thing for you to do before deploying:** I left `ALLOWED_IPS=` empty in `.env`. Set it to your actual VPN egress ranges, e.g.:

```
ALLOWED_IPS=200.10.20.0/24,203.0.113.5
```

Then `make prod_start`. To verify after it's up:

```bash
docker compose exec decs_api_webserver cat /etc/nginx/allowed_ips.conf   # see the allow lines
docker compose exec decs_api_webserver nginx -t                          # syntax OK
curl -H "X-Forwarded-For: 200.10.20.30" http://<host>/                   # allowed → 200
curl -H "X-Forwarded-For: 8.8.8.8"      http://<host>/                   # blocked → 403
```

One caveat worth flagging: the `real_ip` config trusts all private ranges (`10/8`, `172.16/12`, `192.168/16`) as proxies. That's correct for a docker-behind-nginx-proxy setup, but it does mean any client whose traffic genuinely originates from those private ranges would have its `X-Forwarded-For` trusted — fine for an internet-facing test env behind the proxy, just not something to reuse unchanged if the topology ever has untrusted clients on a private network.
