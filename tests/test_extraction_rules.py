import unittest
import tempfile
from pathlib import Path
from PIL import Image
from docx import Document
from docx.shared import Cm

from document_processor import DocumentProcessor
from extractor import PPAMExtractor
from models import DadosMedicamento, PPAMData, PublicacaoDecisao
from template_filler import TemplateFiller


class ExtractionRulesTest(unittest.TestCase):
    def setUp(self):
        self.extractor = PPAMExtractor()

    def test_unicode_fields_are_not_truncated(self):
        parecer = """
Empresa | Laboratório São João S.A. |
Princípio ativo | substância fictícia sódica |
Nome comercial | Produto Ágil |
Forma farmacêutica | solução injetável |
Medicamento de Referência | Referência Única |
"""
        result = self.extractor.extract_sumario(parecer)

        self.assertEqual(result.empresa, "Laboratório São João S.A.")
        self.assertEqual(result.principio_ativo, "substância fictícia sódica")
        self.assertEqual(result.nome_medicamento, "Produto Ágil")
        self.assertEqual(result.forma_farmaceutica, "solução injetável")
        self.assertEqual(result.medicamento_referencia, "Referência Única")
        self.assertEqual(result.categoria, "Genérico")

    def test_primary_packaging_comes_only_from_technical_opinion(self):
        parecer = "Embalagem primária | frasco-ampola de vidro âmbar com 2 mL |"
        bula = "Embalagem primária | blíster de alumínio |"

        result = self.extractor.extract_tecnologia(parecer, bula)
        self.assertEqual(result.embalagem_primaria, "frasco-ampola de vidro âmbar com 2 mL")

        without_opinion_value = self.extractor.extract_tecnologia("Sem esse campo.", bula)
        self.assertIsNone(without_opinion_value.embalagem_primaria)

    def test_dou_uses_only_the_delimited_labels(self):
        dou_text = """
Resolução 999 de 18/09/2026
Nº do DOU:
187
Publicado em: 20/09/2026
"""
        result = self.extractor.extract_publicacao(
            dou_text,
            principio_ativo="substância fictícia",
            numero_registro_ms=" 1.1234.5678.001-9 ",
        )

        self.assertEqual(result.numero_registro_ms, "1.1234.5678.001-9")
        self.assertEqual(result.nome_produto, "substância fictícia")
        self.assertEqual(result.dou_numero, "187")
        self.assertEqual(result.dou_data, "20/09/2026")

        unlabeled = self.extractor.extract_publicacao(
            "Diário Oficial 321, de 21/09/2026",
            principio_ativo="ativo",
            numero_registro_ms="1.0000.0000.001-0",
        )
        self.assertIsNone(unlabeled.dou_numero)
        self.assertIsNone(unlabeled.dou_data)

    def test_manual_registration_and_active_ingredient_flow_through_extract_all(self):
        parecer = "Princípio ativo | cloridrato de substância ácida |"
        dou = "Nº do DOU: 44\nPublicado em: 01/02/2026"
        result = self.extractor.extract_all(
            parecer,
            "",
            dou,
            "",
            numero_registro_ms="1.2222.3333.001-4",
        )

        self.assertEqual(result.publicacao.numero_registro_ms, "1.2222.3333.001-4")
        self.assertEqual(result.publicacao.nome_produto, "cloridrato de substância ácida")

    def test_template_uses_trade_name_except_for_published_product(self):
        data = PPAMData(
            sumario=DadosMedicamento(
                nome_medicamento="Marca Comercial",
                principio_ativo="princípio ativo correto",
            ),
            publicacao=PublicacaoDecisao(nome_produto="princípio ativo correto"),
        )
        replacements = TemplateFiller("unused.docx")._build_replacement_map(data)

        self.assertIn("Marca Comercial", replacements["O medicamento XXX"])
        self.assertEqual(
            replacements["para o medicamento XXX no Diário Oficial de União"],
            "para o medicamento princípio ativo correto no Diário Oficial de União",
        )

    def test_technical_conclusions_are_not_positive_by_default(self):
        result = self.extractor.extract_tecnologia("Texto sem conclusões técnicas.")
        self.assertIsNone(result.cadifa_aprovada)
        self.assertIsNone(result.controle_qualidade_ifa)
        self.assertIsNone(result.processo_fabricacao)
        self.assertIsNone(result.controle_qualidade_produto)

    def test_small_images_are_upscaled_before_ocr(self):
        image = Image.new("RGB", (860, 367), "white")
        prepared = DocumentProcessor._prepare_image_for_ocr(image)

        self.assertEqual(prepared.size, (1720, 734))

    def test_bula_composition_and_excipients_stop_at_section_boundaries(self):
        bula = """
COMPOSIÇÃO
Cada frasco-ampola contém 60 mg de carfilzomibe*.
Excipientes: éter sulfobutílico sódico beta ciclodextrina, ácido cítrico e hidróxido de sódio.
* Após reconstituição, cada mL contém 2 mg de carfilzomibe.
"""
        result = self.extractor.extract_sumario("", bula)

        self.assertEqual(
            result.composicao,
            "Cada frasco-ampola contém 60 mg de carfilzomibe*. Após reconstituição, cada mL contém 2 mg de carfilzomibe.",
        )
        self.assertEqual(
            result.excipientes,
            [
                "éter sulfobutílico sódico beta ciclodextrina",
                "ácido cítrico",
                "hidróxido de sódio",
            ],
        )

    def test_multiline_composition_keeps_active_amount_and_equivalence(self):
        """Reproduz a bula cujo conteúdo de composição ocupa várias linhas."""
        bula = """COMPOSICAO:
Cada mL contem:
cloridrato de escetamina ....
. 57,668 mg
(equivalente a 50 mg de escetamina)
Excipientes: agua para injetaveis, acido cloridrico e/ou hidroxido de sodio para ajuste de pH
"""

        result = self.extractor.extract_sumario("", bula)

        self.assertEqual(
            result.composicao,
            "Cada mL contem: cloridrato de escetamina 57,668 mg (equivalente a 50 mg de escetamina)",
        )

    def test_presentations_exclude_registration_numbers_and_expand_codes(self):
        text = """
Apresentação
Registro
60 MG PO LIOF SOL INFUS IV CT FA VD TRANS
1826100210015
30 MG PO LIOF SOL INFUS IV CT FA VD TRANS
1826100210023
10 MGPO LIOF SOL INFUS IV CT FA VD TRANS
1826100210031
"""
        result = self.extractor._extract_apresentacoes(text)

        self.assertEqual(len(result), 3)
        self.assertTrue(all("182610" not in item for item in result))
        self.assertEqual(
            result[0],
            "60 mg Pó liofilizado para solução para infusão IV - Cartucho, Frasco-ampola de vidro transparente",
        )

    def test_presentations_accept_compact_strength_with_mg_per_ml(self):
        """Reproduz exatamente o OCR da imagem enviada em 20/09/2026."""
        text = """Apresentacao
50MG/MLSOLINJIM/IVCX25AMPVDAMBX2ML
50MG/MLSOLINJIM/IVCX36AMPVDAMBX2ML
"""

        result = self.extractor._extract_apresentacoes(text)

        self.assertEqual(
            result,
            [
                "50 mg/mL Sol. Inj. IM/IV - Cx. 25 Amp. Vd. Amb. x 2 mL",
                "50 mg/mL Sol. Inj. IM/IV - Cx. 36 Amp. Vd. Amb. x 2 mL",
            ],
        )

    def test_dou_labels_accept_removed_spaces_from_ocr(self):
        text = "N°doDOU\n174\nPublicadoem\n09/09/2024"
        result = self.extractor.extract_publicacao(text)

        self.assertEqual(result.dou_numero, "174")
        self.assertEqual(result.dou_data, "09/09/2024")

    def test_generated_document_keeps_body_clear_of_footer(self):
        data = PPAMData(
            sumario=DadosMedicamento(
                empresa="Empresa",
                principio_ativo="Ativo",
                apresentacoes=["60 mg Pó liofilizado para solução para infusão IV"],
            )
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "layout.docx"
            TemplateFiller().fill(data, str(output))
            document = Document(output)
            for section in document.sections:
                self.assertGreaterEqual(section.bottom_margin, Cm(2.49))
                self.assertLessEqual(section.footer_distance, Cm(1.26))
            heading = next(p for p in document.paragraphs if "Apresentações registradas" in p.text)
            first_item = next(p for p in document.paragraphs if p.text.startswith("60 mg"))
            self.assertGreaterEqual(heading.paragraph_format.space_after.pt, 6)
            self.assertGreaterEqual(first_item.paragraph_format.space_before.pt, 3)


if __name__ == "__main__":
    unittest.main()
