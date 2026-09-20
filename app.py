"""
app.py — Interface de automação do PPAM.
Redesign Dark Theme conforme template fornecido pelo usuário (100% Match da Imagem).
"""

import os
import base64
import json
import re
import tempfile
import logging
import time
import shutil
from pathlib import Path
from contextlib import nullcontext
from html import escape

# A interface e os recursos visuais não precisam de conexões externas.
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
os.environ["HF_HUB_OFFLINE"] = "1"

import gradio as gr
from docx import Document

from config import (
    DEFAULT_TEMPLATE,
    SUPPORTED_EXTENSIONS_LIST,
)
from document_processor import DocumentProcessor, DocumentProcessingError
from extractor import PPAMExtractor
from template_filler import TemplateFiller
from audit import AuditLogger
from models import PPAMData

try:
    from desktop_runtime import processing_job
except ImportError:
    processing_job = nullcontext

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)

# Porta oficial da aplicação definitiva.
DEFAULT_SERVER_PORT = 7860


def _embedded_asset(relative_path: str) -> str:
    """Retorna um recurso visual local sem criar dependência de servidor externo."""
    root = Path(getattr(__import__("sys"), "_MEIPASS", Path(__file__).resolve().parent))
    path = root / relative_path
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


HERO_REFERENCE_IMAGE = _embedded_asset("assets/final.png")
APP_ICON_IMAGE = _embedded_asset("assets/ppam-app-icon-v1.png")


def _get_file_paths(file_list):
    if not file_list:
        return []
    if isinstance(file_list, (str, os.PathLike)):
        file_list = [file_list]
    paths = []
    for f in file_list:
        if isinstance(f, (str, os.PathLike)):
            paths.append(str(f))
        elif hasattr(f, "name"):
            paths.append(f.name)
    return paths

def process_documents(parecer_files, bula_files, publicacao_files, outros_files, numero_registro_ms=""):
    """API síncrona da extração; ainda não declara um documento pronto."""
    steps = process_documents_steps(
        parecer_files, bula_files, publicacao_files, outros_files, numero_registro_ms
    )
    while True:
        try:
            next(steps)
        except StopIteration as completed:
            return completed.value


def process_documents_steps(
    parecer_files, bula_files, publicacao_files, outros_files, numero_registro_ms=""
):
    with processing_job():
        return (yield from _process_documents_steps(
            parecer_files, bula_files, publicacao_files, outros_files, numero_registro_ms
        ))


def _process_documents_steps(
    parecer_files, bula_files, publicacao_files, outros_files, numero_registro_ms=""
):
    """Processa o pedido por etapas e informa apenas avanços já concluídos."""
    started = time.perf_counter()
    groups = dict(zip(("parecer", "bula", "publicacao", "outros"),
                      map(_get_file_paths, (parecer_files, bula_files, publicacao_files, outros_files))))
    stats = {"enviados": sum(map(len, groups.values())), "processados": 0, "falhas": 0,
             "arquivos": [], "duracao_segundos": 0.0}
    if not groups["parecer"]:
        return {"erro": "É necessário enviar pelo menos o Parecer Técnico.", "_processing": stats}, ""

    yield 0, "Preparando o processamento"
    texts = {}
    for category, paths in groups.items():
        parts = []
        for path in paths:
            info = {"categoria": category, "arquivo": Path(path).name}
            try:
                text = DocumentProcessor.process_file(path)
                parts.append(f"--- DOCUMENTO: {Path(path).name} ---\n\n{text}")
                info["status"] = "processado"
                stats["processados"] += 1
            except DocumentProcessingError as exc:
                info.update(status="falha", motivo=str(exc))
                stats["falhas"] += 1
            except Exception as exc:
                logger.error("Falha inesperada de leitura: tipo=%s", type(exc).__name__)
                info.update(status="falha", motivo="Falha ao ler o documento. Verifique o arquivo e tente novamente.")
                stats["falhas"] += 1
            stats["arquivos"].append(info)
            done = stats["processados"] + stats["falhas"]
            yield round(65 * done / stats["enviados"]), f"Leitura de {done} de {stats['enviados']} arquivo(s) concluída"
        texts[category] = "\n\n".join(parts)

    stats["duracao_segundos"] = time.perf_counter() - started
    if stats["falhas"]:
        return {"erro": "Não foi possível concluir o pedido. Corrija ou remova os anexos indicados e tente novamente.", "_processing": stats}, ""
    try:
        data = PPAMExtractor().extract_all(
            *(texts[key] for key in groups),
            numero_registro_ms=numero_registro_ms,
        )
    except Exception as exc:
        logger.error("Falha na extração estruturada: tipo=%s", type(exc).__name__)
        return {"erro": "Não foi possível estruturar os dados do parecer. Revise os anexos e tente novamente. Código: EXTRACAO_FALHOU.", "_processing": stats}, ""
    stats["duracao_segundos"] = time.perf_counter() - started
    preview = data.model_dump()
    preview["_alertas"] = data.divergencias_documentos or []
    preview["_source_files"] = {category: [Path(path).name for path in paths] for category, paths in groups.items()}
    preview["_processing"] = stats
    yield 85, "Prévia disponível; preparando a geração do documento"
    return preview, json.dumps(preview, ensure_ascii=False)

def render_header(progress=None):
    """Exibe o status local e acrescenta o percentual durante o processo."""
    if progress is None:
        return HEADER_HTML
    return HEADER_HTML.replace("Processamento Local", f"Processamento {progress}% Local")


def render_hero(progress=None, stage=""):
    """Mantém o hero fixo; o andamento aparece exclusivamente no cabeçalho."""
    return HERO_HTML


def render_processing_status(progress=None, stage="", total_files=0):
    """Mostra a proporção real de arquivos lidos durante o processamento."""
    if progress is None or total_files <= 0:
        return ""
    match = re.search(r"Leitura de\s+(\d+)\s+de\s+(\d+)", stage or "", re.IGNORECASE)
    if match:
        processed = min(int(match.group(1)), total_files)
    elif progress >= 65:
        processed = total_files
    else:
        processed = 0
    file_percent = round(100 * processed / total_files)
    description = escape(stage or "Preparando a análise local")
    return f'''<div class="processing-status active" role="status" aria-live="polite">
      <div class="processing-spinner" aria-hidden="true"></div>
      <div class="processing-copy">
        <div class="processing-line"><strong>{processed} de {total_files} arquivos analisados</strong><b>{file_percent}%</b></div>
        <div class="processing-track"><span style="width:{file_percent}%"></span></div>
        <small>{description}</small>
      </div>
    </div>'''


def render_results(data=None, file_count=0, elapsed=0):
    """Cria a prévia integral e sinaliza em vermelho apenas dados ausentes."""
    data = data or {}
    labels = {
        "empresa": "Empresa", "nome_medicamento": "Medicamento", "principio_ativo": "Princípio ativo",
        "categoria": "Categoria", "forma_farmaceutica": "Forma farmacêutica", "concentracao": "Concentração",
        "rdc_numero": "RDC", "rdc_data": "Data da RDC", "composicao": "Composição",
        "excipientes": "Excipientes", "apresentacoes": "Apresentações", "medicamento_referencia": "Medicamento de referência",
        "cadifa_aprovada": "CADIFA aprovada", "controle_qualidade_ifa": "Controle de qualidade do IFA",
        "validacoes_metodos_ifa": "Validações do IFA", "processo_fabricacao": "Processo de fabricação",
        "controle_qualidade_produto": "Controle de qualidade do produto", "validacoes_metodos_medicamento": "Validações do medicamento",
        "embalagem_primaria": "Embalagem primária", "tipo_comprovacao": "Tipo de comprovação",
        "certificado_equivalencia": "Certificado de equivalência", "centro_equivalencia": "Centro de equivalência",
        "certificado_perfil_dissolucao": "Perfil de dissolução", "houve_bioequivalencia": "Houve bioequivalência",
        "base_legal_bioisencao": "Base legal da bioisenção", "numero_registro_ms": "Registro MS",
        "nome_produto": "Produto publicado",
        "dou_numero": "DOU", "dou_data": "Data do DOU", "resolucao_re_numero": "Resolução-RE",
        "resolucao_re_data": "Data da Resolução-RE", "rdc_aplicavel": "RDC aplicável",
    }
    sections = [("Sumário", data.get("sumario", {})), ("Tecnologia farmacêutica", data.get("tecnologia", {})),
                ("Segurança e eficácia", data.get("seguranca", {})), ("Publicação da decisão", data.get("publicacao", {}))]
    rows = []
    missing = 0
    for title, section in sections:
        section_rows = []
        fields = []
        for key, value in section.items():
            if isinstance(value, dict):
                fields.extend((f"{key} — {nested}", item) for nested, item in value.items())
            else:
                fields.append((key, value))
        for key, value in fields:
            if key == "campos_baixa_confianca":
                shown = "; ".join(value) if value else "Nenhum campo sinalizado"
                section_rows.append(f'<div class="result-field"><span>Campos de baixa confiança</span><strong>{escape(shown)}</strong></div>')
                continue
            absent = value is None or value == "" or value == []
            if absent:
                shown = "Não localizado"
                missing += 1
            elif isinstance(value, list):
                shown = "; ".join(map(str, value))
            elif isinstance(value, bool):
                shown = "Sim" if value else "Não"
            else:
                shown = str(value)
            section_rows.append(f'<div class="result-field"><span>{escape(labels.get(key, key.replace("_", " ").title()))}</span><strong class="{"missing" if absent else ""}">{escape(shown)}</strong></div>')
        if section_rows:
            rows.append(f'<section class="result-section"><h3>{escape(title)}</h3>{"".join(section_rows)}</section>')
    if data.get("divergencias_documentos"):
        rows.append('<section class="result-section"><h3>Divergências entre documentos</h3>' + ''.join(f'<p class="result-alert">{escape(str(item))}</p>' for item in data["divergencias_documentos"]) + '</section>')
    alert = f'<div class="result-alert">{missing} campo(s) não localizado(s): revise os itens destacados em vermelho.</div>' if missing else '<div class="result-ok">Revise os dados extraídos antes de utilizar o parecer.</div>'
    generated = data.get("_document", {})
    ready = bool(generated.get("size"))
    heading = "Parecer gerado com sucesso" if ready else "Prévia disponível para revisão"
    subtitle = "Documento processado localmente — pronto para download" if ready else "Revise os dados e clique em Gerar documento PPAM"
    status = "Concluído" if ready else "Prévia disponível"
    stats = data.get("_processing", {})
    file_count = stats.get("processados", file_count)
    elapsed = stats.get("duracao_segundos", elapsed)
    size_html = f'<p>Tamanho <b>{generated["size"] / 1024:.1f} KB</b></p>' if ready else '<p>Arquivo <b>Ainda não gerado</b></p>'
    return f'''<div class="result-layout">
      <div class="result-success"><div class="success-check">✓</div><h1>{heading}</h1><p>{subtitle}</p></div>
      <div class="result-grid"><article class="document-preview"><div class="preview-head"><h2>Prévia do Documento</h2><span>● {status}</span></div>{alert}<div class="preview-content">{"".join(rows)}</div></article>
      <aside class="result-side"><section><h3>INFORMAÇÕES DO PROCESSAMENTO</h3><p>Arquivos enviados <b>{stats.get('enviados', file_count)}</b></p><p>Arquivos processados <b>{file_count}</b></p><p>Falhas <b>{stats.get('falhas', 0)}</b></p><p>Tempo de processamento <b>{elapsed:.1f}s</b></p><p>Categoria <b>Gen. Não Inéditos Bioisentos</b></p><p>Modalidade <b>100% Local</b></p><p>Status <b class="complete">{status}</b></p></section><section><h3>DOCUMENTO GERADO</h3><p>Formato <b>DOCX</b></p>{size_html}</section></aside></div></div>'''


def generate_ppam(preview_data_str):
    if not preview_data_str:
        return None, {"erro": "Nenhum dado para processar."}
    
    try:
        preview_data = json.loads(preview_data_str)
    except:
        return None, {"erro": "Dados inválidos."}

    preview_data.pop("_arquivo_dados", None)
    preview_data.pop("_alertas", None)

    if "erro" in preview_data:
        return None, preview_data

    data = PPAMData(**preview_data)
    template_path = str(DEFAULT_TEMPLATE)
    
    temp_dir = tempfile.mkdtemp()
    output_docx = os.path.join(temp_dir, "PPAM_GERADO.docx")
    audit_path = os.path.join(temp_dir, "auditoria.json")

    filler = TemplateFiller(template_path)
    filler.fill(data, output_docx)

    source_files = {"arquivos": "documentos enviados"}
    log_data = AuditLogger.generate_log(data, source_files)
    AuditLogger.save_log(log_data, audit_path)

    return output_docx, log_data


# ============================================================
# CSS CUSTOMIZADO (100% Igual à Imagem)
# ============================================================
CUSTOM_CSS = r"""

*, *::before, *::after { box-sizing: border-box; }

body, .gradio-container {
    font-family: 'Inter', sans-serif !important;
    background: #101623 !important; /* Cor exata do monitor escuro no fundo */
    color: #FFFFFF !important;
    margin: 0 !important;
    padding: 0 !important;
    min-height: 100vh !important;
}

footer.svelte-1h775ko { display: none !important; }
.gradio-container > .main { padding: 0 !important; }

/* ── HEADER ── */
header.ppam-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.25rem 2.5rem;
    background: #101623 !important;
}
.logo {
    display: flex; align-items: center; gap: 0.75rem;
    font-weight: 700; font-size: 1.25rem; letter-spacing: -0.02em;
}
.logo-icon {
    width: 36px; height: 36px; border-radius: 8px;
    background: linear-gradient(135deg, #3B82F6 0%, #06B6D4 100%);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem; color: white;
    overflow: hidden;
}
.logo-icon img { width: 100%; height: 100%; display: block; object-fit: cover; }
.logo-text { color: #FFFFFF; }
.logo-text span { color: #06B6D4; font-weight: bold; }
.status-badge {
    display: flex; align-items: center; gap: 0.5rem;
    padding: 0.4rem 1rem;
    background: rgba(0, 172, 193, 0.15);
    border: 1px solid rgba(0, 172, 193, 0.3);
    border-radius: 100px;
    font-size: 0.8rem; font-weight: 500;
    color: #80DEEA;
}
.status-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #00ACC1;
}

/* ── MAIN WRAPPER ── */
#ppam-main {
    max-width: 1400px;
    margin: 0 auto 2rem auto;
    width: 95%;
    padding: 3rem 4rem 3rem 4rem;
    background: #E5E7EB !important; /* O fundo super claro conforme pedido na imagem */
    border-radius: 12px;
}

/* ── HERO FRAME (TÍTULO) ── */
.hero-frame {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    padding: 1.25rem 2rem;
    border: 1.5px solid #475569; /* Borda precisa do frame */
    border-radius: 8px;
    background: transparent;
    margin-bottom: 2rem;
}
.frame-icon svg { width: 32px; height: 32px; stroke: #3B82F6; }
.frame-title {
    font-size: clamp(1.2rem, 2.5vw, 1.8rem);
    font-weight: 800;
    color: #475569; /* Azul bem escuro acinzentado */
    margin: 0;
    letter-spacing: -0.01em;
}

/* ── SIDE-BY-SIDE ── */
.side-by-side {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 3.5rem;
    width: 100%;
}
.sbs-left { flex: 1; }
.sbs-left .subtitle {
    font-size: 1.15rem;
    color: #06B6D4;
    font-weight: 600;
    margin-bottom: 0.75rem;
}
.sbs-left .local-info {
    font-size: 0.95rem;
    color: #94A3B8;
}

/* ── LOADER BOX ── */
.loader-box {
    display: flex;
    align-items: center;
    gap: 2rem;
    background: #1E293B; /* Painel escuro do lado direito */
    padding: 1.5rem 2.5rem;
    border-radius: 16px;
    width: 500px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.15);
    /* Inicia invisivel e liga com a classe active via JS */
    opacity: 0; 
    pointer-events: none;
    transition: opacity 0.3s ease;
}
.loader-box.active { opacity: 1; pointer-events: auto; }

.loader-iconsvg {
    width: 60px; height: 60px;
}
.loader-anim {
    position: relative;
    width: 75px; height: 75px;
}
.loader-ring {
    width: 100%; height: 100%;
    border-radius: 50%;
    background: conic-gradient(#06B6D4 var(--progress, 0%), rgba(59, 130, 246, .25) 0);
    position: relative;
}
.loader-ring::after {
    content: '';
    position: absolute;
    inset: 5px;
    border-radius: 50%;
    background: #1E293B;
}
.loader-value {
    position: absolute;
    inset: 0;
    z-index: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #FFFFFF;
    font-size: 1.3rem;
    font-weight: 800;
}
.loader-text h3 { margin: 0 0 0.5rem; font-size: 1.15rem; font-weight: 600; color: white; }
.loader-text p { margin: 0; font-size: 0.95rem; color: #94A3B8; line-height: 1.4; }

/* ── UPLOADS: SECTION ── */
.upload-title {
    font-size: 1.25rem; font-weight: 600; 
    color: #FFFFFF; /* Brutalmente idêntico à imagem (Branco no fundo cinza) */
    text-shadow: 0 1px 3px rgba(0,0,0,0.1); 
    margin-bottom: 1.5rem; text-align: center; width: 100%;
}
.upload-row {
    display: grid !important;
    grid-template-columns: repeat(4, 1fr) !important;
    gap: 0.75rem !important;
    margin-bottom: 2rem !important;
    width: 100%;
}

/* Redefinição Absoluta do gr.Files para o look da imagem */
.upload-slim {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
}
.upload-slim label { display: none !important; }
.upload-slim [data-testid="upload"] {
    position: relative;
    height: 75px !important;
    min-height: 75px !important;
    background: #1C2433 !important; /* Mesma cor da imagem para os botões */
    border: 1px solid #334155 !important;
    border-radius: 8px !important;
    display: flex !important;
    flex-direction: row !important;
    padding: 0 !important;
    overflow: hidden !important;
    cursor: pointer;
}
.upload-slim [data-testid="upload"]:hover {
    border-color: #06B6D4 !important;
    background: #232C3A !important;
}
/* Limpa os filhos padroes do Gradio */
.upload-slim [data-testid="upload"] > * { display: none !important; }

/* METADE ESQUERDA: Texto + Icone simulado via AFTER/BEFORE (Dependendo da classe) */
.upload-slim [data-testid="upload"]::before {
    display: flex; align-items: center; justify-content: center;
    flex: 1; height: 100%;
    color: #94A3B8; font-size: 0.85rem; font-weight: 500;
    text-align: center; white-space: pre-wrap; line-height: 1.3;
    border-right: 1px solid #334155; padding: 0.5rem;
}
/* METADE DIREITA: "Clique ou arraste" (Igual pra todos) */
.upload-slim [data-testid="upload"]::after {
    content: '↑\\A Clique ou\\A arraste';
    white-space: pre; display: flex; align-items: center; justify-content: center;
    text-align: center; flex: 1; height: 100%;
    color: #64748B; font-size: 0.75rem; font-weight: 500; line-height: 1.3;
}

/* Injeção dos textos esquerdos nativos de cada campo */
.up-1 [data-testid="upload"]::before { content: '📄 Parecer Técnico\\A(Obrigatório)'; }
.up-2 [data-testid="upload"]::before { content: '💊 Bula do\\AMedicamento'; }
.up-3 [data-testid="upload"]::before { content: '📰 Publicação DOU'; }
.up-4 [data-testid="upload"]::before { content: '📁 Outros\\ADocumentos'; }


/* File Preview ativo - sobrepor o conteudo se houver preview */
.upload-slim .file-preview {
    background: #1C2433 !important;
    color: white !important; height: 75px !important; border: 1px solid #06B6D4 !important; border-radius: 8px !important; font-size: 0.8rem !important; padding: 10px !important;
}
.upload-slim .file-preview * { color: white !important; }

/* Arquivos já anexados: substitui o preview claro padrão do Gradio. */
.upload-slim:has(.file-preview) {
    height: 76px !important;
    min-height: 76px !important;
    background: #1C2433 !important;
    border: 1px solid #06B6D4 !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}
.upload-slim .file-preview-holder,
.upload-slim .file-preview,
.upload-slim .file-preview tbody,
.upload-slim .file-preview tr,
.upload-slim .file-preview td {
    background: #1C2433 !important;
    color: #F8FAFC !important;
}
.upload-slim .file-preview-holder {
    width: 100% !important;
    height: 74px !important;
    max-height: 74px !important;
    padding: 0 .8rem !important;
    display: flex !important;
    align-items: center !important;
    overflow: hidden !important;
}
.upload-slim .file-preview {
    margin: 0 !important;
    font-size: .82rem !important;
}
.upload-slim .file-preview .filename {
    min-width: 0 !important;
    color: #F8FAFC !important;
}
.upload-slim .file-preview .stem,
.upload-slim .file-preview .ext { color: #F8FAFC !important; }
.upload-slim .file-preview .download,
.upload-slim .file-preview .download a { color: #94E7F4 !important; }
.upload-slim .label-clear-button {
    color: #CBD5E1 !important;
    font-size: 1.2rem !important;
}
.upload-slim .label-clear-button:hover { color: #FFFFFF !important; }


/* ── BOTAO CTA ── */
#btn-extract, #btn-generate {
    width: 100% !important;
    padding: 1.25rem !important;
    background: linear-gradient(90deg, #3B82F6 0%, #06B6D4 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-size: 1.15rem !important;
    font-weight: 700 !important;
    cursor: pointer !important;
    box-shadow: 0 4px 15px rgba(6,182,212, 0.4) !important;
    display: block !important;
}
#btn-extract:hover, #btn-generate:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(6,182,212, 0.6) !important;
}
#btn-back {
    background: #1C2433 !important; border: 1px solid #334155 !important;
    color: white !important; border-radius: 10px !important;
    padding: 1rem 2rem !important; font-size: 1.05rem !important; font-weight: 500 !important;
}

/* Página de resultado */
#ppam-main:has(.result-layout) { background: transparent !important; padding: 1.5rem 4rem 2rem !important; }
.result-layout { color:#F8FAFC; max-width:1280px; margin:auto; }
.result-success { text-align:center; padding: .5rem 0 1.5rem; }
.success-check { margin:auto auto .65rem; width:58px; height:58px; border-radius:50%; display:grid; place-items:center; background:linear-gradient(135deg,#34D399,#00A878); color:#fff; font-size:2.3rem; font-weight:800; box-shadow:0 0 35px rgba(16,185,129,.55); }
.result-success h1 { margin:0; color:#fff; font-size:2rem; }
.result-success p { margin:.4rem 0 0; color:#A8B5C9; }
.result-grid { display:grid; grid-template-columns:1.7fr 1fr; gap:1.25rem; }
.document-preview,.result-side section { background:linear-gradient(145deg,#0D192B,#091321); border:1px solid #28415F; border-radius:14px; padding:1.5rem; box-shadow:0 12px 28px rgba(0,0,0,.2); }
.document-preview { border-color:#1672C8; }
.preview-head { display:flex; align-items:center; justify-content:space-between; gap:1rem; }
.preview-head h2 { margin:0; color:#fff; font-size:1.2rem; }
.preview-head span,.result-ok { color:#4ADE80; background:rgba(34,197,94,.1); border:1px solid rgba(34,197,94,.3); border-radius:999px; padding:.35rem .7rem; font-weight:700; font-size:.85rem; }
.result-alert { margin:1rem 0; padding:.65rem .8rem; color:#FCA5A5; background:rgba(239,68,68,.12); border:1px solid rgba(239,68,68,.4); border-radius:7px; font-size:.85rem; }
.result-ok { display:inline-block; margin:1rem 0; }
.preview-content { max-height:430px; overflow:auto; padding-right:.4rem; }
.result-section { margin:.9rem 0; padding:.8rem; border-radius:8px; background:rgba(30,41,59,.55); }
.result-section h3,.result-side h3 { margin:0 0 .55rem; color:#B8C5D9; font-size:.78rem; letter-spacing:.03em; text-transform:uppercase; }
.result-field,.result-side p { display:flex; justify-content:space-between; gap:1rem; margin:.35rem 0; padding-bottom:.35rem; border-bottom:1px solid rgba(148,163,184,.15); font-size:.87rem; }
.result-field span,.result-side p { color:#B8C5D9; }.result-field strong,.result-side b { color:#FFF; text-align:right; }.result-field strong.missing { color:#FF6B6B; }.result-side b.complete { color:#4ADE80; }
.result-side { display:grid; gap:.7rem; align-content:start; }.result-side section { padding:1.1rem; }.result-side p:last-child { border:0; padding:0; }
#results-page #btn-generate { max-width:400px; margin:1.25rem auto .75rem; background:linear-gradient(90deg,#12C96B,#08B9D5) !important; }
#results-page #btn-back { display:block; max-width:400px; width:100%; margin:.75rem auto 1.25rem; background:#0D192B !important; }

/* Compatibilidade com a estrutura do Gradio 5.x. */
footer { display: none !important; }
.gradio-container > .main {
    max-width: none !important;
    width: 100% !important;
    margin: 0 !important;
}
.loader-box { display: flex; opacity: 1; pointer-events: auto; }
.loader-box.active { display: flex; opacity: 1; pointer-events: auto; }
.loader-box:not(.active) .loader-anim,
.loader-box:not(.active) .loader-text { display: none; }
.upload-slim > label { display: none !important; }
.upload-slim > button[aria-dropeffect="copy"] {
    position: relative;
    width: 100% !important;
    height: 76px !important;
    min-height: 76px !important;
    background: #1C2433 !important;
    border: 1px solid #334155 !important;
    border-radius: 8px !important;
    display: flex !important;
    flex-direction: row !important;
    padding: 0 !important;
    overflow: hidden !important;
    color: transparent !important;
}
.upload-slim > button[aria-dropeffect="copy"]:hover {
    background: #232C3A !important;
    border-color: #06B6D4 !important;
}
.upload-slim > button[aria-dropeffect="copy"] .wrap { display: none !important; }
.upload-slim > button[aria-dropeffect="copy"]::before {
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 1;
    height: 100%;
    padding: .5rem;
    border-right: 1px solid #334155;
    color: #94A3B8;
    font-size: .85rem;
    font-weight: 500;
    line-height: 1.3;
    text-align: center;
    white-space: pre-wrap;
}
.upload-slim > button[aria-dropeffect="copy"]::after {
    content: '⇧\A Clique ou\A arraste';
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 1;
    height: 100%;
    color: #CBD5E1;
    font-size: .78rem;
    font-weight: 500;
    line-height: 1.2;
    text-align: center;
    white-space: pre;
}
.up-1 > button[aria-dropeffect="copy"]::before { content: '📄  Parecer Técnico'; }
.up-2 > button[aria-dropeffect="copy"]::before { content: '💊  Bula do Medicamento'; }
.up-3 > button[aria-dropeffect="copy"]::before { content: '📰  Publicação DOU'; }
.up-4 > button[aria-dropeffect="copy"]::before { content: '📁  Outros Documentos'; }

@media (max-width: 760px) {
    header.ppam-header { padding: 1rem 1.25rem; }
    .status-badge { font-size: .7rem; padding: .35rem .65rem; }
    #ppam-main { width: calc(100% - 2rem); padding: 1.5rem; }
    .hero-frame { padding: 1rem; gap: .75rem; }
    .frame-title { font-size: 1.25rem; }
    .side-by-side { align-items: stretch; flex-direction: column; gap: 1.5rem; }
    .loader-box { width: 100%; padding: 1.25rem; gap: 1rem; }
    .upload-row { grid-template-columns: 1fr 1fr !important; }
}

/* ── REFERÊNCIA FINAL: alterações exclusivamente visuais ── */
body, .gradio-container {
    background:
      radial-gradient(circle at 50% -20%, rgba(20,58,104,.34), transparent 48%),
      #071426 !important;
}
header.ppam-header {
    max-width: 1460px;
    width: calc(100% - 76px);
    margin: 0 auto;
    padding: 2rem 3rem 1.5rem;
    border-bottom: 1px solid rgba(148,163,184,.26);
}
.logo { font-size: 1.55rem; gap: 1rem; }
.logo-icon { width: 44px; height: 44px; border-radius: 11px; box-shadow: 0 8px 18px rgba(14,165,233,.28); }
.status-badge {
    padding: .65rem 1.25rem;
    border-color: rgba(6,182,212,.55);
    background: rgba(8,111,140,.22);
    color: #7DEBFA;
    font-size: 1rem;
}

#ppam-main {
    max-width: 1484px;
    width: calc(100% - 52px);
    margin: 1.75rem auto 1.75rem;
    padding: 0 0 4.4rem;
    overflow: hidden;
    background:
      radial-gradient(circle at 63% 30%, rgba(185,220,255,.40), transparent 36%),
      linear-gradient(115deg, #F2F7FC 0%, #E8F1FA 100%) !important;
    border: 1px solid rgba(255,255,255,.8);
    border-radius: 5px;
    box-shadow: 0 24px 70px rgba(0,0,0,.28);
}
#ppam-main > div, #ppam-main .form, #ppam-main .block { background: transparent !important; }
#ppam-main .styler {
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
}
#ppam-main .gr-group {
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
}

.hero-showcase {
    min-height: 455px;
    display: grid;
    grid-template-columns: minmax(0, 1.08fr) minmax(0, .92fr);
    align-items: center;
    gap: 3.4rem;
    padding: 0 8.8%;
}
.hero-art-window {
    position: relative;
    width: 100%;
    aspect-ratio: 617 / 434;
    overflow: hidden;
    border-radius: 42% 42% 30% 30% / 34% 34% 28% 28%;
    filter: drop-shadow(0 18px 32px rgba(30,82,128,.12));
}
.hero-art-source {
    position: absolute;
    width: 249% !important;
    max-width: none !important;
    height: auto !important;
    left: -25.9%;
    top: -30.4%;
}
.hero-copy { color: #07336A; padding-top: .2rem; }
.hero-ppam {
    position: relative;
    display: inline-block;
    margin: 0 0 .15rem;
    font-size: clamp(4.4rem, 6.5vw, 6.1rem);
    line-height: .9;
    font-weight: 1000;
    letter-spacing: -.075em;
    background: linear-gradient(180deg, #068DD0 0%, #004884 42%, #002D62 100%);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    filter: drop-shadow(0 3px 0 rgba(0,37,85,.16));
}
.hero-ppam::after {
    content: '✓';
    position: absolute;
    left: 57%; top: -4%;
    color: #09B96F;
    font-size: .42em;
    font-weight: 1000;
    text-shadow: 0 3px 0 #007F55;
}
.hero-copy h1 {
    margin: .55rem 0 .75rem;
    color: #07336A;
    font-size: clamp(2rem, 3vw, 3rem);
    line-height: 1.02;
    letter-spacing: -.035em;
    font-weight: 850;
}
.hero-lead { margin: 0 0 1.7rem; color: #5879A8; font-size: 1.25rem; line-height: 1.38; }
.hero-category { margin: 0; color: #07336A; font-size: 1.15rem; }
.hero-category strong { color: #07336A !important; }
.hero-local { margin: .35rem 0 0; color: #5879A8; font-size: 1rem; }

.upload-title { display: none !important; }
.upload-row {
    width: 85.4% !important;
    margin: 0 auto 1.25rem !important;
    gap: .8rem !important;
}
.upload-slim [data-testid="upload"],
.upload-slim > button[aria-dropeffect="copy"] {
    height: 100px !important;
    min-height: 100px !important;
    border: 1px solid #49617D !important;
    border-radius: 10px !important;
    background: linear-gradient(145deg, #10233A, #0B1A2E) !important;
    box-shadow: inset 0 0 0 4px rgba(255,255,255,.035), 0 6px 16px rgba(2,17,36,.14) !important;
}
.upload-slim [data-testid="upload"]::before,
.upload-slim > button[aria-dropeffect="copy"]::before {
    justify-content: flex-start;
    padding-left: 1.35rem;
    color: #F2F7FC;
    border-right-color: #40536C;
    font-size: .9rem;
}
.upload-slim [data-testid="upload"]::after,
.upload-slim > button[aria-dropeffect="copy"]::after {
    color: #F2F7FC;
    font-size: .86rem;
}
.upload-slim .file-preview-holder, .upload-slim .file-preview { height: 98px !important; max-height: 98px !important; }

#registro-ms {
    width: 85.4%;
    margin: .25rem auto 1rem !important;
    color: #07336A !important;
}
#registro-ms label span { color: #07336A !important; font-weight: 700 !important; }
#registro-ms textarea, #registro-ms input {
    min-height: 44px !important;
    color: #0F2744 !important;
    background: rgba(255,255,255,.76) !important;
    border: 1px solid #AFC3D9 !important;
    border-radius: 8px !important;
}
#btn-extract {
    width: 68.5% !important;
    min-height: 49px !important;
    margin: 0 auto !important;
    padding: .8rem 1rem !important;
    border-radius: 11px !important;
    font-size: 1.2rem !important;
    background: linear-gradient(90deg, #2582F5 0%, #08C0D8 100%) !important;
}
.processing-status {
    width: 68.5%;
    margin: .9rem auto 0;
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: .85rem 1.1rem;
    color: #EAF8FF;
    background: linear-gradient(145deg, #10233A, #0B1A2E);
    border: 1px solid #2C7594;
    border-radius: 11px;
    box-shadow: 0 8px 22px rgba(2,17,36,.18);
    animation: processing-enter .28s ease-out both;
}
.processing-spinner {
    width: 32px;
    height: 32px;
    flex: 0 0 32px;
    border: 3px solid rgba(125,235,250,.22);
    border-top-color: #20D6EA;
    border-radius: 50%;
    animation: processing-spin .9s linear infinite;
}
.processing-copy { flex: 1; min-width: 0; }
.processing-line { display: flex; justify-content: space-between; gap: 1rem; font-size: .9rem; }
.processing-line strong, .processing-line b { color: #F8FCFF !important; }
.processing-track { height: 7px; margin: .45rem 0 .3rem; overflow: hidden; background: #263D59; border-radius: 999px; }
.processing-track span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg,#2582F5,#08C0D8); transition: width .35s ease; }
.processing-copy small { display: block; color: #A8C7D9; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
@keyframes processing-spin { to { transform: rotate(360deg); } }
@keyframes processing-enter { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: translateY(0); } }

@media (max-width: 900px) {
    header.ppam-header { width: calc(100% - 28px); padding: 1.25rem .75rem; }
    #ppam-main { width: calc(100% - 28px); padding-bottom: 2rem; }
    .hero-showcase { grid-template-columns: 1fr; gap: 1.25rem; padding: 2rem 8%; }
    .hero-art-window { max-width: 620px; margin: auto; }
    .hero-copy { text-align: center; }
    .upload-row { grid-template-columns: 1fr 1fr !important; width: 90% !important; }
    #registro-ms, #btn-extract, .processing-status { width: 90% !important; }
}
"""

HEADER_HTML = f"""
<header class="ppam-header">
  <div class="logo">
    <div class="logo-icon"><img src="{APP_ICON_IMAGE}" alt="Ícone PPAM"></div>
    <div class="logo-text">PPAM <span>·</span> Anvisa</div>
  </div>
  <div class="status-badge">
    <span class="status-dot"></span>
    Processamento Local
  </div>
</header>
"""

HERO_HTML = f"""
<section class="hero-showcase">
  <div class="hero-art-window" aria-hidden="true">
    <img class="hero-art-source" src="{HERO_REFERENCE_IMAGE}" alt="">
  </div>
  <div class="hero-copy">
    <div class="hero-ppam" aria-label="PPAM">PPAM</div>
    <h1>Parecer Público de<br>Avaliação de Medicamento</h1>
    <p class="hero-lead">Mais transparência e segurança para a<br>avaliação de medicamentos no Brasil.</p>
    <p class="hero-category"><strong>Categoria: Medicamentos Genéricos Não Inéditos Bioisentos</strong></p>
    <p class="hero-local">(Processo realizado 100% local)</p>
  </div>
</section>
"""


with gr.Blocks(title="PPAM — Gerador Automático") as app:
    header_panel = gr.HTML(render_header())
    preview_state = gr.Textbox(visible=False)

    with gr.Group(elem_id="ppam-main"):
        
        # ══ PÁGINA 1: UPLOAD ══
        with gr.Group(visible=True) as page_upload:
            hero_panel = gr.HTML(render_hero())
            gr.HTML('<p class="upload-title">Selecione os arquivos para processamento</p>')
            
            with gr.Row(elem_classes=["upload-row"]):
                parecer_upload = gr.Files(
                    file_types=SUPPORTED_EXTENSIONS_LIST,
                    elem_classes=["upload-slim", "up-1"],
                )
                bula_upload = gr.Files(
                    file_types=SUPPORTED_EXTENSIONS_LIST,
                    elem_classes=["upload-slim", "up-2"],
                )
                publicacao_upload = gr.Files(
                    file_types=SUPPORTED_EXTENSIONS_LIST,
                    elem_classes=["upload-slim", "up-3"],
                )
                outros_upload = gr.Files(
                    file_types=SUPPORTED_EXTENSIONS_LIST,
                    elem_classes=["upload-slim", "up-4"],
                )

            registro_ms_input = gr.Textbox(
                label="Número de registro MS (preenchimento manual)",
                placeholder="Ex.: 1.1234.5678.001-9",
                lines=1,
                elem_id="registro-ms",
            )
            extract_btn = gr.Button("📄  Iniciar avaliação    →", elem_id="btn-extract")
            processing_panel = gr.HTML("")

        # ══ PÁGINA 2: RESULTADOS ══
        with gr.Group(visible=False, elem_id="results-page") as page_results:
            results_panel = gr.HTML()
            preview_json = gr.JSON(visible=False)
            generate_btn = gr.Button("📄 Gerar documento PPAM", elem_id="btn-generate")
            
            with gr.Row():
                output_file = gr.File(label="PPAM (.docx)")
                audit_output = gr.JSON(label="Log de Auditoria")

            back_btn = gr.Button("← Novo Processamento", elem_id="btn-back")

    # ── EVENTOS ──
    def on_extract(parecer, bula, publicacao, outros, numero_registro_ms):
        started_at = time.perf_counter()
        file_count = sum(len(_get_file_paths(files)) for files in (parecer, bula, publicacao, outros))
        steps = process_documents_steps(
            parecer, bula, publicacao, outros, numero_registro_ms
        )
        while True:
            try:
                progress, stage = next(steps)
            except StopIteration as completed:
                result_dict, result_str = completed.value
                break

            yield (
                gr.update(),
                gr.update(),
                gr.update(visible=True),
                gr.update(visible=False),
                gr.update(),
                render_header(progress),
                render_processing_status(progress, stage, file_count),
                gr.update(),
            )

        if result_dict.get("erro"):
            yield (result_dict, "", gr.update(visible=True), gr.update(visible=False), render_hero(), render_header(), "", "")
            details = "\n".join(f"{item['arquivo']}: {item.get('motivo', '')}" for item in result_dict.get('_processing', {}).get('arquivos', []) if item.get('status') == 'falha')
            raise gr.Error(result_dict["erro"] + ("\n" + details if details else ""))
        elapsed = time.perf_counter() - started_at
        yield (
            result_dict,
            result_str,
            gr.update(visible=False),
            gr.update(visible=True),
            render_hero(),
            render_header(),
            "",
            render_results(result_dict, file_count, elapsed),
        )

    extract_btn.click(
        fn=on_extract,
        inputs=[
            parecer_upload,
            bula_upload,
            publicacao_upload,
            outros_upload,
            registro_ms_input,
        ],
        outputs=[preview_json, preview_state, page_upload, page_results, hero_panel, header_panel, processing_panel, results_panel],
        show_progress="hidden",
    )

    def on_generate(preview_data_str):
        with processing_job():
            docx_path, audit = generate_ppam(preview_data_str)
        if not docx_path:
            raise gr.Error(audit.get("erro", "Não foi possível gerar o documento."))
        Document(docx_path)
        preview = json.loads(preview_data_str)
        preview["_document"] = {"size": Path(docx_path).stat().st_size}
        return docx_path, audit, render_results(preview)

    generate_btn.click(
        fn=on_generate,
        inputs=[preview_state],
        outputs=[output_file, audit_output, results_panel],
    )

    back_btn.click(
        fn=lambda: (gr.update(visible=True), gr.update(visible=False), None, None, None, None, "", "", None, None, None, "", render_hero(), render_header(), ""),
        inputs=[], outputs=[page_upload, page_results, parecer_upload, bula_upload, publicacao_upload, outros_upload, registro_ms_input, preview_state, preview_json, output_file, audit_output, results_panel, hero_panel, header_panel, processing_panel],
        js="() => { const el = document.getElementById('loader-box'); if(el) el.classList.remove('active'); return []; }"
    )

def get_launch_options():
    return dict(share=False, inbrowser=False, debug=False, theme=gr.themes.Base(font=["Arial", "sans-serif"], font_mono=["Consolas", "monospace"]), css=CUSTOM_CSS)


if __name__ == "__main__":
    port = DEFAULT_SERVER_PORT
    logger.info(f"Iniciando a aplicação local na porta {port}...")
    app.launch(
        server_name="127.0.0.1",
        server_port=port,
        **get_launch_options()
    )
