import time
import sys

try:
    from gpiozero import DigitalInputDevice
    sensor = DigitalInputDevice(17, pull_up=True)
    print("==================================================")
    print("   PBL5 - KIỂM TRA ĐỌC TÍN HIỆU CẢM BIẾN GPIO 17")
    print("==================================================")
    print("Nhấn Ctrl+C để dừng...\n")
    
    while True:
        # value: 1 = HIGH (Không có vật), 0 = LOW (Có vật)
        # is_active: True = LOW (Có vật), False = HIGH (Không có vật)
        print(f"Pin Value (1=HIGH, 0=LOW): {sensor.value} | is_active (True=LOW, False=HIGH): {sensor.is_active}")
        time.sleep(0.5)
except ImportError:
    print("❌ Lỗi: Không tìm thấy thư viện gpiozero. Hãy chạy trên Raspberry Pi!")
except KeyboardInterrupt:
    print("\n🛑 Đã dừng chương trình kiểm tra.")
except Exception as e:
    print(f"❌ Có lỗi xảy ra: {e}")
