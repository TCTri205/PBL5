import sys
import os
import subprocess


def main():
    repo_root = os.path.dirname(os.path.abspath(__file__))
    server_path = os.path.join(repo_root, "laptop_server", "server.py")

    # Forward all arguments to server.py
    cmd = [sys.executable, server_path] + sys.argv[1:]

    print("🚀 Starting Laptop Server...")
    print(f"Running: {' '.join(cmd)}")

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
