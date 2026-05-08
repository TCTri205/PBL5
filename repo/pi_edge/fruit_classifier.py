import sys
import os
import time
import numpy as np
import cv2
import onnxruntime as ort
from typing import Tuple, Union, List, Optional


class FruitClassifier:
    def __init__(
        self, model_path: str, imgsz: int = 320, class_names: Optional[List[str]] = None
    ):
        """
        Khởi tạo bộ phân loại trái cây sử dụng ONNX Runtime.

        Args:
            model_path: Đường dẫn tới file model .onnx
            imgsz: Kích thước ảnh đầu vào cho model
            class_names: Danh sách tên các lớp (mặc định là cam, chanh, quyt)
        """
        self.imgsz = imgsz
        # Tối ưu hóa cho Raspberry Pi: Đa luồng CPU và tối ưu đồ thị
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 4  # Số nhân CPU của Pi (thường là 4)
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        # Prefer CPUExecutionProvider for Raspberry Pi for stability
        self.session = ort.InferenceSession(
            model_path, sess_options=opts, providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name

        # Thử lấy tên lớp từ metadata của model (YOLO export thường có)
        try:
            model_meta = self.session.get_modelmeta().custom_metadata_map
            if class_names:
                self.class_names = class_names
            elif "names" in model_meta:
                # YOLO format: "{0: 'cam', 1: 'chanh', ...}" or JSON
                import ast
                import json
                try:
                    names_dict = ast.literal_eval(model_meta["names"])
                except Exception:
                    # Fallback for pure JSON metadata
                    names_dict = json.loads(model_meta["names"].replace("'", '"'))
                
                self.class_names = [names_dict[i] for i in sorted(names_dict.keys())]
                print(f"📦 Auto-loaded classes from model: {self.class_names}")
            else:
                self.class_names = ["cam", "chanh", "quyt"]
        except Exception:
            self.class_names = class_names if class_names else ["cam", "chanh", "quyt"]

        # Warm-up (E3)
        try:
            dummy = np.zeros((1, 3, self.imgsz, self.imgsz), dtype=np.float32)
            t0 = time.time()
            self.session.run(None, {self.input_name: dummy})
            warmup_ms = (time.time() - t0) * 1000
            print(f"🔥 ONNX session warmed up in {warmup_ms:.1f}ms")
        except Exception as e:
            print(f"⚠️ Warm-up failed: {e}")

    def preprocess(self, img: np.ndarray) -> np.ndarray:
        """
        Tiền xử lý ảnh giống như training pipeline.

        Optimization: Resize trước khi chuyển đổi màu sắc để giảm khối lượng tính toán.
        """
        # Resize first (cheaper on BGR)
        img = cv2.resize(img, (self.imgsz, self.imgsz))

        # Convert BGR to RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Chuyển sang Float32 và normalize 0-1
        img = img.astype(np.float32) / 255.0

        # Chuyển từ HWC sang CHW
        img = np.transpose(img, (2, 0, 1))

        # Thêm batch dimension (N, C, H, W)
        img = np.expand_dims(img, axis=0)
        return img

    def predict(
        self, input_data: Union[str, np.ndarray], confidence_threshold: float = 0.5
    ) -> Tuple[Optional[str], float]:
        """
        Dự đoán lớp của ảnh.

        Args:
            input_data: Đường dẫn ảnh (str) hoặc numpy array (OpenCV frame).
            confidence_threshold: Ngưỡng tin cậy tối thiểu.

        Returns:
            Tuple (label, confidence)
        """
        if isinstance(input_data, str):
            img = cv2.imread(input_data)
        else:
            img = input_data

        if img is None:
            return None, 0.0

        # 3. Inference
        outputs = self.session.run(None, {self.input_name: blob})

        # 4. Post-process (E4: Robust output handling)
        raw_output = outputs[0]
        
        # Format 1: Classification (1, num_classes)
        if raw_output.ndim == 2 and raw_output.shape[0] == 1:
            probs = raw_output[0]
            idx = np.argmax(probs)
            confidence = float(probs[idx])
        
        # Format 2: Detection (1, num_detections, 5+num_classes) - YOLO Detect
        elif raw_output.ndim == 3 and raw_output.shape[0] == 1:
            # Lấy detection có confidence cao nhất
            detections = raw_output[0] # Shape (N, 5+C)
            # Giả sử format: [x, y, w, h, box_conf, class_probs...]
            confidences = detections[:, 4] if detections.shape[1] > 4 else np.max(detections, axis=1)
            idx_det = np.argmax(confidences)
            confidence = float(confidences[idx_det])
            
            if detections.shape[1] > 5:
                class_probs = detections[idx_det, 5:]
                idx = np.argmax(class_probs)
            else:
                idx = 0 
        else:
            print(f"⚠️ Unknown model output shape: {raw_output.shape}")
            return "unknown", 0.0

        # 5. Threshold & Label Mapping
        if confidence < confidence_threshold:
            return "unknown", confidence

        try:
            label = self.class_names[idx]
        except (IndexError, TypeError):
            label = f"class_{idx}"
            
        return label, confidence


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python fruit_classifier.py <model_path.onnx> <image_path>")
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

    print("\n--- Result ---")
    print(f"Predicted: {label.upper() if label else 'NONE'}")
    print(f"Confidence: {score:.2%}")
    print(f"Inference time: {(end_time - start_time) * 1000:.2f} ms")
