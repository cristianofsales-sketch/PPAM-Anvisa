"""
models.py — Modelos de dados (Pydantic) para estruturação do PPAM.
Define os schemas de validação para cada seção extraída.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class DadosMedicamento(BaseModel):
    """Seção 1: Sumário das características do medicamento."""
    empresa: Optional[str] = None
    nome_medicamento: Optional[str] = None
    principio_ativo: Optional[str] = None
    categoria: Optional[str] = "Genérico"
    forma_farmaceutica: Optional[str] = None
    concentracao: Optional[str] = None
    rdc_numero: Optional[str] = None
    rdc_data: Optional[str] = None
    composicao: Optional[str] = None
    excipientes: List[str] = Field(default_factory=list)
    apresentacoes: List[str] = Field(default_factory=list)
    medicamento_referencia: Optional[str] = None
    campos_baixa_confianca: List[str] = Field(default_factory=list)


class TecnologiaFarmaceutica(BaseModel):
    """Seção 2: Dados de tecnologia farmacêutica."""
    cadifa_aprovada: Optional[bool] = None
    controle_qualidade_ifa: Optional[bool] = None
    validacoes_metodos_ifa: Optional[bool] = None
    processo_fabricacao: Optional[bool] = None
    controle_qualidade_produto: Optional[bool] = None
    validacoes_metodos_medicamento: Optional[bool] = None
    embalagem_primaria: Optional[str] = None
    campos_baixa_confianca: List[str] = Field(default_factory=list)


class EstudoDesempenho(BaseModel):
    """Estudo de desempenho comparativo in vitro (se aplicável)."""
    aplicavel: Optional[bool] = None
    medicamento_referencia: Optional[str] = None
    fabricante_referencia: Optional[str] = None
    medicamento_teste: Optional[str] = None
    fabricante_teste: Optional[str] = None
    resultados_satisfatorios: Optional[bool] = None


class SegurancaEficacia(BaseModel):
    """Seção 3: Dados de segurança e eficácia."""
    tipo_comprovacao: Optional[str] = None
    medicamento_referencia: Optional[str] = None
    certificado_equivalencia: Optional[bool] = None
    centro_equivalencia: Optional[str] = None
    certificado_perfil_dissolucao: Optional[bool] = None
    houve_bioequivalencia: Optional[bool] = None
    base_legal_bioisencao: Optional[str] = None
    estudo_desempenho: EstudoDesempenho = Field(default_factory=EstudoDesempenho)
    campos_baixa_confianca: List[str] = Field(default_factory=list)


class PublicacaoDecisao(BaseModel):
    """Seção 4: Publicação da decisão."""
    numero_registro_ms: Optional[str] = None
    nome_produto: Optional[str] = None
    dou_numero: Optional[str] = None
    dou_data: Optional[str] = None
    resolucao_re_numero: Optional[str] = None
    resolucao_re_data: Optional[str] = None
    rdc_aplicavel: Optional[str] = None
    campos_baixa_confianca: List[str] = Field(default_factory=list)


class PPAMData(BaseModel):
    """Estrutura completa do PPAM."""
    sumario: DadosMedicamento = Field(default_factory=DadosMedicamento)
    tecnologia: TecnologiaFarmaceutica = Field(default_factory=TecnologiaFarmaceutica)
    seguranca: SegurancaEficacia = Field(default_factory=SegurancaEficacia)
    publicacao: PublicacaoDecisao = Field(default_factory=PublicacaoDecisao)
    divergencias_documentos: List[str] = Field(default_factory=list)
