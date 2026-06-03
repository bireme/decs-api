# Restrict test-environment access to VPN IPs (nginx allow-list)

## Context

The DeCS API needs to be deployed to a **test environment** that should only be
reachable through a VPN. Access must be limited to a configurable set of source
IP ranges, controlled by an **environment variable** so the same image/config can
be deployed to test (restricted) and prod (open) without code changes.

Constraints discovered during exploration:

- The internal nginx (`decs_api_webserver`, `nginx:1.31-alpine`) sits **behind an
  external `nginx-proxy`** (driven by `VIRTUAL_HOST`/`LETSENCRYPT_HOST`). So
  nginx's `$remote_addr` is the *proxy's* container IP, **not** the real VPN
  client. The real client IP is only present in the `X-Forwarded-For` header that
  nginx-proxy appends. A naive `allow/deny $remote_addr` would block everyone.
- The allowed value is **multiple CIDR ranges**, and the restriction must cover
  the **entire site** (including `/static/`).
- nginx config is mounted from `conf/nginx/` into `/etc/nginx/conf.d/`. nginx
  does not read env vars in its config, and `envsubst` cannot expand a list into
  multiple `allow` lines — so the allow-list is generated at container start.

Outcome: setting `ALLOWED_IPS` in the env file restricts the whole site to those
CIDRs; leaving it empty/unset keeps the site open (backward compatible for prod).

## Approach

Recover the real client IP via the nginx `real_ip` module, then apply an
`allow`/`deny` list that is generated from the `ALLOWED_IPS` env var by a small
`docker-entrypoint.d` script when the nginx container starts.

### 1. nginx server config — `conf/nginx/app.conf`

Inside the existing `server { listen 80; ... }` block, **before** the `location`
blocks, add real-IP recovery and the generated allow-list include:

```nginx
server {
    listen 80;
    server_tokens off;

    # Recover real client IP from X-Forwarded-For (set by the fronting nginx-proxy).
    # Trust only private ranges (the internal docker networks / proxy).
    set_real_ip_from 10.0.0.0/8;
    set_real_ip_from 172.16.0.0/12;
    set_real_ip_from 192.168.0.0/16;
    real_ip_header    X-Forwarded-For;
    real_ip_recursive on;

    # IP allow-list, generated from $ALLOWED_IPS at container start.
    # When ALLOWED_IPS is empty the generated file is just "allow all;".
    include /etc/nginx/allowed_ips.conf;
    deny all;

    # Return a clean JSON 403 (instead of nginx's default HTML page) when the
    # allow-list denies the request. recursive_error_pages is off by default,
    # so the return below does not re-trigger this handler.
    error_page 403 @forbidden;
    location @forbidden {
        default_type application/json;
        return 403 '{"detail":"Forbidden: access is restricted to authorized networks."}';
    }
    

    location / { ... }          # unchanged
    location /static/ { ... }   # unchanged
}
```

Notes:
- `allow`/`deny` placed at **server** context is inherited by both `location`
  blocks (neither defines its own access rules) → entire site is covered.
- The include lives at `/etc/nginx/allowed_ips.conf` (NOT under `conf.d/`, which
  is auto-included into the `http {}` context and would misapply the directives).
- `deny all;` stays static in `app.conf`; first-match-wins means when the
  generated file is `allow all;` the deny is never reached.

### 2. Allow-list generator — new file `conf/nginx-entrypoint/30-allowed-ips.sh`

The official nginx image runs/sources every script in `/docker-entrypoint.d/`
before starting nginx. This script turns the comma-separated `ALLOWED_IPS` into
`allow` lines:

```sh
#!/bin/sh
# Generate /etc/nginx/allowed_ips.conf from $ALLOWED_IPS (comma-separated CIDRs/IPs).
OUT=/etc/nginx/allowed_ips.conf
if [ -z "$ALLOWED_IPS" ]; then
    echo "allow all;" > "$OUT"
else
    : > "$OUT"
    echo "$ALLOWED_IPS" | tr ',' '\n' | while read -r cidr; do
        cidr=$(echo "$cidr" | xargs)   # trim whitespace
        [ -n "$cidr" ] && echo "allow $cidr;" >> "$OUT"
    done
fi
```

- No `set -e`/`exit` so it is safe even when the entrypoint *sources* it.
- Make it executable on the host (`chmod +x`) so it runs cleanly; the nginx
  entrypoint also sources non-executable `*.sh` as a fallback.

### 3. Wire the var + script into `docker-compose.yml` (`decs_api_webserver`)

- Add to `environment:`  → `- ALLOWED_IPS=${ALLOWED_IPS}`
- Add to `volumes:`
  `- ./conf/nginx-entrypoint/30-allowed-ips.sh:/docker-entrypoint.d/30-allowed-ips.sh:ro`

(`docker-compose-dev.yml` runs no nginx, so it needs no change — the dev server
stays unrestricted.)

### 4. Env files

- `.env` (test deployment): add the real VPN CIDRs, e.g.
  `ALLOWED_IPS=200.10.20.0/24,203.0.113.5`
- `.env-TEMPLATE`: add `ALLOWED_IPS=` (empty = open; documents the var for prod).

## Files to change

- `conf/nginx/app.conf` — add real_ip block + `include` + `deny all;`
- `conf/nginx-entrypoint/30-allowed-ips.sh` — **new**, generator script (chmod +x)
- `docker-compose.yml` — `decs_api_webserver`: `ALLOWED_IPS` env + script volume
- `.env` — set `ALLOWED_IPS` to the VPN ranges
- `.env-TEMPLATE` — add empty `ALLOWED_IPS=`

## Verification

1. `ALLOWED_IPS=200.10.20.0/24,203.0.113.5` in `.env`, then
   `make prod_start` (or `make prod_run`).
2. Confirm config + generated file:
   - `docker compose exec decs_api_webserver cat /etc/nginx/allowed_ips.conf`
     → shows the `allow ...;` lines.
   - `docker compose exec decs_api_webserver nginx -t` → syntax OK.
3. Simulate client IPs via the recovered header (source is a private docker IP,
   so `real_ip` trusts it and uses the spoofed XFF):
   - Allowed: `curl -H "X-Forwarded-For: 200.10.20.30" http://<host>/` → 200.
   - Blocked: `curl -H "X-Forwarded-For: 8.8.8.8" http://<host>/` → 403.
   - Also verify a `/static/` path returns 403 for the blocked IP (whole-site).
4. Set `ALLOWED_IPS=` (empty), recreate the webserver container, confirm the site
   responds for any IP (open) → backward-compatible default for prod.
5. End-to-end: connect through the actual VPN and load the site; disconnect and
   confirm it is refused.
