# Technical Stack: PBL5 Green Fruit Classification

This document provides a detailed overview of the technology stack and architecture used in this project.

## 🧠 Core Frameworks & AI Models

- **Architecture**: [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) (v8/v11/v12 support).
- **Task**: Image Classification (Multi-class).
- **Target Classes**: `cam` (Orange), `chanh` (Lime), `quyt` (Tangerine).
- **Model Variants**: Typically uses `yolo11s-cls.pt` or similar small/nano variants for performance balancing.

## 💻 Execution Environment

- **Platform**: Google Colab.
- **Storage**: Highly integrated with **Google Drive** for:
  - Persistent dataset storage (`/content/drive/MyDrive/PBL5`).
  - Training results and checkpoints (`/content/drive/MyDrive/YOLO_PBL5_Classification_v2`).
- **Acceleration**: Leverages NVIDIA GPUs available in Colab (T4/P100) via `torch.cuda`.

## 🛠️ Data Processing Pipeline

- **Splitting**: Uses `split-folders` to automatically divide raw data into 80% Training and 20% Validation.
- **Image Processing**:
  - Library: `Pillow` (PIL).
  - Optimizations: Automatic EXIF transposition, RGB conversion, and thumbnail resizing to `MAX_IMAGE_EDGE` (default 640).
  - Failure Handling: Robust error catching for corrupted images.
- **SSD-First Optimization**: To avoid slow I/O from Google Drive during training, the dataset is copied and processed on the Colab local SSD (`/content`) before training starts.

## 🚀 Model Lifecycle & Optimization

- **Training**:
  - Supports **Seamless Resume**: Detects existing `last.pt` on Drive and copies it to local SSD to continue training.
  - Callbacks: Custom `on_model_save` callback to synchronize every checkpoint back to Google Drive immediately.
- **Deployment & Export**:
  - **Formats**: Supports both PyTorch (`.pt`) and **ONNX** (`.onnx`).
  - **Simplification**: Uses `onnx-simplifier` during export to ensure model compatibility and efficiency.
- **Inference**:
  - Flexible inference engine supporting both `.pt` and `.onnx` formats.
  - Automatic input shape resolution for ONNX models.
  - Confidence thresholding (default 0.5) to handle "other" or uncertain classifications.

## 🌏 Deployment Architecture (Edge)

The system is designed to transition from Cloud (Colab) to Edge (Raspberry Pi):

- **Optimization**: Uses **ONNX Runtime** for efficient CPU inference on ARM architecture.
- **Standalone Script**: `repo/pi_inference.py` handles image classification without the heavy `ultralytics` overhead.
- **Integration**: Designed to work in tandem with a WebSocket server for real-time fruit classification reporting.
- **System Design**: See [System Integration Plan](./system_integration_plan.md) for the end-to-end architecture (Camera -> Pi -> Laptop).
- **Guides**:
  - [Raspberry Pi Inference Guide](./raspberry_pi_inference_guide.md)
  - [Raspberry Pi Setup Guide](./raspberry_pi_setup_guide.md)

## 📦 Dependencies

- `ultralytics`: Core YOLO logic.
- `torch`: Deep learning backend.
- `onnx`, `onnxruntime`, `onnxsim`: Model export and optimized inference.
- `numpy`: Numerical processing.
- `split-folders`: Dataset management.
- `IPython`: For visual feedback in Colab.
