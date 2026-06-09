"""
PBL5 - Script chan doan cam bien hong ngoai E18-D80NK
Chay tren Raspberry Pi: python pi_edge/diagnose_sensor.py

Script nay kiem tra:
1. GPIO 17 (mac dinh) voi nhieu cau hinh pull_up khac nhau
2. Cac chan GPIO lan can de tim dung chan cam bien
"""
import time
import sys

def diagnose_single_pin(pin, pull_up_mode):
    """Test mot chan GPIO voi pull_up cu the."""
    from gpiozero import DigitalInputDevice
    try:
        sensor = DigitalInputDevice(pin, pull_up=pull_up_mode)
        readings = []
        for _ in range(5):
            readings.append(sensor.value)
            time.sleep(0.05)
        sensor.close()
        avg = sum(readings) / len(readings)
        return avg, readings
    except Exception as e:
        return None, str(e)


def diagnose_raw_pin(pin):
    """Doc trang thai chan GPIO truc tiep qua RPi.GPIO (khong qua gpiozero)."""
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Test 1: Khong pull (float)
        GPIO.setup(pin, GPIO.IN)
        time.sleep(0.05)
        raw_no_pull = GPIO.input(pin)

        # Test 2: Pull-up
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        time.sleep(0.05)
        raw_pull_up = GPIO.input(pin)

        # Test 3: Pull-down
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        time.sleep(0.05)
        raw_pull_down = GPIO.input(pin)

        GPIO.cleanup(pin)
        return raw_no_pull, raw_pull_up, raw_pull_down
    except Exception as e:
        return None, None, str(e)


def scan_all_pins():
    """Quet tat ca cac chan GPIO pho bien de tim chan nao co tin hieu cam bien."""
    from gpiozero import DigitalInputDevice
    # Cac chan GPIO pho bien tren Raspberry Pi (BCM numbering)
    common_pins = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]
    # Bo qua cac chan dang dung cho motor va servo
    used_pins = {5, 6, 22, 23, 26}  # servo: 5,6,26 | motor: 22,23
    
    print("\n" + "=" * 60)
    print("   QUET TAT CA CAC CHAN GPIO (BCM)")
    print("   Tim chan nao dang o muc LOW (co the la cam bien)")
    print("=" * 60)
    
    low_pins = []
    for pin in common_pins:
        if pin in used_pins:
            print(f"  GPIO {pin:2d}: [BO QUA - dang dung cho servo/motor]")
            continue
        try:
            sensor = DigitalInputDevice(pin, pull_up=True)
            time.sleep(0.05)
            val = sensor.value
            act = sensor.is_active
            sensor.close()
            status = "LOW  (is_active=True)" if act else "HIGH (is_active=False)"
            marker = " <-- CO THE LA CAM BIEN!" if act else ""
            print(f"  GPIO {pin:2d}: Pin Value={val}, {status}{marker}")
            if act:
                low_pins.append(pin)
        except Exception as e:
            print(f"  GPIO {pin:2d}: [LOI: {e}]")
    
    return low_pins


def interactive_test(pin):
    """Test tuong tac: doc lien tuc de kiem tra cam bien co thay doi khong."""
    from gpiozero import DigitalInputDevice
    
    print(f"\n{'=' * 60}")
    print(f"   TEST TUONG TAC - GPIO {pin}")
    print(f"   Hay che/mo cam bien va quan sat gia tri thay doi")
    print(f"   Nhan Ctrl+C de dung")
    print(f"{'=' * 60}\n")
    
    sensor = DigitalInputDevice(pin, pull_up=True)
    last_state = None
    try:
        while True:
            val = sensor.value
            act = sensor.is_active
            state = "CO VAT (LOW)" if act else "KHONG CO VAT (HIGH)"
            
            if act != last_state:
                print(f"  >>> THAY DOI! Pin Value={val}, is_active={act} -> {state}")
                last_state = act
            else:
                print(f"  Pin Value={val}, is_active={act} -> {state}", end="\r")
            
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n\nDa dung.")
    finally:
        sensor.close()


def main():
    print("=" * 60)
    print("   PBL5 - CHAN DOAN CAM BIEN HONG NGOAI E18-D80NK")
    print("=" * 60)
    
    # === Buoc 1: Test GPIO 17 voi RPi.GPIO (raw) ===
    print("\n--- Buoc 1: Doc RAW GPIO 17 (qua RPi.GPIO) ---")
    result = diagnose_raw_pin(17)
    if result[0] is not None:
        no_pull, pull_up, pull_down = result
        print(f"  GPIO 17 (khong pull):  {'HIGH (1)' if no_pull else 'LOW (0)'}")
        print(f"  GPIO 17 (pull-up):     {'HIGH (1)' if pull_up else 'LOW (0)'}")
        print(f"  GPIO 17 (pull-down):   {'HIGH (1)' if pull_down else 'LOW (0)'}")
        
        if no_pull == 0 and pull_up == 0 and pull_down == 0:
            print("\n  !! GPIO 17 LUON O MUC LOW -> Chan bi noi tat xuong GND")
            print("  !! hoac day tin hieu cam bien dang keo xuong LOW lien tuc.")
        elif no_pull == 1 and pull_up == 1 and pull_down == 1:
            print("\n  !! GPIO 17 LUON O MUC HIGH -> Chan bi keo len VCC")
            print("  !! hoac cam bien khong ket noi vao chan nay.")
        elif pull_up == 1 and pull_down == 0:
            print("\n  !! GPIO 17 DANG TROI NOI (floating) -> Cam bien CHUA ket noi!")
    else:
        print(f"  Khong the doc RPi.GPIO: {result[2]}")
    
    # === Buoc 2: Test GPIO 17 voi gpiozero ===
    print("\n--- Buoc 2: Doc GPIO 17 (qua gpiozero, pull_up=True) ---")
    avg, readings = diagnose_single_pin(17, True)
    if avg is not None:
        print(f"  5 lan doc: {readings}")
        print(f"  Trung binh: {avg}")
        if avg > 0.8:
            print("  => Pin LUON o muc LOW (is_active=True)")
        elif avg < 0.2:
            print("  => Pin LUON o muc HIGH (is_active=False)")
        else:
            print("  => Pin KHONG ON DINH (nhieu)")
    
    # === Buoc 3: Quet tat ca cac chan ===
    low_pins = scan_all_pins()
    
    if low_pins:
        print(f"\n--- Cac chan dang o muc LOW: {low_pins} ---")
        print("Neu cam bien cua ban dang ket noi vao mot trong cac chan nay,")
        print("hay thu test tuong tac voi chan do.")
    
    # === Buoc 4: Hoi nguoi dung muon test chan nao ===
    print(f"\n{'=' * 60}")
    print("Nhap so chan GPIO de test tuong tac (VD: 17), hoac 'q' de thoat:")
    try:
        user_input = input("> ").strip()
        if user_input.lower() != 'q' and user_input.isdigit():
            interactive_test(int(user_input))
    except (KeyboardInterrupt, EOFError):
        pass
    
    print("\nHoan tat chan doan.")


if __name__ == "__main__":
    main()
