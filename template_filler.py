"""
template_filler.py — Preenchimento do template .docx do PPAM
com os dados extraídos, aplicando lógica condicional e marcações.
"""

import re
import logging
from copy import deepcopy

from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.text.paragraph import Paragraph

from config import INSTRUCTION_PATTERNS, DEFAULT_TEMPLATE
from models import PPAMData

logger = logging.getLogger(__name__)


class TemplateFiller:
    """Preenche o template .docx do PPAM com os dados extraídos."""

    def __init__(self, template_path: str = None):
        self.template_path = template_path or str(DEFAULT_TEMPLATE)

    def fill(self, data: PPAMData, output_path: str) -> str:
        """Gera o documento Word final a partir do template e dos dados."""
        doc = Document(self.template_path)

        replacements = self._build_replacement_map(data)
        self._replace_in_paragraphs(doc, replacements)

        self._fill_presentations(doc, data)
        self._handle_conditional_blocks(doc, data)
        self._remove_instructional_text(doc)
        self._mark_low_confidence_fields(doc, data)
        self._ensure_footer_clearance(doc)

        doc.save(output_path)
        return output_path

    @staticmethod
    def _ensure_footer_clearance(doc: Document):
        """Reserva espaço entre o corpo do parecer e a paginação do rodapé."""
        minimum_bottom_margin = Cm(2.5)
        maximum_footer_distance = Cm(1.25)
        for section in doc.sections:
            if section.bottom_margin is None or section.bottom_margin < minimum_bottom_margin:
                section.bottom_margin = minimum_bottom_margin
            if section.footer_distance is None or section.footer_distance > maximum_footer_distance:
                section.footer_distance = maximum_footer_distance

    # --------------------------------------------------------
    # MAPEAMENTO DE SUBSTITUIÇÕES
    # --------------------------------------------------------

    def _build_replacement_map(self, data: PPAMData) -> dict:
        """Mapeia placeholders do template para valores extraídos."""
        replacements = {}
        s = data.sumario
        p = data.publicacao

        # Nome comercial e princípio ativo são conceitos independentes.
        principio_ativo_limpo = s.principio_ativo or "[NÃO LOCALIZADO]"
        principio_ativo_limpo = principio_ativo_limpo.replace("(", "").replace(")", "").strip()
        nome_comercial = (s.nome_medicamento or principio_ativo_limpo).strip()
        produto_publicado = (p.nome_produto or principio_ativo_limpo).strip()

        # Medicamento de referência
        med_ref_limpo = s.medicamento_referencia or "[NÃO LOCALIZADO]"
        med_ref_limpo = med_ref_limpo.replace("(", "").replace(")", "").strip()

        # RDC vigente
        rdc_text = f"RDC nº {s.rdc_numero or '[Nº não localizado]'}"
        if s.rdc_data:
            rdc_text += f", de {s.rdc_data}"

        # -------------------------------------------------------------
        # 1. MAPEAMENTO DE FRASES COMPLETAS E COMPLEXAS DO TEMPLATE
        # -------------------------------------------------------------
        # Categoria (Sempre apenas Genérico)
        replacements["Categoria: Genérico, Similar."] = "Categoria: Genérico."

        # Substitui a frase do parágrafo de registro inicial inteira para evitar parênteses órfãos
        replacements["registro do produto NOME COMERCIAL (princípio ativo), forma farmacêutica, concentração), na vigência da Resolução da Diretoria Colegiada - RDC nº XX, de XX/XX/XXXX."] = (
            f"registro do produto {nome_comercial}, {s.forma_farmaceutica or '[NÃO LOCALIZADO]'}, {s.concentracao or '[NÃO LOCALIZADO]'}, na vigência da {rdc_text}."
        )

        # Equivalência terapêutica
        replacements["O medicamento XXX é equivalente terapêutico ao medicamento de referência XXX."] = (
            f"O medicamento {nome_comercial} é equivalente terapêutico ao medicamento de referência {med_ref_limpo}."
        )

        # Estudo de Dissolução Comparativo
        replacements["O medicamento XXX, forma farmacêutica, concentração(ões), comprovou ser semelhante ao medicamento de referência XXX, forma farmacêutica, concentração(ões), conforme Certificado de Perfil de Dissolução Comparativo emitido por centro de Equivalência Farmacêutica devidamente habilitado pela Anvisa."] = (
            f"O medicamento {nome_comercial}, {s.forma_farmaceutica or '[NÃO LOCALIZADO]'}, {s.concentracao or '[NÃO LOCALIZADO]'}, comprovou ser semelhante ao medicamento de referência {med_ref_limpo}, {s.forma_farmaceutica or '[NÃO LOCALIZADO]'}, {s.concentracao or '[NÃO LOCALIZADO]'}, conforme Certificado de Perfil de Dissolução Comparativo emitido por centro de Equivalência Farmacêutica devidamente habilitado pela Anvisa."
        )

        # Estudo de desempenho
        fabricante_ref = data.seguranca.estudo_desempenho.fabricante_referencia or "[FABRICANTE REF NÃO LOCALIZADO]"
        fabricante_teste = data.seguranca.estudo_desempenho.fabricante_teste or "[FABRICANTE TESTE NÃO LOCALIZADO]"
        med_desempenho_ref = data.seguranca.estudo_desempenho.medicamento_referencia or med_ref_limpo
        med_desempenho_teste = data.seguranca.estudo_desempenho.medicamento_teste or nome_comercial
        replacements["O estudo comparou o medicamento de referência XXX, forma farmacêutica, concentração, fabricado por XXX versus o medicamento XXX, forma farmacêutica, concentração, fabricado por XXX."] = (
            f"O estudo comparou o medicamento de referência {med_desempenho_ref}, {s.forma_farmaceutica or '[NÃO LOCALIZADO]'}, {s.concentracao or '[NÃO LOCALIZADO]'}, fabricado por {fabricante_ref} versus o medicamento {med_desempenho_teste}, {s.forma_farmaceutica or '[NÃO LOCALIZADO]'}, {s.concentracao or '[NÃO LOCALIZADO]'}, fabricado por {fabricante_teste}."
        )

        # Dispensações e equivalências remanescentes
        replacements["O medicamento XXX é dispensado do estudo de bioequivalência"] = (
            f"O medicamento {nome_comercial} é dispensado do estudo de bioequivalência"
        )
        replacements["para o medicamento XXX no Diário Oficial de União"] = (
            f"para o medicamento {produto_publicado} no Diário Oficial de União"
        )
        replacements["equivalência terapêutica do medicamento teste com o medicamento de referência XXX"] = (
            f"equivalência terapêutica do medicamento teste com o medicamento de referência {med_ref_limpo}"
        )

        # -------------------------------------------------------------
        # 2. MAPEAMENTO DOS DIVERSOS PLACEHOLDERS PADRÃO DO TEMPLATE
        # -------------------------------------------------------------
        # Empresa
        replacements["A empresa XXX"] = (
            f"A empresa {s.empresa or '[NÃO LOCALIZADO]'}"
        )
        replacements["XXX solicitou"] = (
            f"{s.empresa or '[NÃO LOCALIZADO]'} solicitou"
        )
        replacements["empresa XXX"] = (
            f"empresa {s.empresa or '[NÃO LOCALIZADO]'}"
        )

        # Identificadores de produto
        replacements["NOME COMERCIAL (princípio ativo)"] = nome_comercial
        replacements["NOME COMERCIAL (princípios ativos)"] = nome_comercial
        replacements["NOME COMERCIAL"] = nome_comercial
        replacements["produto NOME COMERCIAL"] = f"produto {nome_comercial}"
        replacements["princípio ativo"] = principio_ativo_limpo

        # Forma farmacêutica e Concentração
        replacements["forma farmacêutica"] = (
            s.forma_farmaceutica or "[NÃO LOCALIZADO]"
        )
        replacements["concentração"] = (
            s.concentracao or "[NÃO LOCALIZADO]"
        )
        
        # Composição e Excipientes da Bula
        replacements["Cada forma farmacêutica/volume contém XX mg de XXX, equivalente a XX mg de XXX base/anidra."] = (
            s.composicao or "[COMPOSIÇÃO NÃO LOCALIZADA NA BULA]"
        )
        excipientes_list = s.excipientes or []
        excipientes_str = ", ".join(excipientes_list) if excipientes_list else "[EXCIPIENTES NÃO LOCALIZADOS NA BULA]"
        replacements["Excipientes: XXX."] = f"Excipientes: {excipientes_str}."

        # RDC vigentes
        replacements["RDC nº XX, de XX/XX/XXXX"] = rdc_text
        replacements[
            "Resolução da Diretoria Colegiada - RDC nº XX, de XX/XX/XXXX"
        ] = f"Resolução da Diretoria Colegiada - {rdc_text}"

        # Medicamento de referência
        replacements["medicamento de referência XXX"] = (
            f"medicamento de referência {med_ref_limpo}"
        )
        replacements["medicamento XXX é equivalente"] = (
            f"medicamento {nome_comercial} é equivalente"
        )
        replacements["conforme bula do produto XXX disponível"] = (
            f"conforme bula do produto {med_ref_limpo} disponível"
        )

        # Embalagem primária
        embalagem = data.tecnologia.embalagem_primaria
        replacements["acondicionado em XXX"] = (
            f"acondicionado em {embalagem or '[VERIFICAR NA BULA]'}"
        )
        replacements["acondicionado em XXX (embalagem primária)"] = (
            f"acondicionado em {embalagem or '[VERIFICAR NA BULA]'} "
            f"(embalagem primária)"
        )

        # Registro MS
        replacements["MS nº 1.XXXX.XXXX"] = (
            f"MS nº {p.numero_registro_ms or '[NÃO LOCALIZADO]'}"
        )
        replacements["registro sanitário MS nº 1.XXXX.XXXX"] = (
            f"registro sanitário MS nº "
            f"{p.numero_registro_ms or '[NÃO LOCALIZADO]'}"
        )

        # DOU
        replacements["Diário Oficial de União n° XX em XX/XX/20XX"] = (
            f"Diário Oficial de União n° "
            f"{p.dou_numero or '[Nº não localizado]'} "
            f"em {p.dou_data or '[Data não localizada]'}"
        )

        # Resolução-RE
        replacements["Resolução-RE n° XX de XX/XX/20XX"] = (
            f"Resolução-RE n° "
            f"{p.resolucao_re_numero or '[Nº não localizado]'} "
            f"de {p.resolucao_re_data or '[Data não localizada]'}"
        )

        # RDC aplicável na publicação
        replacements["Resolução - RDC nº. XX/XXXX"] = (
            f"Resolução - RDC nº. {p.rdc_aplicavel or '[NÃO LOCALIZADO]'}"
        )

        # -------------------------------------------------------------
        # 3. MAPEAMENTO CURINGA PARA EVENTUAIS PLACEHOLDERS XXX DOS MEDICAMENTOS RESTANTES
        # -------------------------------------------------------------
        replacements["O medicamento XXX"] = f"O medicamento {nome_comercial}"
        replacements["medicamento XXX"] = f"medicamento {nome_comercial}"

        # Sort replacements by length descending to avoid partial match overwrites
        sorted_replacements = {k: replacements[k] for k in sorted(replacements, key=len, reverse=True)}
        
        return sorted_replacements

    # --------------------------------------------------------
    # SUBSTITUIÇÃO NO DOCUMENTO
    # --------------------------------------------------------

    def _replace_in_paragraphs(self, doc: Document, replacements: dict):
        """Substitui placeholders em todos os parágrafos e tabelas."""
        for paragraph in doc.paragraphs:
            self._replace_in_paragraph(paragraph, replacements)

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        self._replace_in_paragraph(paragraph, replacements)

    def _replace_in_paragraph(self, paragraph, replacements: dict):
        """Substitui texto em um parágrafo preservando formatação."""
        if not paragraph.runs:
            for old, new in replacements.items():
                if old in paragraph.text:
                    paragraph.text = paragraph.text.replace(old, new)
            return

        full_text = paragraph.text
        for old, new in replacements.items():
            if old in full_text:
                full_text = full_text.replace(old, new)

        if full_text != paragraph.text:
            for run in paragraph.runs:
                run.text = ""
            if paragraph.runs:
                paragraph.runs[0].text = full_text
            else:
                paragraph.add_run(full_text)

    # --------------------------------------------------------
    # BLOCOS CONDICIONAIS
    # --------------------------------------------------------

    def _fill_presentations(self, doc: Document, data: PPAMData):
        """Preenche cada apresentação em seu próprio item de lista, em preto."""
        heading = next(
            (p for p in doc.paragraphs if "Apresentações registradas" in p.text),
            None,
        )
        if heading is not None:
            heading.paragraph_format.space_after = Pt(6)
            heading.paragraph_format.keep_with_next = True

        slots = [p for p in doc.paragraphs if "[descr" in p.text]
        if not slots:
            return

        presentations = data.sumario.apresentacoes or []
        if not presentations:
            presentations = ["[APRESENTAÇÕES NÃO LOCALIZADAS NOS OUTROS DOCUMENTOS]"]

        # Replica o último item de lista se houver mais apresentações que espaços no template.
        anchor = slots[-1]
        while len(slots) < len(presentations):
            cloned = deepcopy(anchor._p)
            anchor._p.addnext(cloned)
            anchor = Paragraph(cloned, anchor._parent)
            slots.append(anchor)

        for index, paragraph in enumerate(slots):
            if index >= len(presentations):
                paragraph._element.getparent().remove(paragraph._element)
                continue
            suffix = "." if index == len(presentations) - 1 else ";"
            text = f"{presentations[index].rstrip('.;')}{suffix}"
            paragraph.paragraph_format.space_before = Pt(3 if index == 0 else 0)
            color = RGBColor(192, 0, 0) if not data.sumario.apresentacoes else RGBColor(0, 0, 0)
            if paragraph.runs:
                for run in paragraph.runs:
                    run.text = ""
                    run.font.color.rgb = color
                run = paragraph.runs[0]
            else:
                run = paragraph.add_run()
            run.text = text
            run.font.color.rgb = color


    def _handle_conditional_blocks(self, doc: Document, data: PPAMData):
        """Remove ou mantém blocos condicionais baseado nos dados extraídos."""
        paragraphs_to_remove = []
        apres_list = data.sumario.apresentacoes or []
        apres_written = False

        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()

            # Processamento de apresentações
            if "[descrição da apresentação]" in text:
                if not apres_written:
                    if apres_list:
                        formatted_list = []
                        for idx, apres in enumerate(apres_list):
                            suffix = "." if idx == len(apres_list) - 1 else ";"
                            formatted_list.append(f"{apres}{suffix}")
                        new_text = "\n".join(formatted_list)
                    else:
                        new_text = "[APRESENTAÇÕES NÃO LOCALIZADAS NOS OUTROS DOCUMENTOS]"
                    
                    for run in paragraph.runs:
                        run.text = ""
                    if paragraph.runs:
                        paragraph.runs[0].text = new_text
                    else:
                        paragraph.text = new_text
                    apres_written = True
                else:
                    paragraphs_to_remove.append(paragraph)

            # CADIFA: manter apenas se aprovada
            if "Cadifa" in text and "aprovada" in text.lower():
                if data.tecnologia.cadifa_aprovada is not True:
                    paragraphs_to_remove.append(paragraph)

            # Perfil de Dissolução: manter apenas se NÃO houve bioequivalência
            if ("Perfil de Dissolução Comparativo" in text or
                    "perfil de dissolução" in text.lower()):
                if (data.seguranca.houve_bioequivalencia is True or
                        data.seguranca.certificado_perfil_dissolucao is not True):
                    paragraphs_to_remove.append(paragraph)

            # Estudo de desempenho: manter apenas se aplicável
            if "desempenho comparativo in vitro" in text.lower() or "foi apresentado estudo comparativo de" in text.lower():
                if data.seguranca.estudo_desempenho.aplicavel is not True:
                    paragraphs_to_remove.append(paragraph)

            # Remoção do texto Genérico/Similar: (EF + Bioisento em razão da FF)
            if "Genérico/Similar: (EF + Bioisento em razão da FF)" in text:
                paragraphs_to_remove.append(paragraph)



        for para in paragraphs_to_remove:
            p_element = para._element
            p_element.getparent().remove(p_element)

    # --------------------------------------------------------
    # LIMPEZA DE TEXTO INSTRUTIVO
    # --------------------------------------------------------

    def _remove_instructional_text(self, doc: Document):
        """Remove texto instrutivo do template (comentários de orientação) sem apagar conteúdo essencial."""
        paragraphs_to_remove = []

        for paragraph in doc.paragraphs:
            text = paragraph.text
            original_text = text
            for pattern in INSTRUCTION_PATTERNS:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    matched_str = match.group(0)
                    # Se o texto da instrução for 80% ou mais do parágrafo inteiro, remove o parágrafo inteiro
                    if len(matched_str.strip()) >= len(text.strip()) * 0.8:
                        paragraphs_to_remove.append(paragraph)
                        break
                    else:
                        # Substitui apenas a instrução, preservando o texto principal
                        text = text.replace(matched_str, "").strip()

            # Se o texto foi modificado mas o parágrafo continua existindo, atualizamos o conteúdo
            if paragraph not in paragraphs_to_remove and text != original_text:
                if paragraph.runs:
                    for run in paragraph.runs:
                        run.text = ""
                    paragraph.runs[0].text = text
                else:
                    paragraph.text = text

        for para in paragraphs_to_remove:
            p_element = para._element
            p_element.getparent().remove(p_element)

    # --------------------------------------------------------
    # MARCAÇÃO DE BAIXA CONFIANÇA
    # --------------------------------------------------------

    def _mark_low_confidence_fields(self, doc: Document, data: PPAMData):
        """Adiciona marcação visual nos campos de baixa confiança."""
        all_low_confidence = (
            data.sumario.campos_baixa_confianca +
            data.tecnologia.campos_baixa_confianca +
            data.seguranca.campos_baixa_confianca +
            data.publicacao.campos_baixa_confianca
        )

        if not all_low_confidence and not data.divergencias_documentos:
            return

        doc.add_paragraph("")
        note = doc.add_paragraph()
        note_run = note.add_run(
            "[NOTA DE REVISÃO — Campos marcados para verificação manual:]"
        )
        note_run.bold = True
        note_run.font.size = Pt(9)

        for field in all_low_confidence:
            p = doc.add_paragraph()
            run = p.add_run(
                f"  • {field}: informação não localizada ou de baixa confiança"
            )
            run.font.size = Pt(9)

        if data.divergencias_documentos:
            div_note = doc.add_paragraph()
            div_run = div_note.add_run("[DIVERGÊNCIAS ENTRE DOCUMENTOS:]")
            div_run.bold = True
            div_run.font.size = Pt(9)

            for div in data.divergencias_documentos:
                p = doc.add_paragraph()
                run = p.add_run(f"  ⚠ {div}")
                run.font.size = Pt(9)
