"""Instalador local do PPAM para Windows, empacotado como PPAM-Instalador.exe."""

import os
import shutil
import subprocess
import sys
import ctypes
import hashlib
import json
import tempfile
import uuid
import zipfile
import argparse
from pathlib import Path


APP_NAME = "PPAM Anvisa"


def resource_path(name: str) -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / name


def notify(title: str, text: str, error: bool = False):
    icon = 0x10 if error else 0x40
    ctypes.windll.user32.MessageBoxW(None, text, title, 0x0 | icon)


def safe_relative(name):
    from pathlib import PurePosixPath
    path = PurePosixPath(name)
    if not name or '\\' in name or ':' in name or path.is_absolute() or any(p in ('..', '.') for p in name.split('/')):
        raise ValueError('Caminho inválido no pacote: ' + name)
    if any(p.endswith((' ', '.')) for p in path.parts):
        raise ValueError('Caminho incompatível com Windows: ' + name)
    return path

class InstallProgress:
    """Small native progress window, without tkinter or third-party GUI libraries."""
    def __enter__(self):
        from ctypes import wintypes
        self.user = ctypes.windll.user32
        self.user.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p]
        self.user.CreateWindowExW.restype = wintypes.HWND
        self.user.SetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
        self.user.DestroyWindow.argtypes = [wintypes.HWND]
        self.user.IsWindow.argtypes = [wintypes.HWND]
        self.window = self.user.CreateWindowExW(0, 'STATIC', 'PPAM — Instalando', 0x10C80000, 400, 300, 550, 150, None, None, None, None)
        if not self.window:
            raise OSError('Não foi possível mostrar o progresso da instalação.')
        self.label = self.user.CreateWindowExW(0, 'STATIC', 'Verificando pacote…', 0x50000000, 25, 30, 490, 55, self.window, None, None, None)
        self.message = wintypes.MSG()
        self.user.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]
        self.user.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        self.user.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        self.user.DispatchMessageW.restype = ctypes.c_ssize_t
        return self

    def update(self, completed, total):
        self.user.SetWindowTextW(self.label, f'Copiando e verificando arquivos: {completed * 100 // max(total, 1)}%\nFeche esta janela para cancelar antes da substituição.')
        while self.user.PeekMessageW(ctypes.byref(self.message), None, 0, 0, 1):
            self.user.TranslateMessage(ctypes.byref(self.message))
            self.user.DispatchMessageW(ctypes.byref(self.message))
        if not self.user.IsWindow(self.window):
            raise InterruptedError('Instalação cancelada. A versão anterior foi preservada.')

    def __exit__(self, *args):
        if self.user.IsWindow(self.window):
            self.user.DestroyWindow(self.window)

def verify_archive(archive, destination=None, progress=None):
    with zipfile.ZipFile(archive) as bundle:
        infos = bundle.infolist()
        names = [item.filename for item in infos]
        if len(set(name.casefold() for name in names)) != len(names):
            raise ValueError('Arquivos duplicados no pacote.')
        for item in infos:
            safe_relative(item.filename)
            if item.is_dir() or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Entrada não permitida no pacote.')
        if bundle.getinfo('manifest.json').file_size > 8_000_000:
            raise ValueError('Manifesto excede limite.')
        manifest = json.loads(bundle.read('manifest.json'))
        if manifest.get('application') != APP_NAME or not manifest.get('version'):
            raise ValueError('Pacote não reconhecido.')
        expected = manifest['files']
        if set(names) != set(expected) | {'manifest.json'} or 'PPAM Anvisa.exe' not in expected or 'uninstall.ps1' not in expected:
            raise ValueError('Pacote incompleto ou com arquivos não declarados.')
        for name, entry in expected.items():
            if bundle.getinfo(name).file_size != entry['size'] or entry['size'] < 0:
                raise ValueError('Tamanho inválido: ' + name)
        total = sum(entry['size'] for entry in expected.values())
        if total > 4_000_000_000:
            raise ValueError('Pacote excede limite de tamanho.')
        if destination and shutil.disk_usage(destination).free < total + 100_000_000:
            raise OSError('Espaço insuficiente para instalar.')
        completed = 0
        for name, entry in expected.items():
            digest = hashlib.sha256()
            output = None
            try:
                if destination:
                    path = Path(destination).joinpath(*safe_relative(name).parts)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    output = path.open('xb')
                with bundle.open(name) as source:
                    while chunk := source.read(1024 * 1024):
                        digest.update(chunk)
                        if output:
                            output.write(chunk)
                        completed += len(chunk)
                        if progress:
                            progress(completed, total)
                if digest.hexdigest() != entry['sha256']:
                    raise ValueError('Falha de integridade: ' + name)
            finally:
                if output:
                    output.close()
        if destination:
            (Path(destination) / 'manifest.json').write_bytes(bundle.read('manifest.json'))
        return manifest

def install_payload(archive, target, register=None, progress=None):
    target = Path(target).absolute()
    if target.is_symlink() or (target.exists() and getattr(target, 'is_junction', lambda: False)()):
        raise ValueError('Destino não pode ser um vínculo.')
    if target.exists() and not ((target / 'PPAM Anvisa.exe').is_file() and (target / '_internal').is_dir()):
        raise ValueError('Destino existente não reconhecido como instalação PPAM. Nenhum arquivo foi substituído.')
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.ppam-stage-', dir=target.parent))
    backup = target.with_name(target.name + '-backup-' + uuid.uuid4().hex[:8])
    swapped = False
    try:
        manifest = verify_archive(archive, stage, progress)
        if target.exists():
            if sys.platform == 'win32':
                from ctypes import wintypes
                kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
                kernel.CreateFileW.restype = wintypes.HANDLE
                kernel.CloseHandle.argtypes = [wintypes.HANDLE]
                handle = kernel.CreateFileW(str(target / 'PPAM Anvisa.exe'), 0x80000000, 0, None, 3, 0, None)
                if handle == ctypes.c_void_p(-1).value:
                    raise OSError('O aplicativo está em uso ou sem permissão de acesso. Feche o PPAM e tente novamente.')
                kernel.CloseHandle(handle)
            # Windows refuses rename while files are held without delete sharing.
            # No running process is terminated by the installer.
            target.rename(backup)
        try:
            stage.rename(target)
            swapped = True
            if register:
                register(target, manifest['version'])
        except Exception:
            if swapped:
                target.rename(stage)
            if backup.exists():
                backup.rename(target)
            raise
        return backup if backup.exists() else None
    finally:
        # Only the unique staging directory created above is disposable.
        if stage.exists():
            shutil.rmtree(stage)

def register_install(target, version, desktop=False):
    import winreg
    script = r'''
$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject WScript.Shell
$locations = @([Environment]::GetFolderPath('Programs'))
if ($env:PPAM_DESKTOP_SHORTCUT -eq '1') { $locations += [Environment]::GetFolderPath('Desktop') }
foreach ($location in $locations) {
    $link = $shell.CreateShortcut((Join-Path $location 'PPAM Anvisa.lnk'))
    $link.TargetPath = Join-Path $env:PPAM_INSTALL_TARGET 'PPAM Anvisa.exe'
    $link.WorkingDirectory = $env:PPAM_INSTALL_TARGET
    $link.Save()
}
'''
    subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script], env=dict(os.environ, PPAM_INSTALL_TARGET=str(target), PPAM_DESKTOP_SHORTCUT='1' if desktop else '0'), check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    key_name = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\PPAM Anvisa'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_name) as key:
        for name, value in {'DisplayName': APP_NAME, 'DisplayVersion': version, 'Publisher': 'PPAM', 'InstallLocation': str(target), 'DisplayIcon': str(target / 'PPAM Anvisa.exe'), 'UninstallString': f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{target / "uninstall.ps1"}"'}.items():
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-payload')
    args = parser.parse_args()
    source = resource_path('payload.zip')
    if args.verify_payload:
        result = {'passed': False}
        try:
            manifest = verify_archive(source)
            result.update(passed=True, version=manifest['version'], files=len(manifest['files']))
        except Exception as exc:
            result['error'] = str(exc)
        Path(args.verify_payload).write_text(json.dumps(result, indent=2), encoding='utf-8')
        return 0 if result['passed'] else 1
    target = Path(os.environ['LOCALAPPDATA']) / APP_NAME
    if ctypes.windll.user32.MessageBoxW(None, f'Instalar PPAM 1.0.6 em:\n{target}\n\nFeche o PPAM antes de continuar. A versão anterior será preservada em uma pasta de backup.', 'Instalar PPAM', 0x4 | 0x20) != 6:
        return 0
    desktop = ctypes.windll.user32.MessageBoxW(None, 'Deseja criar um atalho na área de trabalho?', 'Instalar PPAM', 0x4 | 0x20) == 6
    try:
        from win_prerequisites import runtime_available
        if not runtime_available():
            raise RuntimeError('Instale primeiro o Microsoft Edge WebView2 Runtime pelo site oficial da Microsoft: https://developer.microsoft.com/microsoft-edge/webview2/')
        with InstallProgress() as progress:
            backup = install_payload(source, target, lambda path, version: register_install(path, version, desktop), progress.update)
    except Exception as exc:
        notify('Instalação não concluída', f'Não foi possível instalar o PPAM. Feche o aplicativo e tente novamente.\n\n{exc}', error=True)
        return 1
    text = f'Instalação concluída em:\n{target}'
    if backup:
        text += f'\n\nVersão anterior e arquivos preservados em:\n{backup}'
    if ctypes.windll.user32.MessageBoxW(None, text + '\n\nDeseja abrir o PPAM agora?', 'PPAM instalado', 0x4 | 0x40) == 6:
        subprocess.Popen([str(target / 'PPAM Anvisa.exe')], cwd=target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
