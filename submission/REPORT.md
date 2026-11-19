# Báo cáo Day 09 — Trần Gia Huy, 2A202603049

## 1. Kết luận trước
Pipeline kết luận **Hold** với mã thoát 10. Trong 224 ảnh đầu vào, bước intake loại 19/224 ảnh và giữ lại 205/224 ảnh đưa vào bản nháp clean_v1 nên chưa phát hành dataset. Sau khi duyệt tay xong thì toàn bộ lỗi bắt buộc đều hết với n_errors = 0, nhưng vẫn còn 38/205 ảnh, tương đương 18,5%, có cảnh báo chưa được duyệt và vượt ngưỡng 10%. Nguyên nhân chính là hàng đợi cần duyệt có 125 ảnh, lớn hơn ngân sách duyệt 80 ảnh.

## 2. Lỗi và phân việc
Lấy từ `02_error_list_v1` (gom theo mã lỗi). Cột "ai sửa": **máy** (autofix) hay **người** (hàng đợi); chỉ ghi những mã có mặt trong lô của bạn.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| CORRUPT_IMAGE | 2/224 ảnh, 2 dòng | máy - intake loại | Ảnh hỏng hoặc cắt cụt không đọc được pixel ở img_0010, img_0136; máy kiểm bằng Image.open().load() cho kết quả chắc chắn. |
| BAD_SIZE | 3/224 ảnh, 3 dòng | máy - intake loại | Cạnh ngắn 180px, 226px nhỏ hơn ngưỡng quy định min_side_px = 250px. |
| DUP_IMAGE_EXACT | 8/224 ảnh, 8 dòng | máy - intake loại | Trùng từng byte với mã MD5 giống hệt ảnh trước đó trong lô, xóa bản sao không làm mất dữ liệu. |
| DUP_IMAGE_NEAR | 2/224 ảnh, 2 dòng | máy - intake loại | Trùng gần đúng với ảnh trước gồm img_0076 trùng img_0042 và img_0143 trùng img_0037 với phash = 0 <= 4. |
| LEAK_TEST | 4/224 ảnh, 4 dòng | máy - intake loại | Trùng với ảnh trong tập test gồm test_009, test_033, test_044, test_085, bắt buộc loại để tránh rò rỉ dữ liệu đánh giá. |
| BAD_CLASS_NAME | 2/4 lớp ở data.yaml, 2 dòng | máy - rename_classes | Tên lớp viết hoa sai quy chuẩn là 'Person', 'Bus', máy tự chuẩn hóa về ['car', 'person', 'truck', 'bus']. |
| BAD_FORMAT | 3 dòng, 3/205 ảnh | máy - drop_line + người xem lại | Dòng thiếu cột khi chỉ có 4 cột hoặc chứa nan/inf; máy xóa dòng lỗi cú pháp rồi đẩy ảnh vào hàng đợi. |
| BAD_CLASS_ID | 6 dòng, 6/205 ảnh | máy - drop_line + người xem lại | ID lớp nằm ngoài khoảng 0..3 gồm -1, 4, 7, 93; máy không tự đoán lớp được nên xóa dòng hỏng và chuyển người kiểm lại. |
| BOX_ZERO | 4 dòng, 4/205 ảnh | máy - drop_line + người xem lại | Box có chiều rộng hoặc chiều cao bằng 0, không hợp lệ về hình học. |
| DUP_BOX | 7 dòng, 7/205 ảnh | máy - drop_line + người xem lại | Box lặp cùng lớp có IoU > 0.9 với dòng phía trên trong cùng file nhãn. |
| BOX_OUT_OF_IMAGE | 8 dòng, 8/205 ảnh | máy - clip_box + người xem lại | Box tràn ra ngoài biên [0, 1] từ 0.023 đến 0.060, vượt mức 0.002 nên máy cắt gọn lại về trong khung ảnh. |
| MISSING_LABEL_FILE | 6/205 ảnh, 6 dòng | người - needs_label | Ảnh chưa có file nhãn .txt; máy không thể tự bịa nhãn và cũng không tạo file rỗng vì file rỗng là ảnh nền nên chuyển người gán. |
| CLASS_RARE | 4 dòng cấp dataset | máy - tự hết sau autofix | Báo các lớp lạ -1, 4, 7, 93 có dưới 5 box; sau khi autofix xóa 6 dòng BAD_CLASS_ID thì lỗi này tự hết ở v2. |
| BOX_HUGE | 3 dòng, 3/205 ảnh | người - hàng đợi | Box chiếm 0.97–0.99 diện tích ảnh, vượt mức 0.95 nên cần mắt người phân biệt vật thể lớn thật hay vẽ nhầm cả khung. |
| BOX_TINY | 6 dòng, 4/205 ảnh ở v1; lên 7 dòng, 5 ảnh ở v2 | người - hàng đợi | Cạnh ngắn 8.9–11.9px < 12px, cần duyệt tay xác nhận vật nhỏ ở xa hay nhiễu. |
| EMPTY_LABEL | 12/205 ảnh ở v1, lên 15/205 ảnh ở v2 | người - hàng đợi | File nhãn rỗng, cần kiểm tra xem đây là ảnh nền không có vật thể hay bị gán sót. |
| POSSIBLE_WRONG_CLASS | 18 dòng, 18/205 ảnh | người - hàng đợi | Model yolo26l bắt trùng vị trí với IoU >= 0.5 nhưng khác lớp, cần người phân định car, truck hay bus. |
| POSSIBLE_MISSING | 53 dòng, 52/205 ảnh | người - hàng đợi | Model phát hiện vật với conf >= 0.6 và diện tích >= 600px2 nhưng nhãn không có box tương ứng với IoU < 0.3. |
| POSSIBLE_FALSE_POS | 29 dòng, 27/205 ảnh ở v1; còn 24 dòng, 23 ảnh ở v2 | người - hàng đợi | Box nhãn không khớp dự đoán nào của model ở ngưỡng conf >= 0.1, cần kiểm tra xem vẽ thừa hay model bỏ sót vật khó. |
| POSSIBLE_LOOSE_BOX | 28 dòng, 24/205 ảnh | người - hàng đợi | Khớp vật thể và lớp nhưng 0.3 <= IoU < 0.5, cần người chỉnh lại box cho ôm sát vật. |

Hàng đợi 05_review_queue.csv gồm 125/205 ảnh, xếp thứ tự giảm dần theo điểm priority. Điểm của mỗi ảnh bằng tổng điểm cảnh báo tính theo công thức weight x (1 + conf) cộng thêm điểm từ các thao tác autofix: NEEDS_LABEL = 10, POSSIBLE_WRONG_CLASS = 3, POSSIBLE_MISSING = 2, POSSIBLE_FALSE_POS = 2, FIXED_DROP_LINE = 2, POSSIBLE_LOOSE_BOX = 1.5, EMPTY_LABEL = 1, FIXED_CLIP_BOX = 1, BOX_HUGE = 0.5 và BOX_TINY = 0.3.
- Đứng đầu hàng là img_0020 với priority = 11.524 do vừa bị xóa dòng 3 sai ID lớp theo thao tác FIXED_DROP_LINE cộng 2 điểm, vừa dính cả POSSIBLE_WRONG_CLASS lẫn POSSIBLE_MISSING với conf cao.
- Xếp ngay sau ở vị trí 2 đến 7 là trọn vẹn 6/6 ảnh thiếu file nhãn gồm img_0031, img_0053, img_0126, img_0135, img_0170, img_0219 mang cờ NEEDS_LABEL với priority = 10.0, đảm bảo các ảnh trắng nhãn luôn được gán bù trước khi hết ngân sách.
- Các ảnh chồng chéo nhiều lỗi ngữ nghĩa xếp kế tiếp, còn các lỗi hình học nhẹ như BOX_TINY 0.3 điểm hay BOX_HUGE 0.5 điểm bị đẩy xuống cuối hàng ở vị trí 122–125.

Với ngân sách 80/125 ảnh trong hàng đợi theo ghi nhận ở 06_review_log.csv, đối chiếu với danh sách lỗi sau autofix tại 04_error_list_v2.csv gồm 6 ảnh MISSING_LABEL_FILE, 123 dòng lỗi ngữ nghĩa từ second_opinion và 15 ảnh EMPTY_LABEL, người duyệt đã xử lý được: 6/6 ảnh thiếu file nhãn đạt 100%, 18/18 lỗi POSSIBLE_WRONG_CLASS đạt 100%, 51/53 lỗi POSSIBLE_MISSING đạt 96,2%, 13/24 lỗi POSSIBLE_FALSE_POS đạt 54,2%, 12/28 lỗi POSSIBLE_LOOSE_BOX đạt 42,9% và 11/15 ảnh EMPTY_LABEL đạt 73,3%. Tính chung, người duyệt đã quét được 94/123 cảnh báo của second_opinion, tương đương 76,4%, hoặc 105/138 lỗi, tương đương 76,1% nếu tính cả EMPTY_LABEL.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| duplicates.phash_dist | 2 | 4 | DUP_IMAGE_EXACT: 1.00 / 1.00 → 1.00 / 1.00; DUP_IMAGE_NEAR: 1.00 / 0.50 → 1.00 / 0.67, F1 tăng từ 0.67 lên 0.80 | Ảnh trùng bị máy xóa thẳng ở intake nên bắt buộc ưu tiên precision = 1.00 để không xóa nhầm ảnh sạch. Trong dải 4..14 đều giữ mức 1.00 / 0.67 nên chọn 4 là mốc thấp nhất và an toàn nhất. |
| second_opinion.conf | 0.25 | 0.6 | WRONG_CLASS: 0.56 / 0.83 → 0.62 / 0.83; MISSING: 0.50 / 1.00 → 0.57 / 1.00; LOOSE_BOX: 0.29 / 0.40 → 0.20 / 0.20; FALSE_POS: 0.31 / 1.00 → 0.31 / 1.00 | Tăng precision của MISSING từ 0.50 lên 0.57 và WRONG_CLASS từ 0.56 lên 0.62 để bớt cảnh báo nhiễu trong hàng đợi 80 ảnh mà vẫn giữ recall = 1.00 cho MISSING vì từ 0.7 trở lên recall tụt xuống 0.88 rồi 0.75, chấp nhận giảm recall của LOOSE_BOX. Nhờ đó trên raw, cảnh báo vòng 1 giảm từ 273 xuống 153, hàng đợi giảm từ 145 xuống 125 ảnh, ảnh chưa duyệt còn cảnh báo hạ từ 60/205 tức 29,3% xuống 38/205 tức 18,5%. |

Chỗ calibration dễ đánh lừa nhất là kết quả trên tập calib 39 ảnh không phản ánh đúng phân phối của tập raw 224 ảnh:
- Trên calib, tăng phash_dist từ 2 lên 4 làm recall của DUP_IMAGE_NEAR tăng từ 0.50 lên 0.67. Thế nhưng khi chạy thật trên 224 ảnh raw, cả phash_dist = 2 và 4 đều loại đúng 19 ảnh giống hệt nhau ở bước 1 gồm 8 ảnh trùng byte, 4 ảnh rò rỉ test, 3 ảnh nhỏ, 2 ảnh hỏng và 2 ảnh DUP_IMAGE_NEAR là img_0076 trùng img_0042, img_0143 trùng img_0037 đều có phash = 0; mức 19 ảnh bị loại này hoàn toàn hợp lý. Lý do là calib chèn các biến thể trung gian rơi vào khoảng phash 2..4 mà raw không có, đồng thời calib không có ca LEAK_TEST nào trong khi raw có 4 ảnh.
- Ngược lại, nếu nhìn bảng sweep trên calib thấy phash_dist = 16 đạt F1 cao nhất ở mức 1.00 / 0.83 / 0.91 và không dính FP trên 39 ảnh rồi áp vào raw 224 ảnh với số cặp so sánh lớn gấp hơn 33 lần thì sẽ xóa nhầm 3 cặp ảnh khác hẳn nhau có phash = 16: ảnh đánh tennis img_0011 bị báo trùng với ảnh trượt tuyết trên núi img_0008, img_0084 trùng giả với img_0074 và img_0177 trùng giả với img_0113.
- Ngoài ra, POSSIBLE_FALSE_POS luôn đứng yên ở 0.31 / 1.00 ở mọi mức conf vì nhánh này dùng ngưỡng cứng fp_conf = 0.1, khiến 29 cảnh báo FALSE_POS trên raw không giảm khi chỉnh conf.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
a/ Khi chạy lệnh python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb với ngân sách duyệt bằng 0 nên reviewed = 0, file work/rep_nb/08_summary.json và 07_error_list_v3.txt ghi nhận vẫn còn 6 lỗi bắt buộc với n_errors = 6 thuộc mã MISSING_LABEL_FILE ở các ảnh img_0031, img_0053, img_0126, img_0135, img_0170, img_0219 do autofix chỉ gắn cờ needs_label chứ không tự tạo file nhãn. Gate trả về kết luận **Rework** ngay lập tức trước cả khi xét tỷ lệ cảnh báo 54,6%, thoát với mã thoát 20, trường exported trong 08_summary.json là null và việc **không xuất** dataset thể hiện qua việc thư mục work/exp_nb hoàn toàn không được tạo ra. Khi nâng lên budget = 80, nhờ trọng số NEEDS_LABEL = 10 nằm ở top 2–7 hàng đợi nên cả 6 ảnh này được gán nhãn hết, đưa n_errors về 0 và chuyển trạng thái sang Hold.

b/ Các điểm mù có bằng chứng thực tế:
- Sót vật thể đứng chồng lấp khiến model checker tụt conf tại img_0015: mở ảnh work/viz/img_0015.png chụp cảnh bóng chày có 4 người, cụm bên trái có 2 người đứng sát nhau là trọng tài và người cầm gậy nhưng file nhãn chỉ có 3 box do dòng 3 vẽ lệch vào khoảng giữa 2 người nên thiếu 1 người. Pipeline chỉ báo POSSIBLE_LOOSE_BOX mà bỏ qua POSSIBLE_MISSING: tra data/cache/checker_preds.json thấy dự đoán trọng tài có conf = 0.8941 khớp một phần với dòng 3 tại IoU = 0.369 nên báo LOOSE_BOX, còn dự đoán người cầm gậy chỉ có conf = 0.3986 < 0.6 nên bị lọc mất. Ảnh này chỉ đạt priority = 2.841, xếp hạng 88/125 và nằm ngoài ngân sách 80 ảnh nên lỗi sót nhãn lọt thẳng vào clean_v1.
- Autofix làm mất nhãn vật thật hoặc sinh thêm cảnh báo mới ở img_0020, img_0050 và img_0030:
  - Ở img_0020.txt dòng 3 có nội dung 93 0.719 0.641 0.054 0.242, box bao đúng một người thật nhưng gán nhầm ID lớp 93 nên bị drop_line xóa thẳng, biến lỗi sai lớp thành lỗi thiếu nhãn; nếu vật nhỏ dưới 600px2 hoặc conf < 0.6 sẽ mất dấu hoàn toàn.
  - Ở img_0050.txt dòng 1, box bị xóa do chiều rộng bằng 0.000000, làm file nhãn trở thành rỗng và phát sinh EMPTY_LABEL mới ở v2.
  - Ở img_0030.txt dòng 9, box tràn mép trái sau khi qua clip_box bị cắt chiều rộng từ 0.0383 tương đương khoảng 24px xuống còn 0.0153 tương đương khoảng 9.8px < 12px, tự sinh thêm một cảnh báo BOX_TINY ở vòng 2 mà vòng 1 chưa hề có.
- Lọt ảnh trùng gần đúng bị biến đổi mạnh: ở phash_dist = 4 và cả dải 4..14, trên calib vẫn lọt 2/6 ảnh DUP_IMAGE_NEAR biến đổi mạnh là calib_037 và calib_038. Trên tập raw, pipeline cũng bỏ lọt cặp img_0223 và img_0077 cùng chụp tháp đồng hồ và xe buýt T.J. WALSH nhưng khác độ sáng và bị crop viền với phash = 6, cùng cặp img_0186 và img_0061 cùng chụp cô gái ngồi ghế công viên bị crop khung với phash = 10 vào clean_v1.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa train: ghi "chưa chạy" và lý do, rồi bỏ qua phần còn lại của mục này. Nếu đã train: dán bảng từ `submission/results/comparison.md` (model, epoch, seed, số ảnh train mỗi biến thể).

Chưa chạy vì chưa làm xong các phần khác.

## 6. Quyết định và ghi chú AI
a/ Quyết định cuối là Hold, chưa phát hành clean_v1 vì còn 38/205 ảnh tức 18,5% có cảnh báo chưa được người duyệt, vượt ngưỡng 10%. Để chuyển sang Release cần tăng thêm ngân sách duyệt từ vị trí 81 trở đi trong 05_review_queue.csv sao cho số ảnh chưa duyệt còn cảnh báo giảm xuống tối đa 20/205 ảnh, tương đương 9,76% < 10%. Nghĩa là phải duyệt xử lý thêm ít nhất 18 ảnh có cảnh báo nữa bằng cách tăng ngân sách từ 80 lên tối thiểu 98–125 ảnh, tuyệt đối không nâng ngưỡng conf để ép hàng đợi nhỏ lại; đồng thời kiểm tra thủ công 4 ảnh có file nhãn rỗng còn lại trong clean_v1 gồm img_0013, img_0097, img_0129, img_0192 có hash da39a3ee5e6b để xác nhận đúng là ảnh nền thật.

b/ Dùng Claude,ai để viết 4 module `label_format`, `gate`, `autofix`, `second_opinion`.
- Prompt chính: với mỗi module, tôi dán docstring của file stub và file test tương ứng
  (`tests/test_<tên>.py`) vào AI, nhờ viết hàm chính. Với `label_format`, tôi dán thêm
  `common.py` và `missing_labels.py` khi AI hỏi. Tôi không dán ảnh vào prompt viết code.
- Cách kiểm: (1) đọc từng dòng và nhờ AI giải thích vì sao viết như vậy; (2) chạy `pytest`
  từng module rồi toàn bộ (79 test xanh); (3) chạy `label_format` trên `data/raw` và đối chiếu với
  ảnh tôi tự nhìn bằng `viz_labels.py`: `img_0020` dòng 3 ra `BAD_CLASS_ID`, `img_0050` dòng 1 ra
  `BOX_ZERO`; (4) so `03_fixes.csv` và `02_error_list_v1` với số lỗi tôi quan sát.
- Một lần AI sai: bản `label_format` đầu tiên AI gọi `ds.stems()`, hàm này không tồn tại
  (đúng là `ds.image_files()`), và còn thêm `strip()` và `isfinite` thừa vì AI chưa thấy `common.py`
  (`read_label_lines` đã bỏ dòng trống, `parse_yolo_line` đã chặn `nan`). Tôi phát hiện khi đọc
  `common.py` và sửa lại trước khi chạy test.