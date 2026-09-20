"""Official fail-closed build. Never reuses a previous output directory."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parent
VERSION = '1.0.6'

def run(args, log, **kwargs):
    with log.open('a', encoding='utf-8') as stream:
        stream.write('\nCOMMAND: ' + repr(list(map(str, args))) + '\n')
        stream.flush()
        subprocess.run(list(map(str, args)), cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True, **kwargs)

def main():
    if sys.prefix == sys.base_prefix:
        raise RuntimeError('Use .venv-build; builds from the global Python are not supported.')
    stamp = time.strftime('%Y%m%d-%H%M%S')
    work = ROOT / 'build-candidates' / stamp
    work.mkdir(parents=True, exist_ok=False)
    log = work / 'build.log'
    print('Build log: ' + str(log), flush=True)
    run([sys.executable, '-m', 'pip', 'check'], log)
    run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], log)
    run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--distpath', work / 'dist', '--workpath', work / 'work', ROOT / 'packaging/build.spec'], log)
    payload = work / f'dist/PPAM-Desktop-{VERSION}'
    report = work / 'frozen-self-test.json'
    env = dict(os.environ, PPAM_DATA_DIR=str(work / 'test-data'))
    run([payload / 'PPAM Anvisa.exe', '--self-test', report], log, timeout=240, env=env)
    self_test = json.loads(report.read_text(encoding='utf-8'))
    if not self_test.get('passed') or self_test.get('version') != VERSION:
        raise RuntimeError('Frozen self-test/version did not pass. Installer blocked.')
    shutil.copy2(ROOT / 'packaging/uninstall.ps1', payload / 'uninstall.ps1')
    files = {}
    for p in payload.rglob('*'):
        if p.is_file():
            with p.open('rb') as source:
                digest = hashlib.file_digest(source, 'sha256').hexdigest()
            files[p.relative_to(payload).as_posix()] = {'size': p.stat().st_size, 'sha256': digest}
    (payload / 'manifest.json').write_text(json.dumps({'application': 'PPAM Anvisa', 'version': VERSION, 'files': files}, indent=2), encoding='utf-8')
    archive = work / 'payload.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
        for path in payload.rglob('*'):
            if path.is_file():
                zip_file.write(path, path.relative_to(payload).as_posix())
    installer_name = f'PPAM-Instalador-{VERSION}'
    run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed', '--onefile', '--name', installer_name, '--icon', ROOT / 'assets/ppam-app-icon-v1.ico', '--distpath', work / 'installer', '--workpath', work / 'installer-work', '--specpath', work, '--add-data', str(archive) + ';.', ROOT / 'installer.py'], log)
    installer = work / f'installer/{installer_name}.exe'
    run([installer, '--verify-payload', work / 'installer-verification.json'], log, timeout=240)
    verification = json.loads((work / 'installer-verification.json').read_text(encoding='utf-8'))
    if not verification.get('passed') or verification.get('version') != VERSION:
        raise RuntimeError('Installer verification/version failed.')
    with installer.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    (work / 'candidate.json').write_text(json.dumps({'version': VERSION, 'installer': str(installer), 'sha256': digest, 'size': installer.stat().st_size, 'status': 'candidate — clean-Windows and GUI acceptance pending'}, indent=2), encoding='utf-8')
    print('Validated packaging candidate: ' + str(installer), flush=True)

if __name__ == '__main__':
    main()
