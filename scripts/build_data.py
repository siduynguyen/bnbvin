#!/usr/bin/env python3
"""Cập nhật dữ liệu bnbvin.com (DATA trong index.html + data.json) từ app quản lý.

Dùng:  python3 scripts/build_data.py units.json bookings.json settings_main.json [stats.json]
       python3 scripts/build_data.py --market stats.json      (chỉ cập nhật tab Thị trường)
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


_ZC = [("solari", "Beverly Solari"), ("beverly", "Beverly"), ("glory", "Glory Heights"), ("origami", "Origami"), ("rainbow", "Rainbow"),
       ("opus", "Opus One"), ("masteri", "Masteri Centre Point"), ("mcp", "Masteri Centre Point"), ("lumi", "Lumière Boulevard"), ("lbv", "Lumière Boulevard")]
_ZP = [("bs", "Beverly Solari"), ("be", "Beverly"), ("gh", "Glory Heights"), ("ori", "Origami"), ("os", "Origami")]


def _zones(k):
    """Chuẩn hoá tên khu (gộp 'GH', 'Glory Heights / BS'… về tên phân khu)."""
    out = []
    for part in re.split(r"\s*(?:,|/|;|\+|&|\(|\)| hoặc | và )\s*", str(k)):
        t = part.strip().lower()
        if not t:
            continue
        name = next((v for key, v in _ZC if key in t), None)
        if not name:
            t2 = re.sub(r"^the\s+", "", t)
            name = next((v for key, v in _ZP if t2.startswith(key)), None)
        if not name and re.match(r"^(khu )?s\d*$", t):
            name = "Rainbow / Origami"
        if name and name not in out:
            out.append(name)
    return out


def _part(x):
    """Rút gọn số liệu 1 ngày thành dạng công khai: không tên, không số điện thoại, không số liệu nội bộ."""
    if not x:
        return None
    ut, ot = x.get("uniqT") or {}, x.get("oUniqT") or {}
    z = {}
    for k, v in (x.get("zonesT") or {}).items():
        a, b = int((v or {}).get("2PN", 0)), int((v or {}).get("3PN", 0))
        keys = ["?"] if k == "Không rõ khu" else (_zones(k) or ["?"])
        for key in keys:
            o = z.setdefault(key, [0, 0]); o[0] += a; o[1] += b
    n = x.get("uniq") if x.get("uniq") is not None else x.get("need", 0)
    o = x.get("oUniq") if x.get("oUniq") is not None else x.get("offer", 0)
    return {"n": int(n or 0), "n2": int(ut.get("2PN", 0)), "n3": int(ut.get("3PN", 0)),
            "o": int(o or 0), "o2": int(ot.get("2PN", 0)), "o3": int(ot.get("3PN", 0)), "z": z}


def build_market(stats_p):
    st = docs(stats_p)
    days = []
    for d in sorted(st)[-30:]:
        x = st[d]
        if not re.match(r"\d{4}-\d{2}-\d{2}$", d) or not (x.get("need") or x.get("offer")):
            continue
        bl = x.get("byLen") or {}
        a = _part(x)
        a["m"] = int((bl.get("M") or {}).get("uniq") or 0)
        days.append({"d": d, "partial": bool(x.get("partial")), "all": a, "S": _part(bl.get("S")), "M": _part(bl.get("M"))})
    vn_now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(hours=7)
    market = {"updated": vn_now.strftime("%Y-%m-%dT%H:%M"), "days": days}
    html = (ROOT / "index.html").read_text()
    blob = json.dumps(market, ensure_ascii=False, separators=(",", ":"))
    html, k = re.subn(r"const MARKET = .*?;\n", lambda _: "const MARKET = " + blob + ";\n", html, count=1)
    if not k:
        raise SystemExit("Không tìm thấy 'const MARKET' trong index.html")
    (ROOT / "index.html").write_text(html)
    print(f"market_days={len(days)}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--market"]:
        build_market(sys.argv[2])
    else:
        main(*sys.argv[1:4])
        if len(sys.argv) > 4:
            build_market(sys.argv[4])
