# Báo cáo Day 09 — Trần Gia Huy, 2A202603049

## 1. Kết luận trước

- **Quyết định của pipeline:** **Hold (mã thoát `10`)**.
- **Số lượng ảnh:** Đầu vào có **224 ảnh** (`data/raw`), **19/224 ảnh (8.48%)** bị loại ở Bước 1 (`01_intake.txt`), còn **205/224 ảnh (91.52%)** đi vào `submission/export/clean_v1/` (đây là bản **nháp** xuất ra khi Hold, chưa được phát hành chính thức).
- **Lý do chính:** Sau khi máy tự sửa lỗi cú pháp (`03_fixes.csv`) và người duyệt mô phỏng xử lý hết ngân sách **80/205 ảnh** đầu hàng đợi (`06_review_log.csv`), lô dữ liệu không còn lỗi bắt buộc nào (`n_errors = 0`, toàn bộ 6/6 ảnh thiếu file nhãn đã được người gán đủ). Tuy nhiên, vì hàng đợi cần duyệt có tới **125/205 ảnh** trong khi ngân sách chỉ có **80 ảnh**, vẫn còn **38/205 ảnh (18.54%)** có cảnh báo (`WARN`) chưa được người duyệt — vượt ngưỡng chặn `gate.warn_ratio_hold = 10%` (0.10).

---

## 2. Lỗi và phân việc

Bảng tổng hợp toàn bộ **208 dòng lỗi/cảnh báo** từ `02_error_list_v1.txt` (gồm **19 lỗi cửa vào** trên 224 ảnh từ `01_intake.txt`, **36 lỗi bắt buộc** và **153 cảnh báo** trên 205 ảnh ở vòng quét v1; tổng cộng **55 lỗi bắt buộc** và **153 cảnh báo**):

| Mã lỗi | Mức độ | Số dòng / Số ảnh (kèm mẫu số) | Ai sửa (máy / người) | Vì sao |
|---|---|---:|---|---|
| `CORRUPT_IMAGE` | `ERROR` | 2 dòng (2/224 ảnh: `img_0010`, `img_0136`) | **Máy** (`remove_image` ở intake) | Ảnh hỏng hoặc bị cắt cụt (`UnidentifiedImageError`, `OSError` khi gọi `Image.open().load()`), máy phát hiện chắc chắn 100%. |
| `BAD_SIZE` | `ERROR` | 3 dòng (3/224 ảnh: `img_0107`, `img_0113`, `img_0122`) | **Máy** (`remove_image` ở intake) | Cạnh ngắn (180px, 226px) nhỏ hơn ngưỡng quy định cứng `min_side_px = 250px`. |
| `DUP_IMAGE_EXACT` | `ERROR` | 8 dòng (8/224 ảnh) | **Máy** (`remove_image` ở intake) | Trùng từng byte (MD5 giống hệt ảnh đứng trước trong lô), xoá bản sao là an toàn tuyệt đối. |
| `DUP_IMAGE_NEAR` | `ERROR` | 2 dòng (2/224 ảnh: `img_0076`, `img_0143`) | **Máy** (`remove_image` ở intake) | Trùng gần đúng với `img_0042` và `img_0037` (`phash = 0 <= 4`), loại tự động ở cửa vào. |
| `LEAK_TEST` | `ERROR` | 4 dòng (4/224 ảnh: `img_0049`, `img_0167`, `img_0174`, `img_0221`) | **Máy** (`remove_image` ở intake) | Trùng với ảnh trong `data/test/images` (`test_033`, `test_044`, `test_085`, `test_009`); bắt buộc loại để chống rò rỉ tập test. |
| `BAD_CLASS_NAME` | `ERROR` | 2 dòng (2/4 lớp trong `data.yaml`: `'Person'`, `'Bus'`) | **Máy** (`rename_classes` — 1 lần ghi `data.yaml`) | Sai chữ hoa/thường so với cấu hình chuẩn; máy ghi lại danh sách `['car', 'person', 'truck', 'bus']`. |
| `BAD_FORMAT` | `ERROR` | 3 dòng (3/205 ảnh: `img_0014`, `img_0022`, `img_0179`) | **Máy** (`drop_line`) + **Người** (`FIXED_DROP_LINE`) | Dòng thiếu cột (4/5 cột) hoặc chứa `nan/inf`; máy xoá dòng hỏng để không làm chết script train và đẩy ảnh vào hàng đợi để người kiểm lại. |
| `BAD_CLASS_ID` | `ERROR` | 6 dòng (6/205 ảnh: `img_0020`, `img_0099`, `img_0104`, `img_0117`, `img_0194`, `img_0199`) | **Máy** (`drop_line`) + **Người** (`FIXED_DROP_LINE`) | ID lớp ngoài `0..3` (`-1, 4, 7, 93`); máy không thể tự đoán lớp đúng nên xoá dòng lỗi cú pháp rồi đánh dấu cho người xem lại ảnh. |
| `BOX_ZERO` | `ERROR` | 4 dòng (4/205 ảnh: `img_0050`, `img_0066`, `img_0092`, `img_0185`) | **Máy** (`drop_line`) + **Người** (`FIXED_DROP_LINE`) | Box có chiều rộng hoặc chiều cao bằng `0`, không có diện tích hình học hợp lệ. |
| `DUP_BOX` | `ERROR` | 7 dòng (7/205 ảnh: `img_0001`, `img_0006`, `img_0024`, `img_0094`, `img_0109`, `img_0141`, `img_0193`) | **Máy** (`drop_line`) + **Người** (`FIXED_DROP_LINE`) | Box cùng lớp trùng khít ($\text{IoU} > 0.9$) với dòng trước đó trong cùng file nhãn. |
| `BOX_OUT_OF_IMAGE` | `ERROR` | 8 dòng (8/205 ảnh: `img_0030`, `img_0043`, `img_0078`, `img_0087`, `img_0108`, `img_0144`, `img_0152`, `img_0204`) | **Máy** (`clip_box`) + **Người** (`FIXED_CLIP_BOX`) | Mép box tràn khỏi `[0, 1]` từ `0.023` đến `0.060` (vượt `overflow_tol = 0.002`); máy cắt (`clip`) toạ độ về biên `[0, 1]`. |
| `MISSING_LABEL_FILE` | `ERROR` | 6 dòng (6/205 ảnh: `img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`) | **Người** (`needs_label` $\rightarrow$ `NEEDS_LABEL`) | Ảnh chưa có file `.txt`; máy **không được bịa nhãn** và không được tạo file rỗng (vì file rỗng nghĩa là ảnh nền không có vật), phải chuyển người gán. |
| `CLASS_RARE` | `WARN` | 4 dòng (4 lớp lạ `-1, 4, 7, 93` cấp `<dataset>` có `< 5` box) | **Máy** (tự hết ở v2) | Hệ quả trực tiếp của 6 dòng `BAD_CLASS_ID`; sau khi `autofix` xoá các dòng ID sai này, cảnh báo tự biến mất ở `04_error_list_v2`. |
| `BOX_HUGE` | `WARN` | 3 dòng (3/205 ảnh: `img_0018`, `img_0128`, `img_0196`) | **Người** (hàng đợi duyệt) | Box phủ `0.97–0.99` diện tích ảnh (`> 0.95`); cần người nhìn ảnh để phân biệt vật chụp cận cảnh thật hay box vẽ lỗi phủ kín ảnh. |
| `BOX_TINY` | `WARN` | 6 dòng ở v1 (4/205 ảnh: `img_0026`, `img_0051`, `img_0069`, `img_0161`; lên 7 dòng/5 ảnh ở v2 do thêm `img_0030`) | **Người** (hàng đợi duyệt) | Cạnh ngắn `8.9px–11.9px < 12px`; cần người xác nhận vật nhỏ hợp lệ hay box nhiễu. |
| `EMPTY_LABEL` | `WARN` | 12 dòng ở v1 (12/205 ảnh; tăng lên 15/205 ảnh ở v2 sau khi xoá dòng lỗi duy nhất ở `img_0050`, `img_0104`, `img_0194`) | **Người** (hàng đợi duyệt) | File `.txt` rỗng; chỉ con người mới phân biệt được ảnh nền thật sự hay ảnh bị bỏ sót toàn bộ nhãn. |
| `POSSIBLE_WRONG_CLASS` | `WARN` | 18 dòng (18/205 ảnh) | **Người** (hàng đợi duyệt) | Model `yolo26l` ($\text{conf} \ge 0.6$) khớp vị trí ($\text{IoU} \ge 0.5$) nhưng khác lớp với nhãn; phân biệt ngữ nghĩa `car`/`truck`/`bus` cần mắt người. |
| `POSSIBLE_MISSING` | `WARN` | 53 dòng (52/205 ảnh) | **Người** (hàng đợi duyệt) | Model `yolo26l` thấy vật ($\text{conf} \ge 0.6$, diện tích $\ge 600\text{px}^2$) mà nhãn không có box ($\text{IoU} < 0.3$); chỉ cảnh báo vì model cũng có thể bắt nhầm. |
| `POSSIBLE_FALSE_POS` | `WARN` | 29 dòng ở v1 (27/205 ảnh; giảm còn 24 dòng trên 23/205 ảnh ở v2 sau khi xoá các dòng `BOX_ZERO`/lỗi) | **Người** (hàng đợi duyệt) | Box nhãn không khớp dự đoán nào của model ($\text{conf} \ge 0.1$); cần người kiểm tra là box vẽ thừa hay vật bị khuất mà model bỏ sót. |
| `POSSIBLE_LOOSE_BOX` | `WARN` | 28 dòng (24/205 ảnh) | **Người** (hàng đợi duyệt) | Có dự đoán cùng lớp nhưng độ chồng lấp chỉ đạt $0.3 \le \text{IoU} < 0.5$; cần người chỉnh lại biên box cho ôm sát vật. |

*(Tổng số thao tác trong `03_fixes.csv` là **35 dòng fix**: `20 drop_line` + `8 clip_box` + `1 rename_classes` + `6 needs_label`.)*

- **Vì sao `05_review_queue.csv` xếp ảnh đầu hàng như vậy?**
  Hàm `build_queue` (`pipeline/steps/review_queue.py`) tính điểm ưu tiên (`priority`) cho từng ảnh bằng tổng điểm của mọi cảnh báo `WARN` trên ảnh đó theo công thức $\text{weight}[\text{code}] \times (1 + \text{conf})$ cộng với điểm thao tác `autofix` (`NEEDS_LABEL = 10`, `FIXED_DROP_LINE = 2`, `FIXED_CLIP_BOX = 1`; trọng số cảnh báo: `POSSIBLE_WRONG_CLASS = 3`, `POSSIBLE_MISSING = 2`, `POSSIBLE_FALSE_POS = 2`, `POSSIBLE_LOOSE_BOX = 1.5`, `EMPTY_LABEL = 1`, `BOX_HUGE = 0.5`, `BOX_TINY = 0.3`).
  - Đứng số 1 trong **125/205 ảnh** của hàng đợi là **`img_0020` (`priority = 11.524`)** vì ảnh này bị chồng tới 3 nhóm vấn đề nặng: vừa bị máy xoá dòng 3 có `BAD_CLASS_ID = 93` (`FIXED_DROP_LINE`, $+2.0$), vừa có cảnh báo `POSSIBLE_WRONG_CLASS` (trọng số $3 \times (1 + \text{conf})$) và `POSSIBLE_MISSING` (trọng số $2 \times (1 + \text{conf})$) — chính vật thật ở dòng 3 bị xoá đã kích hoạt thêm cảnh báo thiếu nhãn.
  - Xếp ngay vị trí 2 đến 7 là **6/6 ảnh `NEEDS_LABEL` (`priority = 10.0`)** (`img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`). Trọng số `10` đảm bảo mọi ảnh thiếu file nhãn (lỗi bắt buộc `ERROR` mà máy không tự sửa được) luôn được người duyệt gán bù trước tiên; nếu lọt dù chỉ 1 ảnh, gate sẽ trả về **Rework**.
  - Tiếp theo là các ảnh chồng nhiều cảnh báo ngữ nghĩa hoặc vừa bị xoá/cắt dòng vừa có `POSSIBLE_MISSING` (`img_0160` 8.887, `img_0127` 8.752, `img_0004` 8.357...), trong khi các ảnh chỉ có cảnh báo hình học nhẹ (`BOX_TINY` 0.3, `BOX_HUGE` 0.5) xếp cuối hàng (vị trí 122–125).
- **Với ngân sách 80 ảnh (`06_review_log.csv`), người duyệt xem được bao nhiêu lỗi ngữ nghĩa?**
  Trong `04_error_list_v2.csv` (sau `autofix`, trước người duyệt), có **6 lỗi `MISSING_LABEL_FILE`**, **123 dòng cảnh báo ngữ nghĩa từ `second_opinion`** (`18 POSSIBLE_WRONG_CLASS`, `53 POSSIBLE_MISSING`, `24 POSSIBLE_FALSE_POS`, `28 POSSIBLE_LOOSE_BOX`) và **15 dòng `EMPTY_LABEL`** (tổng **138 dòng cảnh báo ngữ nghĩa**, hoặc **144 dòng** nếu tính cả 6 ảnh thiếu file nhãn). Với ngân sách **80/125 ảnh trong hàng đợi (64.0% hàng đợi, 39.0% tổng số ảnh)**, người duyệt đã xử lý được:
  - **6/6 (100%)** ảnh thiếu file nhãn (`MISSING_LABEL_FILE` / `NEEDS_LABEL`).
  - **18/18 (100%)** dòng `POSSIBLE_WRONG_CLASS`.
  - **51/53 (96.2%)** dòng `POSSIBLE_MISSING` (chỉ còn sót 2 dòng ở `img_0210` và `img_0032` nằm ở vị trí 81–82 trong hàng đợi).
  - **13/24 (54.2%)** dòng `POSSIBLE_FALSE_POS`.
  - **12/28 (42.9%)** dòng `POSSIBLE_LOOSE_BOX`.
  - **11/15 (73.3%)** dòng `EMPTY_LABEL` (còn 4 ảnh `EMPTY_LABEL` chưa duyệt ở vị trí 114, 117, 119, 121 là `img_0013`, `img_0097`, `img_0129`, `img_0192`).
  - **Tổng cộng:** Người duyệt đã giải quyết được **94/123 (76.4%)** cảnh báo của `second_opinion` — hay **105/138 (76.1%)** dòng cảnh báo ngữ nghĩa (và **111/144 = 77.1%** nếu tính cả 6 ảnh `MISSING_LABEL_FILE`).

---

## 3. Calibration (2 ngưỡng)

Kết quả chạy `python -m pipeline.calibrate` trên bộ `data/calib/` (39 ảnh, đối chiếu `data/calib/MANIFEST.csv`, so sánh giữa cấu hình khởi đầu ở `work/calib_before.md` và cấu hình đã chọn ở `submission/calibration/calibration_report.md`):

| Tham số | Khởi đầu | Đã chọn | Precision / Recall / F1 (trước $\rightarrow$ sau) | Lý do (đánh đổi Precision – Recall) |
|---|---:|---:|---|---|
| `duplicates.phash_dist` | `2` | **`4`** | - `DUP_IMAGE_EXACT`: `1.00 / 1.00 / 1.00` $\rightarrow$ `1.00 / 1.00 / 1.00`<br>- `DUP_IMAGE_NEAR`: `1.00 / 0.50 / 0.67` (TP=3, FP=0, FN=3) $\rightarrow$ **`1.00 / 0.67 / 0.80`** (TP=4, FP=0, FN=2) | `DUP_IMAGE_NEAR` là lỗi `ERROR` bị tự động xoá hẳn khỏi dataset mà không qua mắt người, nên phải ưu tiên tuyệt đối **Precision = 1.00** (1 FP đồng nghĩa với xoá mất ảnh tốt). Trên bảng sweep, dải `4..14` cho cùng kết quả `1.00 / 0.67 / 0.80`; chọn **`4`** là mức thấp nhất (an toàn nhất) của vùng plateau này để vừa tăng Recall từ `0.50` lên `0.67` vừa giảm thiểu rủi ro báo trùng giả trên dữ liệu thật. |
| `second_opinion.conf` | `0.25` | **`0.6`** | - `POSSIBLE_WRONG_CLASS`: `0.56 / 0.83 / 0.67` $\rightarrow$ **`0.62 / 0.83 / 0.71`** (FP giảm 4 $\rightarrow$ 3)<br>- `POSSIBLE_MISSING`: `0.50 / 1.00 / 0.67` $\rightarrow$ **`0.57 / 1.00 / 0.73`** (FP giảm 8 $\rightarrow$ 6)<br>- `POSSIBLE_LOOSE_BOX`: `0.29 / 0.40 / 0.33` $\rightarrow$ **`0.20 / 0.20 / 0.20`**<br>- `POSSIBLE_FALSE_POS`: `0.31 / 1.00 / 0.48` $\rightarrow$ **`0.31 / 1.00 / 0.48`** | Cảnh báo ngữ nghĩa đổ vào hàng đợi có ngân sách hữu hạn 80 ảnh: ở `0.25`, báo động giả (FP) quá nhiều làm hàng đợi phình lên **145 ảnh** (273 cảnh báo vòng 1, sau duyệt còn **60/205 ảnh = 29.3%** chưa duyệt). Tăng lên `0.6` giúp tăng Precision của `MISSING` (`0.50` $\rightarrow$ `0.57`) và `WRONG_CLASS` (`0.56` $\rightarrow$ `0.62`) trong khi **giữ nguyên Recall = 1.00 cho `POSSIBLE_MISSING`** và **0.83 cho `POSSIBLE_WRONG_CLASS`** (từ `0.7` trở lên Recall của `MISSING` bị tụt xuống `0.88` rồi `0.75`), kéo cảnh báo vòng 1 xuống **153 dòng**, hàng đợi còn **125 ảnh** và tỉ lệ chưa duyệt giảm từ **29.3% xuống 18.5%**, chấp nhận hy sinh Recall của lỗi nhẹ hơn là `LOOSE_BOX` (`0.40` $\rightarrow$ `0.20`). |

- **Các điểm mà calibration trên bộ `calib` (39 ảnh) có thể đánh lừa bạn (kèm bằng chứng từ dữ liệu `raw`):**
  1. **Tăng `phash_dist` từ `2` lên `4` cải thiện Recall trên `calib` (`0.50` $\rightarrow$ `0.67`), nhưng trên `data/raw` lại không tạo ra khác biệt nào, trong khi chọn theo F1 cao nhất của `calib` (`phash_dist = 16`) lại gây xoá nhầm ảnh trên `raw`:**
     - Trên `data/raw`, cả hai mức `phash_dist = 2` và `phash_dist = 4` đều loại đúng **19 ảnh** như nhau ở Bước 1, vì cả 2 cặp `DUP_IMAGE_NEAR` bị bắt trên `raw` (`img_0076` trùng `img_0042`, `img_0143` trùng `img_0037`) đều có khoảng cách `phash = 0` (chỉ khác nén/byte, không có biến đổi trung gian `phash = 2..4` như lỗi chèn nhân tạo trong `calib`). Ngoài ra `calib` hoàn toàn không có ca `LEAK_TEST` nào, trong khi `raw` có **4 ảnh rò rỉ từ tập test** (`img_0049`, `img_0167`, `img_0174`, `img_0221`).
     - Ngược lại, nếu tin mù quáng vào mức `phash_dist = 16` có F1 cao nhất trên `calib` (`1.00 / 0.83 / 0.91`, 0 FP trên 39 ảnh = 741 cặp), khi chạy trên `data/raw` (224 ảnh = 24.976 cặp, lớn gấp $>33$ lần) sẽ bắt nhầm **3 cặp ảnh hoàn toàn khác nhau** có `phash = 16`: ví dụ `img_0011.jpg` (người đánh tennis trên sân xanh) bị báo trùng với `img_0008.jpg` (hai người trượt tuyết trên núi tuyết), `img_0084` trùng giả với `img_0074`, và `img_0177` trùng giả với `img_0113`.
  2. **`POSSIBLE_FALSE_POS` đứng yên ở `0.31 / 1.00 / 0.48` qua mọi giá trị sweep của `second_opinion.conf`:**
     - Vì nhánh kiểm tra `POSSIBLE_FALSE_POS` dùng ngưỡng cố định `fp_conf = 0.10` (đã ghim trong `configs/pipeline.yaml`) chứ không dùng `second_opinion.conf`, nên dù nâng `conf` lên `0.6` hay `0.8` thì **29 cảnh báo `POSSIBLE_FALSE_POS`** ở vòng 1 (24 cảnh báo ở vòng 2) vẫn giữ nguyên không giảm được báo động giả bằng tham số `conf`.

---

## 4. Cửa chặn và điều pipeline KHÔNG bắt được

### (a) Chứng minh cửa chặn (gate) chặn đúng khi còn lỗi bắt buộc
- Chạy thử pipeline với ngân sách người duyệt bằng `0` (`--budget 0`):
  ```bash
  python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb
  ```
- **Bằng chứng từ `work/rep_nb/08_summary.json` và `work/rep_nb/07_error_list_v3.txt`:**
  - Khi `budget = 0` (`reviewed = 0`), `autofix` chỉ tự sửa được các lỗi cú pháp (`rename_classes`, `drop_line`, `clip_box`), còn **6 ảnh thiếu file nhãn (`MISSING_LABEL_FILE`: `img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`)** chỉ được ghi log `needs_label` chứ không có người gán bù.
  - Ở danh sách lỗi cuối (`work/rep_nb/07_error_list_v3.txt`), vẫn còn nguyên **`error MISSING_LABEL_FILE: 6`** (`n_errors = 6`, cùng `112/205` ảnh có cảnh báo, `warn_ratio = 0.5463`).
  - Cửa chặn (`gate.decide`) lập tức kết luận **`"decision": "Rework"`** với lý do: `"còn 6 lỗi bắt buộc chưa xử lý: không được xuất bản dataset"` (ưu tiên chặn Rework theo lỗi bắt buộc trước cả khi xét tỉ lệ cảnh báo `54.63%`).
  - Lệnh thoát với **mã thoát `20`**, trong `work/rep_nb/08_summary.json` trường `"exported"` nhận giá trị **`null`**, và thư mục **`work/exp_nb` hoàn toàn không được tạo ra**. Ngược lại, khi chạy với ngân sách mặc định `80` ảnh, cả 6 ảnh này đều có trọng số `NEEDS_LABEL = 10` nằm ở top 2–7 của hàng đợi nên luôn được người gán nhãn xong, đưa `n_errors` về `0` và chuyển trạng thái sang **Hold**.

### (b) Các điểm mù mà pipeline KHÔNG bắt được (kèm bằng chứng cụ thể)
1. **Đối tượng thật bị bỏ sót nhãn nhưng bị che khuất / đứng chồng lên người khác khiến model checker tự tin thấp (`img_0015`):**
   - Khi mở ảnh `work/viz/img_0015.png` (cảnh bóng chày có 4 người: cầu thủ bắt bóng, cầu thủ ném bóng, trọng tài áo xanh và cầu thủ cầm gậy đập bóng đứng sát nhau bên trái), file nhãn `data/raw/labels/img_0015.txt` chỉ có **3 box** (dòng 3 `1 0.172213 0.420857 0.179839 0.430822` vẽ lệch phủ nửa trên của cụm người bên trái, tức **thiếu hẳn 1 box `person`**).
   - Tuy nhiên, trong `02_error_list_v1.txt`, `img_0015` chỉ bị cờ `POSSIBLE_LOOSE_BOX` chứ **không hề có `POSSIBLE_MISSING`**. Kiểm tra trực tiếp `data/cache/checker_preds.json` tại khoá `img_0015.jpg` cho thấy `yolo26l` sinh 4 dự đoán: dự đoán trọng tài `[1, 0.8941, 0.2155, 0.6166, 0.2663, 0.7468]` khớp một phần với dòng 3 ($\text{IoU} = 0.369 \in [0.3, 0.5)$) nên chỉ báo `POSSIBLE_LOOSE_BOX`; còn dự đoán người cầm gậy `[1, 0.3986, 0.2010, 0.2845, 0.1791, 0.2856]` chỉ đạt **`conf = 0.3986 < 0.6`** (do bị trọng tài che khuất) nên bị `second_opinion` lọc bỏ (và kể cả ở `conf = 0.25`, dự đoán này vẫn trùng với chính box dòng 3 với $\text{IoU} \ge 0.3$ nên cũng không thể phát cảnh báo `POSSIBLE_MISSING`). Vì chỉ có 1 cảnh báo `POSSIBLE_LOOSE_BOX` (`priority = 2.841`, đứng thứ **88/125** trong `05_review_queue.csv`, nằm ngoài ngân sách 80 ảnh), lỗi thiếu người trên `img_0015` lọt thẳng vào `clean_v1`.
2. **Thao tác tự sửa của `autofix` (`drop_line` và `clip_box`) làm mất nhãn của vật thật hoặc tạo ra lỗi hình học mới (`img_0020` dòng 3, `img_0050` dòng 1, `img_0030` dòng 9):**
   - Trên **`img_0020.txt` dòng 3** (`93 0.719167 0.641359 0.053782 0.242385`), toạ độ box bao đúng một người thật trên vỉa hè nhưng bị gán sai ID lớp thành `93` (`BAD_CLASS_ID`). Vì `autofix` không được đoán ngữ nghĩa nên thực hiện `drop_line` xoá mất dòng này, biến lỗi sai ID lớp thành lỗi **bỏ sót nhãn của vật thật** (may mắn là `yolo26l` bắt lại được qua `POSSIBLE_MISSING` + `FIXED_DROP_LINE` đưa `img_0020` lên hạng 1 hàng đợi; nhưng nếu vật đó nhỏ $< 600\text{px}^2$ hoặc `conf < 0.6` thì sẽ mất vĩnh viễn). Tương tự, trên **`img_0050.txt` dòng 1**, box única trong file bị `drop_line` vì `w = 0.000000` (`BOX_ZERO`), biến file nhãn thành file rỗng (`EMPTY_LABEL` mới phát sinh ở v2).
   - Trên **`img_0030.txt` dòng 9** (`1 -0.003833 0.460058 0.038330 0.184442`), box gốc có chiều rộng $\approx 24.5\text{px}$ ($\ge 12\text{px}$, không bị `BOX_TINY` ở v1) nhưng tràn mép trái ảnh. Sau khi `autofix` thực hiện `clip_box` cắt về biên `[0, 1]` thành `1 0.007666 0.460058 0.015332 0.184442`, chiều rộng phần còn lại co xuống chỉ còn **$9.8\text{px} < 12\text{px}$**, tự sinh ra một cảnh báo `BOX_TINY` mới ở `04_error_list_v2.txt`.
3. **Ảnh trùng gần đúng bị biến đổi mạnh (`phash > 4`) lọt qua Bước 1 (`img_0223` vs `img_0077`, `img_0186` vs `img_0061`):**
   - Trên `data/calib`, ở `phash_dist = 4` (và suốt dải `4..14`), vẫn có **2/6 ảnh `DUP_IMAGE_NEAR`** ở mức biến đổi 3–4 (`calib_037` của `calib_015`, `calib_038` của `calib_024` — bị crop và thu nhỏ mạnh) không bắt được.
   - Thực tế trên `data/raw`, vì giữ `phash_dist = 4` để đảm bảo `Precision = 1.00`, pipeline đã bỏ lọt cặp **`img_0223.jpg` và `img_0077.jpg`** (cùng cảnh góc phố có tháp đồng hồ và xe minibus `"T.J. WALSH"`, chỉ khác độ sáng và crop nhẹ viền, `phash = 6`) và cặp **`img_0186.jpg` và `img_0061.jpg`** (cùng ảnh cô gái ngồi ghế dài công viên nhưng bị crop khung hình, `phash = 10`). Cả hai cặp ảnh trùng này đều lọt vào `submission/export/clean_v1/`.

---

## 5. Train: raw vs clean (tùy chọn, chấm riêng)

**Chưa chạy** (phần train trên Google Colab là phần tùy chọn, chấm riêng 15 điểm; bài nộp kiểm tra theo phần lõi `python scripts/check_submission.py --no-train`).

---

## 6. Quyết định và ghi chú AI

### (a) Quyết định cuối và điều kiện để chuyển thành Release
- **Quyết định cuối cùng:** **Hold** (chưa phát hành bộ dữ liệu `clean_v1` vào sản xuất).
- **Cần làm gì để chuyển từ Hold sang Release?**
  1. **Tăng ngân sách người duyệt để hạ tỉ lệ ảnh còn cảnh báo xuống $< 10\%$ (`warn_ratio_hold = 0.10`):** Với mẫu số **205 ảnh**, để tỉ lệ cảnh báo $< 10\%$ thì số ảnh chưa duyệt còn cảnh báo phải $\le 20$ ảnh ($20/205 = 9.76\% < 10\%$). Hiện tại đang còn **38/205 ảnh (18.54%)** chưa duyệt có cảnh báo (nằm trong 45 ảnh cuối hàng đợi `05_review_queue.csv` từ vị trí 81 đến 125). Do đó, cần bổ sung người duyệt để xử lý thêm **ít nhất 18 ảnh** có cảnh báo nữa (tức nâng ngân sách duyệt từ `80` lên tối thiểu **`98`–`125` ảnh**), tuyệt đối **không** dùng cách tăng giả tạo ngưỡng `second_opinion.conf` để làm rỗng hàng đợi.
  2. **Kiểm tra thủ công 4 ảnh có file nhãn rỗng (`EMPTY_LABEL`) còn sót trong `clean_v1`:** Trong `07_error_list_v3.txt` và `submission/export/clean_v1/manifest.json` (có `label_sha1 = da39a3ee5e6b`, kích thước `0 byte`), vẫn còn 4 ảnh chưa được người duyệt là **`img_0013`, `img_0097`, `img_0129`, `img_0192`** (xếp ở vị trí 114, 117, 119, 121 trong hàng đợi). Trước khi Release, người duyệt bắt buộc phải mở xem 4 ảnh này để xác nhận chúng thực sự là ảnh nền không có đối tượng (`car, person, truck, bus`) chứ không phải ảnh bị bỏ sót toàn bộ nhãn.

### (b) Ghi chú sử dụng AI khi viết code
- **Prompt chính:** Dán docstring và file unit test tương ứng của từng module (`pipeline/checks/label_format.py` kèm `tests/test_label_format.py`, và tương tự cho `gate.py`, `autofix.py`, `second_opinion.py`) vào AI (Claude), mô tả đủ 4 ý: đầu vào, đầu ra, quy tắc/ngưỡng đọc từ `cfg`, và xử lý ca biên không làm gãy script.
- **Cách kiểm code AI:** Đọc hiểu từng dòng đối chiếu với `pipeline/common.py`, chạy unit test của từng module và toàn bộ test suite (`python -m pytest -q` đạt **`79 passed`**), sau đó chạy thật trên `data/raw` và mở ảnh trực quan bằng `scripts/viz_labels.py` để kiểm chứng chéo các ca cụ thể (như `img_0020` dòng 3 bị `BAD_CLASS_ID=93`, `img_0050` dòng 1 bị `BOX_ZERO`, `img_0030` dòng 9 bị `clip_box` sinh `BOX_TINY`, và `img_0015` trong `checker_preds.json`):
  ```text
  C:\cvat\K5-L23-DAY09-2A202603049-AutoQCPipeline>python -m pytest tests/test_label_format.py -q
  ..............                                                                                                   [100%]
  14 passed in 0.55s
  ```
- **1 lần AI sai:** Khi viết `label_format.py` ban đầu, AI tự đoán phương thức `ds.stems()` không tồn tại trong lớp `Dataset` và viết thừa `.strip()` cùng kiểm tra `math.isfinite()` bên ngoài vì chưa đọc `pipeline/common.py`; đã sửa lại dùng `for img in ds.image_files(): stem = img.stem` và tận dụng `parse_yolo_line()` có sẵn trong `common.py`.
