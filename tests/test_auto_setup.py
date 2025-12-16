"""
Test script to simulate fresh install scenario
This temporarily renames FFmpeg files to test auto-setup
"""
import os
import sys
import shutil

def test_auto_setup():
    print("=" * 60)
    print("Testing Auto-Setup on Fresh Install")
    print("=" * 60)
    
    app_dir = os.path.dirname(os.path.abspath(__file__))
    ffmpeg_path = os.path.join(app_dir, "ffmpeg.exe")
    ffprobe_path = os.path.join(app_dir, "ffprobe.exe")
    
    # Backup existing files
    backup_suffix = ".backup_test"
    ffmpeg_backup = ffmpeg_path + backup_suffix
    ffprobe_backup = ffprobe_path + backup_suffix
    
    try:
        print("\n1. Backing up existing FFmpeg files...")
        if os.path.exists(ffmpeg_path):
            shutil.move(ffmpeg_path, ffmpeg_backup)
            print(f"   ✓ Backed up ffmpeg.exe")
        
        if os.path.exists(ffprobe_path):
            shutil.move(ffprobe_path, ffprobe_backup)
            print(f"   ✓ Backed up ffprobe.exe")
        
        print("\n2. Testing auto-setup (simulating fresh install)...")
        print("   Importing setup_ffmpeg...")
        
        import setup_ffmpeg
        setup_ffmpeg.setup()
        
        print("\n3. Verifying files were created...")
        if os.path.exists(ffmpeg_path):
            print(f"   ✓ ffmpeg.exe created successfully")
        else:
            print(f"   ✗ ffmpeg.exe NOT found")
            return False
            
        if os.path.exists(ffprobe_path):
            print(f"   ✓ ffprobe.exe created successfully")
        else:
            print(f"   ✗ ffprobe.exe NOT found")
            return False
        
        print("\n4. Cleaning up test files...")
        # Remove the downloaded files
        if os.path.exists(ffmpeg_path):
            os.remove(ffmpeg_path)
        if os.path.exists(ffprobe_path):
            os.remove(ffprobe_path)
        
        return True
        
    finally:
        print("\n5. Restoring original files...")
        # Restore backups
        if os.path.exists(ffmpeg_backup):
            if os.path.exists(ffmpeg_path):
                os.remove(ffmpeg_path)
            shutil.move(ffmpeg_backup, ffmpeg_path)
            print(f"   ✓ Restored ffmpeg.exe")
        
        if os.path.exists(ffprobe_backup):
            if os.path.exists(ffprobe_path):
                os.remove(ffprobe_path)
            shutil.move(ffprobe_backup, ffprobe_path)
            print(f"   ✓ Restored ffprobe.exe")

if __name__ == "__main__":
    print("\nAuto-Setup Integration Test")
    print("This simulates a fresh install by temporarily removing FFmpeg.\n")
    
    success = test_auto_setup()
    
    print("\n" + "=" * 60)
    if success:
        print("✓ AUTO-SETUP TEST PASSED")
        print("The application will auto-configure FFmpeg on first run!")
    else:
        print("✗ AUTO-SETUP TEST FAILED")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
