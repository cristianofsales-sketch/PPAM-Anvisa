"""Snapshot the installed dependency closure, excluding unrelated environments."""
from importlib.metadata import distribution
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

roots = ['gradio', 'pywebview', 'pdfplumber', 'python-docx', 'pydantic', 'PyYAML', 'Pillow', 'rapidocr_onnxruntime', 'PyInstaller', 'setuptools']
pending = [(name, frozenset()) for name in roots]
seen = set()
versions = {}
while pending:
    name, extras = pending.pop()
    name = canonicalize_name(name)
    if (name, extras) in seen:
        continue
    seen.add((name, extras))
    package = distribution(name)
    versions[name] = package.version
    for spec in package.requires or []:
        requirement = Requirement(spec)
        if requirement.marker and not any(requirement.marker.evaluate({'extra': extra}) for extra in extras | {''}):
            continue
        pending.append((requirement.name, frozenset(requirement.extras)))
target = Path(__file__).resolve().parents[1] / 'requirements-build.lock.txt'
target.write_text('# Windows x64 / Python 3.11.9 — installed dependency snapshot\n' + '\n'.join(f'{name}=={version}' for name, version in sorted(versions.items())) + '\n', encoding='utf-8')
print(f'{len(versions)} locked dependencies: {target}')
