#!/usr/bin/env bash
## Trigger an alert by killing the app, wait for it to fire, then restore.
## Used in: deck §10 demo, lab Track 02 grading checkpoint.

set -euo pipefail

echo "Step 1: kill app container"
docker stop day23-app >/dev/null

# Count active alerts via the Alertmanager v2 API. The state lives at
# status.state (nested), so a flat grep misses it — parse the JSON instead.
active_alerts() {
  curl -fsS http://localhost:9093/api/v2/alerts 2>/dev/null \
    | python -c "import json,sys; print(sum(1 for a in json.load(sys.stdin) if a.get('status',{}).get('state')=='active'))" 2>/dev/null \
    || echo 0
}

echo "Step 2: wait 90s for ServiceDown alert to fire"
for i in {1..18}; do
  sleep 5
  if [ "$(active_alerts)" -gt 0 ]; then
    echo "  alert fired (after ${i}*5s)"
    break
  fi
  echo "  no alert yet (${i}*5s)"
done

echo "Step 3: restart app"
docker start day23-app >/dev/null

echo "Step 4: wait 60s for alert to resolve"
for i in {1..12}; do
  sleep 5
  if [ "$(active_alerts)" -eq 0 ]; then
    echo "  alert resolved"
    exit 0
  fi
done

echo "alert did not resolve within 60s" >&2
exit 1
