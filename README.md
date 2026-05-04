# PBL5: Green Fruit Classification using YOLO

A machine learning project focused on classifying green fruits (Oranges, Limes, and Tangerines) using the YOLOv8/v11 architecture, optimized for execution in Google Colab environments.

## 🌟 Key Features

- **Modern AI**: Built on the latest Ultralytics YOLO framework.
- **Colab Optimized**: SSD-first training strategy to minimize Google Drive I/O bottlenecks.
- **Persistence**: Automatic synchronization of checkpoints and results to Google Drive.
- **Deployment Ready**: Export support for ONNX format with simplification.

## 📂 Repository Structure

- `YOLO_Training_Colab_v2.ipynb`: The main notebook for data preparation, training, validation, and export.
- `YOLO_Inference_Colab.ipynb`: dedicated notebook for testing models on new images.
- `repo/`: Contains core logic and utilities.
- `model/`: Storage for model weights and configuration.

## 🛠 Tech Stack

Detailed information about the technologies and architectural decisions can be found in **[TECH_STACK.md](./repo/docs/TECH_STACK.md)**.

## 🌏 Raspberry Pi Deployment & Integration

Hệ thống đã được tối ưu hóa và kiểm tra kỹ lưỡng cho việc triển khai thực tế:

- **[Quick Start Checklist](./repo/docs/deployment_checklist.md)**: Các bước kiểm tra nhanh trước khi chạy.
- **[Raspberry Pi Setup Guide](./repo/docs/raspberry_pi_setup_guide.md)** ⭐: Thiết lập phần cứng và môi trường.
- **[Hardware Integration Plan](./repo/docs/implementation/hardware_integration_plan.md)**: Chi tiết về điều khiển băng chuyền và cảm biến.
- **[System Integration Plan](./repo/docs/system_integration_plan.md)**: Luồng dữ liệu và thiết lập WebSocket.

## ⚙️ Hardware Control

Hệ thống tích hợp điều khiển băng chuyền tự động:
- **Motor**: L298N (Pins 22, 23) để điều khiển di chuyển trái cây.
- **Sensor**: E18-D80NK (Pin 17) để phát hiện vật thể và kích hoạt camera.
- **An toàn**: Tự động dừng khẩn cấp (Emergency Stop) khi phát hiện kẹt băng chuyền hoặc lỗi cảm biến.

## 🚀 Running the System

Tại thư mục `repo/`, sử dụng các script tiện ích:

1. **Server**: `python start_server.py`
2. **Edge (Pi)**: `python start_pi.py --server <IP_LAPTOP>`

## 🧪 Dataset & Classes

Mô hình phân loại chính xác 3 loại trái cây xanh:

- `cam` (Orange)
- `chanh` (Lime)
- `quyt` (Tangerine)
