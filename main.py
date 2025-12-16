import flet as ft
import subprocess
import json
import os
import threading
import time
import sys
import logging
import traceback
import asyncio

# --- Auto-Setup FFmpeg (First Run) ---
# This ensures FFmpeg is available before the app starts
try:
    import setup_ffmpeg
    setup_ffmpeg.setup()
except Exception as e:
    print(f"Warning: FFmpeg auto-setup failed: {e}")
    print("The application may not work correctly without FFmpeg.")


# --- Logging Setup ---
logging.basicConfig(
    filename='app_log.txt',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
console_handler = logging.StreamHandler()
console_handler.setLevel=logging.DEBUG
logging.getLogger().addHandler(console_handler)

def log(msg):
    print(msg)
    logging.info(msg)

def log_error(msg):
    print(f"ERROR: {msg}")
    logging.error(msg)

# --- Constants & Theme ---
BORDER_RADIUS = 12
BUTTON_HEIGHT = 48
INPUT_HEIGHT = 48
PRIMARY_COLOR = ft.Colors.INDIGO
BG_COLOR = ft.Colors.GREY_50
SURFACE_COLOR = ft.Colors.WHITE

# --- Backend Logic (Subprocess) ---

class YtDlpService:
    def __init__(self):
        self._current_process = None
        self._cancel_flag = False

    def cancel(self):
        self._cancel_flag = True
        if self._current_process:
            try:
                log("Attempting to kill process...")
                self._current_process.terminate()
                # Force kill if needed
                # self._current_process.kill() 
                log("Process termination signal sent.")
            except Exception as e:
                log_error(f"Error killing process: {e}")

    def get_info(self, url):
        """Fetches metadata using subprocess. Supports single videos and playlists."""
        log(f"Fetching info for: {url}")
        
        # Build command: python -m yt_dlp -J --flat-playlist --socket-timeout 15 [url]
        # --flat-playlist: Get playlist metadata without full video info (faster)
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "-J",
            "--flat-playlist",
            "--socket-timeout", "30",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "--source-address", "0.0.0.0", # Force IPv4
            url
        ]

        try:
            # Use Popen/communicate to capture output safely
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            stdout, stderr = process.communicate(timeout=90) # Hard timeout for the process
            
            if process.returncode != 0:
                log_error(f"yt-dlp failed with code {process.returncode}")
                # Common error: not a valid URL or private video
                log_error(f"Stderr: {stderr}")
                return None
            
            info = json.loads(stdout)
            
            # Basic validation
            if 'title' not in info and 'id' not in info and '_type' not in info:
                 log(f"Warning: Unexpected info format: {info.keys()}")

            log(f"Info extracted: {info.get('title', 'Unknown')} | Type: {info.get('_type', 'video')}")
            return info

        except subprocess.TimeoutExpired:
            log_error("Timeout expired while fetching info.")
            process.kill()
            return None
        except Exception as e:
            log_error(f"Exception in get_info: {e}")
            log_error(traceback.format_exc())
            return None

    def download(self, url, output_path, quality, codec, is_audio, progress_hook):
        """Downloads using subprocess and parses progress."""
        self._cancel_flag = False
        log(f"Starting download: {url} -> {output_path}")

        # Construct Output Template
        out_tmpl = os.path.join(output_path, '%(title)s.%(ext)s')

        # Base Command
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--no-playlist",
            "--socket-timeout", "15",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "--source-address", "0.0.0.0",
            "--restrict-filenames",
            "--newline", # Important for progress parsing
            "--progress",
            "--ffmpeg-location", os.path.dirname(os.path.abspath(__file__)), # Force local ffmpeg
            "-o", out_tmpl,
            url
        ]

        # Format/Quality Setup
        if is_audio:
            cmd.extend(["-f", "bestaudio/best"])
            cmd.extend(["--extract-audio", "--audio-format", codec])
            
            # Simple fallback: let yt-dlp handle it.
            if quality == 'low': cmd.extend(["--audio-quality", "128K"])
            elif quality == 'high': cmd.extend(["--audio-quality", "320K"]) 
            
        else:
            # Video
            if quality == 'high':
                cmd.extend(["-f", f"bestvideo+bestaudio/best"])
            elif quality == 'medium':
                cmd.extend(["-f", f"bestvideo[height<=720]+bestaudio/best"])
            elif quality == 'low':
                cmd.extend(["-f", f"bestvideo[height<=480]+bestaudio/best"])
            
            cmd.extend(["--merge-output-format", codec])

        current_file = None # Track file for cleanup
        tracked_files = set() # Track all potential temp files

        try:
            self._current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                bufsize=1,            # Line buffered
                universal_newlines=True
            )

            # Read stdout line by line
            for line in self._current_process.stdout:
                line = line.strip()
                if not line: continue

                # Check cancel
                if self._cancel_flag:
                    self._current_process.terminate()
                    # Wait briefly for termination
                    try:
                         self._current_process.wait(timeout=2)
                    except: 
                         self._current_process.kill()
                    return False, "Cancelado pelo usuário"
                
                # Capture destination filenames (including intermediates for merges)
                # [download] Destination: D:\...\file.f137.mp4
                if line.startswith('[download] Destination:'):
                    f = line.replace('[download] Destination:', '').strip()
                    tracked_files.add(f)
                    log(f"Tracking temp file: {f}")
                
                # [download] file.mp4 has already been downloaded
                elif line.startswith('[download]') and 'has already been downloaded' in line:
                    parts = line.split()
                    if len(parts) > 1:
                        f = parts[1]
                        tracked_files.add(f)

                # [Merger] Merging formats into "D:\...\file.mp4"
                elif line.startswith('[Merger] Merging formats into'):
                    # output is usually: [Merger] Merging formats into "filename"
                    # We need to extract the filename from quotes
                    try:
                        f = line.split('"')[1]
                        tracked_files.add(f)
                        log(f"Tracking merge target: {f}")
                    except:
                        pass

                # Simple progress parsing
                # [download]  23.5% of ...
                if line.startswith('[download]'):
                    parts = line.split()
                    data = {'status': 'downloading'}
                    for i, part in enumerate(parts):
                        if '%' in part:
                            data['_percent_str'] = part
                        if 'of' in parts and i < len(parts)-1 and parts[i] == 'of':
                             data['_total_bytes_str'] = parts[i+1]
                        if '/s' in part:
                             data['_speed_str'] = part
                        if 'ETA' in parts and i < len(parts)-1 and parts[i] == 'ETA':
                             data['_eta_str'] = parts[i+1]
                    progress_hook(data)
                
                # Check for post-processing
                if '[ExtractAudio]' in line or '[Merger]' in line:
                     progress_hook({'status': 'processing'})

            self._current_process.wait()
            
            if self._current_process.returncode == 0:
                log("Download finished successfully.")
                return True, "Download Completo"
            else:
                stderr_out = self._current_process.stderr.read()
                log_error(f"Download failed: {stderr_out}")
                return False, "Erro no download (Ver log)"

        except Exception as e:
            log_error(f"Exception during download: {e}")
            return False, str(e)
        finally:
            self._current_process = None
            # Cleanup on cancel
            if self._cancel_flag:
                 log(f"Cleanup initiated. Files to check: {tracked_files}")
                 for fpath in tracked_files:
                     try:
                         # 1. Check exact path
                         if os.path.exists(fpath):
                             os.remove(fpath)
                             log(f"Deleted: {fpath}")
                         # 2. Check .part
                         if os.path.exists(fpath + ".part"):
                             os.remove(fpath + ".part")
                             log(f"Deleted: {fpath}.part")
                         # 3. Check .ytdl (sometimes used)
                         if os.path.exists(fpath + ".ytdl"):
                             os.remove(fpath + ".ytdl")
                             log(f"Deleted: {fpath}.ytdl")
                     except Exception as ex:
                         log_error(f"Failed to cleanup {fpath}: {ex}")


# --- UI (Flet) ---

def main(page: ft.Page):
    log("Application started.")
    
    # Theme & Setup
    page.title = "Modern Video Downloader"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 900
    page.window_height = 850
    page.padding = 40
    page.bgcolor = BG_COLOR
    page.scroll = ft.ScrollMode.AUTO 
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER 
    
    # Icon Setup
    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    if os.path.exists(icon_path):
        page.window_icon = icon_path

    page.theme = ft.Theme(
        color_scheme_seed=PRIMARY_COLOR,
        visual_density=ft.VisualDensity.COMFORTABLE,
    )
    
    service = YtDlpService()
    
    # --- Components Helpers ---
    
    def create_dropdown(ref, label, options, default_val):
        return ft.Dropdown(
            ref=ref,
            label=label,
            options=options,
            value=default_val,
            border_radius=BORDER_RADIUS,
            # height=INPUT_HEIGHT, # Removed invalid prop
            filled=True,
            bgcolor=SURFACE_COLOR,
            content_padding=15,
            text_size=14,
        )

    # --- Header ---

    header = ft.Column([
        ft.Text("Media Downloader", size=32, weight=ft.FontWeight.W_800, color=PRIMARY_COLOR),
        ft.Text("Baixe áudio e vídeo com alta qualidade", size=14, color=ft.Colors.GREY_700),
    ], spacing=5, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    
    # --- Input Section ---
    
    url_tf = ft.TextField(
        label="URL da Mídia",
        hint_text="Cole o link do YouTube aqui...",
        expand=True,
        text_size=15,
        border_radius=BORDER_RADIUS,
        bgcolor=SURFACE_COLOR,
        border_color=ft.Colors.TRANSPARENT,
        focused_border_color=PRIMARY_COLOR,
        content_padding=15,
        height=BUTTON_HEIGHT,
        prefix_icon=ft.Icons.LINK,
    )

    async def paste_action(e):
        clip_text = await page.get_clipboard_async()
        if clip_text:
            url_tf.value = clip_text
            url_tf.update()

    paste_btn = ft.ElevatedButton(
        "Colar",
        icon=ft.Icons.PASTE_ROUNDED,
        icon_color=ft.Colors.WHITE,
        color=ft.Colors.WHITE,
        bgcolor=PRIMARY_COLOR,
        height=BUTTON_HEIGHT,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS),
            padding=20,
        ),
        on_click=paste_action
    )

    input_row = ft.Container(
        content=ft.Row([url_tf, paste_btn], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START),
        padding=ft.padding.symmetric(vertical=20)
    )

    analyze_btn = ft.ElevatedButton(
        "ANALISAR MÍDIA", 
        color=ft.Colors.WHITE, 
        bgcolor=PRIMARY_COLOR, 
        height=50, 
        width=200,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS),
            elevation=5
        ),
        elevation=4
    )

    # --- Content Container ---
    content_container = ft.Column(spacing=25, expand=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER) 

    async def analyze_action(e):
        url = url_tf.value
        if not url:
            page.show_snack_bar(ft.SnackBar(ft.Text("Por favor, insira uma URL.")))
            return

        # Show Loading
        content_container.controls.clear()
        loading = ft.Column([
            ft.ProgressRing(color=PRIMARY_COLOR, stroke_width=3),
            ft.Text("Buscando informações...", color=ft.Colors.GREY_700, weight=ft.FontWeight.W_500)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15)
        
        content_container.controls.append(ft.Container(content=loading, alignment=ft.alignment.center, padding=50))
        page.update()

        # Run fetch in executor to avoid blocking and allow clean async wait
        loop = asyncio.get_running_loop()
        try:
            # Use wait_for to enforce UI side timeout as well
            info = await asyncio.wait_for(
                loop.run_in_executor(None, service.get_info, url),
                timeout=100.0
            )
        except asyncio.TimeoutError:
             log_error("UI Timeout on analysis.")
             info = None
        except Exception as e:
             log_error(f"Analysis Failed: {e}")
             info = None
            
        if not info:
            content_container.controls.clear()
            content_container.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED_400, size=48),
                        ft.Text("Não foi possível carregar o link.", color=ft.Colors.RED_700, weight=ft.FontWeight.BOLD),
                        ft.Text("Verifique o arquivo app_log.txt para detalhes.", color=ft.Colors.GREY_600, size=12)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    alignment=ft.alignment.center, padding=30, bgcolor=ft.Colors.RED_50, border_radius=BORDER_RADIUS
                )
            )
            page.update()
            return

        if info.get('_type') == 'playlist' or ('entries' in info and len(info.get('entries', [])) > 0):
             show_playlist_options(info)
        else:
             show_options(info)
    
    analyze_btn.on_click = analyze_action

    # --- References for Options ---
    download_type_ref = ft.Ref[ft.Tabs]()
    quality_video_ref = ft.Ref[ft.Dropdown]()
    format_video_ref = ft.Ref[ft.Dropdown]()
    quality_audio_ref = ft.Ref[ft.Dropdown]()
    format_audio_ref = ft.Ref[ft.Dropdown]()
    download_btn = ft.Ref[ft.ElevatedButton]()
    cancel_btn = ft.Ref[ft.ElevatedButton]()
    path_text = ft.Ref[ft.Text]()
    progress_bar = ft.Ref[ft.ProgressBar]()
    status_text = ft.Ref[ft.Text]()
    open_folder_btn = ft.Ref[ft.ElevatedButton]()
    
    # Global File Picker
    file_picker = ft.FilePicker(on_result=lambda e: (path_text.current.__setattr__("value", e.path), path_text.current.update(), download_btn.current.__setattr__("disabled", False), download_btn.current.update()) if e.path else None)
    page.overlay.append(file_picker)

    def show_options(info):
        content_container.controls.clear()
        
        title = info.get('title', 'Unknown Title')
        thumb = info.get('thumbnail', '')
        duration = info.get('duration_string', 'N/A')
        
        # 1. Metadata Card
        meta_card = ft.Card(
            elevation=2,
            surface_tint_color=SURFACE_COLOR,
            color=SURFACE_COLOR,
            content=ft.Container(
                content=ft.Row([
                    ft.Image(src=thumb, width=180, height=100, border_radius=BORDER_RADIUS, fit=ft.ImageFit.COVER),
                    ft.Column([
                        ft.Text(title, size=16, weight=ft.FontWeight.BOLD, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, width=400, color=ft.Colors.GREY_900),
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.TIMER, size=14, color=ft.Colors.GREY_500),
                                ft.Text(f"{duration}", size=13, color=ft.Colors.GREY_600),
                            ], spacing=5),
                            margin=ft.margin.only(top=5)
                        )
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=2)
                ], alignment=ft.MainAxisAlignment.START),
                padding=15,
            )
        )

        # 2. Tabs
        audio_col = ft.Column([
            create_dropdown(quality_audio_ref, "Qualidade de Áudio", [
                ft.dropdown.Option("high", "Alta (320kbps) - Melhor Qualidade"),
                ft.dropdown.Option("medium", "Média (192kbps) - Padrão"),
                ft.dropdown.Option("low", "Baixa (128kbps) - Leve"),
            ], "high"),
            create_dropdown(format_audio_ref, "Formato do Arquivo", [
                 ft.dropdown.Option("mp3", "MP3 - Compatibilidade Universal"),
                 ft.dropdown.Option("m4a", "M4A (AAC) - Melhor Compressão"),
                 ft.dropdown.Option("wav", "WAV - Sem Perdas (Pesado)"),
            ], "mp3")
        ], spacing=20)

        video_col = ft.Column([
            create_dropdown(quality_video_ref, "Qualidade de Vídeo", [
                ft.dropdown.Option("high", "Máxima (Até 4K/8K)"),
                ft.dropdown.Option("medium", "HD (720p)"),
                ft.dropdown.Option("low", "SD (480p) - Economia de Dados"),
            ], "high"),
            create_dropdown(format_video_ref, "Formato do Arquivo", [
                 ft.dropdown.Option("mp4", "MP4 - Compatível"),
                 ft.dropdown.Option("mkv", "MKV - Moderno"),
                 ft.dropdown.Option("webm", "WebM - Web"),
            ], "mp4")
        ], spacing=20)

        tabs = ft.Tabs(
            ref=download_type_ref,
            selected_index=1,
            animation_duration=300,
            indicator_color=PRIMARY_COLOR,
            label_color=PRIMARY_COLOR,
            unselected_label_color=ft.Colors.GREY_500,
            tabs=[
                ft.Tab(text="VÍDEO", icon=ft.Icons.VIDEOCAM, content=ft.Container(content=video_col, padding=20)),
                ft.Tab(text="ÁUDIO", icon=ft.Icons.AUDIOTRACK, content=ft.Container(content=audio_col, padding=20)),
            ],
            expand=True,
        )
        
        tabs_card = ft.Container(
            bgcolor=SURFACE_COLOR,
            border=ft.border.all(1, ft.Colors.GREY_200),
            border_radius=BORDER_RADIUS,
            content=ft.Container(content=tabs, height=280) 
        )

        # 3. Path
        # file_picker reused from main scope
        # page.overlay.append(file_picker) # Already appended

        path_display = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, color=PRIMARY_COLOR),
                    bgcolor=ft.Colors.INDIGO_50,
                    padding=10,
                    border_radius=8,
                ),
                ft.Column([
                    ft.Text("Salvar na pasta", size=11, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_600),
                    ft.Text("Nenhum local selecionado", ref=path_text, size=14, color=ft.Colors.GREY_900, weight=ft.FontWeight.BOLD, width=500, overflow=ft.TextOverflow.ELLIPSIS)
                ], spacing=2)
            ]),
            padding=15,
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=BORDER_RADIUS,
            bgcolor=SURFACE_COLOR,
            on_click=lambda _: file_picker.get_directory_path(),
            ink=True,
            tooltip="Clique para alterar a pasta de destino"
        )

        # 4. Buttons
        btn_start = ft.ElevatedButton(
            "INICIAR DOWNLOAD",
            ref=download_btn,
            icon=ft.Icons.DOWNLOAD_ROUNDED,
            bgcolor=PRIMARY_COLOR,
            color=ft.Colors.WHITE,
            height=55,
            width=280,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=30), elevation=4),
            disabled=True,
            on_click=start_download_wrapper
        )
        
        btn_cancel = ft.ElevatedButton(
            "CANCELAR",
            ref=cancel_btn,
            icon=ft.Icons.CLOSE_ROUNDED,
            bgcolor=ft.Colors.RED_500,
            color=ft.Colors.WHITE,
            height=55,
            width=200,
            visible=False,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=30)),
            on_click=lambda _: service.cancel()
        )
        
        btn_open = ft.ElevatedButton(
            "ABRIR PASTA",
            ref=open_folder_btn,
            icon=ft.Icons.FOLDER_ROUNDED,
            bgcolor=ft.Colors.GREEN_600,
            color=ft.Colors.WHITE,
            height=55,
            width=220,
            visible=False,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=30)),
            on_click=lambda _: os.startfile(path_text.current.value)
        )

        actions_column = ft.Column([
            path_display,
            ft.Container(height=10),
            ft.ProgressBar(ref=progress_bar, width=600, height=8, border_radius=4, value=0, visible=False, color=PRIMARY_COLOR, bgcolor=ft.Colors.GREY_200),
            ft.Text("", ref=status_text, size=13, color=ft.Colors.GREY_700, weight=ft.FontWeight.W_500),
            ft.Container(height=10),
            ft.Row([btn_start, btn_cancel, btn_open], alignment=ft.MainAxisAlignment.CENTER, spacing=15)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        content_container.controls.extend([
            meta_card,
            tabs_card,
            actions_column
        ])
        page.update()

    async def start_download_wrapper(e):
        dl_path = path_text.current.value
        url = url_tf.value
        
        download_btn.current.visible = False
        cancel_btn.current.visible = True
        open_folder_btn.current.visible = False
        progress_bar.current.visible = True
        progress_bar.current.value = None
        status_text.current.value = "Iniciando download..."
        page.update()

        current_tab_idx = download_type_ref.current.selected_index
        is_audio = (current_tab_idx == 1) 
        if is_audio:
            qual = quality_audio_ref.current.value
            codec = format_audio_ref.current.value
        else:
            qual = quality_video_ref.current.value
            codec = format_video_ref.current.value

        def progress_hook(d):
            if d.get('status') == 'downloading':
                try:
                    p = d.get('_percent_str', '').replace('%','')
                    total = d.get('_total_bytes_str', 'N/A')
                    speed = d.get('_speed_str', 'N/A')
                    if p and p != 'N/A':
                        val = float(p) / 100
                        progress_bar.current.value = val
                    status_text.current.value = f"Baixando: {p}% de {total} ({speed})"
                    page.update()
                except Exception as ex:
                    log_error(f"Error parse progress: {ex}")
            elif d.get('status') == 'finished':
                status_text.current.value = "Processando arquivo final..."
                progress_bar.current.value = None
                page.update()

        def do_download():
            success, msg = service.download(url, dl_path, qual, codec, is_audio, progress_hook)
            if success:
                status_text.current.value = "Download e conversão concluídos!"
                progress_bar.current.value = 1
                progress_bar.current.color = ft.Colors.GREEN
                open_folder_btn.current.visible = True
                download_btn.current.visible = True
                download_btn.current.text = "BAIXAR OUTRO"
            else:
                status_text.current.value = f"Erro: {msg}"
                progress_bar.current.color = ft.Colors.RED if "Cancelado" not in msg else ft.Colors.ORANGE
                progress_bar.current.value = 1
                download_btn.current.visible = True
            
            cancel_btn.current.visible = False
            download_btn.current.disabled = False
            page.update()

        t = threading.Thread(target=do_download)
        t.start()
        # No loop wait here, just fire and forget, UI updates via callback

    # --- Playlist UI Support ---

    def format_seconds(seconds):
        if not seconds: return "N/A"
        try:
            val = int(seconds)
            m, s = divmod(val, 60)
            h, m = divmod(m, 60)
            if h > 0:
                return f"{h}:{m:02d}:{s:02d}"
            return f"{m}:{s:02d}"
        except:
            return "N/A"

    def estimate_size(duration_sec, is_audio, quality):
        if not duration_sec: return 0
        # Bitrate assumptions (approximate)
        # Audio: High=320kbps, Med=192kbps, Low=128kbps
        # Video: High(1080p)=4500kbps, Med(720p)=2500kbps, Low(480p)=1000kbps
        # Size (MB) = (kbps * duration) / 8 / 1024
        
        rate = 0
        if is_audio:
            if quality == "high": rate = 320
            elif quality == "medium": rate = 192
            else: rate = 128
        else:
            # Video includes audio, so add ~128kbps
            if quality == "high": rate = 4500 + 128
            elif quality == "medium": rate = 2500 + 128
            else: rate = 1000 + 128
            
        mb = (rate * duration_sec) / 8192 # 8 * 1024
        return mb

    class PlaylistEntry:
        def __init__(self, entry_data, index):
            self.data = entry_data
            self.index = index
            self.ref_quality = ft.Ref[ft.Dropdown]()
            self.ref_format = ft.Ref[ft.Dropdown]()
            self.ref_type_icon = ft.Ref[ft.Icon]()
            self.ref_status = ft.Ref[ft.Text]()
            self.is_audio = False # Default to video logic initially
            
            # Setup initial values
            self.quality_val = "high"
            self.format_val = "mp4"

        def get_control(self):
            title = self.data.get('title', 'Unknown')
            duration = self.data.get('duration_string', '')
            if not duration:
                 sec = self.data.get('duration')
                 duration = format_seconds(sec)
            
            # Try to get thumbnail. --flat-playlist entries often have 'thumbnails' list or none.
            thumb_src = ""
            if self.data.get('thumbnails') and len(self.data['thumbnails']) > 0:
                 # Get the first one (usually smallest) or last (largest). Let's try last for best quality.
                 thumb_src = self.data['thumbnails'][-1].get('url', '')
            
            # Visual Content: Image or Icon
            visual_content = ft.Icon(ft.Icons.VIDEO_FILE, color=PRIMARY_COLOR, size=40)
            if thumb_src:
                visual_content = ft.Image(src=thumb_src, width=80, height=45, fit=ft.ImageFit.COVER, border_radius=4)

            return ft.Container(
                content=ft.Row([
                    ft.Text(f"{self.index}.", weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_500, width=30),
                    visual_content,
                    ft.Column([
                        ft.Text(title, weight=ft.FontWeight.W_600, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, width=350),
                        ft.Text(f"Duração: {duration}", size=12, color=ft.Colors.GREY_500)
                    ], spacing=2),
                    ft.VerticalDivider(width=10, color=ft.Colors.TRANSPARENT),
                    # Individual Controls
                    ft.Dropdown(
                        ref=self.ref_quality,
                        width=120,
                        # height property removed as it causes TypeError
                        content_padding=10,
                        text_size=12,
                        value="high",
                        options=[
                            ft.dropdown.Option("high", "Alta"),
                            ft.dropdown.Option("medium", "Média"),
                            ft.dropdown.Option("low", "Baixa"),
                        ],
                        on_change=self.update_state
                    ),
                    ft.Dropdown(
                        ref=self.ref_format,
                        width=100,
                        # height property removed
                        content_padding=10,
                        text_size=12,
                        value="mp4",
                        options=[
                            ft.dropdown.Option("mp4", "MP4"),
                            ft.dropdown.Option("mp3", "MP3"),
                            # More added dynamically based on global toggle if needed, or static standard
                        ],
                        on_change=self.update_state
                    ),
                    ft.Container(width=10),
                    ft.Text("", ref=self.ref_status, size=12, color=ft.Colors.GREY_600, width=80, text_align=ft.TextAlign.RIGHT)
                ], alignment=ft.MainAxisAlignment.START),
                padding=10,
                border=ft.border.all(1, ft.Colors.GREY_200),
                border_radius=8,
                bgcolor=SURFACE_COLOR
            )

        def update_state(self, e):
            self.quality_val = self.ref_quality.current.value
            self.format_val = self.ref_format.current.value

        def sync_global(self, is_audio, quality, fmt):
            self.is_audio = is_audio
            # Update values
            self.ref_quality.current.value = quality
            self.quality_val = quality
            
            # Update options for format if switching type
            if is_audio:
                 self.ref_format.current.options = [
                     ft.dropdown.Option("mp3", "MP3"),
                     ft.dropdown.Option("m4a", "M4A"),
                     ft.dropdown.Option("wav", "WAV")
                 ]
            else:
                 self.ref_format.current.options = [
                     ft.dropdown.Option("mp4", "MP4"),
                     ft.dropdown.Option("mkv", "MKV"),
                     ft.dropdown.Option("webm", "WebM")
                 ]
            
            # Check if current format is valid for new type, else reset
            valid_opts = [o.key for o in self.ref_format.current.options]
            if fmt in valid_opts:
                self.ref_format.current.value = fmt
                self.format_val = fmt
            else:
                self.ref_format.current.value = valid_opts[0]
                self.format_val = valid_opts[0]

            self.ref_quality.current.update()
            self.ref_format.current.update()

    def show_playlist_options(info):
        content_container.controls.clear()
        
        entries = info.get('entries', [])
        title = info.get('title', 'Playlist Desconhecida')
        
        # Refs for Global Controls
        global_type_ref = ft.Ref[ft.Tabs]()
        global_qual_ref = ft.Ref[ft.Dropdown]()
        size_est_ref = ft.Ref[ft.Text]()
        
        playlist_entries = []
        
        # Header
        header_card = ft.Container(
            content=ft.Column([
                ft.Text("PLAYLIST DETECTADA", size=12, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
                ft.Text(title, size=20, weight=ft.FontWeight.W_800),
                ft.Text(f"{len(entries)} Vídeos encontrados", color=ft.Colors.GREY_600)
            ]),
            padding=10
        )

        def update_size_est():
             is_audio = (global_type_ref.current.selected_index == 1)
             qual = global_qual_ref.current.value
             total_sec = 0
             for e in entries:
                 if e.get('duration'):
                     total_sec += float(e['duration'])
             
             mb = estimate_size(total_sec, is_audio, qual)
             size_est_ref.current.value = f"Estimado: ~{int(mb)} MB"
             size_est_ref.current.update()

        # Global Controls
        def on_global_change(e):
             # 0=Video, 1=Audio
             is_audio = (global_type_ref.current.selected_index == 1)
             qual = global_qual_ref.current.value
             # Map global quality to format defaults or keep simple
             fmt = "mp3" if is_audio else "mp4"
             
             for entry in playlist_entries:
                 entry.sync_global(is_audio, qual, fmt)
             
             update_size_est()
             page.update()

        global_controls = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Controle Universal", weight=ft.FontWeight.BOLD),
                    ft.Tabs(
                        ref=global_type_ref,
                        selected_index=0,
                        on_change=on_global_change,
                        tabs=[ft.Tab(text="Vídeo"), ft.Tab(text="Áudio")]
                    ),
                    ft.Dropdown(
                        ref=global_qual_ref,
                        label="Qualidade Global",
                        options=[
                            ft.dropdown.Option("high", "Alta"),
                            ft.dropdown.Option("medium", "Média"),
                            ft.dropdown.Option("low", "Baixa"),
                        ],
                        value="high",
                        on_change=on_global_change
                    )
                ], spacing=10),
                padding=15
            ),
            color=SURFACE_COLOR,
            elevation=2
        )

        # List
        lv = ft.ListView(expand=False, height=350, spacing=10)
        idx = 1
        for entry in entries:
             # Basic filter for valid entries
             if entry.get('title') == '[Private video]': continue
             pe = PlaylistEntry(entry, idx)
             playlist_entries.append(pe)
             lv.controls.append(pe.get_control())
             idx += 1

        # Path & Action
        # Re-use path helpers from main scope (file_picker, path_text)
        path_display = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, color=PRIMARY_COLOR),
                ft.Text("Salvar em: ", color=ft.Colors.GREY_600),
                ft.Text("Selecionar Pasta", ref=path_text, weight=ft.FontWeight.BOLD, width=400, overflow=ft.TextOverflow.ELLIPSIS)
            ]),
            padding=15,
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=BORDER_RADIUS,
            on_click=lambda _: file_picker.get_directory_path(),
            ink=True,
            bgcolor=SURFACE_COLOR
        )

        btn_dl_all = ft.ElevatedButton(
            "BAIXAR PLAYLIST COMPLETA",
            icon=ft.Icons.PLAYLIST_ADD_CHECK_ROUNDED,
            bgcolor=PRIMARY_COLOR,
            color=ft.Colors.WHITE,
            height=55,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=30)),
            on_click=lambda e: start_playlist_download(playlist_entries)
        )
        
        # Calculate initial size
        initial_mb = 0
        total_sec = sum([float(e.get('duration', 0)) for e in entries])
        # Default is Video High
        initial_mb = estimate_size(total_sec, False, "high")

        dl_row = ft.Row([
            ft.Column([
                btn_dl_all,
                ft.Text(f"Estimado: ~{int(initial_mb)} MB", ref=size_est_ref, size=12, color=ft.Colors.GREY_600, text_align=ft.TextAlign.CENTER)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)
        ], alignment=ft.MainAxisAlignment.CENTER)

        btn_cancel_playlist = ft.ElevatedButton(
            "CANCELAR",
            icon=ft.Icons.CLOSE_ROUNDED,
            bgcolor=ft.Colors.RED_500,
            color=ft.Colors.WHITE,
            height=55,
            visible=False,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=30)),
            on_click=lambda _: service.cancel()
        )
        
        # Progress area for playlist
        playlist_progress_col = ft.Column(visible=False, spacing=10)

        content_container.controls.extend([
             header_card,
             global_controls,
             ft.Container(content=lv, height=350, border=ft.border.all(1, ft.Colors.GREY_200), border_radius=8, padding=5),
             path_display,
             playlist_progress_col,
             ft.Row([dl_row, btn_cancel_playlist], alignment=ft.MainAxisAlignment.CENTER, spacing=10)
        ])
        page.update()

        def start_playlist_download(entries_list):
             if not path_text.current.value or path_text.current.value == "Nenhum local selecionado":
                  page.show_snack_bar(ft.SnackBar(ft.Text("Selecione uma pasta de destino!")))
                  return

             dl_row.visible = False
             btn_cancel_playlist.visible = True
             playlist_progress_col.visible = True
             
             # Create progress bars (Modernized)
             
             # Sub-components for progress
             prog_bar = ft.ProgressBar(width=None, value=0, color=PRIMARY_COLOR, bgcolor=ft.Colors.GREY_200, height=10, border_radius=5)
             
             txt_item_counter = ft.Text("Item 0/0", weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_800, size=14)
             txt_percent = ft.Text("0%", weight=ft.FontWeight.W_900, color=PRIMARY_COLOR, size=24)
             txt_status_detail = ft.Text("Preparando...", color=ft.Colors.GREY_500, size=12, text_align=ft.TextAlign.CENTER)

             progress_card = ft.Container(
                 content=ft.Column([
                     ft.Row([
                         ft.Container(
                             content=txt_item_counter,
                             padding=ft.padding.symmetric(horizontal=10, vertical=5),
                             bgcolor=ft.Colors.GREY_200,
                             border_radius=20
                         ),
                         ft.Container(expand=True), # Spacer
                         txt_percent
                     ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                     prog_bar,
                     ft.Container(content=txt_status_detail, alignment=ft.alignment.center)
                 ], spacing=10),
                 padding=20,
                 bgcolor=ft.Colors.INDIGO_50,
                 border_radius=12,
                 border=ft.border.all(1, ft.Colors.INDIGO_100)
             )

             playlist_progress_col.controls = [progress_card]
             page.update()
             
             def dl_thread():
                 total = len(entries_list)
                 completed = 0
                 
                 for i, item in enumerate(entries_list):
                     if service._cancel_flag: break
                     
                     # UI Update for Item Start
                     item.ref_status.current.value = "Baixando..."
                     item.ref_status.current.color = ft.Colors.BLUE
                     item.ref_status.current.update()
                     
                     # Update Counter: Item 1/6
                     txt_item_counter.value = f"Item {i+1}/{total}"
                     txt_status_detail.value = f"Iniciando: {item.data.get('title', '...')}"
                     progress_card.update()

                     # Download
                     vid_url = item.data.get('url')
                     if not vid_url and item.data.get('id'):
                         vid_url = f"https://www.youtube.com/watch?v={item.data.get('id')}"
                     
                     def item_hook(d):
                         if d.get('status') == 'downloading':
                             p = d.get('_percent_str', '').replace('%','')
                             speed = d.get('_speed_str', '')
                             eta = d.get('_eta_str', '')
                             if p:
                                 # Update individual
                                 item.ref_status.current.value = f"{p}%"
                                 item.ref_status.current.update()
                                 
                                 # Update Global Logic
                                 # We can either make the bar represent the SINGLE item progress or the TOTAL progress.
                                 # User asked for "75% ... Item 2/6". This implies the percentage is for the CURRENT item.
                                 # Let's stick to Current Item Percentage on the main text, but maybe mapped to bar?
                                 # Or better: Bar = Total Progress?
                                 # Actually, usually in playlists: Bar = Total Items Completed? 
                                 # Let's make Bar = (Completed Items + Current%) / Total
                                 
                                 current_p_val = float(p) / 100
                                 total_p = (completed + current_p_val) / total
                                 
                                 prog_bar.value = total_p
                                 txt_percent.value = f"{p}%"
                                 txt_status_detail.value = f"Baixando: {speed} - ETA: {eta}"
                                 progress_card.update()
                                 
                     success, msg = service.download(
                         vid_url, 
                         path_text.current.value, 
                         item.quality_val, 
                         item.format_val, 
                         item.is_audio, 
                         item_hook
                     )
                     
                     if success:
                         item.ref_status.current.value = "Concluído"
                         item.ref_status.current.color = ft.Colors.GREEN
                     else:
                         item.ref_status.current.value = "Erro"
                         item.ref_status.current.color = ft.Colors.RED
                         log_error(f"Failed item {i}: {msg}")
                     
                     item.ref_status.current.update()
                     completed += 1
                     
                     # Force update bar to next integer step
                     prog_bar.value = completed / total
                     progress_card.update()

                 if service._cancel_flag:
                      txt_status_detail.value = "Download Cancelado"
                      txt_status_detail.color = ft.Colors.RED
                      prog_bar.color = ft.Colors.RED
                 else:
                      txt_status_detail.value = "Playlist Finalizada com Sucesso!"
                      txt_status_detail.color = ft.Colors.GREEN
                      prog_bar.value = 1
                      prog_bar.color = ft.Colors.GREEN
                      txt_percent.value = "100%"
                 
                 progress_card.update()
                 dl_row.visible = True
                 btn_cancel_playlist.visible = False
                 page.update()

             t = threading.Thread(target=dl_thread)
             t.start()

    # --- Main Assembly ---
    page.add(
        ft.Container(
            content=ft.Column([
                ft.Container(height=10),
                header,
                input_row,
                ft.Container(content=analyze_btn, alignment=ft.alignment.center),
                ft.Divider(height=40, color=ft.Colors.TRANSPARENT),
                content_container
            ]),
            alignment=ft.alignment.top_center,
            width=800 
        )
    )

if __name__ == "__main__":
    try:
        ft.app(target=main)
    except Exception as e:
        log_error(f"Fatal error: {e}")
        input("Press enter to exit...")
