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
        # Prefer CPUExecutionProvider for Raspberry Pi for stability
        self.session = ort.InferenceSession(
            model_path, providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name

        # Lấy tên lớp (mapping từ training)
        self.class_names = class_names if class_names else ["cam", "chanh", "quyt"]

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

        blob = self.preprocess(img)
        outputs = self.session.run(None, {self.input_name: blob})

        # Giả sử output là tensor xác suất (logits -> softmax)
        probs = outputs[0][0]

        idx = np.argmax(probs)
        confidence = probs[idx]

        if confidence < confidence_threshold:
            return "unknown", confidence

        return self.class_names[idx], confidence


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
