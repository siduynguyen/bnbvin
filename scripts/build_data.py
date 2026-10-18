#!/usr/bin/env python3
"""Cập nhật dữ liệu bnbvin.com (DATA trong index.html + data.json) từ app quản lý.

Dùng:  python3 scripts/build_data.py units.json bookings.json settings_main.json
Mỗi tệp là kết quả đọc từ app (dạng {docId: {...}} , [{id, data}] hoặc {documents: [...]}).
- Lịch bận: mọi booking không huỷ, ngày trả phòng >= hôm qua.
- Giá, loại, phân khu, số khách… lấy từ app; ảnh giữ nguyên ảnh đang có trên trang.
- Căn mới trên app (chưa có ảnh trên trang) vẫn được thêm, không có ảnh.
"""
import json, re, sys, datetime, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def docs(path):
    raw = json.load(open(path))
    if isinstance(raw, dict) and "documents" in raw:
        raw = raw["documents"]
    out = {}
    if isinstance(raw, list):
        for x in raw:
            did = x.get("id") or x.get("doc_id") or x.get("path", "").split("/")[-1]
            out[did] = x.get("data", x)
    elif isinstance(raw, dict):
        for k, v in raw.items():
            out[k] = v.get("data", v) if isinstance(v, dict) else v
    return out


def main(units_p, bookings_p, main_p):
    units, bookings = docs(units_p), docs(bookings_p)
    sm = json.load(open(main_p))
    sm = sm.get("data", sm)

    html = (ROOT / "index.html").read_text()
    m = re.search(r"const DATA = (\{.*?\});\n", html)
    data = json.loads(m.group(1))
    old = {u["id"]: u for u in data["units"]}

    vn_now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(hours=7)
    floor = (vn_now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    new_units = []
    for uid, u in units.items():
        if u.get("hidden") or u.get("archived"):
            continue
        o = old.get(uid, {})
        new_units.append({
            "id": uid, "c": u.get("name") or o.get("c", uid), "z": u.get("zone") or o.get("z", ""),
            "t": u.get("type") or o.get("t", ""), "p": u.get("price") or 0, "m": u.get("monthlyPrice") or 0,
            "g": u.get("maxGuests") or 0, "we": u.get("weekendPrice") or u.get("price") or 0,
            "a": u.get("area") or 0, "v": u.get("view") or "", "am": u.get("amenities") or [],
            "d": u.get("desc") or "", "ph": o.get("ph", []),
        })
    order = {u["id"]: i for i, u in enumerate(data["units"])}
    new_units.sort(key=lambda u: (order.get(u["id"], 10**6), u["c"]))

    busy = {}
    for b in bookings.values():
        if b.get("status") in ("cancelled", "canceled", "huy") or not b.get("unitId"):
            continue
        ci, co = b.get("checkIn"), b.get("checkOut")
        if not ci or not co or co < floor:
            continue
        busy.setdefault(b["unitId"], []).append([ci, co])
    for k in busy:
        busy[k].sort()

    data["units"] = new_units
    data["busy"] = busy
    if sm.get("contacts"):
        data["contacts"] = sm["contacts"]
    if sm.get("extras"):
        data["extras"] = sm["extras"]
    data["updated"] = vn_now.strftime("%Y-%m-%dT%H:%M")

    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html = html[: m.start(1)] + blob + html[m.end(1):]
    (ROOT / "index.html").write_text(html)

    lite = {k: data[k] for k in ("updated", "extras", "contacts", "busy")}
    lite["units"] = [{**{k: v for k, v in u.items() if k != "ph"}, "ph0": (u["ph"][0] if u["ph"] else "")} for u in new_units]
    (ROOT / "data.json").write_text(json.dumps(lite, ensure_ascii=False, separators=(",", ":")))
    print(f"units={len(new_units)} busy_units={len(busy)} updated={data['updated']}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
