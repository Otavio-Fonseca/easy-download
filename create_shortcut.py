import os
import sys
import subprocess

def get_desktop_path():
    user_profile = os.environ['USERPROFILE']
    possible_paths = [
        os.path.join(user_profile, 'Desktop'),
        os.path.join(user_profile, 'OneDrive', 'Desktop')
    ]
    for p in possible_paths:
        if os.path.isdir(p):
            return p
    return possible_paths[0] # Fallback

def create_shortcut_at(path):
    desktop = path
    target = os.path.abspath("iniciar.bat")
    working_dir = os.path.dirname(target)
    icon = os.path.abspath("assets/icon.png")
    shortcut_path = os.path.join(desktop, "Video Downloader.lnk")
    
    vbs_script = f"""
    Set oWS = WScript.CreateObject("WScript.Shell")
    sLinkFile = "{shortcut_path}"
    Set oLink = oWS.CreateShortcut(sLinkFile)
    oLink.TargetPath = "{target}"
    oLink.WorkingDirectory = "{working_dir}"
    oLink.IconLocation = "{icon}"
    oLink.Save
    """
    
    vbs_file = "temp_shortcut.vbs"
    with open(vbs_file, "w") as f:
        f.write(vbs_script)
        
    try:
        subprocess.run(["cscript", "//Nologo", vbs_file], check=True)
        print(f"Shortcut created successfully at: {shortcut_path}")
        return True
    except subprocess.CalledProcessError:
        print(f"Failed to create at {shortcut_path}")
        return False
    finally:
        if os.path.exists(vbs_file):
            os.remove(vbs_file)

def main():
    user_profile = os.environ['USERPROFILE']
    possible_paths = [
        os.path.join(user_profile, 'Desktop'),
        os.path.join(user_profile, 'OneDrive', 'Desktop')
    ]
    
    for p in possible_paths:
        if os.path.isdir(p):
            print(f"Trying {p}...")
            if create_shortcut_at(p):
                return

if __name__ == "__main__":
    main()
