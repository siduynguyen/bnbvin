// BnbVin · máy chủ tài khoản (Cloudflare Worker + KV). Xem auth/README.md
// Biến: KV "USERS" (binding), Secret TOKEN_SECRET, REPORT_KEY, ADMIN_KEY; Text TRIAL_DAYS (mặc định 30), GOOGLE_CLIENT_ID (tuỳ chọn, bật đăng nhập Google)
const ORIGINS = ["https://bnbvin.com", "https://www.bnbvin.com"];
const DAY = 86400000;
const enc = new TextEncoder();
const b64 = (u8) => btoa(String.fromCharCode(...new Uint8Array(u8)));
const unb64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
const b64u = (u8) => b64(u8).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

function cors(req) {
  const o = req.headers.get("Origin") || "";
  const h = { "Vary": "Origin", "Access-Control-Allow-Headers": "Content-Type, Authorization", "Access-Control-Allow-Methods": "GET, POST, OPTIONS" };
  if (ORIGINS.includes(o) || /^http:\/\/localhost(:\d+)?$/.test(o)) h["Access-Control-Allow-Origin"] = o;
  return h;
}
const json = (req, obj, status = 200) =>
  new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...cors(req) } });

function normPhone(p) {
  let d = String(p || "").replace(/\D/g, "");
  if (d.startsWith("84") && d.length === 11) d = "0" + d.slice(2);
  return /^0\d{9}$/.test(d) ? d : "";
}
async function hashPw(pw, salt) {
  const k = await crypto.subtle.importKey("raw", enc.encode(pw), "PBKDF2", false, ["deriveBits"]);
  return b64(await crypto.subtle.deriveBits({ name: "PBKDF2", salt, iterations: 100000, hash: "SHA-256" }, k, 256));
}
async function hmac(env, msg) {
  const k = await crypto.subtle.importKey("raw", enc.encode(env.TOKEN_SECRET), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return b64u(await crypto.subtle.sign("HMAC", k, enc.encode(msg)));
}
// id tài khoản: "0912345678" (SĐT) hoặc "g:email" (Google)
const kvKey = (id) => (id.startsWith("g:") ? id : "u:" + id);
async function makeToken(env, id) {
  const exp = Date.now() + 60 * DAY, p = b64u(enc.encode(id));
  return `${p}.${exp}.${await hmac(env, p + "." + exp)}`;
}
async function authUser(req, env) {
  const t = (req.headers.get("Authorization") || "").replace(/^Bearer /, "");
  const [p, exp, sig] = t.split(".");
  if (!p || !exp || !sig || Number(exp) < Date.now()) return null;
  if ((await hmac(env, p + "." + exp)) !== sig) return null;
  let id; try { id = new TextDecoder().decode(unb64(p.replace(/-/g, "+").replace(/_/g, "/"))); } catch { return null; }
  const u = await env.USERS.get(kvKey(id), "json");
  return u ? { phone: id, u } : null;
}
// Xác minh ID token của Google (RS256) bằng khoá công khai của Google
async function verifyGoogle(env, cred) {
  const [h, p, sg] = String(cred || "").split(".");
  if (!h || !p || !sg) return null;
  const dj = (x) => JSON.parse(new TextDecoder().decode(unb64(x.replace(/-/g, "+").replace(/_/g, "/"))));
  const head = dj(h), pl = dj(p);
  const jwks = await (await fetch("https://www.googleapis.com/oauth2/v3/certs")).json();
  const jwk = jwks.keys.find((k) => k.kid === head.kid);
  if (!jwk || head.alg !== "RS256") return null;
  const key = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
  const ok = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, unb64(sg.replace(/-/g, "+").replace(/_/g, "/")), enc.encode(h + "." + p));
  if (!ok || pl.aud !== env.GOOGLE_CLIENT_ID || !/^(https:\/\/)?accounts\.google\.com$/.test(pl.iss) || pl.exp * 1000 < Date.now() || !pl.email_verified) return null;
  return { email: String(pl.email).toLowerCase(), name: pl.name || "" };
}
function status(u) {
  const now = Date.now();
  const until = Math.max(u.trialEnd || 0, u.paidUntil || 0);
  return { trialEnd: u.trialEnd, paidUntil: u.paidUntil || 0, until, active: until > now, daysLeft: Math.max(0, Math.ceil((until - now) / DAY)), paid: (u.paidUntil || 0) > now };
}
async function body(req) { try { return await req.json(); } catch { return {}; } }

export default {
  async fetch(req, env) {
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(req) });
    const url = new URL(req.url), path = url.pathname;
    try {
      if (path === "/health") return json(req, { ok: true, kv: !!env.USERS, secrets: !!(env.TOKEN_SECRET && env.REPORT_KEY && env.ADMIN_KEY) });

      if (path === "/register" && req.method === "POST") {
        const b = await body(req), phone = normPhone(b.phone), pw = String(b.password || "");
        if (!phone) return json(req, { error: "Số điện thoại chưa đúng (10 số, bắt đầu bằng 0)." }, 400);
        if (pw.length < 6) return json(req, { error: "Mật khẩu cần ít nhất 6 ký tự." }, 400);
        if (await env.USERS.get("u:" + phone)) return json(req, { error: "Số này đã đăng ký. Hãy đăng nhập." }, 409);
        const salt = crypto.getRandomValues(new Uint8Array(16));
        const u = { salt: b64(salt), hash: await hashPw(pw, salt), created: Date.now(), trialEnd: Date.now() + Number(env.TRIAL_DAYS || 30) * DAY, paidUntil: 0, name: String(b.name || "").slice(0, 60) };
        await env.USERS.put("u:" + phone, JSON.stringify(u));
        return json(req, { token: await makeToken(env, phone), phone, ...status(u) });
      }

      if (path === "/login" && req.method === "POST") {
        const b = await body(req), phone = normPhone(b.phone), pw = String(b.password || "");
        const fk = "f:" + phone, fails = Number(await env.USERS.get(fk) || 0);
        if (fails >= 8) return json(req, { error: "Nhập sai nhiều lần. Thử lại sau 15 phút." }, 429);
        const u = phone && (await env.USERS.get("u:" + phone, "json"));
        if (!u || (await hashPw(pw, unb64(u.salt))) !== u.hash) {
          if (phone) await env.USERS.put(fk, String(fails + 1), { expirationTtl: 900 });
          return json(req, { error: "Sai số điện thoại hoặc mật khẩu." }, 401);
        }
        await env.USERS.delete(fk);
        return json(req, { token: await makeToken(env, phone), phone, ...status(u) });
      }

      if (path === "/google" && req.method === "POST") {
        if (!env.GOOGLE_CLIENT_ID) return json(req, { error: "Chưa bật đăng nhập Google." }, 501);
        const g = await verifyGoogle(env, (await body(req)).credential);
        if (!g) return json(req, { error: "Không xác minh được tài khoản Google." }, 401);
        const id = "g:" + g.email;
        let u = await env.USERS.get(id, "json");
        if (!u) { u = { created: Date.now(), trialEnd: Date.now() + Number(env.TRIAL_DAYS || 30) * DAY, paidUntil: 0, name: g.name, email: g.email, contact: "" }; await env.USERS.put(id, JSON.stringify(u)); }
        return json(req, { token: await makeToken(env, id), phone: g.email, needContact: !u.contact, ...status(u) });
      }

      if (path === "/profile" && req.method === "POST") { // khách để lại số Zalo để bạn đối chiếu khi gia hạn
        const a = await authUser(req, env);
        if (!a) return json(req, { error: "Hết phiên đăng nhập." }, 401);
        const c = normPhone((await body(req)).contact);
        if (!c) return json(req, { error: "Số điện thoại chưa đúng." }, 400);
        a.u.contact = c; await env.USERS.put(kvKey(a.phone), JSON.stringify(a.u));
        return json(req, { ok: true });
      }

      if (path === "/me") {
        const a = await authUser(req, env);
        return a ? json(req, { phone: a.phone, ...status(a.u) }) : json(req, { error: "Hết phiên đăng nhập." }, 401);
      }

      if (path === "/key") {
        const a = await authUser(req, env);
        if (!a) return json(req, { error: "Hết phiên đăng nhập." }, 401);
        const s = status(a.u);
        if (!s.active) return json(req, { error: "Đã hết hạn dùng thử. Vui lòng gia hạn.", ...s }, 402);
        return json(req, { key: env.REPORT_KEY, ...s });
      }

      if (path.startsWith("/admin/")) {
        if (!env.ADMIN_KEY || req.headers.get("X-Admin-Key") !== env.ADMIN_KEY) return json(req, { error: "Không có quyền." }, 403);
        if (path === "/admin/users") {
          const out = [];
          for (const prefix of ["u:", "g:"]) {
            let cursor;
            do {
              const l = await env.USERS.list({ prefix, cursor }); cursor = l.list_complete ? undefined : l.cursor;
              for (const k of l.keys) { const u = await env.USERS.get(k.name, "json"); if (u) out.push({ phone: prefix === "u:" ? k.name.slice(2) : k.name, contact: u.contact || "", name: u.name, created: u.created, ...status(u) }); }
            } while (cursor);
          }
          return json(req, { users: out.sort((a, b) => b.created - a.created) });
        }
        const b = await body(req), phone = String(b.phone || "").startsWith("g:") ? b.phone : normPhone(b.phone), u = phone && (await env.USERS.get(kvKey(phone), "json"));
        if (!u) return json(req, { error: "Không thấy số này." }, 404);
        if (path === "/admin/extend") { // gia hạn thêm N ngày kể từ hạn hiện tại (hoặc từ hôm nay nếu đã hết)
          const days = Number(b.days) || 30, base = Math.max(Date.now(), u.paidUntil || 0);
          u.paidUntil = base + days * DAY;
        } else if (path === "/admin/reset") { // đặt lại mật khẩu
          const salt = crypto.getRandomValues(new Uint8Array(16)); u.salt = b64(salt); u.hash = await hashPw(String(b.password || ""), salt);
        } else if (path === "/admin/delete") { await env.USERS.delete(kvKey(phone)); return json(req, { ok: true }); }
        else return json(req, { error: "Không có lệnh này." }, 404);
        await env.USERS.put(kvKey(phone), JSON.stringify(u));
        return json(req, { ok: true, phone, ...status(u) });
      }
      return json(req, { error: "Không tìm thấy." }, 404);
    } catch (e) {
      return json(req, { error: "Lỗi máy chủ." }, 500);
    }
  },
};
