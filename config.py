"""
config.py — Configuração centralizada da aplicação PPAM.
Todas as constantes, parâmetros e listas de sigilo ficam aqui.
"""

import os
import sys
from pathlib import Path

# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================

# Limite seguro de caracteres por requisição (~30k tokens)
MAX_CHARS_PER_CHUNK = 80000

# Limite mínimo de texto para considerar extração de PDF bem-sucedida
MIN_PDF_TEXT_LENGTH = 100

# ============================================================
# CAMINHOS
# ============================================================

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
TEMPLATE_DIR = BASE_DIR / "templates"
DEFAULT_TEMPLATE = TEMPLATE_DIR / "FORM-754.POP-F-ANVISA-083_V.03_1_2.docx"

# ============================================================
# PADRÕES DE TEXTO INSTRUTIVO NO TEMPLATE (devem ser removidos)
# ============================================================

INSTRUCTION_PATTERNS = [
    r"Manter esta frase apenas nos casos em que houver Cadifa aprovada\.?",
    r"Manter este item apenas quando não tiver sido apresentado estudo de bioequivalência.*",
    r"\[descrição da apresentação\]",
    r"Modelo de parecer público aplicável a medicamentos genéricos não inéditos e medicamentos similares\.?",
    r"Manter este item apenas quando.*",
    r"Caso contrário.*este tópico deve ser retirado\.?",
]

# ============================================================
# BLACKLIST DE SIGILO — Termos que NUNCA podem aparecer no PPAM
# ============================================================

SIGILO_BLACKLIST = [
    "etapa de síntese", "etapas de síntese", "síntese química",
    "parâmetro de processo", "parâmetros industriais",
    "validação de processo de esterilização",
    "controle em processo", "controles em processo",
    "relatório de produção", "relatório interno",
    "variável dependente", "variáveis dependentes",
    "composição quantitativa", "quantidade de excipiente",
    "fórmula mestra", "fórmula-mestra",
    "rendimento do processo", "rendimento industrial",
    "especificação de matéria-prima",
    "procedimento operacional padrão",
    "POP de fabricação",
    "detalhamento das etapas físicas",
    "síntese física",
    "descrição detalhada das etapas",
    "controle de qualidade executado pelo fabricante do IFA",
]

# ============================================================
# FORMATOS SUPORTADOS
# ============================================================

SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".tiff": "image",
    ".bmp": "image",
}

SUPPORTED_EXTENSIONS_LIST = sorted(SUPPORTED_EXTENSIONS.keys())
