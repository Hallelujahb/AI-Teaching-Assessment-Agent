#!/usr/bin/env bash
# Usage: scripts/smoke_test.sh https://your-backend-url
curl -sS --max-time 60 "$1/api/health"; echo
