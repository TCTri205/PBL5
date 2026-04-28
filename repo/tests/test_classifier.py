import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import os
import sys

# Add pi_edge to path so we can import fruit_classifier
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "pi_edge"))
from fruit_classifier import FruitClassifier


class TestFruitClassifier(unittest.TestCase):
    @patch("onnxruntime.InferenceSession")
    def setUp(self, mock_session):
        # Mocking the ONNX session
        self.mock_session_instance = MagicMock()
        mock_session.return_value = self.mock_session_instance

        # Define mock inputs for InferenceSession
        mock_input = MagicMock()
        mock_input.name = "input_node"
        self.mock_session_instance.get_inputs.return_value = [mock_input]

        self.classifier = FruitClassifier(model_path="dummy_model.onnx", imgsz=320)

    def test_preprocess(self):
        # Create a dummy BGR image (H, W, C)
        dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)
        blob = self.classifier.preprocess(dummy_img)

        # Check shape (N, C, H, W)
        self.assertEqual(blob.shape, (1, 3, 320, 320))
        # Check normalization (values between 0 and 1)
        self.assertTrue(np.all(blob >= 0) and np.all(blob <= 1))

    def test_predict_success(self):
        # Setup mock return value for session.run
        # it returns a list of outputs, each output is a batch of results
        # for a classifier, it's (1, num_classes)
        # Assuming classes: 0: cam, 1: chanh, 2: quyt
        mock_output = np.array([[0.9, 0.05, 0.05]])
        self.mock_session_instance.run.return_value = [mock_output]

        dummy_img = np.zeros((320, 320, 3), dtype=np.uint8)
        label, confidence = self.classifier.predict(dummy_img)

        self.assertEqual(label, "cam")
        self.assertAlmostEqual(confidence, 0.9)

    def test_predict_threshold(self):
        # Mock low confidence output
        mock_output = np.array([[0.3, 0.4, 0.3]])
        self.mock_session_instance.run.return_value = [mock_output]

        dummy_img = np.zeros((320, 320, 3), dtype=np.uint8)
        # Use a high threshold
        label, confidence = self.classifier.predict(dummy_img, confidence_threshold=0.8)

        self.assertEqual(label, "unknown")
        self.assertAlmostEqual(confidence, 0.4)

    @patch("cv2.imread")
    def test_predict_file_path(self, mock_imread):
        # Mock cv2.imread to return a dummy image
        mock_imread.return_value = np.zeros((320, 320, 3), dtype=np.uint8)

        mock_output = np.array([[0.1, 0.1, 0.8]])
        self.mock_session_instance.run.return_value = [mock_output]

        label, confidence = self.classifier.predict("some_image.jpg")

        self.assertEqual(label, "quyt")
        self.assertAlmostEqual(confidence, 0.8)
        mock_imread.assert_called_once_with("some_image.jpg")


if __name__ == "__main__":
    unittest.main()
