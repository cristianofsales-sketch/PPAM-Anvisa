"""Early startup diagnostics; stdlib imports only."""
import contextlib
import ctypes
import json
import logging
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading

VERSION = "1.0.6"
_jobs = 0
_lock = threading.Lock()

@contextlib.contextmanager
def processing_job():
    global _jobs
    with _lock:
        _jobs += 1
    try:
        yield
    finally:
        with _lock:
            _jobs -= 1

def is_processing():
    with _lock:
        return _jobs > 0

def prepare_environment():
    data = Path(os.environ.get("PPAM_DATA_DIR", str(Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "PPAM Anvisa-data")))
    logs = data / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    cache = data / "cache"
    cache.mkdir(exist_ok=True)
    session = Path(tempfile.mkdtemp(prefix="session-", dir=cache))
    os.environ.update(PPAM_DATA_DIR=str(data), PPAM_CACHE_DIR=str(session), GRADIO_TEMP_DIR=str(session / "gradio"), GRADIO_ANALYTICS_ENABLED="False", HF_HUB_OFFLINE="1", PPAM_DESKTOP="1", TEMP=str(session), TMP=str(session))
    tempfile.tempdir = str(session)
    log = logs / "desktop.log"
    if sys.stdout is None:
        sys.stdout = (logs / 'console.log').open('a', encoding='utf-8', buffering=1)
    if sys.stderr is None:
        sys.stderr = sys.stdout
    from logging.handlers import RotatingFileHandler
    logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler(log, maxBytes=2000000, backupCount=3, encoding="utf-8")], force=True)
    logging.info("PPAM %s startup; frozen=%s", VERSION, bool(getattr(sys, "frozen", False)))
    return log

def preflight_resources():
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    required = [
        "templates/FORM-754.POP-F-ANVISA-083_V.03_1_2.docx",
        "assets/final.png",
        "assets/ppam-app-icon-v1.png",
        "assets/ppam-app-icon-v1.ico",
    ]
    if getattr(sys, "frozen", False):
        required += ["safehttpx/version.txt", "gradio/templates/frontend/index.html", "rapidocr_onnxruntime/config.yaml"]
        if len(list((root / "rapidocr_onnxruntime").rglob("*.onnx"))) < 3:
            raise RuntimeError("RECURSO_AUSENTE: modelos OCR. Reinstale o PPAM.")
        if not list((root / "webview").rglob("WebView2Loader.dll")):
            raise RuntimeError("RECURSO_AUSENTE: WebView2Loader.dll. Reinstale o PPAM.")
    for relative in required:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"RECURSO_AUSENTE: {relative}. Reinstale o PPAM.")
    return required

def port_available(port=7860):
    # Windows can permit a loopback bind alongside a wildcard listener that
    # uses SO_REUSEADDR. An accepting server must still be treated as occupied.
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.5):
            return False
    except OSError:
        pass
    try:
        with socket.socket() as sock:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False

def runtime_available():
    if sys.platform != "win32":
        return False
    import winreg
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            try:
                with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\EdgeUpdate\Clients", 0, winreg.KEY_READ | view) as clients:
                    for index in range(winreg.QueryInfoKey(clients)[0]):
                        with winreg.OpenKey(clients, winreg.EnumKey(clients, index)) as key:
                            try:
                                name = winreg.QueryValueEx(key, "name")[0]
                                version = winreg.QueryValueEx(key, "pv")[0]
                                if "webview2" in name.lower() and version != "0.0.0.0":
                                    return True
                            except OSError:
                                pass
            except OSError:
                pass
    return False

def message(text, error=False):
    return ctypes.windll.user32.MessageBoxW(None, text, "PPAM • Anvisa", 0x10 if error else 0x40)

def self_test(report):
    """Runs inside the executable, not the host's Python environment."""
    result = {"version": VERSION, "frozen": bool(getattr(sys, "frozen", False)), "passed": False}
    try:
        result["resources"] = preflight_resources()
        import safehttpx
        import gradio
        import webview
        from rapidocr_onnxruntime import RapidOCR
        RapidOCR()
        from docx import Document
        from models import PPAMData
        from template_filler import TemplateFiller
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "synthetic.docx"
            data = PPAMData()
            data.sumario.apresentacoes = ["50 mg/ml SOL INJ - caixa 25 ampolas", "50 mg/ml SOL INJ - caixa 36 ampolas"]
            TemplateFiller().fill(data, str(output))
            doc = Document(output)
            for text in data.sumario.apresentacoes:
                assert any(p.text.strip().rstrip('.;') == text for p in doc.paragraphs), text
        from app import app, get_launch_options
        import urllib.request
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            test_port = sock.getsockname()[1]
        try:
            app.launch(server_name="127.0.0.1", server_port=test_port, prevent_thread_lock=True, **get_launch_options())
            with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/", timeout=30) as response:
                assert response.status == 200
        finally:
            app.close()
        result["passed"] = True
    except Exception:
        import traceback
        result["error"] = traceback.format_exc()
    Path(report).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if result["passed"] else 1
