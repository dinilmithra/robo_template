import os
import sys
import venv
import platform
import subprocess
from pathlib import Path


def main():
    # Prevent bytecode generation for this process
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

    print("=" * 63)
    print("Setting up Python Virtual Environment")
    print("=" * 63)

    # Check if Python is accessible
    print(f"Python version: {sys.version.split()[0]}")

    # Define paths
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    # Place .venv one level above the project root (i.e., in the parent of check_proxy_status)
    venv_dir = project_root / ".venv"
    requirements_file = project_root / "requirements.txt"

    print(f"Project root: {project_root}")

    # Change working directory to project root
    os.chdir(project_root)

    # Create virtual environment using venv API
    if not venv_dir.exists():
        print("Creating virtual environment using venv module API...")
        try:
            builder = venv.EnvBuilder(with_pip=True)
            builder.create(str(venv_dir))
            print("Virtual environment created successfully")
        except Exception as e:
            print(f"Error: Failed to create virtual environment: {e}")
            input("Press Enter to exit")
            sys.exit(1)
    else:
        print("Virtual environment already exists")

    # Determine the path to the virtual environment's Python executable
    if platform.system() == "Windows":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    if not venv_python.exists():
        print(f"Error: Could not find python executable at {venv_python}")
        input("Press Enter to exit")
        sys.exit(1)

    print(f"\nUsing virtual environment python: {venv_python}")

    # Upgrade pip
    print("\nUpgrading pip...")
    try:
        subprocess.check_call(
            [str(venv_python), "-m", "pip", "install", "--upgrade", "pip"]
        )
    except subprocess.CalledProcessError:
        print("Error: Failed to upgrade pip")
        input("Press Enter to exit")
        sys.exit(1)

    # Install requirements
    if requirements_file.exists():
        print("\nInstalling packages from requirements.txt...")
        try:
            subprocess.check_call(
                [str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"]
            )
        except subprocess.CalledProcessError:
            print("Error: Failed to install packages")
            input("Press Enter to exit")
            sys.exit(1)
    else:
        print(f"\nWarning: requirements.txt not found at {requirements_file}")

    print("\n" + "=" * 63)
    print("Setup Complete!")
    print("=" * 63 + "\n")
    input("Press Enter to exit")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        input("Press Enter to exit")
