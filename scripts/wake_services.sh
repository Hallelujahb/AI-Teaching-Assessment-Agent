#!/usr/bin/env bash
# Usage: scripts/wake_services.sh BACKEND_URL FRONTEND_URL
# Free hosts sleep. Run this a few minutes before the demo.
for url in "$1/api/health" "$2"; do
  curl -sS -o /dev/null --max-time 90 -w "%{http_code} $url\n" "$url"
done
