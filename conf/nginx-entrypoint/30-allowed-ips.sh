#!/bin/sh
# Generate /etc/nginx/allowed_ips.conf from $ALLOWED_IPS (comma-separated CIDRs/IPs).
# Run by the nginx image entrypoint (/docker-entrypoint.d) before nginx starts.
# Empty/unset ALLOWED_IPS -> "allow all;" (site stays open, e.g. for prod).
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
