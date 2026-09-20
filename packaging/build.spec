from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata
from pathlib import Path
root = Path(SPECPATH).parent
datas = [
    (str(root / 'templates'), 'templates'),
    (str(root / 'assets'), 'assets'),
]
binaries = []
hiddenimports = []
for package in ('gradio', 'gradio_client', 'safehttpx', 'groovy', 'hf_gradio', 'webview', 'rapidocr_onnxruntime'):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h
for distribution in ('gradio', 'pywebview', 'safehttpx', 'rapidocr_onnxruntime'):
    datas += copy_metadata(distribution, recursive=True)
a = Analysis([str(root / 'desktop_app.py')], pathex=[str(root)], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, excludes=['tkinter', 'torch', 'tensorflow', 'spacy', 'IPython', 'matplotlib'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='PPAM Anvisa', icon=str(root / 'assets' / 'ppam-app-icon-v1.ico'), debug=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='PPAM-Desktop-1.0.6')
