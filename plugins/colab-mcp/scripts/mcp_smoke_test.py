import json
import os
import subprocess
import sys
import time
from pathlib import Path


def main():
    plugin_root = Path(__file__).resolve().parents[1]
    start_script = plugin_root / "scripts" / "start-colab-mcp.ps1"

    env = os.environ.copy()
    env.setdefault("UV_CACHE_DIR", r"C:\Users\james\OneDrive\Documents\Playground\.uv-cache")
    env.setdefault("UV_PYTHON", "python")

    # 1) Basic command resolution test.
    help_run = subprocess.run(
        [
            "pwsh",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(start_script),
            "--help",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=90,
    )
    if help_run.returncode != 0:
        raise RuntimeError(
            "Launcher help test failed: "
            + (help_run.stderr.strip() or help_run.stdout.strip() or "unknown error")
        )

    if "ColabMCP is an MCP server" not in help_run.stdout:
        raise RuntimeError("Unexpected --help output: did not detect ColabMCP banner text.")

    # 2) Live boot test: start server briefly and verify process stays alive.
    proc = subprocess.Popen(
        [
            "pwsh",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(start_script),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )

    try:
        time.sleep(5)
        if proc.poll() is not None:
            raise RuntimeError(f"Server exited early with code {proc.returncode}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    output = {
        "status": "ok",
        "help_test": "passed",
        "boot_test": "passed",
        "note": (
            "Server startup is healthy. Actual Colab command execution requires a client session "
            "with an active Colab tab and dynamic tool refresh."
        ),
    }
    print(json.dumps(output))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        sys.exit(1)
