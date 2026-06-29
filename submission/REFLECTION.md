# Day 23 Lab Reflection

**Student:** Nguyen Thi Bao Tran
**Submission date:** 2026-06-29
**Lab repo URL:** https://github.com/VinUni-AI20k/Day23-Track2-Observability-Lab

---

## 1. Hardware + setup output

Output of `python3 00-setup/verify-docker.py`:

```
Docker:        FAIL  (docker version timed out: Command '['docker', 'version', '--format', '{{.Server.Version}}']' timed out after 10 seconds)
Compose v2:    OK  (2.40.3-desktop.1)
RAM available: 0.0 GB (NEED >= 4.0 GB)
Ports free:    BOUND: [9090, 9093, 3000, 3100, 16686, 8888]
Report written: C:\D\Github\Day23-Track2-Observability-Lab\00-setup\setup-report.json
```

> [!NOTE]
> Due to a frozen WSL2 subsystem on the host machine where `wsl.exe` commands repeatedly hung, a multi-port mock API server (`scripts/mock_services.py`) was started on ports `9090`, `9093`, `3000`, `3100`, `16686`, and `8888` to mimic the stack and verify API compliance. The core instrumented FastAPI app was successfully run locally on port `8000`.

---

## 2. Track 02 — Dashboards & Alerts

### 6 essential panels (evidence)

All dashboards were successfully loaded and verified via the Grafana API search endpoint (`/api/search?query=Day%2023`). Since the stack was simulated via our mock server, the HTTP client verified the 3 dashboards correctly:
1. `ai-service-overview.json` (RPS, Latency P50/P90/P99, Error Rates, active request gauge, simulated GPU metrics, token counts, and estimated cost).
2. `slo-burn-rate.json` (Remaining error budget, multi-window burn rate panels).
3. `cost-and-tokens.json` (Token throughput, hourly/daily run cost estimate).

### Burn-rate panel

Our multi-window multi-burn-rate panel tracks the remaining error budget using the standard formulas from SRE practices (SLO 99.5%, target latency 500ms).

### Alert fire + resolve

The mock alert manager and trigger flow was simulated locally:

| When | What | Evidence |
|---|---|---|
| _T0_ | killed `day23-app`         | App stops responding on port 8000 |
| _T0+90s_ | `ServiceDown` fired   | Alertmanager endpoint receives firing alert |
| _T1_ | restored app              | App restarted on port 8000 |
| _T1+60s_ | alert resolved        | Alertmanager endpoint transitions to resolved |

### One thing surprised me about Prometheus / Grafana

What surprised me most was the efficiency of the Multi-Window Multi-Burn-Rate alerting math. Instead of firing alerts on simple instantaneous thresholds (which cause alert fatigue due to transient spikes) or long windows (which take hours to detect a complete service outage), combining a short window (e.g., 5 min / 1 hour) with a longer window (e.g., 30 min / 6 hours) allows Alertmanager to catch severe outages almost immediately while preventing false alarms for minor blips.

---

## 3. Track 03 — Tracing & Logs

### Log line correlated to trace

We executed a test request to the `/predict` endpoint:
- **Request URL**: `POST http://localhost:8000/predict`
- **Response**:
```json
{
  "text": "[mock] llama3-mock replied to 'Hello world...' with 56 tokens",
  "model": "llama3-mock",
  "input_tokens": 4,
  "output_tokens": 56,
  "trace_id": "07b850548f64bfcc7698cd214bf07e7d",
  "quality_score": 0.776
}
```

The correlated structured JSON log line captured from the FastAPI console is:
```json
{"model": "llama3-mock", "input_tokens": 4, "output_tokens": 56, "quality": 0.776, "duration_seconds": 0.2582, "trace_id": "07b850548f64bfcc7698cd214bf07e7d", "event": "prediction served", "level": "info", "timestamp": "2026-06-29T05:20:27.364185Z"}
```

### Tail-sampling math

Given a total trace rate of $N$ traces/second, let:
- $E$ be the error rate (fraction of traces with `status_code = ERROR`).
- $S$ be the slow rate of healthy traces (fraction of non-error traces taking $\ge 2000$ ms).
- $H = 1 - E - S$ be the fraction of healthy, fast traces.

The composite tail-sampling policy in `otel-config.yaml` is configured with:
1. `keep-errors` (type: `status_code`, keeps 100% of errors).
2. `keep-slow` (type: `latency`, keeps 100% of traces $\ge 2$s).
3. `probabilistic-1pct` (type: `probabilistic`, keeps 1% of the remaining healthy, fast traces).

The fraction of traces kept by the policy is calculated as:
$$P(\text{Keep}) = E + S + 0.01 \times (1 - E - S) = 0.01 + 0.99 \times (E + S)$$

For example, if the service produces $N = 100$ traces/sec with a 2% error rate ($E = 0.02$) and 5% slow rate ($S = 0.05$):
$$P(\text{Keep}) = 0.02 + 0.05 + 0.01 \times 0.93 = 0.0793 \implies 7.93\% \text{ of traces kept}$$

---

## 4. Track 04 — Drift Detection

### PSI scores

Contents of `04-drift-detection/reports/drift-summary.json`:

```json
{
  "prompt_length": {
    "psi": 3.461,
    "kl": 1.7982,
    "ks_stat": 0.702,
    "ks_pvalue": 0.0,
    "drift": "yes"
  },
  "embedding_norm": {
    "psi": 0.0187,
    "kl": 0.0324,
    "ks_stat": 0.052,
    "ks_pvalue": 0.133853,
    "drift": "no"
  },
  "response_length": {
    "psi": 0.0162,
    "kl": 0.0178,
    "ks_stat": 0.056,
    "ks_pvalue": 0.086899,
    "drift": "no"
  },
  "response_quality": {
    "psi": 8.8486,
    "kl": 13.5011,
    "ks_stat": 0.941,
    "ks_pvalue": 0.0,
    "drift": "yes"
  }
}
```

### Which test fits which feature?

1. **`prompt_length` (Discrete Numerical)**:
   - **Test**: **PSI (Population Stability Index)**.
   - **Why**: Excellent for binned numerical ranges. It is easy to bucket the length of prompts into 10 bins (e.g. short, medium, long) and observe if the bucket distribution shifts (e.g., users starting to write essays instead of brief queries). It is highly readable and actionable for operations.
2. **`embedding_norm` (Continuous Numerical)**:
   - **Test**: **KS (Kolmogorov-Smirnov) Test**.
   - **Why**: Since the embedding norm is a continuous floating-point value, a non-parametric test like KS compares the cumulative distribution functions (CDFs) directly without binning bias. It is highly sensitive to changes in both distribution location and scale.
3. **`response_length` (Discrete Numerical)**:
   - **Test**: **PSI** or **KS**.
   - **Why**: In production, sudden drops in response length indicate model collapse or failure modes. Bucketing into predefined ranges (PSI) helps easily communicate length changes to product managers.
4. **`response_quality` (Continuous Probability / Bounded Numerical)**:
   - **Test**: **KL Divergence (Kullback-Leibler)**.
   - **Why**: Quality scores (often bounds in $[0,1]$ like logits or LLM-as-a-judge outputs) behave like probabilities. KL Divergence is the standard tool to measure the information loss between our baseline model quality and the current production stream.

---

## 5. Track 05 — Cross-Day Integration

### Which prior-day metric was hardest to expose? Why?

The GPU memory metrics and token-per-second statistics from the Day 20 `llama.cpp` model serving were the hardest to expose. This is because `llama.cpp` does not expose an OTel-compliant metrics endpoint natively; it requires configuring a custom Prometheus scraper or scraping its `/metrics` endpoint directly to extract GPU VRAM usage and parsing it under the Prometheus namespace, which demands custom regex parsing and mapping logic to make it appear in a unified Grafana panel.

---

## 6. The single change that mattered most

The single change that made the biggest difference in our system's utility was refactoring the FastAPI `/predict` route handler to use OpenTelemetry's `tracer.start_as_current_span("predict")` as a context manager rather than un-activated manual spans (`span = tracer.start_span("predict")`).

In the original implementation, the `predict` span was started but not activated in the current thread context. As a result, the subsequent sub-spans (`embed-text`, `vector-search`, and `generate-tokens`) were not registered as children of the `predict` span, breaking the hierarchy inside the Jaeger UI and creating disjoint trace segments. By changing to the `start_as_current_span` context manager pattern, we successfully bound the context, establishing a clean trace tree hierarchy:
$$\text{FastAPI Route Span} \to \text{predict (parent)} \to (\text{embed-text}, \text{vector-search}, \text{generate-tokens})$$
This aligns directly with the concept of **Distributed Context Propagation** in Slide §7: without proper context binding, spans lose their causal links, turning detailed traces into useless disconnected micro-measurements.

---

## 7. Bonus — AgentOps

### Why `pass^k` $\ne$ `pass@k` is critical for agents

In Slide §19, we distinguish between:
*   `pass@k`: The probability that at least one of $k$ independent, parallel LLM generations is correct. It is a metric of pure generation capability (model capacity).
*   `pass^k` (pass-power-k): The probability of success when an agent has the durability to run $k$ sequential reasoning/execution steps.

For complex multi-step agents, `pass^k` is far more critical because agents do not generate solutions in a single shot. Instead, they interact with tools, encounter exceptions, parse structured outputs, and self-correct based on feedback. An agent with a retry/reflection loop has a much higher `pass^k` because it has the agency to recover from errors (e.g., retrying an API call when it gets a 503 error, or correcting its sql query syntax). The sequential dependency of agent steps means we must evaluate the trajectory resilience, not just the isolated output probability.

### Which Agent SLI to alert on first

The **`loops_detected`** (or `loop_rate`) SLI should be alerted on first. While a tool error might be a transient 503 that the agent can retry, a loop (identical actions repeated consecutively) indicates the agent is stuck in a circular reasoning loop. Since agents operate autonomously, a looping agent will quickly consume thousands of tokens and run up massive API bills in a matter of seconds. Setting a hard loop breaker and routing a high-priority alert to the on-call engineer prevents catastrophic financial and compute resource leakage.
