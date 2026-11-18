# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Trace case đã phân tích (C-002@11 · FM-03)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11` (trial `R-seeded_regression-C-002-s11` trong report `E-seeded_regression-20261118-d627`, eval set `d6271d1687a5`) |
| Triệu chứng | `lab8` grader FAIL (`status resolved != denied`): ledger `refund_vnd=20000` (`refund_count=1`) trong khi nhãn `label` yêu cầu `refund_vnd=0` (`refund_count=0`, `denied`). Event 6 `reply` nói `"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."` dù đơn thực tế chỉ trễ 2 ngày (< ngưỡng 3 ngày của `SHIP-LATE-03`). |
| Bước sai đầu tiên | Event `#3`: `model_override` — `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event `#1` (`handoff`: gửi task `check_applicable_policy` với `facts={}`, allowlist tool chuẩn, không chứa secret) và Event `#2` (`investigator`: `lookup_order` trả đúng bản ghi DB của `O-202` với `status="delivered", delay_days=2, shipping_fee_vnd=20000`) đều chính xác 100%. Sai lệch chỉ bắt đầu ngay tại Event `#3` khi agent tin số `5 ngày` trong ticket để ghi đè `delay_days` từ `2` lên `5`, kéo theo Event `#4` (`quote`) tính nhầm `amount_vnd=20000` và Event `#6` chi sai `20.000đ`. |
| Failure mode | `FM-03` (`ticket_trust` — tin ticket hơn DB) trong `docs/failure_taxonomy.md` |
| Đối chứng | Cùng `C-002@11` trên shape `fixed`: sau Event `#2` (`investigator`, `delay_days=2`), `fixed` **không có** `model_override`, đi thẳng tới Event `#3` `quote` với `{"amount_vnd": 0, "reason": "no_entitlement", "clause_ids": [], "parts": {}}` và Event `#4` `reply` từ chối hợp lệ (`ledger=0, status=denied`, PASS). |
| Regression test | `src/tests/test_lab9_regressions.py::test_trace_case_c002_ticket_trust_regression` (kiểm tra `DbFactKept`, `RefundAmountCorrect`, `TrialPass`). Đã xác nhận **FAIL** trên `seeded_regression` (và `swarm@55`) và **PASS** trên `fixed` (`pytest -q tests/test_lab9_regressions.py`). |
| Chưa chắc chắn | `MockLLM` mô phỏng bước parse/override một cách xác định theo seed; trên LLM thật, tỷ lệ agent bị prompt trong ticket dẫn dụ có thể phụ thuộc thêm vào cách diễn đạt ngoài mẫu `"trễ N ngày"` và nhiệt độ sinh văn bản. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
