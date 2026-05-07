# 🎭 Trick Mode - Hướng Dẫn Sử Dụng

Chế độ Trick (hay còn gọi là Manual Mode) cho phép bạn điều khiển hệ thống phân loại trái cây **mà không cần AI model**. Đây là tính năng hữu ích cho việc demo, test hardware, hoặc khi không có model sẵn.

## ✨ Trick Mode hoạt động như thế nào?

Thay vì dùng camera + AI model để nhận diện trái cây, bạn có thể:

1. **Bấm phím** trên browser dashboard để chọn loại trái cây
2. **Hệ thống sẽ giả vờ** như đang chạy AI - hiển thị label + confidence ngẫu nhiên
3. **Băng chuyền vẫn hoạt động** thật - servo gạt trái cây theo đúng loại bạn chọn
4. **Camera vẫn chụp ảnh thật** để hiển thị lên dashboard

→ Kết quả: Người xem nghĩ hệ thống AI đang hoạt động, nhưng thực ra bạn kiểm soát hoàn toàn!

## 🚀 Bắt Đầu Nhanh

### 1. Khởi động Server (Laptop)

```bash
cd repo
python start_server.py --host 0.0.0.0 --port 8765
```

### 2. Khởi động Pi với chế độ Manual

```bash
cd repo
python start_pi.py --server <LAPTOP_IP> --port 8765 --manual-control
```

**Tham số tùy chọn:**
- `--manual-run-duration 3.0` - Thời gian chạy băng chuyền (mặc định 2.0 giây)

### 3. Mở Dashboard

```
http://<LAPTOP_IP>:8765/
```

## ⌨️ Các Phím Điều Khiển

| Phím | Label | Servo | Confidence |
|------|-------|-------|------------|
| `1` | 🍊 Cam | Pin 5 | 82-98% |
| `2` | 🍋 Chanh | Pin 6 | 82-98% |
| `3` | 🍊 Quyt | Pin 26 | 82-98% |
| `4` | ❓ Unknown | Không gạt | 35-55% |
| `←` (Left) | 🍊 Cam | Pin 5 | 82-98% |
| `↓` (Down) | 🍋 Chanh | Pin 6 | 82-98% |
| `→` (Right) | 🍊 Quyt | Pin 26 | 82-98% |
| `↑` (Up) | ❓ Unknown | Không gạt | 35-55% |

## 🎮 Cách Sử Dụng

1. Đảm bảo Pi đã kết nối (server log hiển thị `[+] Pi connected from:`)
2. Mở dashboard trên browser
3. Bấm phím `1`, `2`, `3`, hoặc `4` (hoặc các mũi tên)
4. Quan sát:
   - ✅ Băng chuyền bắt đầu chạy
   - ✅ Servo gạt trái cây (nếu không phải unknown)
   - ✅ Dashboard hiển thị kết quả với confidence ngẫu nhiên
   - ✅ Băng chuyền tự dừng sau 2 giây

## 🔧 Khác Biệt Giữa Auto Mode và Manual Mode

| Tính năng | Auto Mode | Manual Mode |
|-----------|-----------|-------------|
| AI Model | ✅ Dùng YOLO | ❌ Không dùng |
| Sensor | ✅ Dùng cảm biến | ❌ Không dùng |
| Điều khiển bằng phím | ❌ Không | ✅ Có |
| Confidence | Từ model thật | Ngẫu nhiên 82-98% |
| Label | Từ model thật | Từ phím bấm |

## 📋 Kiểm Tra Nhanh

Sau khi khởi động, kiểm tra log:

**Server:**
```
[INFO] Listening on http://0.0.0.0:8765
[+] Pi connected from: 192.168.1.xxx:xxxxx
[+] Dashboard client connected.
```

**Pi:**
```
[INFO] 🔄 Connecting to ws://192.168.1.xxx:8765/ws/pi...
[INFO] ✅ Connection established!
[INFO] 🔍 Opening camera at index 0...
[INFO] ✅ Camera OK: index=0, MJPEG, 640x480
```

## 🧪 Test Không Cần Hardware

Nếu chỉ muốn test WebSocket + Dashboard mà không có Pi thật:

```bash
cd repo
python -m unittest discover -s tests -p "test_*.py" -v
```

## ⚠️ Lưu Ý

1. **Debounce 300ms** - Bấm nhanh cũng chỉ nhận 1 command mỗi 300ms
2. **Arrow keys** có thể làm scroll trang - đã có `preventDefault()`
3. **Camera warmup** - lần đầu có thể mất 6-10 giây
4. **Frame ID** tăng liên tục, không reset khi reconnect

## 📖 Tài Liệu Chi Tiết

- [TRICK_PIPELINE.md](./TRICK_PIPELINE.md) - Chi tiết kỹ thuật đầy đủ
- [PIPELINE.md](./PIPELINE.md) - Auto mode pipeline
- [repo/docs/](./repo/docs/) - Tài liệu Raspberry Pi

---

**Mẹo demo**: Khi không nói cho khách biết, họ sẽ nghĩ hệ thống AI thật đang hoạt động! 🎭