"""
audit.py — Geração de log de auditoria para rastreabilidade.
"""

import json
import logging
from datetime import datetime

from models import PPAMData
from config import SIGILO_BLACKLIST

logger = logging.getLogger(__name__)


class AuditLogger:
    """Gera log de auditoria estruturado."""

    @staticmethod
    def generate_log(data: PPAMData, source_files: dict) -> dict:
        """Gera log estruturado de auditoria."""
        return {
            "timestamp": datetime.now().isoformat(),
            "source_files": source_files,
            "extracted_data": data.model_dump(),
            "low_confidence_fields": {
                "sumario": data.sumario.campos_baixa_confianca,
                "tecnologia": data.tecnologia.campos_baixa_confianca,
                "seguranca": data.seguranca.campos_baixa_confianca,
                "publicacao": data.publicacao.campos_baixa_confianca,
            },
            "divergences": data.divergencias_documentos,
            "sigilo_blacklist_applied": SIGILO_BLACKLIST,
        }

    @staticmethod
    def save_log(log_data: dict, output_path: str):
        """Salva o log em arquivo JSON."""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Log de auditoria salvo em: {output_path}")
