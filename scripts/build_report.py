#!/usr/bin/env python3
"""Dựng thi-truong.html: phần miễn phí (công khai) + phần trả phí (mã hóa AES-GCM, khóa từ mật khẩu).
Chạy: REPORT_PW='mat-khau' python3 scripts/build_report.py
Chỉ dùng số liệu tổng hợp - không tên, không số điện thoại."""
import os, re, json, base64, hashlib, pathlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
ROOT = pathlib.Path(__file__).resolve().parent.parent
pw = os.environ.get("REPORT_PW")
if not pw: raise SystemExit("Thiếu REPORT_PW")
idx = (ROOT/"index.html").read_text()
M = json.loads(re.search(r"const MARKET = (\{.*?\});\n", idx, re.S).group(1))
AB = json.loads((ROOT/"data/abnb_summary.json").read_text())
days = [d for d in M["days"] if not d["partial"]]
last = days[-1]; w7 = days[-7:]
def tr(d): return {"d": d["d"], "n": d["all"]["n"], "o": d["all"]["o"]}
free = {"updated": M["updated"], "day": last["d"], "n": last["all"]["n"], "o": last["all"]["o"],
        "trend": [tr(d) for d in w7],
        "ab": {"total": AB["total"], "n2": AB["groups"][2]["n"], "last": AB["groups"][2]["m"][-1], "snap": AB["snapshot"]}}
def zsum(ds):
    z = {}
    for d in ds:
        for k, (c, o) in d["all"]["z"].items():
            a = z.setdefault(k, [0, 0]); a[0] += c; a[1] += o
    return z
def pk(d):
    a = d["all"]
    return {"d": d["d"], "n": a["n"], "n2": a["n2"], "n3": a["n3"], "o": a["o"], "o2": a["o2"], "o3": a["o3"], "m": a.get("m", 0),
            "S": d["S"]["n"], "M": d["M"]["n"]}
paid = {"days": [pk(d) for d in days[-14:]], "z7": zsum(w7), "z14": zsum(days[-14:]), "ab": AB}
raw = json.dumps(paid, ensure_ascii=False, separators=(",", ":")).encode()
salt = os.urandom(16); iv = os.urandom(12)
key = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200000, 32)
ct = AESGCM(key).encrypt(iv, raw, None)
blob = {"s": base64.b64encode(salt).decode(), "i": base64.b64encode(iv).decode(), "c": base64.b64encode(ct).decode()}
t = (ROOT/"tpl/thi-truong.tpl.html").read_text()
t = t.replace("/*FREE*/null", json.dumps(free, ensure_ascii=False)).replace("/*PAID*/null", json.dumps(blob))
(ROOT/"thi-truong.html").write_text(t)
print("ok", len(t))
