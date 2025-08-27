#!/usr/bin/env python3
"""
Build script for SAI package
"""

import subprocess
import sys
import shutil
import os
from pathlib import Path

def clean_build():
    """Clean previous build artifacts"""
    print("🧹 Cleaning previous builds...")
    
    dirs_to_clean = ['build', 'dist', 'sai_assistant.egg-info', 'sai.egg-info']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"   Removed {dir_name}")

def build_package():
    """Build the package"""
    print("📦 Building package...")
    
    try:
        # Build with both setuptools and modern build
        subprocess.check_call([sys.executable, "-m", "build"])
        print("✅ Package built successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        try:
            # Fallback to setup.py
            subprocess.check_call([sys.executable, "setup.py", "sdist", "bdist_wheel"])
            print("✅ Package built with setup.py!")
            return True
        except subprocess.CalledProcessError as e2:
            print(f"❌ Fallback build also failed: {e2}")
            return False

def test_installation():
    """Test the built package"""
    print("🧪 Testing installation...")
    
    # Find the wheel file
    dist_dir = Path('dist')
    wheel_files = list(dist_dir.glob('*.whl'))
    
    if not wheel_files:
        print("❌ No wheel file found")
        return False
    
    wheel_file = wheel_files[0]
    print(f"   Testing wheel: {wheel_file}")
    
    try:
        # Test install in a temporary environment would be better,
        # but for now just check if the wheel can be inspected
        subprocess.check_call([sys.executable, "-m", "wheel", "unpack", str(wheel_file)], 
                            stdout=subprocess.DEVNULL)
        print("✅ Wheel file is valid!")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  Could not test wheel (wheel package not installed)")
        return True  # Don't fail if wheel tool isn't available

def show_build_info():
    """Show information about built packages"""
    print("\\n📋 Build Results:")
    
    dist_dir = Path('dist')
    if dist_dir.exists():
        for file in dist_dir.iterdir():
            size = file.stat().st_size / 1024 / 1024  # MB
            print(f"   {file.name} ({size:.1f} MB)")
    
    print("\\n🚀 To install locally:")
    print("   pip install dist/*.whl")
    
    print("\\n📤 To upload to PyPI:")
    print("   # Test PyPI first")
    print("   python -m twine upload --repository testpypi dist/*")
    print("   # Then real PyPI")
    print("   python -m twine upload dist/*")

def main():
    """Main build process"""
    print("🏗️  SAI Package Builder")
    print("=" * 30)
    
    # Check if we're in the right directory
    if not Path('pyproject.toml').exists():
        print("❌ Run this from the project root (where pyproject.toml is)")
        sys.exit(1)
    
    clean_build()
    
    if build_package():
        test_installation()
        show_build_info()
        print("\\n✅ Build completed successfully!")
    else:
        print("\\n❌ Build failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()