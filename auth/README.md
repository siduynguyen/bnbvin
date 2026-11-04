# Tài khoản bnbvin (đăng nhập bằng số điện thoại)

Worker `auth/worker.js` (Cloudflare Workers + KV) giữ tài khoản. Mỗi người đăng ký bằng SĐT + mật khẩu, tự được 30 ngày dùng thử; hết hạn thì bị khoá phần đầy đủ cho tới khi bạn gia hạn.
Cách hoạt động: dữ liệu đầy đủ nằm trong trang đã mã hoá; Worker chỉ đưa "khoá mở" cho người còn hạn.

## Cài đặt (làm 1 lần, ~10 phút)
1. Cloudflare → Workers & Pages → KV → Create namespace tên `USERS`.
2. Workers & Pages → Create → Worker, tên `bnbvin-auth` → dán nguyên `worker.js` → Deploy.
3. Worker → Settings → Bindings → Add → KV namespace: biến `USERS` chọn namespace vừa tạo.
4. Settings → Variables and Secrets: Secret `TOKEN_SECRET` (chuỗi ngẫu nhiên dài), `REPORT_KEY` (khoá mở báo cáo, đưa cho Claude), `ADMIN_KEY` (mật khẩu quản trị). Text `TRIAL_DAYS` = 30 (tuỳ chọn).
5. Mở `<địa-chỉ-worker>/health` phải thấy `kv:true, secrets:true`.
6. Gửi địa chỉ Worker cho Claude để gắn vào trang.

## Quản lý người dùng
Mở `bnbvin.com/admin.html`, nhập địa chỉ Worker + ADMIN_KEY: xem danh sách, gia hạn 30 ngày sau khi nhận chuyển khoản, đặt lại mật khẩu, xoá.

## Đăng nhập bằng Google (tuỳ chọn)
1. console.cloud.google.com → APIs & Services → Credentials → Create credentials → OAuth client ID → Web application. Authorized JavaScript origins: `https://bnbvin.com`, `https://www.bnbvin.com`.
2. Chép Client ID (dạng `xxxx.apps.googleusercontent.com`).
3. Worker → Variables: Text `GOOGLE_CLIENT_ID` = Client ID đó. Đưa Client ID cho Claude để gắn vào trang (`GOOGLE_CLIENT_ID` trong `tpl/thi-truong.tpl.html`).
Khách đăng nhập Google sẽ được hỏi để lại số Zalo; trang quản trị hiển thị cả email lẫn số Zalo để đối chiếu khi gia hạn.

## Khách quên mật khẩu
Khách nhắn Zalo từ số đã đăng ký → vào admin.html bấm "Đặt MK" → gửi mật khẩu tạm. Hoặc khách đăng nhập bằng Google.
