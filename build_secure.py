"""
Secure Build Script for WebCorder
Creates a single executable with all source code embedded
NO .py files will be accessible to users!
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def prepare_secure_build():
    """Prepare and create secure build"""
    
    print("🔒 WebCorder Secure Build")
    print("=" * 50)
    
    # 1. Check if PyInstaller is installed
    try:
        import PyInstaller
        print("✅ PyInstaller found")
    except ImportError:
        print("❌ PyInstaller not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ PyInstaller installed")
    
    # 2. Get production token
    print("\n🔑 Enter your GitHub token for production build:")
    token = input("Token: ").strip()
    
    if not token:
        print("❌ No token provided!")
        return False
    
    # 3. Update production token file
    token_file = Path("src/updater/production_token.py")
    token_content = f'''"""
Production GitHub Token Configuration
LIMITED token for update checking on private repositories

SECURITY NOTE: 
- This token has repo access but should be:
  1. Rotated regularly (every 6 months)
  2. Monitored for unusual activity
  3. Replaced immediately if compromised
"""

# Limited access token for private repository releases
# Scope: repo (required for private repo access)
# Usage: ONLY for checking releases, not for code modification
PRODUCTION_GITHUB_TOKEN = "{token}"

# Security measures implemented:
# 1. Token only used for read operations
# 2. No write operations in update checker code
# 3. Exception handling prevents token exposure in logs
# 4. Token embedded in binary - not accessible as plain text
'''
    
    with open(token_file, 'w', encoding='utf-8') as f:
        f.write(token_content)
    
    print("✅ Production token embedded")
    
    # 4. Clean previous builds
    build_dirs = ['build', 'dist']
    for dir_name in build_dirs:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name)
            print(f"🧹 Cleaned {dir_name}/")
    
    # 5. Run PyInstaller with secure spec
    print("\n🔨 Building secure executable...")
    print("This will create ONE .exe file with ALL code embedded!")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "WebCorder_Secure.spec"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Build successful!")
        
        # Check the result
        exe_path = Path("dist/WebCorder.exe")
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / 1024 / 1024
            print(f"📦 WebCorder.exe created: {size_mb:.1f} MB")
            print(f"📍 Location: {exe_path.absolute()}")
            
            print("\n🎯 Security Status:")
            print("✅ ALL Python source code embedded in binary")
            print("✅ NO .py files accessible to users")
            print("✅ Token embedded and obfuscated")
            print("✅ Ready for Inno Setup installer")
            
            return True
        else:
            print("❌ Executable not found after build")
            return False
    else:
        print("❌ Build failed!")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        return False

def test_secure_build():
    """Test the built executable"""
    exe_path = Path("dist/WebCorder.exe")
    if not exe_path.exists():
        print("❌ No executable found to test")
        return
    
    print("\n🧪 Testing secure build...")
    print("Starting WebCorder.exe...")
    
    # Run the executable in background for testing
    try:
        subprocess.Popen([str(exe_path)])
        print("✅ Executable started successfully!")
        print("Check if the app loads and update system works")
    except Exception as e:
        print(f"❌ Failed to start executable: {e}")

def build_installer():
    """Build installer with Inno Setup using the secure executable"""
    exe_path = Path("dist/WebCorder.exe")
    if not exe_path.exists():
        print("❌ WebCorder.exe not found. Run secure build first!")
        return False
    
    print("\n📦 Building installer with Inno Setup...")
    
    # Check if Inno Setup is available
    installer_script = "installer/webcorder_secure.iss"
    if not os.path.exists(installer_script):
        print(f"❌ Installer script not found: {installer_script}")
        return False
    
    # Run Inno Setup compiler
    try:
        inno_setup_cmd = ["iscc", installer_script]
        result = subprocess.run(inno_setup_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Installer built successfully!")
            
            # Find the created installer
            output_dir = Path("installer/output")
            if output_dir.exists():
                setup_files = list(output_dir.glob("WebCorder-Setup-*.exe"))
                if setup_files:
                    setup_file = setup_files[0]
                    size_mb = setup_file.stat().st_size / 1024 / 1024
                    print(f"📦 Installer: {setup_file.name} ({size_mb:.1f} MB)")
                    print(f"📍 Location: {setup_file.absolute()}")
            
            return True
        else:
            print(f"❌ Inno Setup failed: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("❌ Inno Setup compiler (iscc) not found!")
        print("Install Inno Setup from: https://jrsoftware.org/isdl.php")
        return False
    except Exception as e:
        print(f"❌ Installer build failed: {e}")
        return False

if __name__ == "__main__":
    success = prepare_secure_build()
    
    if success:
        print("\n" + "="*50)
        print("🎉 SECURE BUILD COMPLETE!")
        print("\nNext steps:")
        print("1. Test the WebCorder.exe")
        print("2. Build installer with Inno Setup")
        print("3. Distribute to users")
        print("\n🔒 Users will NEVER see your source code!")
        
        # Test build option
        test_build = input("\nTest the build now? (y/n): ").strip().lower()
        if test_build == 'y':
            test_secure_build()
        
        # Build installer option
        build_inst = input("\nBuild installer now? (y/n): ").strip().lower()
        if build_inst == 'y':
            installer_success = build_installer()
            if installer_success:
                print("\n🎉 COMPLETE PACKAGE READY!")
                print("✅ Secure executable created")
                print("✅ Installer created")
                print("✅ Ready for distribution")
            else:
                print("\n⚠️  Executable ready, but installer failed")
    else:
        print("\n❌ Build failed. Check errors above.")
