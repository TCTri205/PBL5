import sys
import os
import time
import numpy as np
import cv2
import onnxruntime as ort

class FruitClassifier:
    def __init__(self, model_path, imgsz=320):
        """
        Khởi tạo bộ phân loại trái cây sử dụng ONNX Runtime.
        """
        self.imgsz = imgsz
        # Prefer CPUExecutionProvider for Raspberry Pi for stability
        self.session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        
        # Lấy tên lớp (mapping từ training)
        # Giả sử mapping mặc định từ notebook: 0: cam, 1: chanh, 2: quyt
        self.class_names = ['cam', 'chanh', 'quyt']

    def preprocess(self, img):
        """
        Tiền xử lý ảnh giống như training pipeline.
        """
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (self.imgsz, self.imgsz))
        
        # Chuyển sang Float32 và normalize 0-1
        img = img.astype(np.float32) / 255.0
        
        # Chuyển từ HWC sang CHW
        img = np.transpose(img, (2, 0, 1))
        
        # Thêm batch dimension (N, C, H, W)
        img = np.expand_dims(img, axis=0)
        return img

    def predict(self, img_path, confidence_threshold=0.5):
        """
        Dự đoán lớp của ảnh.
        """
        img = cv2.imread(img_path)
        if img is None:
            return None, 0.0
            
        blob = self.preprocess(img)
        outputs = self.session.run(None, {self.input_name: blob})
        
        # Giả sử output là tensor xác suất (logits -> softmax)
        probs = outputs[0][0]
        
        # Tính softmax nếu output là raw logits (YOLO ONNX thường output softmaxed probs)
        # Nếu output chưa softmax:
        # exp_probs = np.exp(probs - np.max(probs))
        # probs = exp_probs / exp_probs.sum()
        
        idx = np.argmax(probs)
        confidence = probs[idx]
        
        if confidence < confidence_threshold:
            return "unknown", confidence
            
        return self.class_names[idx], confidence

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python pi_inference.py <model_path.onnx> <image_path>")
        sys.exit(1)
        
    model_file = sys.argv[1]
    image_file = sys.argv[2]
    
    if not os.path.exists(model_file):
        print(f"Error: Model file {model_file} not found.")
        sys.exit(1)
        
    classifier = FruitClassifier(model_file)
    
    start_time = time.time()
    label, score = classifier.predict(image_file)
    end_time = time.time()
    
    print(f"\n--- Result ---")
    print(f"Predicted: {label.upper()}")
    print(f"Confidence: {score:.2%}")
    print(f"Inference time: {(end_time - start_time)*1000:.2f} ms")
