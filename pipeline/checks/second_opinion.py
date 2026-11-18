"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def _labels(ds, stem):
    """[(số dòng gốc, lớp, (cx, cy, w, h))] của các dòng hợp lệ; dòng hỏng / lớp lạ bị bỏ qua."""
    out = []
    for no, ln in ds.read_label_lines(stem) or []:
        try:
            c, x, y, w, h = parse_yolo_line(ln)
        except ValueError:
            continue
        if 0 <= c < len(ds.classes):
            out.append((no, c, (x, y, w, h)))
    return out


def run(ds, cfg, preds=None):
    p = cfg["second_opinion"]
    conf_thr, min_area, fp_conf = p["conf"], p["min_area_px"], p["fp_conf"]
    iou_missing, iou_match, iou_loose = p["iou_missing"], p["iou_match"], p["iou_loose"]

    if preds is None:
        preds = get_preds(ds, cfg, "checker")
    out = []

    for img in ds.image_files():
        stem = img.stem
        if stem not in preds or ds.read_label_lines(stem) is None:   # không có dự đoán / không có file nhãn
            continue
        size = ds.image_size(stem)
        if size is None:                                             # ảnh hỏng: không tính được diện tích
            continue
        W, H = size
        labels = _labels(ds, stem)
        preds_img = [(int(r[0]), float(r[1]), tuple(r[2:6])) for r in preds[stem]]

        def add(code, msg, line=None, **extra):
            out.append(Issue("second_opinion", WARN, code, stem, msg, line, extra))

        # 1) Mỗi dự đoán đủ tin cậy và đủ lớn: tối đa MỘT cảnh báo
        for cls, conf, box in preds_img:
            if conf < conf_thr or box[2] * W * box[3] * H < min_area:
                continue
            cands = [(iou_xywh(box, lb), c) for _, c, lb in labels if iou_xywh(box, lb) >= iou_missing]
            if not cands:
                add("POSSIBLE_MISSING", "model thấy vật mà nhãn không có box", conf=conf)
                continue
            same = [i for i, c in cands if c == cls]
            if same:
                if max(same) < iou_loose:
                    add("POSSIBLE_LOOSE_BOX", "đúng vật nhưng box lỏng/lệch", conf=conf, iou=round(max(same), 3))
                continue                                             # nhãn đúng lớp đã phủ vật này
            other = max(i for i, _ in cands)
            if other >= iou_match:
                add("POSSIBLE_WRONG_CLASS", "cùng vị trí nhưng khác lớp", conf=conf, iou=round(other, 3))
            # còn lại: mơ hồ, không cờ

        # 2) Mỗi dòng nhãn không khớp dự đoán nào (conf >= fp_conf, không lọc diện tích)
        fp_boxes = [box for _, conf, box in preds_img if conf >= fp_conf]
        for no, c, lb in labels:
            best = max((iou_xywh(lb, b) for b in fp_boxes), default=0.0)
            if best < iou_missing:
                add("POSSIBLE_FALSE_POS", "box nhãn không khớp vật nào model thấy", line=no, iou=round(best, 3))
    return out