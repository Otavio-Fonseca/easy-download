# Easy Download

Uma aplicação desktop moderna e minimalista para baixar vídeos e áudios do YouTube e outras plataformas com facilidade. Desenvolvido com Python e Flet.

![Screenshot](https://via.placeholder.com/800x450.png?text=Easy+Download+Preview)

## ✨ Funcionalidades

- 🎥 **Baixar Vídeos**: Escolha entre alta qualidade (até 4K), HD ou SD.
- 🎵 **Baixar Áudio**: Extraia áudio em MP3, M4A ou WAV.
- 🔗 **Colar Rápido**: Botão dedicado para colar links da área de transferência.
- 📂 **Gerenciamento**: Escolha a pasta de destino e abra-a facilmente após o download.
- 🚀 **Performance**: Downloads rápidos e interface que não trava (processamento em segundo plano).

## 🛠️ Pré-requisitos

- [Python 3.8+](https://www.python.org/downloads/) instalado.
- [FFmpeg](https://ffmpeg.org/download.html) (Necessário para juntar áudio e vídeo em alta qualidade e para conversões de áudio). Certifique-se de adicioná-lo ao PATH do sistema.

## 📦 Instalação

1. Clone o repositório:
   ```bash
   git clone https://github.com/Otavio-Fonseca/easy-download.git
   cd easy-download
   ```

2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

## 🚀 Como Usar

### Windows
Basta clicar duas vezes no arquivo `iniciar.bat` incluído na pasta.

### Via Terminal
```bash
python main.py
```

## 📝 Tecnologias

- **Frontend**: [Flet](https://flet.dev/) (Flutter para Python).
- **Backend**: [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Engine de download robusta).

---
Desenvolvido por Otávio Fonseca.
