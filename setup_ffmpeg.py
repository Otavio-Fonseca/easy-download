import os
import sys
import shutil
import zipfile
import urllib.request
import subprocess

FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_EXE = "ffmpeg.exe"
FFPROBE_EXE = "ffprobe.exe"

def show_message(msg):
    import ctypes
    ctypes.windll.user32.MessageBoxW(0, msg, "Configuração Inicial", 0)

def log(msg):
    print(f"[Auto-Setup] {msg}")

def check_installed():
    """Check if ffmpeg is available in current dir or PATH."""
    if os.path.exists(FFMPEG_EXE) and os.path.exists(FFPROBE_EXE):
        return True
    
    # Check PATH
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False

def download_progress(count, block_size, total_size):
    percent = int(count * block_size * 100 / total_size)
    sys.stdout.write(f"\rDownloading FFmpeg... {percent}%")
    sys.stdout.flush()

def setup():
    if check_installed():
        log("FFmpeg found. Skipping download.")
        return

    log("FFmpeg not found. Starting auto-setup...")
    # Notify user since console is hidden
    import threading
    threading.Thread(target=show_message, args=("O FFmpeg está sendo configurado pela primeira vez.\nIsso pode levar alguns instantes. O programa abrirá em breve.",)).start()

    zip_name = "ffmpeg_temp.zip"
    
    try:
        # 1. Download
        log(f"Downloading from {FFMPEG_URL}")
        urllib.request.urlretrieve(FFMPEG_URL, zip_name, reporthook=download_progress)
        print() # Newline after progress
        log("Download complete.")

        # 2. Extract
        log("Extracting files...")
        with zipfile.ZipFile(zip_name, 'r') as zip_ref:
            # The zip usually contains a root folder like 'ffmpeg-x.x-essentials_build/'
            # We need to find where bin/ffmpeg.exe is.
            file_list = zip_ref.namelist()
            ffmpeg_src = next((f for f in file_list if f.endswith('bin/ffmpeg.exe')), None)
            ffprobe_src = next((f for f in file_list if f.endswith('bin/ffprobe.exe')), None)
            
            if not ffmpeg_src or not ffprobe_src:
                log("Error: Could not find executables in zip.")
                return

            # Extract specific files to current dir
            # ZipFile.extract extracts with full path, so we extract to temp then move.
            zip_ref.extract(ffmpeg_src)
            zip_ref.extract(ffprobe_src)
            
            # Move from moved path to root
            shutil.move(ffmpeg_src, FFMPEG_EXE)
            shutil.move(ffprobe_src, FFPROBE_EXE)
            
            log("Executables moved to root.")

        # 3. Cleanup
        log("Cleaning up temporary files...")
        os.remove(zip_name)
        # Remove the top-level folder created by extraction (e.g., 'ffmpeg-6.0...')
        top_folder = ffmpeg_src.split('/')[0]
        if os.path.exists(top_folder):
            shutil.rmtree(top_folder)

        log("FFmpeg setup successful!")

    except Exception as e:
        log(f"Error during setup: {e}")
        if os.path.exists(zip_name): os.remove(zip_name)

if __name__ == "__main__":
    setup()
