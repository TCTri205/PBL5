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

Follow these guides to move from research to a real-world system:

- **[Raspberry Pi Inference Guide](./repo/docs/raspberry_pi_inference_guide.md)**: Manual setup and script usage.
- **[System Integration Plan](./repo/docs/system_integration_plan.md)**: **Full End-to-End Design** (Camera capture + Pi Inference + Laptop communication).

## 🚀 Getting Started

1. Open `YOLO_Training_Colab_v2.ipynb` in [Google Colab](https://colab.research.google.com/).
2. Mount your Google Drive and set the `DRIVE_SOURCE` path to your raw dataset.
3. Run the cells to process data and begin training.
4. Use `YOLO_Inference_Colab.ipynb` to run predictions using your trained `best.pt` or `best.onnx` model.

## 🧪 Dataset

The model currently expects three classes of fruits:

- `cam` (Orange)
- `chanh` (Lime)
- `quyt` (Tangerine)
