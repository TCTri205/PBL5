import unittest
import sys
import os

# runner.py
if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover('tests', pattern='test_*.py')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        with open('test_errors.txt', 'w', encoding='utf-8') as f:
            for failure in result.failures:
                f.write(f"FAILURE: {failure[0]}\n{failure[1]}\n\n")
            for error in result.errors:
                f.write(f"ERROR: {error[0]}\n{error[1]}\n\n")
