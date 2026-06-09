#!/usr/bin/env python3
"""
PBL5 - Script kiem tra rieng biet dong co Servo (MG996R)
Chay tren Raspberry Pi: python pi_edge/test_servo.py
"""

import os
import sys
import time

# Support UTF-8 encoding for standard outputs to avoid errors in Windows terminals
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

def is_raspberry_pi():
    """Kiểm tra xem đang chạy trên Raspberry Pi thật hay không."""
    try:
        with open('/proc/device-tree/model', 'r') as f:
            return 'Raspberry Pi' in f.read()
    except Exception:
        return False

# Import gpiozero hoặc Mock nếu không chạy trên Pi
try:
    from gpiozero import AngularServo
    print("[+] Da import gpiozero.")
except ImportError:
    if not is_raspberry_pi() or os.environ.get("TESTING") == "1":
        print("[!] Warning: gpiozero not found or not on RPi. Using Mock hardware classes.")
        class AngularServo:
            def __init__(self, pin, min_pulse_width=0.0005, max_pulse_width=0.0025, min_angle=-90, max_angle=90):
                self.pin = pin
                self.min_pulse_width = min_pulse_width
                self.max_pulse_width = max_pulse_width
                self.min_angle = min_angle
                self.max_angle = max_angle
                self._angle = 0
                print(f"[MOCK] Khoi tao AngularServo tren pin {pin} (pulse: {min_pulse_width}s - {max_pulse_width}s)")
            
            @property
            def angle(self):
                return self._angle
            
            @angle.setter
            def angle(self, val):
                self._angle = val
                print(f"[MOCK] Servo pin {self.pin} -> Set goc: {val} do")
            
            def close(self):
                print(f"[MOCK] Dong servo tren pin {self.pin}")
    else:
        print("[X] gpiozero not found! Vui long cai dat hoac chay tren Raspberry Pi.")
        sys.exit(1)


# Cau hinh servo mac dinh giong conveyor_controller.py
DEFAULT_SERVOS = {
    "1": {"name": "Cam (Mang 1)", "pin": 5, "active_angle": -45},
    "2": {"name": "Chanh (Mang 2)", "pin": 6, "active_angle": -45},
    "3": {"name": "Quyt (Mang 3)", "pin": 16, "active_angle": -45}
}

def init_servo(pin):
    """Khoi tao doi tuong AngularServo voi thong so giong nhu he thong."""
    try:
        return AngularServo(
            pin,
            min_pulse_width=0.0005,
            max_pulse_width=0.0025,
            min_angle=-90,
            max_angle=90
        )
    except Exception as e:
        print(f"[X] Khong the khoi tao Servo tren pin {pin}: {e}")
        return None

def test_sweep(servo, step_delay=0.02):
    """Quay qua lai de kiem tra su tron tru."""
    print("\n--- Dang quet goc tu 0 -> -45 -> 45 -> 0 ---")
    
    # 0 -> -45
    print("Quay tu 0 ve -45...")
    for angle in range(0, -46, -5):
        servo.angle = angle
        time.sleep(step_delay)
    time.sleep(0.5)
    
    # -45 -> 45
    print("Quay tu -45 len 45...")
    for angle in range(-45, 46, 5):
        servo.angle = angle
        time.sleep(step_delay)
    time.sleep(0.5)
    
    # 45 -> 0
    print("Quay tu 45 ve 0...")
    for angle in range(45, -1, -5):
        servo.angle = angle
        time.sleep(step_delay)
    time.sleep(0.5)
    print("[+] Quet hoan tat!")


def test_interactive(servo):
    """Cho phep nhap goc tuy y tu ban phim."""
    print("\n--- Che do dieu khien truc tiep ---")
    print("Nhap goc muon quay (khoang tu -90 den 90).")
    print("Nhan 'q' hoac Enter de quay lai menu.")
    
    while True:
        try:
            inp = input("Nhap goc (-90 den 90): ").strip()
            if inp.lower() in ['q', '']:
                break
            
            angle = float(inp)
            if -90 <= angle <= 90:
                print(f"-> Di chuyen den goc {angle} do")
                servo.angle = angle
            else:
                print("[!] Vui long nhap goc trong khoang [-90, 90]!")
        except ValueError:
            print("[!] Gia tri khong hop le! Vui long nhap mot so hoac 'q'.")

def main_menu():
    while True:
        print("\n" + "="*50)
        print("        PBL5 - CONG CU KIEM TRA SERVO INTERACTIVE")
        print("="*50)
        print("Chon servo muon kiem tra:")
        for k, v in DEFAULT_SERVOS.items():
            print(f"  {k}. Servo {v['name']} (GPIO Pin: {v['pin']})")
        print("  4. Nhap GPIO Pin tuy chon")
        print("  5. Thoat")
        print("-"*50)
        
        choice = input("Nhap lua chon (1-5): ").strip()
        
        if choice in ["1", "2", "3"]:
            cfg = DEFAULT_SERVOS[choice]
            pin = cfg["pin"]
            name = cfg["name"]
            active_angle = cfg["active_angle"]
        elif choice == "4":
            pin_input = input("Nhap GPIO Pin (BCM): ").strip()
            if not pin_input.isdigit():
                print("[!] GPIO pin phai la mot so!")
                continue
            pin = int(pin_input)
            name = f"Custom Pin {pin}"
            active_angle = -45
        elif choice == "5":
            print("Cam on ban da su dung!")
            break
        else:
            print("[!] Lua chon khong hop le!")
            continue
        
        print(f"\n[*] Dang khoi tao servo '{name}' tren pin {pin}...")
        servo = init_servo(pin)
        if not servo:
            continue
        
        # Reset ve goc 0
        servo.angle = 0
        
        while True:
            print(f"\n--- Menu servo '{name}' (Pin: {pin}) ---")
            print(f"  1. Gat thu goc active ({active_angle} do) va thu ve (0 do)")
            print("  2. Quet goc tu tu (0 -> -45 -> 45 -> 0) de test do tron tru")
            print("  3. Nhap goc tuy y tu ban phim (-90 den 90)")
            print("  4. Dua ve goc 0 (Vi tri can bang)")
            print("  5. Chon servo khac / Quay lai")
            print("-"*50)
            
            sub_choice = input("Nhap lua chon (1-5): ").strip()
            
            if sub_choice == "1":
                print(f"Gat den goc active: {active_angle} do")
                servo.angle = active_angle
                time.sleep(1.0)
                print("Thu ve goc: 0 do")
                servo.angle = 0
                time.sleep(0.5)
            elif sub_choice == "2":
                test_sweep(servo)
            elif sub_choice == "3":
                test_interactive(servo)
            elif sub_choice == "4":
                print("Dua ve goc 0 do...")
                servo.angle = 0
            elif sub_choice == "5":
                break
            else:
                print("[!] Lua chon khong hop le!")
        
        print(f"[*] Dang giai phong servo '{name}'...")
        servo.close()


if __name__ == "__main__":
    main_menu()
