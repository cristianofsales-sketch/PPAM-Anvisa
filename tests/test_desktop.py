import hashlib
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from desktop_runtime import processing_job, is_processing, port_available, preflight_resources
from installer import verify_archive, install_payload, safe_relative

class PackagingTests(unittest.TestCase):
    def make_package(self, directory, corrupt=False):
        path = Path(directory) / 'payload.zip'
        files = {'PPAM Anvisa.exe': b'fake-test-executable', '_internal/resource.txt': b'resource', 'uninstall.ps1': b'# test'}
        manifest = {'application': 'PPAM Anvisa', 'version': 'test', 'files': {name: {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for name, data in files.items()}}
        if corrupt:
            manifest['files']['PPAM Anvisa.exe']['sha256'] = '0' * 64
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('manifest.json', json.dumps(manifest))
            for name, data in files.items():
                archive.writestr(name, data)
        return path

    def test_resource_template(self):
        resources = preflight_resources()
        self.assertIn('assets/ppam-app-icon-v1.png', resources)
        self.assertIn('assets/ppam-app-icon-v1.ico', resources)

    def test_processing_state_restored_on_failure(self):
        with self.assertRaises(ValueError):
            with processing_job():
                self.assertTrue(is_processing())
                raise ValueError()
        self.assertFalse(is_processing())

    def test_port_conflict(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.assertFalse(port_available(sock.getsockname()[1]))

    def test_wildcard_listener_is_not_reused(self):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('0.0.0.0', 0))
            sock.listen()
            self.assertFalse(port_available(sock.getsockname()[1]))

    def test_reject_unsafe_paths(self):
        for path in ('../secret', '/root', 'C:/windows', 'a\\b', 'a/../b', 'a:stream', 'a./b'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                safe_relative(path)

    def test_integrity_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                verify_archive(self.make_package(directory, corrupt=True))

    def test_install_and_preserve_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            package = self.make_package(directory)
            target = Path(directory) / 'Instalação com espaços'
            self.assertIsNone(install_payload(package, target))
            (target / 'parecer-pessoal.docx').write_bytes(b'keep')
            backup = install_payload(package, target)
            self.assertEqual((backup / 'parecer-pessoal.docx').read_bytes(), b'keep')
            self.assertTrue((target / 'manifest.json').is_file())

    def test_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            package = self.make_package(directory)
            target = Path(directory) / 'app'
            install_payload(package, target)
            (target / 'keep.txt').write_text('original')
            def fail(*args):
                raise OSError('simulated registration error')
            with self.assertRaises(OSError):
                install_payload(package, target, fail)
            self.assertEqual((target / 'keep.txt').read_text(), 'original')

    def test_refuse_unrecognized_target(self):
        with tempfile.TemporaryDirectory() as directory:
            package = self.make_package(directory)
            with self.assertRaises(ValueError):
                install_payload(package, Path(directory))

class WorkflowTests(unittest.TestCase):
    def test_invalid_documents(self):
        from document_processor import DocumentProcessor, DocumentProcessingError
        with tempfile.TemporaryDirectory() as directory:
            for name, data in [('empty.docx', b''), ('broken.docx', b'bad'), ('legacy.doc', b'bad')]:
                path = Path(directory) / name
                path.write_bytes(data)
                with self.assertRaises(DocumentProcessingError):
                    DocumentProcessor.process_file(str(path))

    def test_preview_and_loading(self):
        from app import render_results, render_hero, render_header, render_processing_status, process_documents
        from models import PPAMData
        data = PPAMData()
        data.tecnologia.cadifa_aprovada = False
        data.seguranca.estudo_desempenho.fabricante_teste = 'Empresa fictícia'
        rendered = render_results(data.model_dump())
        self.assertIn('Empresa fictícia', rendered)
        self.assertIn('>Não</strong>', rendered)
        self.assertIn('Não localizado', rendered)
        self.assertNotIn('pronto para download', rendered)
        self.assertNotIn('45%', render_hero())
        self.assertNotIn('45%', render_header())
        self.assertNotIn('23%', render_hero(23))
        self.assertIn('Processamento 23% Local', render_header(23))
        self.assertIn('class="hero-showcase"', render_hero())
        self.assertIn('Parecer Público de', render_hero())
        self.assertNotIn('loader-ring', render_hero())
        self.assertNotIn('active', render_processing_status())
        processing = render_processing_status(32, 'Leitura de 2 de 4 arquivo(s) concluída', 4)
        self.assertIn('2 de 4 arquivos analisados', processing)
        self.assertIn('50%', processing)
        self.assertIn('active', processing)
        self.assertIn('erro', process_documents(None, None, None, None)[0])

    def test_docx_presentations(self):
        from models import PPAMData
        from template_filler import TemplateFiller
        from docx import Document
        from docx.oxml.ns import qn
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'generated.docx'
            data = PPAMData()
            data.sumario.apresentacoes = ['50 mg/ml - 25 ampolas', '50 mg/ml - 36 ampolas']
            TemplateFiller().fill(data, str(path))
            doc = Document(path)
            selected = [p for p in doc.paragraphs if p.text.strip().rstrip('.;') in data.sumario.apresentacoes]
            self.assertEqual(len(selected), 2)
            for paragraph in selected:
                self.assertTrue(paragraph._p.xpath('./w:pPr/w:numPr'))
                for run in paragraph.runs:
                    if run.text:
                        self.assertEqual(str(run.font.color.rgb), '000000')

if __name__ == '__main__':
    unittest.main()
