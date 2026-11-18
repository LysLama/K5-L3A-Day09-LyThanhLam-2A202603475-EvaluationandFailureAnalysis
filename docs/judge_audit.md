# Judge audit

Chạy:
- `python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5`
- `python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Tỉ lệ fail (quan sát → Rogan-Gladen) | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|---|
| `tone_ok` (`judge_tone_public.csv`) | 100 | 0.757 | 0.857 | 0.800 | 0.28 → 0.30 | **PASS** (`tp=24, fp=4, fn=6, tn=66`) | **dùng** (có giám sát) |
| `helpful` (`judge_helpful_public.csv`) | 100 | 0.375 | 1.000 | 0.300 | 0.09 → 0.30 | **FAIL** (`tp=9, fp=0, fn=21, tn=70`) | **loại** |

## Audit thủ công các bất đồng (10 case đại diện cho cả hai judge)
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & Hành động sửa rubric / hệ thống |
|---|---|---|---|---|---|
| 1 | `H-008` (`tone_ok`) | `PASS` | `FAIL` | Người | `"Em đã hoàn tiền cho anh rồi nha..."` — xưng `em`/`nha` quá suồng sã, judge hiểu nhầm là thân thiện. **Sửa rubric:** cấm đại từ suồng sã (`em`, `bạn`, `nha`, `nhé`) trong CSKH LogiX. |
| 2 | `H-017` (`tone_ok`) | `PASS` | `FAIL` | Người | `"Dạ, bạn ơi LogiX đã hoàn 25.000đ... rồi nha."` — dùng `bạn` và `nha` dù có chữ `Dạ`. **Sửa rubric:** bổ sung ví dụ negative rằng câu có `Dạ` vẫn `FAIL` nếu xưng `bạn`/`nha`. |
| 3 | `H-029` (`tone_ok`) | `PASS` | `FAIL` | Người | `"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."` — giọng ra lệnh đuổi khách. **Sửa rubric:** nêu rõ mẫu câu có `Dạ, vui lòng` nhưng chứa mệnh lệnh/ngăn khách hỏi tiếp phải chấm `FAIL`. |
| 4 | `H-042` (`tone_ok`) | `FAIL` | `PASS` | Người | `"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."` — đủ ý, lịch sự, judge phạt oan vì thiếu xin lỗi. **Sửa rubric:** chỉ yêu cầu lời xin lỗi khi từ chối hoặc báo lỗi, không phạt câu xác nhận hoàn tiền ngắn gọn. |
| 5 | `H-051` (`tone_ok`) | `FAIL` | `PASS` | Người | `"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."` — judge phạt vì từ tiếng Anh `refund`. **Sửa rubric:** đưa `refund` vào danh sách thuật ngữ CS LogiX cho phép. |
| 6 | `H-081` (`tone_ok`) | `FAIL` | `PASS` | Judge | `"Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ."` — ghi chú cho thấy nhãn người bị gán nhầm do đọc nhầm ticket. **Hành động:** sửa nhãn gốc và kiểm tra chéo 2 người với các mẫu biên. |
| 7 | `HL-015` (`helpful`) | `PASS` | `FAIL` | Người | `"Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ."` trong khi ledger ghi `40.000đ` (FM-08). **Hành động:** không dùng LLM judge cho độ đúng số tiền; chuyển sang code grader đối chiếu ledger (`ReplyLedgerMatch`). |
| 8 | `HL-016` (`helpful`) | `PASS` | `FAIL` | Người | Reply dài dòng xin lỗi rập khuôn (`"Dạ, LogiX thành thật xin lỗi..."`) nhưng báo sai số tiền (`55.000đ` vs ledger `35.000đ`). Minh họa rõ **verbosity/politeness bias** của judge. |
| 9 | `HL-047` (`helpful`) | `PASS` | `FAIL` | Người | `"Ok bạn, đơn O-515 xử lý rồi nhé."` — sai xưng hô (`Ok bạn`, `nhé`) và không rõ số tiền hoàn. **Hành động:** tách tiêu chí giọng điệu (`tone_ok`) sang rubric đã calibrate; bỏ `helpful` chung chung. |
| 10 | `HL-070` (`helpful`) | `PASS` | `FAIL` | Người | Lặp lại lời xin lỗi 2 lần và báo `50.000đ` trong khi ledger ghi `30.000đ`. **Hành động:** bắt buộc kiểm tra đối chiếu số tiền với DB/ledger bằng code trước khi dùng bất kỳ đánh giá ngữ nghĩa nào. |

## Kết luận
- **Tiêu chí bị loại (`helpful`) và lý do không được dùng làm gate:**
  - Ma trận nhầm lẫn của `judge_helpful_public.csv` là `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}`: tuy `Precision = 1.000`, nhưng bỏ sót tới **21/30 ca lỗi thực (`fn=21`)**, khiến **`Recall = 0.300 < 0.70`** và **`κ = 0.375 < 0.60`**, đồng thời làm tỉ lệ lỗi quan sát tụt ảo xuống `0.09` trong khi tỉ lệ lỗi thực sau hiệu chỉnh Rogan-Gladen là `0.30`.
  - Trong 21 ca `fn` bị lọt có **18 ca sai tiền (`FM-08`)** và **3 ca sai xưng hô**. Nguyên nhân gốc rễ là: (1) judge chỉ đọc văn bản reply mà không có quyền truy vấn `refund_ledger`, và (2) judge mắc **verbosity/politeness bias** (thấy reply xin lỗi dài, lịch sự nên chấm `PASS` dù hoàn sai tiền). Dùng `helpful` làm CI gate sẽ **bỏ lọt lỗi tài chính nghiêm trọng** và tạo cảm giác an toàn giả.
  - Theo quy tắc Lab 9, tính đúng đắn của tiền và phê duyệt phải chấm bằng **code grader** (`RefundAmountCorrect`, `ApprovalBypass`, `ReplyLedgerMatch`), chỉ dùng `tone_ok` cho phần sắc thái ngôn ngữ sau khi sửa rubric các case biên.
- **Rủi ro còn lại:** Judge mới chỉ được kiểm trên dữ liệu replay đã công khai (`n = 100` mỗi CSV); cần gán nhãn người trên tập held-out mới (nhất là các mẫu paraphrase ở v2) trước khi dùng judge cho dữ liệu sản xuất thật.
