import flet as ft
import subprocess
import json
import os
import threading
import time
import sys
import logging
import traceback

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
        """Fetches metadata using subprocess."""
        log(f"Fetching info for: {url}")
        
        # Build command: python -m yt_dlp -J --no-playlist --socket-timeout 10 [url]
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "-J",
            "--no-playlist",
            "--socket-timeout", "15",
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
            
            stdout, stderr = process.communicate(timeout=45) # Hard timeout for the process
            
            if process.returncode != 0:
                log_error(f"yt-dlp failed with code {process.returncode}")
                log_error(f"Stderr: {stderr}")
                return None
            
            info = json.loads(stdout)
            log(f"Info extracted: {info.get('title', 'Unknown')}")
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
            "-o", out_tmpl,
            url
        ]

        # Format/Quality Setup
        if is_audio:
            cmd.extend(["-f", "bestaudio/best"])
            cmd.extend(["--extract-audio", "--audio-format", codec])
            
            # Note: Quality arg for audio in CLI is --audio-quality, typically 0-9 (0 best) or bitrate.
            # Map simplified quality to bitrate equivalent for ffmpeg if needed, 
            # OR just use standard defaults. yt-dlp's --audio-quality is 5 by default.
            # Creating complex post-processor args via CLI is tricky. 
            # We will rely on default best conversion for stability.
            if quality == 'low': cmd.extend(["--audio-quality", "128K"])
            elif quality == 'high': cmd.extend(["--audio-quality", "320K"]) # ffmpeg usage
            # Simple fallback: let yt-dlp handle it.
            
        else:
            # Video
            if quality == 'high':
                cmd.extend(["-f", f"bestvideo+bestaudio/best"])
            elif quality == 'medium':
                cmd.extend(["-f", f"bestvideo[height<=720]+bestaudio/best"])
            elif quality == 'low':
                cmd.extend(["-f", f"bestvideo[height<=480]+bestaudio/best"])
            
            cmd.extend(["--merge-output-format", codec])

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
                if self._cancel_flag:
                    self._current_process.terminate()
                    return False, "Cancelado pelo usuário"
                
                line = line.strip()
                if not line: continue
                
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
                    progress_hook(data)
                
                # Check for post-processing
                if '[ExtractAudio]' in line or '[Merger]' in line:
                     progress_hook({'status': 'finished'})

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

        info = None
        def fetch():
            nonlocal info
            info = service.get_info(url)
        
        t = threading.Thread(target=fetch)
        t.start()
        
        start_time = time.time()
        while t.is_alive():
            if time.time() - start_time > 45: # Extended timeout for subprocess
                log_error("UI Timeout on analysis.")
                break
            await __import__("asyncio").sleep(0.1)
            
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
        file_picker = ft.FilePicker(on_result=lambda e: (path_text.current.__setattr__("value", e.path), path_text.current.update(), download_btn.current.__setattr__("disabled", False), download_btn.current.update()) if e.path else None)
        page.overlay.append(file_picker)

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
