import os
import shutil
import subprocess
import sys

# Constants
EXE_NAME = "DesktopWindowHelper"
ENTRY_POINT = "stealth_app.py"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")
BUILD_DIR = os.path.join(BASE_DIR, "build")

def clean_build():
    """Cleans up previous build directories."""
    print("Cleaning previous builds...")
    for folder in [DIST_DIR, BUILD_DIR]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f" Removed: {folder}")
            
    spec_file = os.path.join(BASE_DIR, f"{EXE_NAME}.spec")
    if os.path.exists(spec_file):
        os.remove(spec_file)
        print(f" Removed: {spec_file}")

def run_pyinstaller():
    """Runs PyInstaller to compile stealth_app.py into a single, console-less executable."""
    print(f"\nCompiling {ENTRY_POINT} into {EXE_NAME}.exe...")
    
    # Base command
    cmd = [
        "pyinstaller",
        "--onefile",
        "--noconsole",
        f"--name={EXE_NAME}",
        # Include solvers package explicitly to prevent dynamic import issues
        "--collect-submodules=solvers",
        # Specify entry point
        ENTRY_POINT
    ]
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=BASE_DIR)
    
    if result.returncode == 0:
        print("\nPyInstaller compilation completed successfully!")
    else:
        print("\n[ERROR] PyInstaller compilation failed!")
        sys.exit(result.returncode)

def setup_release():
    """Copies config.json and .env template to the distribution directory."""
    print("\nSetting up distribution release folder...")
    dist_exe_dir = os.path.join(DIST_DIR)
    
    # Copy config.json
    src_config = os.path.join(BASE_DIR, "config.json")
    dst_config = os.path.join(dist_exe_dir, "config.json")
    if os.path.exists(src_config):
        shutil.copy2(src_config, dst_config)
        print(f" Copied: config.json -> {dst_config}")
        
    # Copy .env (if it exists) or create a template
    src_env = os.path.join(BASE_DIR, ".env")
    dst_env = os.path.join(dist_exe_dir, ".env")
    if os.path.exists(src_env):
        shutil.copy2(src_env, dst_env)
        print(f" Copied: .env -> {dst_env}")
    else:
        with open(dst_env, "w") as f:
            f.write("# Gemini API Key Configuration\nGEMINI_API_KEY=\n")
        print(f" Created: .env template -> {dst_env}")

    print("\n-----------------------------------------------------")
    print(f"Success! Your stealth background assistant is ready.")
    print(f"Executable path: {os.path.join(dist_exe_dir, EXE_NAME + '.exe')}")
    print(f"Ensure your .env file in the 'dist' folder contains your GEMINI_API_KEY.")
    print("-----------------------------------------------------")
    print("\n[STEALTH EXTRA TIP - Code Obfuscation with Pyarmor]:")
    print("To prevent reverse engineering of your python bytecode, you can run:")
    print("  pip install pyarmor")
    print(f"  pyarmor pack -e \" --onefile --noconsole --name={EXE_NAME} --collect-submodules=solvers\" {ENTRY_POINT}")
    print("This will obfuscate the python files using pyarmor before compiling with PyInstaller.")

if __name__ == "__main__":
    clean_build()
    
    # Double-check if pyinstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("[ERROR] PyInstaller package is not installed. Run 'pip install pyinstaller'.")
        sys.exit(1)
        
    run_pyinstaller()
    setup_release()
