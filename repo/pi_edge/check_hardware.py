import os
import sys
import cv2
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def check_dependencies():
    logger.info("🔍 Checking dependencies...")
    try:
        import onnxruntime
        import websockets
        import numpy
        import gpiozero
        logger.info("✅ Core dependencies found (including gpiozero).")
    except ImportError as e:
        logger.error(f"❌ Missing dependency: {e}")
        return False
    
    # Check for libgomp (critical for ONNX)
    if sys.platform == "linux":
        import subprocess
        try:
            subprocess.check_output(["ldconfig", "-p | grep libgomp"], shell=True)
            logger.info("✅ libgomp found.")
        except Exception:
            logger.warning("⚠️  libgomp might be missing. If ONNX fails, run: sudo apt install libgomp1")
            
    return True

def check_model():
    logger.info("🔍 Checking model file...")
    model_path = os.path.join(os.path.dirname(__file__), "model", "best.onnx")
    if os.path.exists(model_path):
        logger.info(f"✅ Model found at {model_path}")
        return True
    else:
        logger.warning(f"⚠️  Model NOT found at {model_path}")
        return False

def check_camera():
    logger.info("🔍 Checking camera access...")
    for i in range(3):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                logger.info(f"✅ Camera found and working at index {i}")
                cap.release()
                return True
            cap.release()
    logger.error("❌ No working camera found at indices 0, 1, or 2.")
    return False

def check_servos():
    logger.info("🔍 Checking servos (GPIO 5, 6, 26)...")
    try:
        from gpiozero import AngularServo
        import time
        pins = [5, 6, 26]
        labels = ["Cam (5)", "Chanh (6)", "Quyt (26)"]
        
        for i, pin in enumerate(pins):
            try:
                s = AngularServo(pin, min_angle=0, max_angle=180, 
                                min_pulse_width=0.0005, max_pulse_width=0.0025)
                logger.info(f"Testing Servo {labels[i]} -> 40 degrees...")
                s.angle = 40
                time.sleep(0.5)
                s.angle = 0
                time.sleep(0.5)
                s.close()
                logger.info(f"✅ Servo {labels[i]} OK.")
            except Exception as e:
                logger.error(f"❌ Servo {labels[i]} failed: {e}")
        return True
    except ImportError:
        logger.warning("⚠️ gpiozero not found, skipping servo hardware test.")
        return False

def check_power():
    """Kiểm tra nguồn điện (chỉ trên Raspberry Pi)."""
    if sys.platform == "linux":
        logger.info("🔍 Checking power supply stability...")
        try:
            # vcgencmd get_throttled returns hex. If not 0, there's a problem.
            import subprocess
            output = subprocess.check_output(["vcgencmd", "get_throttled"]).decode()
            status = output.split("=")[1].strip()
            if status == "0x0":
                logger.info("✅ Power supply is stable.")
            else:
                logger.warning(f"⚠️  Power issue detected (throttled={status}). Check your power supply!")
        except Exception:
            pass # vcgencmd might not be available

def main():
    logger.info("=== PBL5 Hardware Diagnostic Tool ===")
    
    deps = check_dependencies()
    model = check_model()
    cam = check_camera()
    servos = check_servos()
    check_power()
    
    print("\n--- Summary ---")
    print(f"Dependencies: {'OK' if deps else 'FAIL'}")
    print(f"Model File:   {'OK' if model else 'MISSING'}")
    print(f"Camera:       {'OK' if cam else 'NOT FOUND'}")
    print(f"Servos (5,6,26): {'OK' if servos else 'SKIP/FAIL'}")
    
    if deps and model and cam and servos:
        print("\n✨ Everything looks good! You are ready to run the streamer.")
    else:
        print("\n❌ Some checks failed. Please fix them before starting.")

if __name__ == "__main__":
    main()
