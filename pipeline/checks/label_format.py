"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    p = cfg["label_format"]
    tol, dup_iou = p["overflow_tol"], p["dup_box_iou"]
    min_px, max_frac = p["min_box_px"], p["max_box_frac"]
    n_cls = len(ds.classes)
    out = []

    for img in ds.image_files():
        stem = img.stem
        lines = ds.read_label_lines(stem)   # None = thiếu file nhãn (việc của missing_labels)
        if not lines:                       # None hoặc file rỗng
            continue
        size = ds.image_size(stem)          # None nếu ảnh hỏng: bỏ qua BOX_TINY
        kept = []                           # (lớp, box) hợp lệ ở các dòng trước, để tìm DUP_BOX

        def add(sev, code, no, msg, **extra):
            out.append(Issue("label_format", sev, code, stem, msg, no, extra))

        for no, ln in lines:
            try:
                c, x, y, w, h = parse_yolo_line(ln)
            except ValueError as e:
                add(ERROR, "BAD_FORMAT", no, f"dòng không hợp lệ: {e}")
                continue
            if not 0 <= c < n_cls:
                add(ERROR, "BAD_CLASS_ID", no, f"id lớp {c} ngoài 0..{n_cls - 1}")
                continue
            if w <= 0 or h <= 0:
                add(ERROR, "BOX_ZERO", no, "box rộng hoặc cao bằng 0")
                continue

            over = max(w / 2 - x, x + w / 2 - 1, h / 2 - y, y + h / 2 - 1)
            if over > tol:
                add(ERROR, "BOX_OUT_OF_IMAGE", no, f"box tràn ảnh {over:.3f}", overflow=over)

            box = (x, y, w, h)
            if any(c2 == c and iou_xywh(box, b2) > dup_iou for c2, b2 in kept):
                add(ERROR, "DUP_BOX", no, "trùng với một box cùng lớp ở dòng trước")
            kept.append((c, box))

            if size and min(w * size[0], h * size[1]) < min_px:
                add(WARN, "BOX_TINY", no, f"cạnh ngắn {min(w * size[0], h * size[1]):.1f}px < {min_px}")
            if w * h > max_frac:
                add(WARN, "BOX_HUGE", no, f"box phủ {w * h:.2f} diện tích ảnh")
    return out
