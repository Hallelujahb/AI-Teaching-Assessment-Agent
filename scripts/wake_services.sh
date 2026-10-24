#!/usr/bin/env bash
# Usage: scripts/wake_services.sh BACKEND_URL [FRONTEND_URL]
# Free hosts sleep. Run before the demo. /api/health also wakes the database.
BACKEND="${1:?usage: wake_services.sh BACKEND_URL [FRONTEND_URL]}"; BACKEND="${BACKEND%/}"
for i in 1 2 3 4 5; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 90 "$BACKEND/api/health")
  echo "backend attempt $i: HTTP $code"; [ "$code" = "200" ] && break; sleep 10
done
if [ -n "$2" ]; then echo "frontend: HTTP $(curl -s -o /dev/null -w '%{http_code}' --max-time 60 "${2%/}/")"; fi
