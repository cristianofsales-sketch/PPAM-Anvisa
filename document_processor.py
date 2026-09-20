"""
document_processor.py — Extração de texto de PDF, Word e Imagem (100% local).
Detecta formato e extrai texto localmente utilizando Python Libraries.
"""

import re
import logging
from pathlib import Path
from typing import List

import pdfplumber
from docx import Document
from PIL import Image, ImageOps

# Inicializado somente quando uma imagem precisa de OCR.
ocr_engine = None

from config import (
    MAX_CHARS_PER_CHUNK,
    MIN_PDF_TEXT_LENGTH,
    SUPPORTED_EXTENSIONS,
)

logger = logging.getLogger(__name__)


class DocumentProcessingError(ValueError):
    """Mensagem segura de validação; nunca deve ser usada como texto extraído."""


class DocumentProcessor:
    """Extrai texto de PDF, Word e Imagem usando bibliotecas locais."""

    @staticmethod
    def process_file(file_path: str) -> str:
        """Detecta o tipo de arquivo e extrai o texto."""
        ext = Path(file_path).suffix.lower()

        if ext == ".doc":
            raise DocumentProcessingError("O formato .doc legado não é suportado. Converta para .docx ou PDF pesquisável.")
        if ext not in SUPPORTED_EXTENSIONS:
            raise DocumentProcessingError(f"Formato não suportado: {ext or '(sem extensão)'}. Use DOCX, PDF pesquisável ou imagem.")
        if not Path(file_path).is_file():
            raise DocumentProcessingError("O arquivo não está disponível. Anexe-o novamente.")
        if Path(file_path).stat().st_size == 0:
            raise DocumentProcessingError("O arquivo está vazio. Envie um documento com conteúdo.")

        file_type = SUPPORTED_EXTENSIONS[ext]

        try:
            if file_type == "pdf":
                text = DocumentProcessor._process_pdf(file_path)
            elif file_type == "docx":
                text = DocumentProcessor._process_docx(file_path)
            elif file_type == "image":
                text = DocumentProcessor._process_image(file_path)
            if not text or not text.strip():
                raise DocumentProcessingError("Nenhum texto legível foi encontrado. Envie um documento pesquisável ou uma imagem mais nítida.")
            return text
        except DocumentProcessingError:
            raise
        except Exception as exc:
            # Não registrar caminhos, texto clínico ou mensagens de bibliotecas
            # que possam incorporar conteúdo do documento.
            logger.error("Falha na leitura de documento: formato=%s tipo=%s", ext, type(exc).__name__)
            raise DocumentProcessingError("Não foi possível ler o arquivo. Verifique se ele está corrompido, protegido ou em formato incompatível.") from exc

    @staticmethod
    def _process_pdf(file_path: str) -> str:
        """Extrai texto de PDF usando pdfplumber."""
        text_parts = []

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)

        full_text = "\n\n".join(text_parts).strip()

        # PDF escaneado (sem OCR avançado local por padrão, apenas aviso)
        if len(full_text) < MIN_PDF_TEXT_LENGTH:
            raise DocumentProcessingError("O PDF contém texto insuficiente e pode ser escaneado. Converta para PDF pesquisável antes de anexar; OCR de páginas PDF não está disponível nesta versão.")
            
        return full_text

    @staticmethod
    def _process_docx(file_path: str) -> str:
        """Extrai texto de documentos Word."""
        doc = Document(file_path)
        text_parts = []

        for paragraph in doc.paragraphs:
            text_parts.append(paragraph.text)

        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells)
                text_parts.append(row_text)

        return "\n\n".join(text_parts).strip()

    @staticmethod
    def _process_image(file_path: str) -> str:
        """Transcreve imagem usando RapidOCR (Local ONNXRuntime)."""
        global ocr_engine
        if ocr_engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                ocr_engine = RapidOCR()
            except Exception as exc:
                logger.error("Falha ao inicializar OCR: tipo=%s", type(exc).__name__)
                raise DocumentProcessingError("O OCR local não está disponível. Repare a instalação ou envie DOCX/PDF pesquisável. Código: OCR_INDISPONIVEL.") from exc
            
        logger.info("Iniciando OCR local de imagem.")
        try:
            # Imagens pequenas perdem os espaços entre palavras no OCR. A ampliação
            # preserva a geometria da linha sem inventar ou segmentar palavras.
            with Image.open(file_path) as source:
                prepared = DocumentProcessor._prepare_image_for_ocr(source)
                result, _ = ocr_engine(prepared)
            if not result:
                raise DocumentProcessingError("O OCR não encontrou texto legível na imagem. Envie uma imagem mais nítida ou um documento pesquisável.")
            
            # result é uma lista onde index 1 é o texto detectado
            text_lines = [line[1] for line in result if len(line) >= 2]
            return "\n".join(text_lines).strip()
        except DocumentProcessingError:
            raise
        except Exception as exc:
            logger.error("Falha no OCR: tipo=%s", type(exc).__name__)
            raise DocumentProcessingError("Falha ao reconhecer o texto da imagem. Tente outra imagem ou envie DOCX/PDF pesquisável. Código: OCR_FALHOU.") from exc

    @staticmethod
    def _prepare_image_for_ocr(image: Image.Image) -> Image.Image:
        """Corrige orientação e amplia imagens pequenas para preservar espaços."""
        prepared = ImageOps.exif_transpose(image).convert("RGB")
        width, height = prepared.size
        if width <= 0 or height <= 0:
            return prepared

        # A hipótese foi validada nos arquivos reais: 2x recupera os espaços.
        # O limite impede consumo excessivo de memória em imagens já grandes.
        scale = min(2.0, 3200.0 / max(width, height))
        if scale <= 1.0:
            return prepared.copy()
        return prepared.resize(
            (round(width * scale), round(height * scale)),
            Image.Resampling.LANCZOS,
        )

    @staticmethod
    def process_multiple_files(file_paths: List[str]) -> str:
        """Processa múltiplos arquivos e concatena o texto."""
        all_text = []

        for fp in file_paths:
            text = DocumentProcessor.process_file(fp)
            all_text.append(f"--- DOCUMENTO: {Path(fp).name} ---\n\n{text}")

        return "\n\n".join(all_text)

    @staticmethod
    def extract_sections(text: str) -> dict:
        """Identifica seções do Parecer Técnico por numeração (2.4, 2.5, 2.6, etc.)."""
        sections = {}
        current_section = "geral"
        current_text = []

        section_pattern = re.compile(r'^(\d+\.\d+(?:\.\d+)?)\s+(.+)')

        for line in text.split("\n"):
            match = section_pattern.match(line.strip())
            if match:
                if current_text:
                    sections[current_section] = "\n".join(current_text)
                current_section = match.group(1)
                current_text = [line]
            else:
                current_text.append(line)

        if current_text:
            sections[current_section] = "\n".join(current_text)

        return sections

    @staticmethod
    def chunk_text(text: str, max_chars: int = MAX_CHARS_PER_CHUNK) -> List[str]:
        """Divide texto longo em chunks."""
        if len(text) <= max_chars:
            return [text]

        chunks = []
        paragraphs = text.split("\n\n")
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) > max_chars:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para

        if current_chunk:
            chunks.append(current_chunk)

        return chunks
