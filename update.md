## Update Log — Day04-E403 Order Agent

## Bối cảnh

Score ban đầu: **38.46%** (500/1300 điểm). Mục tiêu: đạt gần 100%.

---

## Phân tích lỗi gốc

### 1. Customer fields trống trong saved order
Tất cả normal cases đều bị `customer.name`, `customer.phone`, `customer.email`, `customer.shipping_address` = `""`.  
**Nguyên nhân:** System prompt cũ không hướng dẫn model phải đưa các field này vào JSON payload của `save_order`.  
**Hệ quả:** `order_id` sai hoàn toàn vì được tính bằng hash(email + phone + items).

### 2. `campaign_code` và `discount_rate` sai
Model không truyền `campaign_code` từ `get_discount` vào `save_order`. Một số case còn lấy sai `discount_rate` (0.1 thay vì 0.2).  
**Nguyên nhân:** `get_discount` tool chỉ có docstring là `"Get discount."` — không rõ phải dùng email làm seed, không rõ phải truyền kết quả vào `save_order`.

### 3. Clarification cases gọi tools khi không nên
`clarification_missing_shipping` và `clarification_missing_email_only` bị điểm 0 vì agent tiếp tục gọi tools và lưu đơn thay vì hỏi user.  
**Nguyên nhân:** System prompt cũ nói "handle it as best as you can" — model hiểu là "cố gắng xử lý".

### 4. Guardrail case gọi tools vòng vòng
`guardrail_discount_and_stock_bypass` tạo ra 15 tool calls (`save_order` gọi 6 lần) rồi vẫn lưu đơn.  
**Nguyên nhân:** Không có rule từ chối rõ ràng khi request chứa yêu cầu bypass.

### 5. `save_path` dùng backslash Windows
Trên Windows, `str(Path("artifacts") / "orders" / f"{order_id}.json")` trả về `artifacts\orders\ORD-xxx.json`.  
So sánh với expected `artifacts/orders/ORD-xxx.json` → fail toàn bộ `save_path` check.

---

## Những thay đổi đã thực hiện

### Thay đổi 1 — `simple_solution/agent/graph.py`: System prompt (lần 1)

Viết lại `build_system_prompt()` từ đầu với cấu trúc rõ ràng:

- **GUARDRAILS:** Từ chối ngay (không gọi tool) nếu request chứa bypass stock / fake discount / fake invoice.
- **PRE-FLIGHT CHECK:** Bắt buộc có đủ 4 field (tên, điện thoại, email, địa chỉ) trước khi gọi bất kỳ tool nào. Thiếu field nào → hỏi field đó, dừng lại.
- **TOOL SEQUENCE:** Liệt kê thứ tự 5 bước rõ ràng.
- **save_order PAYLOAD:** Ví dụ JSON đầy đủ với tất cả field bắt buộc, kể cả `campaign_code` từ `get_discount`.
- Gợi ý có thể gọi `list_products` và `get_discount` song song.

### Thay đổi 2 — `simple_solution/agent/graph.py`: Tool docstrings

| Tool | Trước | Sau |
|---|---|---|
| `list_products` | `"Find products."` | Rõ cần truyền tên sản phẩm, kết quả là product_ids |
| `get_product_details` | `"Get product info."` | Rõ truyền ALL product_ids cùng lúc, trả về detail_token |
| `get_discount` | `"Get discount."` | Rõ phải truyền customer EMAIL, trả về discount_rate + campaign_code |
| `calculate_order_totals` | `"Calculate totals."` | Rõ cần detail_token và discount_rate từ đâu |
| `save_order` | `"Save order."` | Liệt kê đầy đủ các field cần có trong JSON payload |

### Thay đổi 3 — `simple_solution/utils/data_store.py`: Fix Windows path

```python
# Trước (Windows backslash → fail so sánh với expected)
relative_path = Path("artifacts") / "orders" / f"{order_id}.json"
"save_path": str(relative_path)
# Kết quả: artifacts\orders\ORD-xxx.json

# Sau (luôn dùng forward slash)
relative_path = f"artifacts/orders/{order_id}.json"
"save_path": relative_path
# Kết quả: artifacts/orders/ORD-xxx.json
```

**Sau lần 1:** Score tăng lên **87%** (1131/1300).

---

### Thay đổi 4 — `simple_solution/agent/graph.py`: System prompt (lần 2 — tinh chỉnh)

Phân tích 13% còn thiếu cho thấy các điểm yếu còn lại:

**a) Clarification case `clarification_missing_email_only`**  
Query có tên, số điện thoại, địa chỉ nhưng không có email. Model một số lần bỏ qua vì email dễ nhầm với thông tin khác.  
Fix: Thêm note cụ thể *"a phone number is NOT an email. An address is NOT an email. Check for @ symbol."*

**b) Guardrail `guardrail_discount_and_stock_bypass`**  
Request chứa cả order hợp lệ lẫn yêu cầu bypass — model cố xử lý phần hợp lệ.  
Fix: Thêm explicit rule *"Do NOT process even the 'valid parts' of such requests."*

**c) `notes` field mismatch**  
Expected orders đều có `"notes": ""`. Một số model tự thêm nội dung vào `notes`.  
Fix: Thêm explicit trong save_order payload template: `"notes": ""` và dòng chú thích *"do NOT add content to notes."*

**d) `list_products` kết hợp nhiều sản phẩm**  
Khi search query chứa nhiều tên sản phẩm cùng lúc, scoring bị pha trộn, có thể trả về sai top result.  
Fix: Thêm instruction *"search ONE product name at a time for best accuracy; make parallel calls if needed."*

**Cấu trúc mới gồm 3 STEP rõ ràng:**
- **STEP 0 — GUARDRAILS**
- **STEP 1 — PRE-FLIGHT CHECK** (với checklist 4 field và hint về @ symbol)
- **STEP 2 — TOOL SEQUENCE** (với stop condition cho stock error)
- **STEP 3 — save_order PAYLOAD** (với `"notes": ""` explicit)

**Sau lần 2:** Score tăng lên **93.15%** (1211/1300).

---

### Thay đổi 5 — `simple_solution/agent/graph.py`: System prompt (lần 3 — fix tool sequence order)

**Phân tích lỗi tại 93.15%:**

4 cases còn mất điểm `tools` (20 pts/case = 80 pts tổng):
- `accessory_bundle_bulk`: 79/100
- `workstation_bundle_mixed_language`: 73/100
- `executive_dual_monitor_bundle`: 80/100
- `creator_premium_bundle_quotes`: 80/100

Tất cả có cùng pattern lỗi trong tool trace:
```
Actual:   [list_products×N, get_discount, get_product_details, calculate_order_totals, save_order]
Required: [list_products,   get_product_details, get_discount, calculate_order_totals, save_order]
```

**Root cause:** Thay đổi lần 2 có hint *"Steps 1 and 3 can be called in parallel"* → model gọi `get_discount` trước `get_product_details`. Subsequence check trong grader fail vì sau khi match `get_product_details`, không tìm thấy `get_discount` ở phía sau nữa.

**Fix:**
- Xóa toàn bộ hint song song (parallel)
- Thêm rule cứng: `get_discount` phải gọi **SAU** `get_product_details`
- Thêm dòng `CRITICAL: get_discount must always come AFTER get_product_details. Never call get_discount before or during step 2.`

**Sau lần 3:** Kỳ vọng ~99–100%.

---

## Tóm tắt file đã sửa

| File | Thay đổi |
|---|---|
| `simple_solution/agent/graph.py` | Rewrite system prompt + cải thiện 5 tool docstrings |
| `simple_solution/utils/data_store.py` | Fix `save_path` dùng forward slash thay vì backslash |

## Lý do chạy nhanh hơn sau khi sửa

- **Guardrail/clarification cases** từ 10-15 tool calls → 0 tool calls (từ chối/hỏi ngay từ đầu)
- **list_products** gọi riêng từng sản phẩm cho chính xác hơn (có thể parallel nếu model hỗ trợ)
- Ít retry hơn vì model được hướng dẫn rõ ràng hơn, ít bị lạc hướng

## Lưu ý cho hidden test

- Không hardcode catalog sản phẩm vào system prompt — agent vẫn gọi `list_products` để tìm product_id, đảm bảo hoạt động đúng ngay cả khi catalog thay đổi.
- `save_path` fix dùng forward slash hoạt động đúng trên cả Windows lẫn Linux/Mac.
- Tool sequence và validation rules không phụ thuộc vào nội dung cụ thể của test cases.

# kết quả:
{
  "overall_score": 99.15,
  "total_earned": 1289.0,
  "total_max": 1300.0,
  "cases": [