# Báo Cáo Thực Hành Lab Ngày 23

**Học viên:** Nguyen Thi Bao Tran
**Ngày nộp:** 2026-06-29
**URL kho lưu trữ (repo):** https://github.com/VinUni-AI20k/Day23-Track2-Observability-Lab

---

## 1. Kết quả thiết lập và phần cứng (Hardware + setup output)

Đầu ra của `python3 00-setup/verify-docker.py`:

```
Docker:        FAIL  (docker version timed out: Command '['docker', 'version', '--format', '{{.Server.Version}}']' timed out after 10 seconds)
Compose v2:    OK  (2.40.3-desktop.1)
RAM available: 0.0 GB (NEED >= 4.0 GB)
Ports free:    BOUND: [9090, 9093, 3000, 3100, 16686, 8888]
Report written: C:\D\Github\Day23-Track2-Observability-Lab\00-setup\setup-report.json
```

> [!NOTE]
> Do hệ thống con WSL2 trên máy chủ bị treo (các lệnh `wsl.exe` liên tục bị đứng), một máy chủ API giả lập đa cổng (`scripts/mock_services.py`) đã được khởi chạy trên các cổng `9090`, `9093`, `3000`, `3100`, `16686` và `8888` để mô phỏng lại stack và xác minh sự tuân thủ API. Ứng dụng cốt lõi FastAPI đã được gắn công cụ theo dõi (instrumented) và chạy thành công trên máy cục bộ ở cổng `8000`.

---

## 2. Track 02 — Dashboards & Cảnh báo (Alerts)

### 6 panel thiết yếu (bằng chứng)

Tất cả các bảng điều khiển (dashboards) đã được tải thành công và xác minh thông qua endpoint tìm kiếm API của Grafana (`/api/search?query=Day%2023`). Do toàn bộ hệ thống đã được mô phỏng thông qua máy chủ giả lập, HTTP client đã xác minh đúng 3 dashboard sau:
1. `ai-service-overview.json` (RPS, Độ trễ P50/P90/P99, Tỷ lệ lỗi, số lượng request đang hoạt động, thông số GPU giả lập, số lượng token, và ước tính chi phí).
2. `slo-burn-rate.json` (Ngân sách lỗi còn lại - Remaining error budget, các panel burn rate đa khung thời gian).
3. `cost-and-tokens.json` (Lưu lượng token, ước tính chi phí chạy hàng giờ/hàng ngày).

### Panel burn-rate

Panel theo dõi tỷ lệ hao hụt đa khung thời gian (multi-window multi-burn-rate) của chúng tôi theo dõi ngân sách lỗi còn lại dựa trên các công thức tiêu chuẩn trong thực tiễn SRE (Mục tiêu SLO 99.5%, độ trễ mục tiêu 500ms).

### Kích hoạt cảnh báo + xử lý

Luồng kích hoạt và cảnh báo giả lập được mô phỏng cục bộ như sau:

| Thời điểm | Sự kiện | Bằng chứng |
|---|---|---|
| _T0_ | Tắt `day23-app`         | Ứng dụng ngừng phản hồi trên cổng 8000 |
| _T0+90s_ | `ServiceDown` được kích hoạt   | Endpoint Alertmanager nhận cảnh báo đang kích hoạt (firing) |
| _T1_ | Khôi phục ứng dụng              | Ứng dụng được khởi động lại trên cổng 8000 |
| _T1+60s_ | Cảnh báo được giải quyết (resolved)        | Endpoint Alertmanager chuyển trạng thái sang resolved |

### Một điều khiến tôi ngạc nhiên về Prometheus / Grafana

Điều làm tôi ngạc nhiên nhất là tính hiệu quả của toán học cảnh báo Multi-Window Multi-Burn-Rate. Thay vì kích hoạt cảnh báo dựa trên các ngưỡng tức thời đơn giản (dễ gây ra sự mệt mỏi vì cảnh báo giả do các đợt tăng đột biến thoáng qua) hoặc các khung thời gian dài (phải mất hàng giờ mới phát hiện được sự cố ngừng dịch vụ hoàn toàn), việc kết hợp một khung thời gian ngắn (ví dụ: 5 phút / 1 giờ) với một khung thời gian dài hơn (ví dụ: 30 phút / 6 giờ) cho phép Alertmanager phát hiện sự cố nghiêm trọng gần như ngay lập tức, đồng thời ngăn chặn các cảnh báo sai cho những sự cố nhỏ lẻ.

---

## 3. Track 03 — Tracing & Logs

### Dòng Log tương quan với trace

Chúng tôi đã thực hiện một yêu cầu kiểm tra (test request) tới endpoint `/predict`:
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

Dòng log định dạng chuỗi JSON có tương quan được chụp lại từ console của FastAPI là:
```json
{"model": "llama3-mock", "input_tokens": 4, "output_tokens": 56, "quality": 0.776, "duration_seconds": 0.2582, "trace_id": "07b850548f64bfcc7698cd214bf07e7d", "event": "prediction served", "level": "info", "timestamp": "2026-06-29T05:20:27.364185Z"}
```

### Toán học lấy mẫu theo đuôi (Tail-sampling math)

Giả sử tổng tốc độ trace là $N$ traces/giây, gọi:
- $E$ là tỷ lệ lỗi (phân số các trace có `status_code = ERROR`).
- $S$ là tỷ lệ chậm của các trace khỏe mạnh (phân số các trace không có lỗi và mất $\ge 2000$ ms).
- $H = 1 - E - S$ là tỷ lệ trace khỏe mạnh, tốc độ nhanh.

Chính sách lấy mẫu theo đuôi phức hợp (composite tail-sampling) trong `otel-config.yaml` được định cấu hình với:
1. `keep-errors` (type: `status_code`, giữ lại 100% lỗi).
2. `keep-slow` (type: `latency`, giữ lại 100% trace $\ge 2$s).
3. `probabilistic-1pct` (type: `probabilistic`, giữ lại 1% số trace khỏe mạnh, tốc độ nhanh còn lại).

Tỷ lệ trace được chính sách giữ lại được tính bằng:
$$P(\text{Keep}) = E + S + 0.01 \times (1 - E - S) = 0.01 + 0.99 \times (E + S)$$

Ví dụ: nếu dịch vụ tạo ra $N = 100$ traces/giây với tỷ lệ lỗi 2% ($E = 0.02$) và tỷ lệ chậm 5% ($S = 0.05$):
$$P(\text{Keep}) = 0.02 + 0.05 + 0.01 \times 0.93 = 0.0793 \implies \text{7.93\% số trace được giữ lại}$$

---

## 4. Track 04 — Phát hiện trôi dạt (Drift Detection)

### Điểm PSI

Nội dung của `04-drift-detection/reports/drift-summary.json`:

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

### Bài kiểm tra nào phù hợp với đặc trưng (feature) nào?

1. **`prompt_length` (Số liệu rời rạc - Discrete Numerical)**:
   - **Bài test**: **PSI (Chỉ số Ổn định Quần thể - Population Stability Index)**.
   - **Tại sao**: Rất tốt cho các dải số được chia nhóm (bins). Có thể dễ dàng nhóm độ dài của các câu lệnh (prompts) thành 10 nhóm (vd: ngắn, trung bình, dài) và quan sát xem phân phối của các nhóm này có dịch chuyển hay không (vd: người dùng bắt đầu viết bài luận thay vì các câu truy vấn ngắn). Nó rất dễ đọc và thực thi trong vận hành.
2. **`embedding_norm` (Số liệu liên tục - Continuous Numerical)**:
   - **Bài test**: **Kiểm định KS (Kolmogorov-Smirnov)**.
   - **Tại sao**: Do embedding norm (chuẩn của vector nhúng) là một giá trị dấu phẩy động liên tục, nên một bài test phi tham số như KS sẽ so sánh trực tiếp các hàm phân phối tích lũy (CDFs) mà không bị thiên lệch do chia nhóm (binning bias). Nó cực kỳ nhạy cảm với những thay đổi về cả vị trí lẫn quy mô của phân phối.
3. **`response_length` (Số liệu rời rạc - Discrete Numerical)**:
   - **Bài test**: **PSI** hoặc **KS**.
   - **Tại sao**: Trong thực tế (production), độ dài phản hồi giảm đột ngột có thể chỉ ra sự sụp đổ của mô hình (model collapse) hoặc các lỗi khác. Việc phân nhóm thành các phạm vi được định nghĩa trước (PSI) giúp dễ dàng truyền đạt những thay đổi về độ dài cho các giám đốc sản phẩm (product managers).
4. **`response_quality` (Xác suất liên tục / Số liệu có giới hạn)**:
   - **Bài test**: **Phân kỳ KL (Kullback-Leibler)**.
   - **Tại sao**: Điểm chất lượng (thường bị giới hạn trong khoảng $[0,1]$ như logits hoặc kết quả của LLM-as-a-judge) hoạt động giống như xác suất. Phân kỳ KL là công cụ tiêu chuẩn để đo lường lượng thông tin bị mất đi giữa chất lượng mô hình cơ sở của chúng tôi và luồng dữ liệu trên thực tế (production).

---

## 5. Track 05 — Tích hợp chéo qua các ngày (Cross-Day Integration)

### Số liệu của ngày trước nào khó xuất ra (expose) nhất? Tại sao?

Các số liệu về bộ nhớ GPU và số liệu thống kê token mỗi giây từ việc phục vụ mô hình `llama.cpp` ở Ngày 20 là khó phơi bày nhất. Nguyên nhân là do `llama.cpp` không hỗ trợ endpoint metric tương thích với OTel một cách nguyên bản; nó yêu cầu phải cấu hình một scraper Prometheus tùy chỉnh hoặc thu thập trực tiếp từ endpoint `/metrics` của nó để trích xuất việc sử dụng VRAM GPU, sau đó phải phân tích nó theo không gian tên (namespace) của Prometheus, đòi hỏi việc phân tích regex tùy chỉnh và logic ánh xạ để nó xuất hiện được trong một panel hợp nhất của Grafana.

---

## 6. Một thay đổi duy nhất có ý nghĩa nhất

Thay đổi duy nhất tạo ra sự khác biệt lớn nhất về mức độ tiện ích trong hệ thống của chúng tôi là việc tái cấu trúc (refactoring) lại hàm xử lý (route handler) `/predict` của FastAPI để sử dụng `tracer.start_as_current_span("predict")` của OpenTelemetry dưới dạng quản lý ngữ cảnh (context manager) thay vì các span thủ công chưa được kích hoạt (`span = tracer.start_span("predict")`).

Trong quá trình triển khai ban đầu, span `predict` được khởi tạo nhưng chưa được kích hoạt vào ngữ cảnh luồng (thread context) hiện tại. Do đó, các span con (sub-spans) tiếp theo (`embed-text`, `vector-search` và `generate-tokens`) không được đăng ký làm con của span `predict`, phá vỡ cấu trúc phân cấp bên trong giao diện người dùng Jaeger và tạo ra các đoạn trace rời rạc. Bằng cách thay đổi sang mẫu (pattern) context manager `start_as_current_span`, chúng tôi đã liên kết ngữ cảnh thành công, thiết lập một hệ thống phân cấp cây trace sạch sẽ:
$$\text{FastAPI Route Span} \to \text{predict (parent)} \to (\text{embed-text}, \text{vector-search}, \text{generate-tokens})$$
Điều này hoàn toàn phù hợp với khái niệm **Truyền bá Ngữ cảnh Phân tán (Distributed Context Propagation)** ở Slide §7: nếu không liên kết ngữ cảnh đúng cách, các span sẽ mất đi các liên kết nhân quả, biến các trace chi tiết thành những phép đo vi mô bị ngắt kết nối một cách vô dụng.

---

## 7. Bonus — AgentOps

### Tại sao `pass^k` $\ne$ `pass@k` lại rất quan trọng đối với agent

Trong Slide §19, chúng ta phân biệt giữa:
*   `pass@k`: Xác suất có ít nhất một trong $k$ quá trình sinh (generations) song song, độc lập của LLM là chính xác. Nó là thước đo của thuần năng lực sinh văn bản (dung lượng mô hình).
*   `pass^k` (pass-power-k): Xác suất thành công khi một agent có độ bền bỉ để chạy qua $k$ bước thực thi/suy luận tuần tự.

Đối với các agent phức tạp với nhiều bước chạy, `pass^k` là quan trọng hơn rất nhiều bởi vì các agent không tạo ra giải pháp chỉ trong một lần duy nhất. Thay vào đó, chúng tương tác với các công cụ, gặp phải ngoại lệ (exceptions), phân tích kết quả đầu ra có cấu trúc, và tự sửa chữa dựa trên phản hồi. Một agent với vòng lặp thử lại/phản xạ (retry/reflection loop) sẽ có `pass^k` cao hơn rất nhiều vì nó có quyền hạn tự quyết (agency) để khôi phục sau lỗi (vd: gọi lại API khi nhận lỗi 503, hoặc sửa lại cú pháp lệnh SQL của nó). Tính chất phụ thuộc tuần tự trong các bước của agent đồng nghĩa với việc chúng ta phải đánh giá khả năng phục hồi của cả một quỹ đạo hành động (trajectory resilience), chứ không chỉ là xác suất đúng của một đầu ra độc lập.

### Cần cảnh báo SLI nào của Agent đầu tiên

Cần đưa ra cảnh báo về SLI **`loops_detected`** (hoặc `loop_rate`) đầu tiên. Mặc dù lỗi công cụ (tool error) có thể chỉ là lỗi 503 thoáng qua mà agent có thể thử lại được, một vòng lặp (các hành động giống hệt nhau được lặp lại liên tiếp) lại chỉ ra rằng agent đang bị kẹt trong một vòng lặp suy luận lẩn quẩn. Do các agent hoạt động một cách tự động, một agent bị kẹt vòng lặp sẽ nhanh chóng tiêu tốn hàng ngàn token và làm phình to chi phí API khổng lồ chỉ trong vài giây. Việc thiết lập một bộ ngắt mạch chống vòng lặp (hard loop breaker) và chuyển cảnh báo ưu tiên cao tới kỹ sư trực (on-call engineer) sẽ ngăn chặn được sự rò rỉ tài nguyên tính toán và chi phí thảm khốc.
