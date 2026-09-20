"""
extractor.py — Extração de campos estruturados do Parecer Técnico
usando expressões regulares e lógicas locais (sem APIs externas).
"""

import re
import json
import logging
import unicodedata
from typing import List, Optional

from config import SIGILO_BLACKLIST
from models import (
    DadosMedicamento,
    TecnologiaFarmaceutica,
    SegurancaEficacia,
    PublicacaoDecisao,
    EstudoDesempenho,
    PPAMData,
)

logger = logging.getLogger(__name__)


class PPAMExtractor:
    """Extrai campos estruturados do Parecer Técnico (100% Local)."""

    def __init__(self):
        logger.info("Configurando extrator local baseado em regras.")
        
    def _validate_sigilo(self, text: str) -> bool:
        """Verifica se o texto contém termos sigilosos da blacklist."""
        text_lower = text.lower()
        for term in SIGILO_BLACKLIST:
            if term.lower() in text_lower:
                logger.warning(f"Termo sigiloso detectado: '{term}'")
                return False
        return True

    def _identify_low_confidence(self, data: dict) -> List[str]:
        """Identifica campos com valor None, vazio ou lista vazia."""
        return [k for k, v in data.items() if v is None or v == [] or v == ""]

    def _safe_search(self, pattern, text, group=1, default=None):
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return self._clean_field_value(match.group(group))
        return default

    @staticmethod
    def _clean_field_value(value: Optional[str]) -> Optional[str]:
        """Normaliza um valor sem remover acentos nem juntar palavras."""
        if value is None:
            return None
        value = unicodedata.normalize("NFC", str(value))
        value = value.replace("\u00a0", " ").replace("\u200b", " ")
        value = re.sub(r"[ \t\f\v]+", " ", value)
        value = value.strip(' \t\r\n|;,:"\'“”«»')
        return value or None

    def _extract_labeled_value(self, text: str, label_pattern: str) -> Optional[str]:
        """Extrai o conteúdo da mesma linha ou da linha seguinte a um rótulo."""
        lines = [self._clean_field_value(line) or "" for line in text.splitlines()]
        label = re.compile(rf"^\s*(?:{label_pattern})\s*[:\-–—|]?\s*(.*?)\s*$", re.IGNORECASE)
        for index, line in enumerate(lines):
            match = label.match(line)
            if not match:
                continue
            inline = self._clean_field_value(match.group(1))
            if inline:
                return inline
            for following in lines[index + 1:index + 3]:
                candidate = self._clean_field_value(following)
                if candidate and not re.match(r"^-{3,}|DOCUMENTO\s*:", candidate, re.IGNORECASE):
                    return candidate
        return None

    def _extract_table_or_label(self, text: str, label_pattern: str) -> Optional[str]:
        """Lê campos de tabelas DOCX ou de rótulos em linhas, preservando Unicode."""
        table_match = re.search(
            rf"(?:^|\n)\s*(?:{label_pattern})\s*\|\s*([^|\r\n]+)",
            text,
            re.IGNORECASE,
        )
        if table_match:
            return self._clean_field_value(table_match.group(1).replace("\u2013", "-"))
        return self._extract_labeled_value(text, label_pattern)

    def _extract_apresentacoes(self, outros_text: str) -> List[str]:
        """
        Extrai apresentações registradas de texto OCR (possivelmente compactado/sem espaços).

        Diagnóstico real: OCR retorna linhas como:
          'Apresentacao'
          '50MG/MLSOLIN]IM/IVCX25AMPVDAMBX2ML'
          '50MG/MLSOLINJIM/IVCX36AMPVDAMBX2ML'

        Estratégia:
          1. Localiza o cabeçalho (com ou sem acento)
          2. Captura linhas seguintes como candidatas
          3. Decodifica tokens compactados em texto legível
          4. Fallback: retorna linha bruta se não conseguir decodificar
        """
        EXCLUIR = {
            "apresentacoes registradas", "apresentações registradas",
            "apresentacao", "apresentação", "registradas", "apresentacoes",
            "registro", "número de registro", "numero de registro",
        }

        linhas = outros_text.splitlines()
        inicio_bloco = None

        # Localiza cabeçalho — aceita com/sem acento, com/sem "registradas"
        for i, linha in enumerate(linhas):
            l = linha.strip()
            if re.search(r"Apresenta[çc][aã]o(?:[eê]s)?\s*(?:registradas?)?\s*:?$", l, re.IGNORECASE):
                inicio_bloco = i + 1
                break

        # Se não achou cabeçalho, tenta processar todas as linhas
        candidatas = linhas[inicio_bloco:] if inicio_bloco is not None else linhas

        apresentacoes = []
        for linha in candidatas:
            l = linha.strip().lstrip("•-–*· ").strip()

            if not l or l.lower() in EXCLUIR:
                continue
            if l.startswith("---") or l.upper().startswith("DOCUMENTO"):
                continue
            if len(l) < 4:
                continue
            # Linhas numéricas da coluna "Registro" não são apresentações.
            digits_only = re.sub(r"[.\-\s]", "", l)
            if digits_only.isdigit() and len(digits_only) >= 8:
                continue
            # O OCR pode remover todos os espaços da linha. Validar a informação
            # sem depender de fronteiras de palavras preserva concentrações como
            # ``50MG/ML`` e apresentações como ``SOLINJ...CX25AMP``.
            ascii_line = "".join(
                char for char in unicodedata.normalize("NFKD", l)
                if not unicodedata.combining(char)
            )
            compact = re.sub(r"[^A-Z0-9%/]", "", ascii_line.upper())
            has_strength = bool(re.search(
                r"\d+(?:[.,]\d+)?(?:MG(?:/ML|/G)?|MCG(?:/ML)?|UI(?:/ML)?|G|%)",
                compact,
            ))
            has_form_or_pack = bool(re.search(
                r"(?:SOLINJ|SOLINFUS|POLIOF|COMP|CAPS|SUSP|CREME|GEL|POMADA|CX\d+|CT|FA|AMP|VD)",
                compact,
            ))
            if not (has_strength and has_form_or_pack):
                continue

            decodificado = self._decode_ocr_compact(l)
            apresentacoes.append(decodificado)

        # Deduplicar mantendo ordem
        seen = set()
        result = []
        for a in apresentacoes:
            if a.lower() not in seen:
                seen.add(a.lower())
                result.append(a)
        return result

    def _decode_ocr_compact(self, texto: str) -> str:
        """
        Converte texto OCR compactado (sem espaços entre tokens) em formato legível.

        Exemplo:
          '50MG/MLSOLIN]IM/IVCX25AMPVDAMBX2ML'
          -> '50 mg/mL Sol. Inj. IM/IV - Cx. 25 Amp. Vd. Amb. x 2 mL'
        """
        s = texto

        # Passo 1: inserir espaço após concentração (ex: 50MG -> 50 mg)
        s = re.sub(
            r"(\d+(?:[,\.]\d+)?)\s*(MG/ML|MG/G|MCG/ML|UI/ML|MG|MCG|G(?=/|\b)|ML|%)",
            lambda m: m.group(1) + " " + m.group(2).lower() + " ",
            s, flags=re.IGNORECASE
        )

        # Passo 2: expandir forma farmacêutica compacta
        formas = [
            (r"SOL[\s\]\|]?INJ",           "Sol. Inj."),
            (r"PO\s*LIOF(?:ILIZAD[OA])?",    "Pó liofilizado"),
            (r"SOL\s*INFUS(?=IV\b)",         "para solução para infusão "),
            (r"SOL\s*INFUS(?:[AÃ]O)?",       "para solução para infusão"),
            (r"SOLU[CÇ][AÃ]O\s*INJET[AÁ]VEL", "Solução Injetável"),
            (r"SOLU[CÇ][AÃ]O\s*ORAL",      "Solução Oral"),
            (r"COMPRIMIDOS?\.?",            "Comprimidos"),
            (r"COMP\b\.?",                  "Comprimidos"),
            (r"C[AÁ]PSULAS?\.?",            "Cápsulas"),
            (r"CAPS\b\.?",                  "Cápsulas"),
            (r"SUSPENS[AÃ]O\b",             "Suspensão"),
            (r"SUSP\b\.?",                  "Suspensão"),
            (r"GEL\b\.?",                   "Gel"),
            (r"CREME\b\.?",                 "Creme"),
            (r"POMADA\b\.?",                "Pomada"),
        ]
        for pat, rep in formas:
            s = re.sub(pat, " " + rep + " ", s, flags=re.IGNORECASE)

        # Passo 3: separar via de administração
        s = re.sub(r"\b(IM/IV|IV\b|IM\b|SC\b|VO\b|SL\b)", r" \1 ", s, flags=re.IGNORECASE)

        # Passo 4: separar embalagem
        s = re.sub(r"\bCT\b|CT(?=FA|VD|TRANS|$)", " - Cartucho, ", s, flags=re.IGNORECASE)
        s = re.sub(r"CX\.?\s*(\d+)",          r" - Cx. \1 ", s, flags=re.IGNORECASE)
        s = re.sub(r"BL(?:ISTER)?\.?\s*(\d+)", r" Blíster \1 ", s, flags=re.IGNORECASE)
        s = re.sub(r"FR\.?\s*(\d+)",           r" Fr. \1 ", s, flags=re.IGNORECASE)

        # Passo 5: tipo de recipiente
        recipientes = [
            (r"\bFA\b|FA(?=VD|TRANS|$)", "Frasco-ampola"),
            (r"VD\s*TRANS",              "de vidro transparente"),
            (r"FRASCO[\s-]?AMP(?:OLA)?", "Frasco-ampola"),
            (r"VD\s*AMB",                "Vd. Amb."),
            (r"(?<!FRASCO-)AMP(?:OLA)?\.?", "Amp."),
            (r"SACH[EÊ]\.?",             "Sachê"),
            (r"BISNAGA",                 "Bisnaga"),
        ]
        for pat, rep in recipientes:
            s = re.sub(pat, " " + rep + " ", s, flags=re.IGNORECASE)

        # Passo 6: volume no final (ex: X2ML → x 2 mL)
        s = re.sub(r"X\s*(\d+(?:[,\.]\d+)?)\s*(ML|G\b|MG)", r" x \1 \2", s, flags=re.IGNORECASE)
        s = re.sub(r"\b(\d+(?:[,\.]\d+)?)\s*(ML|G\b)",      r"\1 \2",     s, flags=re.IGNORECASE)

        # Passo 7: limpar caracteres estranhos de OCR e espaços duplos
        s = re.sub(r"[\[\]\|\\]", " ", s)
        s = re.sub(r"\s{2,}", " ", s)
        s = re.sub(r"\s+,", ",", s)
        s = re.sub(r",\s*,", ",", s)
        # Apresentação canônica das unidades, independentemente da caixa usada
        # pelo OCR ou das transformações anteriores.
        s = re.sub(r"\bmg/ml\b", "mg/mL", s, flags=re.IGNORECASE)
        s = re.sub(r"\bmcg/ml\b", "mcg/mL", s, flags=re.IGNORECASE)
        s = re.sub(r"\bui/ml\b", "UI/mL", s, flags=re.IGNORECASE)
        s = re.sub(r"\bml\b", "mL", s, flags=re.IGNORECASE)
        s = s.strip(" -")

        return s.strip() if len(s.strip()) >= 5 else texto

    # --------------------------------------------------------
    # EXTRAÇÃO POR SEÇÃO

    def _extract_bula_composition(self, bula_text: str) -> Optional[str]:
        """Extrai todo o bloco de composição sem atravessar os excipientes."""
        lines = [
            re.sub(r"[ \t\f\v]+", " ", unicodedata.normalize("NFC", line)).strip()
            for line in bula_text.splitlines()
        ]

        captured = []
        collecting = False
        for line in lines:
            heading = re.match(
                r"^COMPOSI(?:ÇÃO|CAO)\s*:?\s*(.*)$",
                line,
                re.IGNORECASE,
            )
            if heading:
                collecting = True
                inline = heading.group(1).strip()
                if inline:
                    captured.append(inline)
                continue

            if not collecting and re.search(
                r"^Cada\s+.+?\bcont[eé]m\b", line, re.IGNORECASE
            ):
                collecting = True

            if not collecting:
                continue
            if re.match(r"^Excipientes?\s*:", line, re.IGNORECASE):
                break
            if captured and re.match(r"^[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ\s]{4,}:?$", line):
                break
            if line:
                captured.append(line)

        if not captured:
            return None

        main = " ".join(captured)
        # O OCR pode transformar pontilhados de tabela em uma linha isolada
        # antes da quantidade. Eles são separadores visuais, não conteúdo.
        main = re.sub(r"\s*\.{2,}\s*", " ", main)
        main = re.sub(r"(?:^|\s)\.\s+(?=\d)", " ", main)
        main = re.sub(r"\s{2,}", " ", main).strip()

        note = next(
            (
                re.sub(r"^\*\s*", "", line).strip()
                for line in lines
                if re.search(r"^\*\s*Ap[oó]s\s+reconstitui", line, re.IGNORECASE)
            ),
            None,
        )
        return f"{main} {note}" if note else main

    def _extract_bula_excipients(self, bula_text: str) -> List[str]:
        """Extrai somente a lista de excipientes, preservando ordem e palavras."""
        lines = [self._clean_field_value(line) or "" for line in bula_text.splitlines()]
        captured = []
        collecting = False
        for line in lines:
            match = re.match(r"^Excipientes?\s*:\s*(.*)$", line, re.IGNORECASE)
            if match:
                collecting = True
                if match.group(1):
                    captured.append(match.group(1))
                continue
            if not collecting:
                continue
            if not line or line.startswith("*") or re.match(r"^[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ\s]{4,}$", line):
                break
            captured.append(line)

        if not captured:
            return []
        raw = " ".join(captured).rstrip(". ")
        parts = re.split(r"\s*,\s*|\s+e\s+(?=[A-Za-zÀ-ÖØ-öø-ÿ])", raw, flags=re.IGNORECASE)
        result = []
        seen = set()
        for part in parts:
            cleaned = self._clean_field_value(part)
            if not cleaned:
                continue
            key = cleaned.casefold()
            if key not in seen:
                seen.add(key)
                result.append(cleaned)
        return result

    def extract_sumario(self, parecer_text: str, bula_text: str = "", outros_text: str = "") -> DadosMedicamento:
        """Extrai dados do Sumário das Características usando Regex aprimorado."""
        result = {
            "empresa": None,
            "nome_medicamento": None,
            "principio_ativo": None,
            "categoria": "Genérico",
            "forma_farmaceutica": None,
            "concentracao": None,
            "rdc_numero": None,
            "rdc_data": None,
            "composicao": None,
            "excipientes": [],
            "apresentacoes": [],
            "medicamento_referencia": None
        }

        # Extrair dados da tabela FIDR no final do documento (muito mais preciso)
        result["empresa"] = self._extract_table_or_label(parecer_text, r"Empresa|Solicitante|Requerente")
        principio = self._extract_table_or_label(parecer_text, r"Princ[ií]pio\s+ativo|F[áa]rmaco|Subst[âa]ncia")
        nome_comercial = self._extract_table_or_label(parecer_text, r"Nome\s+comercial")
        
        if principio:
            principio = re.sub(r'\(.*?\)', '', principio).strip()
            result["principio_ativo"] = principio
        if nome_comercial and nome_comercial.lower() not in ["não aplicável", "nao aplicavel"]:
            result["nome_medicamento"] = nome_comercial
            
        result["forma_farmaceutica"] = self._extract_table_or_label(parecer_text, r"Forma\s+farmac[êe]utica")
        result["medicamento_referencia"] = self._extract_table_or_label(parecer_text, r"Medicamento\s+de\s+Refer[êe]ncia")

        # Concentração
        conc_match = re.search(r"(\d+(?:,\d+)?\s*(?:mg/mL|mg|g|mcg|UI|%))", parecer_text, re.IGNORECASE)
        if conc_match:
            result["concentracao"] = conc_match.group(1)

        # Apresentações: Obrigatório buscar apenas em "Outros Documentos"
        if outros_text:
            apresentacoes = self._extract_apresentacoes(outros_text)
            if apresentacoes:
                result["apresentacoes"] = apresentacoes
                logger.info(f"[DIAGNÓSTICO] Apresentações extraídas: {apresentacoes}")
            else:
                logger.warning("[DIAGNÓSTICO] Nenhuma apresentação localizada em outros_text.")

        # RDC regex
        rdc_match = re.search(r"RDC\s*[nN]?[ºo]?\s*(\d+/\d{4})(?:.*?de\s*(\d{1,2}/\d{1,2}/\d{4}))?", parecer_text, re.IGNORECASE)
        if rdc_match:
            result["rdc_numero"] = rdc_match.group(1)
            date_match = re.search(r"(\d{2}/\d{2}/\d{4})", parecer_text[rdc_match.end():rdc_match.end()+30])
            if date_match:
                result["rdc_data"] = date_match.group(1)
            
        # Extração Exclusiva da BULA (Composição e Excipientes)
        if bula_text:
            result["excipientes"] = self._extract_bula_excipients(bula_text)
            result["composicao"] = self._extract_bula_composition(bula_text)

        campos_baixa = self._identify_low_confidence(result)
        return DadosMedicamento(**result, campos_baixa_confianca=campos_baixa)

    def extract_tecnologia(self, parecer_text: str, bula_text: str = "", outros_text: str = "") -> TecnologiaFarmaceutica:
        """Extrai dados de Tecnologia Farmacêutica via Regex local."""
        result = {
            "cadifa_aprovada": None,
            "controle_qualidade_ifa": None,
            "validacoes_metodos_ifa": None,
            "processo_fabricacao": None,
            "controle_qualidade_produto": None,
            "validacoes_metodos_medicamento": None,
            "embalagem_primaria": None
        }

        # CADIFA
        cadifa_text = re.search(r"CADIFA[^.]*aprovad[ao]", parecer_text, re.IGNORECASE)
        if cadifa_text:
            result["cadifa_aprovada"] = True

        if re.search(r"(?:controle\s+de\s+qualidade|testes?).*?IFA.*?(?:adequad|satisfat[óo]ri|aprovad)", parecer_text, re.IGNORECASE | re.DOTALL):
            result["controle_qualidade_ifa"] = True
            
        # Validação IFA / Produto Terminado com DOTALL flexível
        if re.search(r"valida.*?(?:IFA|ativo).*?adequad", parecer_text, re.IGNORECASE|re.DOTALL):
            result["validacoes_metodos_ifa"] = True
            
        if re.search(r"valida.*?(?:produto|medicamento|terminado).*?adequad", parecer_text, re.IGNORECASE|re.DOTALL):
            result["validacoes_metodos_medicamento"] = True

        if re.search(r"(?:controle\s+de\s+qualidade|testes?).*?(?:produto\s+terminado|medicamento).*?(?:adequad|satisfat[óo]ri|aprovad)", parecer_text, re.IGNORECASE | re.DOTALL):
            result["controle_qualidade_produto"] = True
            
        # Processo de fabricacao
        if re.search(r"processo\s*de\s*fabrica[çc][ãa]o.*?(?:atende satisfatoriamente|satisfat[óo]ri[ao]|aprovad[ao]|adequad[ao])", parecer_text, re.IGNORECASE|re.DOTALL):
             result["processo_fabricacao"] = True

        # Embalagem primária: por regra, somente o Parecer Técnico pode fornecê-la.
        embalagem = self._extract_table_or_label(parecer_text, r"Embalagem\s+prim[áa]ria")
        if not embalagem:
            emb_match = re.search(
                r"(?:embalagem\s+prim[áa]ria\s+refere-se\s+[aà]|acondicionado\s+em)\s*"
                r"([^\r\n.;]+(?:\.[A-Za-zÀ-ÖØ-öø-ÿ]{1,4}\.?[^\r\n.;]*)?)",
                parecer_text,
                re.IGNORECASE,
            )
            if emb_match:
                embalagem = self._clean_field_value(emb_match.group(1))
        if embalagem and len(embalagem) > 4:
            result["embalagem_primaria"] = embalagem
        
        campos_baixa = self._identify_low_confidence(result)
        return TecnologiaFarmaceutica(**result, campos_baixa_confianca=campos_baixa)

    def extract_seguranca(self, parecer_text: str, bula_text: str = "", outros_text: str = "") -> SegurancaEficacia:
        """Extrai dados de Segurança e Eficácia via heurística local Regex."""
        result = {
            "tipo_comprovacao": None,
            "medicamento_referencia": None,
            "certificado_equivalencia": None,
            "centro_equivalencia": None,
            "certificado_perfil_dissolucao": None,
            "houve_bioequivalencia": None,
            "base_legal_bioisencao": None,
            "estudo_desempenho": {}
        }
        
        # Tipo de Comprovação: Heurística usando palavras
        has_bio = bool(re.search(r"Bioisen[çc][ãa]o\s*em\s*raz[ãa]o\s*da\s*forma\s*farmac[êe]utica", parecer_text, re.IGNORECASE))
        has_ef = bool(re.search(r"Equival[êe]ncia\s*Farmac[êe]utica.*?equivalente\s*ao\s*medicamento\s*de\s*refer[êe]ncia", parecer_text, re.IGNORECASE|re.DOTALL))
        
        if has_bio and has_ef:
            result["tipo_comprovacao"] = "EF + Bioisento em razão da FF"
        elif has_ef:
            result["tipo_comprovacao"] = "Equivalência Farmacêutica"
        elif has_bio:
            result["tipo_comprovacao"] = "Bioisenção"

        # Tentar base legal (Bioneisenção)
        if re.search(r"RDC.*?749/2022.*?art\.\s*7", parecer_text, re.IGNORECASE):
            result["base_legal_bioisencao"] = "rdc_749_2022_art7"
        elif re.search(r"RDC.*?749/2022.*?art\.\s*18", parecer_text, re.IGNORECASE):
            result["base_legal_bioisencao"] = "rdc_749_2022_art18"
        elif re.search(r"RDC.*?37/2011", parecer_text, re.IGNORECASE):
            result["base_legal_bioisencao"] = "rdc_37_2011"

        result["medicamento_referencia"] = self._extract_table_or_label(
            parecer_text,
            r"Medicamento\s+de\s+Refer[êe]ncia",
        )

        # Certificado e Centro
        if has_ef or re.search(r"O estudo foi realizado pelo Centro de Equival[êe]ncia", parecer_text, re.IGNORECASE):
             result["certificado_equivalencia"] = True
             centro_match = re.search(r"pelo Centro de Equival[êe]ncia(?:.*?)\s+([A-Z][a-zA-Z0-9\s]+)", parecer_text, re.IGNORECASE)
             if centro_match:
                 # captura básica do centro se tiver nome
                 nome_centro = centro_match.group(1).strip()
                 if len(nome_centro) > 4 and "devidamente habilitado" not in nome_centro:
                     result["centro_equivalencia"] = nome_centro
                     
        # Certificado Perfil 
        if re.search(r"(?:perfil\s*de\s*dissolu[çc][ãa]o\s*comparativo|Certificado\s*de\s*Perfil).*?(?:conforme|aprovado|satisfat[óo]rio)", parecer_text, re.IGNORECASE):
            result["certificado_perfil_dissolucao"] = True
        elif has_bio:
            result["certificado_perfil_dissolucao"] = False

        if result["tipo_comprovacao"] and "Bioisento" in result["tipo_comprovacao"]:
            result["houve_bioequivalencia"] = False

        estudo = {
            "aplicavel": None,
            "medicamento_referencia": None,
            "fabricante_referencia": None,
            "medicamento_teste": None,
            "fabricante_teste": None,
            "resultados_satisfatorios": None
        }
        
        # Desempenho
        if re.search(r"estudo\s*comparativo\s*de\s*desempenho", parecer_text, re.IGNORECASE):
             estudo["aplicavel"] = True
             estudo["resultados_satisfatorios"] = bool(re.search(r"desempenho.*?satisfat[óo]rio", parecer_text, re.IGNORECASE))

        result["estudo_desempenho"] = estudo

        campos_baixa = self._identify_low_confidence(result)
        return SegurancaEficacia(**result, campos_baixa_confianca=campos_baixa)

    def extract_publicacao(
        self,
        publicacao_text: str,
        principio_ativo: Optional[str] = None,
        numero_registro_ms: Optional[str] = None,
    ) -> PublicacaoDecisao:
        """Extrai somente os campos delimitados do upload do DOU."""
        result = {
            "numero_registro_ms": self._clean_field_value(numero_registro_ms),
            "nome_produto": self._clean_field_value(principio_ativo),
            "dou_numero": None,
            "dou_data": None,
            "resolucao_re_numero": None,
            "resolucao_re_data": None,
            "rdc_aplicavel": None
        }
        
        # Registro MS é exclusivamente manual. Não se tenta inferi-lo do OCR.

        # A edição do DOU é lida somente do campo "Nº do DOU:".
        dou_value = self._extract_labeled_value(
            publicacao_text,
            r"N\s*[º°o]?\s*do\s*DOU",
        )
        if dou_value:
            dou_num = re.search(r"\b(\d{1,4})\b", dou_value)
            if dou_num:
                result["dou_numero"] = dou_num.group(1)
        
        re_num = re.search(r"Resoluc[ãa]o.*?(\d+(?:[\.\,]\d+)?)", publicacao_text, re.IGNORECASE | re.DOTALL)
        if re_num: result["resolucao_re_numero"] = re_num.group(1)
        
        # A data é lida somente do campo "Publicado em:".
        published_value = self._extract_labeled_value(publicacao_text, r"Publicado\s*em")
        if published_value:
            date_match = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b", published_value)
            if date_match:
                result["dou_data"] = date_match.group(1).replace("-", "/")
        
        campos_baixa = self._identify_low_confidence(result)
        return PublicacaoDecisao(**result, campos_baixa_confianca=campos_baixa)

    # --------------------------------------------------------
    # VALIDAÇÃO CRUZADA
    # --------------------------------------------------------

    def validate_cross_documents(self, data: PPAMData) -> List[str]:
        """Valida consistência entre Parecer, Bula e Publicação."""
        divergencias = []

        if not data.publicacao.numero_registro_ms:
            divergencias.append("Número de registro MS não informado manualmente")

        if (data.sumario.rdc_numero and
                data.publicacao.rdc_aplicavel and
                data.sumario.rdc_numero not in data.publicacao.rdc_aplicavel):
            divergencias.append(
                f"Divergência de RDC: sumário menciona RDC "
                f"{data.sumario.rdc_numero}, "
                f"publicação menciona {data.publicacao.rdc_aplicavel}"
            )

        if not data.sumario.medicamento_referencia:
            divergencias.append("Medicamento de referência não localizado no Parecer Técnico")

        return divergencias

    # --------------------------------------------------------
    # EXTRAÇÃO COMPLETA
    # --------------------------------------------------------

    def extract_all(
        self,
        parecer_text: str,
        bula_text: str,
        publicacao_text: str,
        outros_text: str = "",
        numero_registro_ms: Optional[str] = None,
    ) -> PPAMData:
        """Executa extração completa de todas as seções (Modo Local)."""
        sumario = DadosMedicamento()
        tecnologia = TecnologiaFarmaceutica()
        seguranca = SegurancaEficacia()
        publicacao = PublicacaoDecisao()

        try:
            logger.info("Extraindo Sumário das Características (Local)...")
            sumario = self.extract_sumario(parecer_text, bula_text, outros_text)
        except Exception as e:
            logger.error(f"Falha na extração do Sumário: {e}")

        try:
            logger.info("Extraindo Dados de Tecnologia Farmacêutica (Local)...")
            tecnologia = self.extract_tecnologia(parecer_text, bula_text)
        except Exception as e:
            logger.error(f"Falha na extração de Tecnologia: {e}")

        try:
            logger.info("Extraindo Dados de Segurança e Eficácia (Local)...")
            seguranca = self.extract_seguranca(parecer_text)
        except Exception as e:
            logger.error(f"Falha na extração de Segurança: {e}")

        try:
            logger.info("Extraindo Dados de Publicação da Decisão (Local)...")
            publicacao = self.extract_publicacao(
                publicacao_text or "",
                principio_ativo=sumario.principio_ativo,
                numero_registro_ms=numero_registro_ms,
            )
        except Exception as e:
            logger.error(f"Falha na extração de Publicação: {e}")

        data = PPAMData(
            sumario=sumario,
            tecnologia=tecnologia,
            seguranca=seguranca,
            publicacao=publicacao,
        )

        data.divergencias_documentos = self.validate_cross_documents(data)

        return data
