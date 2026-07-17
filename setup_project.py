"""
Falcon
Module: setup_project.py
Version: 1.1.0

Initializes the Falcon project structure.

Safe to run multiple times.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

FOLDERS = [
    "candidate_generation",
    "analysis",
    "technical",
    "market",
    "pattern",
    "execution",
    "dashboard",
    "common",
    "strategies",
    "strategies/Leadership",
    "strategies/Emerging",
    "strategies/Reversal",
    "data",
    "logs",
    "reports",
    "cache",
    "tests",
]

FILES = {
    "README.md": "# Falcon\n",
    "CHANGELOG.md": "# Changelog\n",
    "ROADMAP.md": "# Roadmap\n",
    "PROJECT_CHARTER.md": "# Project Charter\n",
    "strategies/Leadership/screen.query": "",
    "strategies/Emerging/screen.query": "",
    "strategies/Reversal/screen.query": "",
}


def create_folder(folder: str):
    path = PROJECT_ROOT / folder
    existed = path.exists()
    path.mkdir(parents=True, exist_ok=True)

    gitkeep = path / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()

    print(f"[{'EXISTS' if existed else 'CREATE'}] {folder}")


def create_file(file_path: str, content: str):
    path = PROJECT_ROOT / file_path
    if path.exists():
        print(f"[EXISTS] {file_path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"[CREATE] {file_path}")


def main():
    print("=" * 50)
    print("Falcon Project Setup")
    print("=" * 50)

    for folder in FOLDERS:
        create_folder(folder)

    for file_path, content in FILES.items():
        create_file(file_path, content)

    print("=" * 50)
    print("Falcon project initialized successfully.")
    print("=" * 50)


if __name__ == "__main__":
    main()
