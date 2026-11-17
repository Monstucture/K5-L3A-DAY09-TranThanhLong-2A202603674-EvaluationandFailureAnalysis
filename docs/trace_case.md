# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-008 --seed 11
python -m lab9.trace_case --shape fixed --claim C-008 --seed 11   # đối chứng
```

## Case của nhóm: C-008 — reply nói sai số tiền (FM-08)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-008@11` (lỗi lặp lại ở cả 5 seed 11/22/33/44/55). Run ID: điền sau khi chạy `lab9.eval --shape seeded_regression` ở M4 (`reports/eval_seeded_regression.json`). |
| Triệu chứng | Grader Lab 8 báo **PASS (ok)**. Reply: "Dạ, LogiX đã hoàn **35.000đ** cho đơn O-808", nhưng ledger ghi `refund_vnd=20000` (khớp nhãn). Khách được báo nhiều hơn số tiền thực hoàn 15.000đ. |
| Bước sai đầu tiên | Event 5 `reply`: `{"text": "Dạ, LogiX đã hoàn 35.000đ cho đơn O-808."}` |
| Vì sao là bước *đầu tiên* | Event 1–4 đúng: handoff hợp lệ (1), `lookup_order` thấy O-808 `delivered_late` (2), `quote` 35000 từ SHIP-LATE-03 là số đề nghị (3, giống hệt shape `fixed`), `refund_history` 0 lần/0đ (4). Ledger cuối ghi 20000 (đúng nhãn) nên tiền không sai; chỉ lời nói ở event 5 lấy số quote 35000 thay vì số đã ghi vào ledger. |
| Failure mode | FM-08 misreport (`docs/failure_taxonomy.md`) |
| Đối chứng | `fixed C-008@11`: event 4 `reply` = "đã hoàn **20.000đ**", khớp ledger 20000. Khác biệt duy nhất: reply lấy số từ ledger, không từ quote. |
| Regression test | `tests/test_lab9_trace_case.py`: `test_fixed_reply_matches_ledger` (pass trên `fixed`) và `test_seeded_regression_misreports_amount` (reply ≠ ledger trên variant lỗi). So reply với **ledger**, không dựa vào grader Lab 8. Metric FM-08 ở M3 (`metric_spec.yaml`) sẽ làm cùng việc ở cấp gate. |
| Chưa chắc chắn | Trace không cho biết **vì sao** shape lỗi lấy số quote (35000) cho reply: có thể do bug trong variant hay do thứ tự bước; trace chỉ chứng minh reply != ledger. MockLLM nên mọi seed cho cùng kết quả, chưa chứng minh được tỉ lệ lỗi với LLM thật. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai (ở đây thì ngược lại: ledger đúng, reply sai).
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
