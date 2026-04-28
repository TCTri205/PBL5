# Technical Stack: PBL5 Green Fruit Classification

This document provides a detailed overview of the technology stack and architecture used in this project.

## 🧠 Core Frameworks & AI Models

- **Architecture**: [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) (v8/v11/v12 support).
- **Task**: Image Classification (Multi-class).
- **Target Classes**: `cam` (Orange), `chanh` (Lime), `quyt` (Tangerine).
- **Model Variants**: Typically uses `yolo11n-cls.pt` or `yolo8n-cls.pt` for optimal edge performance.

## 💻 Execution Environment

- **Platform**: Google Colab.
- **Storage**: Integrated with **Google Drive** for persistent storage:
  - Dataset source: `/content/drive/MyDrive/PBL5`
  - Training artifacts: `/content/drive/MyDrive/YOLO_PBL5_Classification`
- **Acceleration**: NVIDIA GPUs (T4/L4) via `torch.cuda`.

## 🛠️ Data Processing Pipeline

- **SSD-First Strategy**: Dataset is copied from Drive to local SSD (`/content`) to maximize I/O throughput during training.
- **Splitting**: Uses `split-folders` (80% Train, 20% Val) with a fixed seed for reproducibility.
- **Image Standardization**:
  - Format: JPEG (reduced from RAW/PNG to save space).
  - Processing: `Pillow` for EXIF transposition and `RGB` conversion.
  - Dimension: Optimized for `imgsz=224` or `320`.

## 🚀 Model Lifecycle & Optimization

- **Training**:
  - **Seamless Resume**: Automatic detection of `last.pt` on Drive to continue interrupted sessions.
  - **Immediate Sync**: custom `on_model_save` callback to sync weights to Drive every few epochs.
- **Deployment & Export**:
  - **Standalone Binary**: Exported to **ONNX** format for cross-platform compatibility.
  - **Simplification**: Processed with `onnx-simplifier` to remove redundant nodes.
- **Inference**: Optimized for **ONNX Runtime** on CPU.

## 🌏 Deployment Architecture (Edge)

The system transitions from Cloud (Colab) to Edge (Raspberry Pi):

- **Edge Device**: Raspberry Pi 4 (4GB+ RAM recommended).
- **Inference Engine**: **ONNX Runtime** (CPUExecutionProvider).
- **Standalone Script**: `repo/pi_edge/fruit_classifier.py` for lightweight classification.
- **Communication**: WebSocket protocol for real-time reporting to a monitoring server.
- **Guides**:
  - [System Integration Plan](./system_integration_plan.md) ⭐
  - [Raspberry Pi Setup Guide](./raspberry_pi_setup_guide.md)
  - [Raspberry Pi Inference Guide](./raspberry_pi_inference_guide.md)

## 📦 Running the System

1. **Server (Laptop)**: `python start_server.py`
2. **Edge (Pi)**: `python start_pi.py --server <IP_LAPTOP>`

## 📦 Dependencies

- `ultralytics>=8.3.0`: Core YOLO logic.
- `onnxruntime`, `onnxsim`: Optimized edge inference.
- `opencv-python-headless`: Image capture and processing.
- `websockets`: Real-time communication.
- `numpy`: Numerical operations.
