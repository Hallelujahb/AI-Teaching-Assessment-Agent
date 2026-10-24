#!/usr/bin/env bash
# Usage: scripts/smoke_test.sh https://your-backend.example.com
# Checks the deployed API reads real records. No keys needed.
BASE="${1:?usage: smoke_test.sh BACKEND_URL}"; BASE="${BASE%/}"
fail=0
check() { # name, url
  code=$(curl -s -o /tmp/smoke.out -w '%{http_code}' --max-time 90 "$2")
  if [ "$code" = "200" ]; then echo "PASS  $1"; else echo "FAIL  $1 (HTTP $code)"; fail=1; fi
}
check "health" "$BASE/api/health"
check "list assessments" "$BASE/api/assessments"
AID=$(grep -o "\"id\": *\"\?[A-Za-z0-9_-]*" /tmp/smoke.out | head -1 | sed "s/.*: *\"\?//")
[ -n "$AID" ] || { echo "FAIL  no assessment id found"; exit 1; }
check "assessment + rubric ($AID)" "$BASE/api/assessments/$AID"
check "list batches ($AID)" "$BASE/api/assessments/$AID/batches"
[ $fail = 0 ] && echo "ALL PASSED" || echo "SOME FAILED"; exit $fail
