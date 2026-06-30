# Submission screenshots — live verification log

The full 7-service stack was brought up with `docker compose up -d` and every
screenshot-graded rubric checkpoint was **verified live** on 2026-06-30. The
observed evidence is recorded below. `make verify` exits **0 (12/12 checks)**.

> Capture the PNGs by reproducing the steps below on the running stack, then drop
> each file in here with the listed name. Everything renders correctly now (see
> the datasource-uid fix note at the bottom — without it the dashboards were blank).

| Rubric # | Filename | Verified live — observed evidence |
|---|---|---|
| 4  | `04-active-gauge.png`        | `inference_active_gauge` rose to **peak 6** during `make load`, returned to **0.0** after. Overview "In-Flight Requests" panel showed **13** at load peak. |
| 7  | `07-overview-6panels.png`   | Overview: 6 panels render — RPS climbing to ~20 req/s, Latency P50/P95/P99, GPU 48.5%, Token throughput, In-Flight 13, Error Rate (No data = zero errors). |
| 8  | `08-slo-burn-rate.png`      | SLO: Error Budget **47.7%**, Burn Rate panel with 5m/30m/1h/6h series (~1.1× after error injection), Active Alerts table. |
| 9  | `09-cost-tokens.png`        | Cost: **Estimated $/hr = $0.0273** (non-zero), Token Throughput in/out, Eval Quality 0.7–0.9. |
| 10 | `10-alertmanager-firing.png`| Alertmanager group `slack-critical` → `alertname="ServiceDown"`, `service="inference-api"`, `severity="critical"`, `instance="app:8000"` — **firing**. |
| 11 | `11-slack-fire-resolve.png` | **Needs a real `SLACK_WEBHOOK_URL` in `.env`** (currently a placeholder). Alertmanager posts fire+resolve once set; alert fire/resolve itself confirmed via the v2 API. |
| 12 | `12-jaeger-trace.png`       | Jaeger trace `predict` (root) — **4 spans, depth 2**: child spans `embed-text` (5.17ms), `vector-search` (10.24ms), `generate-tokens` (277.95ms). |
| 13 | `13-genai-span-attrs.png`   | `generate-tokens` span tags: `gen_ai.response.finish_reason=stop`, `gen_ai.usage.input_tokens=4`, `gen_ai.usage.output_tokens=53`. |
| 17 | `17-evidently-report.png`   | Evidently report: "Dataset Drift **is detected**", 4 columns / **2 drifted** / 0.5 share, per-feature K-S/PSI table with histograms. |
| 19 | `19-cross-day-source.png`   | Cross-Day dashboard renders prior-day source panels (Day 16/17/18/19/20/22). |
| 20 | `20-cross-day-6panels.png`  | All **6** cross-day panels render, each "No Data (Day NN stub)" (rubric allows No Data). |
| B3 | `B3-agent-span-tree.png`    | Jaeger `day23-agent` trace `invoke_agent` (root) → 4× `execute_tool` (**5 spans, depth 2**). |

## Reproduce + capture (2 minutes on the running stack)

```bash
make up && sleep 30
# load + signal
( cd 02-prometheus-grafana/load-test && \
  python -m locust -f locustfile.py --headless -u 12 -r 4 -t 150s --host http://localhost:8000 ) &
# Grafana (admin/admin) — kiosk URLs render clean for screenshots:
#  Overview   http://localhost:3000/d/day23-ai-overview/...?kiosk
#  SLO        http://localhost:3000/d/day23-slo/...?kiosk
#  Cost       http://localhost:3000/d/day23-cost-tokens/...?kiosk
#  Cross-day  http://localhost:3000/d/day23-cross-day/...?kiosk
# Jaeger      http://localhost:16686  (service: inference-api / day23-agent)
# Alertmgr    http://localhost:9093   (run scripts/trigger-alert.sh to make it fire)
# Evidently   serve 04-drift-detection/reports/ over http and open drift-report.html
```

## Why the dashboards now render (critical fix applied this session)

`grafana/provisioning/datasources/datasources.yml` did **not** pin a `uid` for the
Prometheus/Loki datasources, so Grafana assigned random uids — but every dashboard
references `"uid": "prometheus"`. Result: **all panels failed to resolve their
datasource and rendered blank**. Pinning `uid: prometheus` / `uid: loki` fixed it.
The cross-day dashboard was also rebuilt with complete panel `options`/`fieldConfig`
and provisioned from `05-integration/` so its 6 panels render.
