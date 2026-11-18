"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line

DROP_LINE = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_IMAGE = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}
EPS = 1e-6


def _fix(image, line, action, before, after):
    return {"image": image, "line": line, "action": action, "before": before, "after": after}


def _clip(text):
    """Cắt box về trong [0,1]. Trả về dòng mới, hoặc None nếu box không còn diện tích."""
    c, x, y, w, h = parse_yolo_line(text)
    x1, x2 = max(0.0, x - w / 2), min(1.0, x + w / 2)
    y1, y2 = max(0.0, y - h / 2), min(1.0, y + h / 2)
    nw, nh = x2 - x1, y2 - y1
    if nw <= EPS or nh <= EPS:
        return None
    return f"{c} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {nw:.6f} {nh:.6f}"


def fix(ds, issues, cfg):
    errors = sorted((i for i in issues if i.severity == ERROR),
                    key=lambda i: (i.image, i.line or 0, i.code))
    fixes = []

    # 1) Xoá ảnh (+ nhãn): mỗi ảnh một fix, dù có nhiều lỗi
    removed = set()
    for stem in sorted({i.image for i in errors if i.code in REMOVE_IMAGE}):
        img = ds.image_path(stem)
        if img is None:                       # ảnh đã bị xoá từ trước: bỏ qua êm
            continue
        img.unlink()
        if ds.label_path(stem).exists():
            ds.label_path(stem).unlink()
        removed.add(stem)
        fixes.append(_fix(stem, None, "remove_image", img.name, "(đã xoá)"))

    # 2) Đổi tên lớp trong data.yaml
    if any(i.code == "BAD_CLASS_NAME" for i in errors):
        d = {}
        if ds.yaml_path.exists():
            d = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        before = list(ds.yaml_names().values())
        d["names"] = list(cfg["classes"])
        ds.yaml_path.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
        fixes.append(_fix("data.yaml", None, "rename_classes", str(before), str(list(cfg["classes"]))))

    # 3) Thiếu file nhãn: KHÔNG tạo file, chuyển người gán
    for stem in sorted({i.image for i in errors if i.code == "MISSING_LABEL_FILE"} - removed):
        if not ds.label_path(stem).exists():
            fixes.append(_fix(stem, None, "needs_label", "(không có file)", "chuyển người gán"))

    # 4) Lỗi theo dòng: gom theo file, ghi lại MỘT lần (số dòng trong issue là số dòng GỐC)
    per_image = defaultdict(lambda: defaultdict(set))      # stem -> số dòng -> tập mã lỗi
    for i in errors:
        if i.line is not None and i.image not in removed and (i.code in DROP_LINE or i.code == "BOX_OUT_OF_IMAGE"):
            per_image[i.image][i.line].add(i.code)

    for stem in sorted(per_image):
        path = ds.label_path(stem)
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8", errors="replace").splitlines()
        new = []
        for no, text in enumerate(raw, 1):                  # enumerate trên TOÀN BỘ dòng, kể cả dòng trống
            codes = per_image[stem].get(no)
            if not codes:
                new.append(text)
            elif codes & DROP_LINE:                         # xoá thắng cắt: chỉ 1 fix drop_line
                fixes.append(_fix(stem, no, "drop_line", text, "(đã xoá)"))
            else:                                           # chỉ còn BOX_OUT_OF_IMAGE
                clipped = _clip(text)
                if clipped is None:
                    fixes.append(_fix(stem, no, "drop_line", text, "(đã xoá)"))
                else:
                    new.append(clipped)
                    fixes.append(_fix(stem, no, "clip_box", text, clipped))
        path.write_text("".join(ln + "\n" for ln in new), encoding="utf-8")
    return fixes
