# Tests Directory

Este diretório contém scripts de teste para validar a funcionalidade da aplicação.

## Scripts Disponíveis

### `test_auto_setup.py`
Testa a funcionalidade de auto-configuração do FFmpeg simulando uma instalação limpa.

**Como executar:**
```bash
python tests/test_auto_setup.py
```

### `test_download.py`
Testa o download real de vídeo com merge de FFmpeg.

**Como executar:**
```bash
python tests/test_download.py
```

## Notas

- Os testes são opcionais e não são necessários para o funcionamento da aplicação
- Executar os testes requer conexão com a internet
- `test_auto_setup.py` faz backup temporário dos arquivos FFmpeg existentes
