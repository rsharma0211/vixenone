#!/usr/bin/env python3
import subprocess
import sys


def main():
    print("Triggering demo seed via Firebase Admin SDK inside API container...")
    check_running = subprocess.run(
        ["docker", "compose", "ps", "--services", "--filter", "status=running"],
        capture_output=True,
        text=True,
    )
    if "api" in check_running.stdout.split():
        cmd = ["docker", "compose", "exec", "-T", "api", "python", "-m", "app.cli.seed"]
    else:
        cmd = ["docker", "compose", "run", "--rm", "-T", "api", "python", "-m", "app.cli.seed"]

    res = subprocess.run(cmd)
    sys.exit(res.returncode)


if __name__ == "__main__":
    main()
