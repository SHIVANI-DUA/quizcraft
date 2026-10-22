"""Local launcher: python start.py (or double-click start.bat on Windows)."""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent


def run(*args, **kwargs):
    subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description="Set up and run Quizcraft locally.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        raise RuntimeError("Install Python 3.12 or newer, then run this launcher again.")
    if not 1 <= args.port <= 65535:
        raise RuntimeError("Choose a port between 1 and 65535.")
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", args.port)) == 0:
            raise RuntimeError(
                f"Port {args.port} is already in use. If Quizcraft is running, open "
                f"http://127.0.0.1:{args.port}/ . Otherwise run: python start.py --port {args.port + 1 if args.port < 65535 else 8000}"
            )
    environment = ROOT / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        print("Creating the app's Python environment...", flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
    # Verify pinned dependencies without requiring third-party imports in this launcher.
    requirements = [line for line in (ROOT / "requirements-lock.txt").read_text().splitlines()
                    if line.strip() and not line.startswith("#")]
    check_code = (
        "from importlib.metadata import version; "
        f"requirements={requirements!r}; "
        "assert all(version(item.split('==')[0]) == item.split('==')[1] for item in requirements)"
    )
    installed = subprocess.run([str(python), "-c", check_code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if installed.returncode:
        print("Installing Django and Django REST Framework (internet required the first time)...", flush=True)
        run(python, "-m", "pip", "install", "-r", "requirements-lock.txt")
    run(python, "manage.py", "migrate", "--noinput")
    run(python, "manage.py", "seed_demo")
    print(f"\nQuizcraft is ready: http://127.0.0.1:{args.port}/", flush=True)
    print("Keep this window open. Press Ctrl+C to stop the server.\n", flush=True)
    run(python, "manage.py", "runserver", f"127.0.0.1:{args.port}", "--noreload")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nQuizcraft stopped.")
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f"\nCould not start Quizcraft: {error}", file=sys.stderr)
        sys.exit(1)
