import asyncio
import os
import sys
import unittest
from unittest.mock import patch

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "pi_edge"))

from conveyor_controller import ConveyorController


class TestConveyorControllerSensorLogic(unittest.IsolatedAsyncioTestCase):
    def make_controller(self, sensor_active_low=True):
        with patch("conveyor_controller.ServoSorter"):
            controller = ConveyorController(sensor_active_low=sensor_active_low)
        self.addCleanup(controller.shutdown)
        return controller

    async def test_active_low_default_treats_gpio_active_as_blocked(self):
        controller = self.make_controller()

        controller.sensor.is_active = True
        self.assertTrue(controller.has_object)
        self.assertTrue(await controller.wait_for_object(timeout=1.0))

        controller.sensor.is_active = False
        self.assertFalse(controller.has_object)
        self.assertTrue(await controller.wait_until_clear(timeout=1.0))

    async def test_active_high_inverts_gpiozero_active_state(self):
        controller = self.make_controller(sensor_active_low=False)

        controller.sensor.is_active = False
        self.assertTrue(controller.has_object)
        self.assertTrue(await controller.wait_for_object(timeout=1.0))

        controller.sensor.is_active = True
        self.assertFalse(controller.has_object)
        self.assertTrue(await controller.wait_until_clear(timeout=1.0))


if __name__ == "__main__":
    unittest.main()
