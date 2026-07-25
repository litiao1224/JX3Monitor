# -*- coding: utf-8 -*-
"""JX3 Monitor - Standalone Executable & ZIP Package Builder."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Navigate to project root
project_root = Path(os.getcwd()).resolve()

print(f"Python: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Working directory: {project_root}")

# Terminate any running instances of the app to avoid file lock
if sys.platform == "win32":
    try:
        subprocess.run(["taskkill", "/F", "/IM", "小鹦鹉记账.exe", "/T"], capture_output=True)
    except Exception:
        pass

# Ensure PyInstaller and runtime packages are installed
for pkg in ["customtkinter", "Pillow", "pyinstaller"]:
    try:
        res = subprocess.run([sys.executable, "-m", "pip", "show", pkg], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Installing {pkg}...")
            subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)
    except Exception as exc:
        print(f"Warning checking package {pkg}: {exc}")

# Build in local temp dir to prevent Google Drive file lock errors
temp_build_dir = Path(tempfile.gettempdir()) / "jx3_monitor_build"
temp_dist = temp_build_dir / "dist"
temp_work = temp_build_dir / "build"

if temp_build_dir.exists():
    try:
        shutil.rmtree(temp_build_dir, ignore_errors=True)
    except Exception:
        pass
temp_dist.mkdir(parents=True, exist_ok=True)
temp_work.mkdir(parents=True, exist_ok=True)

# Run PyInstaller specifying --distpath and --workpath
print("\n=== Starting PyInstaller build ===")
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--distpath", str(temp_dist),
    "--workpath", str(temp_work),
    "小鹦鹉记账.spec"
]
print(f"Command: {' '.join(cmd)}")
result = subprocess.run(cmd, capture_output=True, text=True)
if result.stdout:
    print(result.stdout[-1000:])
if result.stderr:
    print("STDERR:", result.stderr[-1000:])

temp_app_dir = temp_dist / "小鹦鹉记账"

if result.returncode == 0 and temp_app_dir.exists():
    print("\n=== PyInstaller build successful! ===")
    
    # Copy build result to local dist directory
    dist_dir = project_root / "dist"
    target_app_dir = dist_dir / "小鹦鹉记账"
    zip_output_path = dist_dir / "小鹦鹉记账.zip"
    
    dist_dir.mkdir(parents=True, exist_ok=True)
    
    if target_app_dir.exists():
        try:
            shutil.rmtree(target_app_dir, ignore_errors=True)
        except Exception as exc:
            print(f"Warning cleaning old target dir: {exc}")
            
    print(f"Copying build output to {target_app_dir}...")
    if sys.platform == "win32":
        subprocess.run(["robocopy", str(temp_app_dir), str(target_app_dir), "/MIR", "/NJH", "/NJS", "/NC", "/NS", "/NP"], capture_output=True)
    else:
        shutil.copytree(temp_app_dir, target_app_dir, dirs_exist_ok=True, ignore_dangling_symlinks=True)
    
    # Create ZIP archive for distribution
    print("\n=== Creating distribution ZIP archive ===")
    if zip_output_path.exists():
        try:
            zip_output_path.unlink()
        except Exception:
            pass
            
    archive_base = str(dist_dir / "小鹦鹉记账")
    zip_result = shutil.make_archive(archive_base, "zip", str(dist_dir), "小鹦鹉记账")
    zip_size_mb = os.path.getsize(zip_result) / (1024 * 1024)
    print(f"\n✅ 打包成功！")
    print(f"1. 独立运行路径: {target_app_dir / '小鹦鹉记账.exe'}")
    print(f"2. 免安装压缩包: {zip_result} ({zip_size_mb:.2f} MB)")
else:
    print(f"\n=== 打包失败 (Exit Code {result.returncode}) ===")
    sys.exit(1)
