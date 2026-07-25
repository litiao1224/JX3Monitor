# -*- coding: utf-8 -*-
"""JX3 Monitor - Standalone Executable & ZIP Package Builder."""
import os
import shutil
import subprocess
import sys

# Navigate to project root
project_root = os.path.dirname(os.path.abspath(__file__))
os.chdir(project_root)

print(f"Python: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")

# Ensure PyInstaller and runtime packages are installed
for pkg in ["customtkinter", "Pillow", "pyinstaller"]:
    try:
        res = subprocess.run([sys.executable, "-m", "pip", "show", pkg], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Installing {pkg}...")
            subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)
    except Exception as exc:
        print(f"Warning checking package {pkg}: {exc}")

# Clean old dist/build artifacts
dist_dir = os.path.join(project_root, "dist")
build_dir = os.path.join(project_root, "build")
app_dist_dir = os.path.join(dist_dir, "小鹦鹉记账")
zip_output_path = os.path.join(dist_dir, "小鹦鹉记账.zip")

print("\n=== Cleaning old build artifacts ===")
if os.path.exists(build_dir):
    shutil.rmtree(build_dir, ignore_errors=True)
if os.path.exists(app_dist_dir):
    shutil.rmtree(app_dist_dir, ignore_errors=True)
if os.path.exists(zip_output_path):
    try:
        os.remove(zip_output_path)
    except Exception:
        pass

# Run PyInstaller with spec file
print("\n=== Starting PyInstaller build ===")
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--clean",
    "--noconfirm",
    "小鹦鹉记账.spec"
]
print(f"Command: {' '.join(cmd)}")
result = subprocess.run(cmd, capture_output=True, text=True)
if result.stdout:
    print(result.stdout[-1000:])
if result.stderr:
    print("STDERR:", result.stderr[-1000:])

if result.returncode == 0 and os.path.exists(app_dist_dir):
    print("\n=== Build successful! ===")
    print(f"Executable directory: {app_dist_dir}")
    print(f"Main EXE: {os.path.join(app_dist_dir, '小鹦鹉记账.exe')}")
    
    # Create ZIP archive for distribution
    print("\n=== Creating distribution ZIP archive ===")
    archive_base = os.path.join(dist_dir, "小鹦鹉记账")
    zip_result = shutil.make_archive(archive_base, "zip", dist_dir, "小鹦鹉记账")
    zip_size_mb = os.path.getsize(zip_result) / (1024 * 1024)
    print(f"ZIP package created: {zip_result} ({zip_size_mb:.2f} MB)")
else:
    print(f"\n=== Build FAILED (exit code {result.returncode}) ===")
    sys.exit(1)
