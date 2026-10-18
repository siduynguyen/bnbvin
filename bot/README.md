# Trợ lý BnbVin (bot chat trên bnbvin.com)

- `worker.js`: máy chủ bot, chạy trên Cloudflare Workers (miễn phí). Dán nguyên tệp vào trình sửa code của Worker.
- Dữ liệu bot đọc: `../data.json` (căn hộ, giá, lịch bận, cập nhật mỗi sáng 6:45) và `../kb.md` (ghi chú của chủ nhà: giờ nhận/trả phòng, cọc, nội quy…).
- Khung chat nằm cuối `../index.html`; điền địa chỉ Worker vào `BOT_URL` để hiện nút chat.

Biến cần điền trong Worker (Settings → Variables and Secrets):

| Tên | Loại | Ghi chú |
|---|---|---|
| ANTHROPIC_API_KEY | Secret | console.anthropic.com → API keys |
| WHATSAPP_PHONE | Text | số WhatsApp nhận báo đơn, dạng +84365329311 |
| WHATSAPP_APIKEY | Secret | lấy miễn phí từ CallMeBot (xem callmebot.com/blog/free-api-whatsapp-messages) |
| TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID | | tuỳ chọn, không dùng ở Việt Nam |
| RESEND_API_KEY | Secret | resend.com → API keys (đăng ký bằng email nhận thông báo) |
| EMAIL_TO | Text | siduybosch@gmail.com |
| MODEL | Text | tuỳ chọn, mặc định claude-haiku-5-5 |

Kiểm tra: mở `<worker>/health`, `ai`, `whatsapp`, `email` phải là `true`.
