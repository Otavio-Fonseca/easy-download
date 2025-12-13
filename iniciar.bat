@echo off
echo Iniciando Video Downloader...
echo Logs serao salvos em app_log.txt
python setup_ffmpeg.py
python create_shortcut.py
python main.py
echo.
echo O programa encerrou.
pause
