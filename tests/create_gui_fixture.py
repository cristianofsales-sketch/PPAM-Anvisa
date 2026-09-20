"""Synthetic input for local desktop acceptance; no patient or real product data."""
from pathlib import Path
from docx import Document

target = Path(__file__).resolve().parent / 'fixtures'
target.mkdir(exist_ok=True)
document = Document()
document.add_heading('PARECER TÉCNICO — TESTE FICTÍCIO', 0)
for text in (
    'Documento sintético destinado exclusivamente à validação de software.',
    'Empresa: Laboratório Fictício de Teste',
    'Princípio ativo: substância fictícia',
    'Categoria: Genérico',
    'Forma farmacêutica: solução injetável',
    'Concentração: 50 mg/ml',
    'Apresentações registradas:',
    '50 mg/ml SOL INJ IM/IV - Cx. 25 Amp. Vd. Amb. x 2 ml;',
    '50 mg/ml SOL INJ IM/IV - Cx. 36 Amp. Vd. Amb. x 2 ml.',
    '2.4 Tecnologia farmacêutica',
    'Dados intencionalmente incompletos para verificar os avisos de campos ausentes.',
):
    document.add_paragraph(text)
document.save(target / 'parecer-sintetico.docx')
print(target / 'parecer-sintetico.docx')
