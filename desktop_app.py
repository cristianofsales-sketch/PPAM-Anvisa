"""Inicializador desktop do PPAM: abre a interface Gradio em uma janela nativa."""

import ctypes
from ctypes import wintypes
import logging
import sys
import threading
from desktop_runtime import prepare_environment, preflight_resources, port_available, runtime_available, message, self_test, is_processing


def main():
    try:
        log = prepare_environment()
    except OSError:
        message('Não foi possível criar a pasta de dados do PPAM. Verifique as permissões e o espaço em disco.', True)
        return 1
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        return self_test(sys.argv[2])
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    mutex = kernel.CreateMutexW(None, False, "Local\\PPAM-Anvisa-Desktop-7860")
    if not mutex:
        message("Não foi possível iniciar o aplicativo. Tente novamente.", True)
        return 1
    if ctypes.get_last_error() == 183:
        user = ctypes.windll.user32
        user.FindWindowW.restype = wintypes.HWND
        user.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        window = user.FindWindowW(None, "PPAM • Anvisa")
        if window:
            user.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
            user.SetForegroundWindow.argtypes = [wintypes.HWND]
            user.ShowWindow(window, 9)
            user.SetForegroundWindow(window)
        else:
            message("O PPAM já está iniciando. Aguarde a janela abrir.")
        kernel.CloseHandle(mutex)
        return 0
    server = None
    try:
        preflight_resources()
        if not runtime_available():
            raise RuntimeError("WEBVIEW2_AUSENTE: instale o Microsoft Edge WebView2 Runtime pelo site oficial da Microsoft e abra o PPAM novamente: https://developer.microsoft.com/microsoft-edge/webview2/")
        while not port_available():
            answer = ctypes.windll.user32.MessageBoxW(None, "A porta 7860 está ocupada. Feche a outra aplicação ou a versão de navegador do PPAM e clique em Repetir. Nenhum processo será encerrado automaticamente.", "PPAM — Porta ocupada", 0x5 | 0x30)
            if answer != 4:
                return 1
        import webview
        webview.settings["ALLOW_DOWNLOADS"] = True
        window = webview.create_window("PPAM • Anvisa", html='<html><body style="background:#0b1220;color:white;font:24px Segoe UI;text-align:center;padding-top:20%">Abrindo o PPAM…<p style="font-size:16px">Preparando processamento local</p></body></html>', width=1440, height=920, min_size=(1000, 700))
        stopped = threading.Event()
        def closing():
            if is_processing():
                if ctypes.windll.user32.MessageBoxW(None, "Há um processamento em andamento. Deseja interrompê-lo e fechar?", "PPAM", 0x4 | 0x30) != 6:
                    return False
            stopped.set()
        window.events.closing += closing
        def start_server():
            nonlocal server
            try:
                from app import app, get_launch_options
                server = app
                if stopped.is_set():
                    return
                server.launch(server_name="127.0.0.1", server_port=7860, prevent_thread_lock=True, **get_launch_options())
                if stopped.is_set():
                    server.close()
                    return
                window.load_url("http://127.0.0.1:7860/")
            except Exception:
                logging.exception("Desktop startup failed")
                message(f"Não foi possível abrir o PPAM. Repare a instalação. Detalhes em:\n{log}", True)
                window.destroy()
        webview.start(start_server, gui="edgechromium", debug=False, private_mode=True)
        stopped.set()
        return 0
    except Exception as exc:
        logging.exception("Desktop failed")
        message(f"Não foi possível iniciar o PPAM.\n\n{exc}\n\nDiagnóstico: {log}", True)
        return 1
    finally:
        if server is not None:
            server.close()
        kernel.CloseHandle(mutex)


if __name__ == "__main__":
    sys.exit(main())
