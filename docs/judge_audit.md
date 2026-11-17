# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`  (FAIL = lớp dương, judge replay từ CSV)

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | **Đạt** cả 3 (tp 24, fp 4, fn 6, tn 66) | **Dùng** (cho tiêu chí giọng điệu, sau khi sửa rubric bên dưới) |
| helpful | 100 | 0.375 | 1.000 | 0.300 | **Không đạt**: κ 0.375 < 0.6, R 0.30 < 0.7 (tp 9, fp 0, fn 21, tn 70) | **Loại** khỏi gate |

## ≥5 case audit thủ công (tone_ok, 10 bất đồng; chọn 7)
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 "Em đã hoàn tiền cho anh rồi nha…" | PASS | FAIL | Người | Xưng "em"/"nha" quá suồng sã; judge nhầm "suồng sã" với "thân thiện". Rubric: liệt kê xưng hô bắt buộc (anh/chị, "Dạ") và cấm "nha/nhé" khi khiếu nại. |
| 2 | H-029 "…không cần nhắn thêm." | PASS | FAIL | Người | Giọng ra lệnh; judge chỉ thấy "Dạ, vui lòng". Rubric: đánh giá cả câu, câu mệnh lệnh với khách = FAIL dù có "Dạ". |
| 3 | H-042 "Dạ, đơn O-808 đã hoàn 120.000đ…" | FAIL | PASS | Người | Ngắn nhưng đủ ý; judge phạt vì "thiếu xin lỗi". Rubric: lời xin lỗi không bắt buộc khi kết quả là hoàn tiền thành công. |
| 4 | H-051 "…đã refund 90.000đ…" | FAIL | PASS | Người | "refund" được CS LogiX cho phép. Rubric: thêm danh sách từ vay mượn được phép. |
| 5 | H-063 "…và sẽ hoàn thêm" | PASS | FAIL | Người, nhưng sai tiêu chí | Đây là lời hứa ngoài kết quả hệ thống = lỗi độ chính xác/FM-08, không phải tone. Rubric tone loại bỏ nội dung số tiền; để grader code/ledger bắt. |
| 6 | H-081 "đơn O-107 chưa đủ điều kiện…" | FAIL | PASS | **Judge** | Nhãn người sai (đọc nhầm ticket). Hành động: sửa nhãn trong CSV nguồn (bản sao của nhóm), κ tăng nhẹ. |
| 7 | H-088 "Dạ, dạ, LogiX…" | FAIL | PASS | Mơ hồ (judge nghiêm hơn rubric hiện tại) | Lỗi gõ lặp "Dạ". Rubric chưa nói typo. Hành động: quy định rõ lỗi chính tả nhẹ không FAIL tone, hoặc ghi vào tiêu chí "chính tả" riêng. |

Tổng: judge sai ở 8/10 bất đồng nhìn lại (người đúng), judge đúng ở 1 (H-081), 1 mơ hồ (H-088). Khuynh hướng của judge: dễ dãi với xưng hô/giọng ra lệnh (fn 6) và quá nghiêm với tiêu chí không có trong rubric (fp 4: xin lỗi, tiếng Anh, typo).

## Kết luận
- **Dùng `tone_ok`**: κ 0.757, P 0.857, R 0.800 đều trên ngưỡng. Tỉ lệ FAIL quan sát 0.28, sau Rogan-Gladen ≈ 0.30 (judge hơi đếm thiếu). Vẫn cần sửa rubric theo bảng trên.
- **Loại `helpful`**: P = 1.0 nhưng R = 0.30 (bỏ sót 21/30 lỗi thật), κ = 0.375. 18 trong 21 bất đồng là **FM-08 (reply nói số tiền khác ledger, ví dụ HL-015 "55.000đ" so với ledger 40.000đ)** và 3 là sai xưng hô ("Ok bạn…"); judge không thấy ledger, và những reply dài có nhiều câu xin lỗi trông "hữu ích" nên nó cho PASS. Tỉ lệ FAIL quan sát 0.09, hiệu chỉnh 0.30: gate dựa trên judge này sẽ cho qua gần 70% lỗi. Tiền/số liệu phải chấm bằng code đọc ledger (metric FM-08 ở M3), không bằng judge.
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật. n = 100 nên khoảng tin cậy của κ còn rộng.
