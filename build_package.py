import subprocess
import sys
import os

# Navigate to project root
project_root = os.path.dirname(os.path.abspath(__file__))
os.chdir(project_root)

print(f"Python: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")

# Check if pyinstaller is installed
try:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "show", "pyinstaller"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("pyinstaller not found, installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller>=6.0"], check=True)
except Exception as e:
    print(f"Error checking pyinstaller: {e}")

# Run PyInstaller with the spec file
print("\n=== Starting PyInstaller build ===")
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--clean",
    "--noconfirm",
    "小鹦鹉记账.spec"
]
print(f"Command: {' '.join(cmd)}")
result = subprocess.run(cmd, capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

if result.returncode == 0:
    print("\n=== Build successful! ===")
    # Check output
    dist_dir = os.path.join(project_root, "dist", "小鹦鹉记账")
    if os.path.exists(dist_dir):
        print(f"\nOutput directory: {dist_dir}")
        for root, dirs, files in os.walk(dist_dir):
            level = root.replace(dist_dir, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f'{indent}{os.path.basename(root)}/')
            subindent = ' ' * 2 * (level + 1)
            for file in files[:20]:  # Show first 20 files
                filepath = os.path.join(root, file)
                size_mb = os.path.getsize(filepath) / (1024 * 1024)
                print(f'{subindent}{file} ({size_mb:.2f} MB)')
            if len(files) > 20:
                print(f'{subindent}... and {len(files) - 20} more files')
    else:
        print("WARNING: Expected output directory not found!")
else:
    print(f"\n=== Build FAILED (exit code {result.returncode}) ===")
