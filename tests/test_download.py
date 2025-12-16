"""
Test script to verify FFmpeg integration with yt-dlp
"""
import subprocess
import sys
import os
import tempfile
import shutil

def test_ffmpeg_location():
    """Test that ffmpeg can be found by yt-dlp"""
    print("=" * 60)
    print("Testing FFmpeg Integration")
    print("=" * 60)
    
    # Get current directory (where ffmpeg should be)
    app_dir = os.path.dirname(os.path.abspath(__file__))
    ffmpeg_path = os.path.join(app_dir, "ffmpeg.exe")
    ffprobe_path = os.path.join(app_dir, "ffprobe.exe")
    
    # Check files exist
    print(f"\n1. Checking FFmpeg files...")
    if os.path.exists(ffmpeg_path):
        print(f"   ✓ ffmpeg.exe found at: {ffmpeg_path}")
    else:
        print(f"   ✗ ffmpeg.exe NOT found at: {ffmpeg_path}")
        return False
        
    if os.path.exists(ffprobe_path):
        print(f"   ✓ ffprobe.exe found at: {ffprobe_path}")
    else:
        print(f"   ✗ ffprobe.exe NOT found at: {ffprobe_path}")
        return False
    
    # Test with a short public domain video
    print(f"\n2. Testing download with FFmpeg merge...")
    test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # "Me at the zoo" - first YouTube video (short)
    
    # Create temp directory for test
    temp_dir = tempfile.mkdtemp()
    
    try:
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--no-playlist",
            "--ffmpeg-location", app_dir,
            "-f", "bestvideo[height<=360]+bestaudio/best",  # Low quality for speed
            "--merge-output-format", "mp4",
            "-o", os.path.join(temp_dir, "test_video.%(ext)s"),
            test_url
        ]
        
        print(f"   Running command: {' '.join(cmd[:8])}...")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print(f"   ✓ Download successful!")
            print(f"   ✓ FFmpeg merge completed without errors")
            
            # Check if file was created
            files = os.listdir(temp_dir)
            if files:
                print(f"   ✓ Output file created: {files[0]}")
            
            return True
        else:
            print(f"   ✗ Download failed with code {result.returncode}")
            print(f"   Error output: {result.stderr[:500]}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"   ✗ Test timed out (network issue or slow download)")
        return False
    except Exception as e:
        print(f"   ✗ Test failed with exception: {e}")
        return False
    finally:
        # Cleanup
        try:
            shutil.rmtree(temp_dir)
            print(f"\n3. Cleanup completed")
        except:
            pass

if __name__ == "__main__":
    print("\nFFmpeg Integration Test")
    print("This will download a short test video to verify FFmpeg is working.\n")
    
    success = test_ffmpeg_location()
    
    print("\n" + "=" * 60)
    if success:
        print("✓ ALL TESTS PASSED - FFmpeg is properly configured!")
    else:
        print("✗ TESTS FAILED - Check the errors above")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
