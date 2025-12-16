# Estrutura do Projeto - Video Downloader

```
Video Downloader/
│
├── 📁 assets/              # Recursos visuais (ícones, imagens)
│   └── icon.png
│
├── 📁 tests/               # Scripts de teste
│   ├── README.md
│   ├── test_auto_setup.py  # Testa auto-configuração do FFmpeg
│   └── test_download.py    # Testa download real
│
├── 📄 main.py              # Aplicação principal (Flet UI)
├── 📄 setup_ffmpeg.py      # Auto-configuração do FFmpeg
├── 📄 create_shortcut.py   # Cria atalho na área de trabalho
├── 📄 iniciar.bat          # Script de inicialização Windows
├── 📄 requirements.txt     # Dependências Python
├── 📄 README.md            # Documentação do projeto
└── 📄 .gitignore           # Arquivos ignorados pelo Git

Arquivos Ignorados (não versionados):
├── ffmpeg.exe              # Baixado automaticamente (99MB)
├── ffprobe.exe             # Baixado automaticamente (99MB)
├── app_log.txt             # Log de execução
└── __pycache__/            # Cache Python
```

## Arquivos Principais

### `main.py`
- Interface gráfica com Flet
- Gerenciamento de downloads
- Suporte a vídeo e áudio
- Playlists e vídeos individuais
- **Auto-configura FFmpeg na primeira execução**

### `setup_ffmpeg.py`
- Download automático do FFmpeg
- Instalação local (não afeta sistema)
- Mensagem visual para o usuário
- Execução silenciosa quando já instalado

### `create_shortcut.py`
- Cria atalho na área de trabalho
- Facilita acesso rápido

### `iniciar.bat`
- Script de inicialização conveniente
- Executa `main.py` automaticamente

## Testes

Os scripts de teste estão em `tests/`:
- **test_auto_setup.py**: Simula instalação limpa e verifica auto-configuração
- **test_download.py**: Testa download real com merge FFmpeg

## Dependências

Instaladas via `pip install -r requirements.txt`:
- `flet` - Framework UI
- `yt-dlp` - Download de vídeos

FFmpeg é baixado automaticamente na primeira execução.

## Gitignore

Arquivos grandes e temporários são ignorados:
- Binários do FFmpeg (~200MB)
- Logs de execução
- Cache Python
- Ambientes virtuais
