from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
BUILD_OUTPUT = FRONTEND / "dist" / "clinica-turnos" / "browser"
PUBLIC = ROOT / "public"


def run_npm(*arguments: str) -> None:
    command_name = "npm.cmd" if os.name == "nt" else "npm"
    command = [command_name, *arguments]
    if os.name == "nt":
        subprocess.run(subprocess.list2cmdline(command), cwd=FRONTEND, check=True, shell=True)
    else:
        subprocess.run(command, cwd=FRONTEND, check=True)


def main() -> None:
    if not (FRONTEND / "package-lock.json").exists():
        raise SystemExit("No se encontró frontend/package-lock.json.")
    run_npm("ci")
    run_npm("run", "build")
    if not BUILD_OUTPUT.is_dir():
        raise SystemExit(f"No se encontró la salida Angular: {BUILD_OUTPUT}")
    if PUBLIC.resolve() != (ROOT / "public").resolve() or PUBLIC.parent.resolve() != ROOT:
        raise SystemExit("La ruta de salida pública no coincide con la carpeta del proyecto.")
    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    PUBLIC.mkdir(exist_ok=True)
    shutil.copytree(BUILD_OUTPUT, PUBLIC, dirs_exist_ok=True)
    print(f"Frontend copiado a {PUBLIC}")


if __name__ == "__main__":
    main()
