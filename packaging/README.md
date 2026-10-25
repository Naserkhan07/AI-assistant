# Packaging

- **Windows installer**: `pip install pyinstaller && pyinstaller --windowed --name Nixi nixi/main.py`
- **MSIX / winget**: manifest in `packaging/msix/` (future)
- **Headless CLI**: `python -m nixi.cli chat` — no GUI required
- **Health check**: `python -m nixi.cli doctor`
