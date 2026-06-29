# Submission screenshots — capture manifest

Rubric verifies ~11 core checkpoints (+1 bonus) by screenshot. Capture each as a PNG
with the filename below and commit it into this folder. Grader cross-references this
manifest against `rubric.md`.

> **Status note (2026-06-29):** On this machine the WSL2/Docker backend is hung, so the
> 7-service stack was reproduced with `scripts/mock_services.py` (ports 9090/9093/3000/3100/16686/8888)
> and the FastAPI app ran locally on :8000. File-based evidence (`drift-summary.json`,
> `agentops-report.json`, `setup-report.json`, `REFLECTION.md`) is committed. The image
> captures below are **pending a real `make up`** on a host with a healthy Docker engine —
> bring the stack up, run `make demo`, then capture each shot.

| Rubric # | Filename | What to show |
|---|---|---|
| 4  | `04-active-gauge.png`        | `inference_active_gauge` rising during `make load`, returning to 0 after |
| 7  | `07-overview-6panels.png`   | Overview dashboard, all 6 panels rendering data post-load |
| 8  | `08-slo-burn-rate.png`      | SLO burn-rate dashboard with populated burn rates |
| 9  | `09-cost-tokens.png`        | Cost-and-tokens dashboard showing non-zero $/hr estimate |
| 10 | `10-alertmanager-firing.png`| Alertmanager UI showing `ServiceDown` firing after `make alert` |
| 11 | `11-slack-fire-resolve.png` | Slack channel showing BOTH the fire and the resolve message |
| 12 | `12-jaeger-trace.png`       | Jaeger trace for `POST /predict` with 3 child spans |
| 13 | `13-genai-span-attrs.png`   | Span attributes panel following GenAI semantic conventions |
| 17 | `17-evidently-report.png`   | Evidently HTML drift report rendered in browser |
| 19 | `19-cross-day-source.png`   | Cross-day dashboard with ≥1 prior-day source connected |
| 20 | `20-cross-day-6panels.png`  | Cross-day dashboard, all 6 panels (data or "No Data") |
| B3 | `B3-agent-span-tree.png`    | Jaeger span tree for `day23-agent` |

## How to capture quickly

```bash
make up && sleep 30      # stack healthy
make demo                # load -> alert -> trace -> drift, generates all signal
# Grafana   http://localhost:3000  (admin/admin)
# Alertmgr  http://localhost:9093
# Jaeger    http://localhost:16686
# Evidently open 04-drift-detection/reports/drift-report.html
```
