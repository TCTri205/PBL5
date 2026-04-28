import sys
import os
import subprocess


def main():
    repo_root = os.path.dirname(os.path.abspath(__file__))
    pi_edge_path = os.path.join(repo_root, "pi_edge", "cam_stream.py")

    # Forward all arguments to cam_stream.py
    cmd = [sys.executable, pi_edge_path] + sys.argv[1:]

    print("🚀 Starting Raspberry Pi Streamer...")
    print(f"Running: {' '.join(cmd)}")

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
