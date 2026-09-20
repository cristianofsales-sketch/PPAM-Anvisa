# Mapeamento de informações para preenchimento do PPAM

## Escopo

Este documento mapeia o conteúdo exigido pelo template
`templates/FORM-754.POP-F-ANVISA-083_V.03_1_2.docx` para os quatro tipos de
documentos recebidos pela aplicação: Parecer Técnico, Bula do Medicamento,
Publicação no DOU e Outros Documentos.

O template exige três classes diferentes de informação:

1. **Valores dinâmicos**: nomes, concentrações, datas, apresentações e números.
2. **Condições comprovadas**: conclusões técnicas que só podem constar quando
   houver evidência expressa, como aprovação da CADIFA ou resultado satisfatório.
3. **Texto institucional fixo**: título, links e explicações gerais que não
   dependem da extração.

Ausência de informação não significa “não”. Todo campo condicional deve admitir
três estados: **confirmado**, **não confirmado** e **não localizado**.

## Legenda do diagnóstico atual

- **Parcial**: existe no modelo/extrator, mas a regra não é suficientemente segura.
- **Ausente**: o campo ou a granularidade necessária ainda não existe.
- **Incorreto**: há preenchimento automático sem evidência ou associação errada.

## 1. Identificação e sumário do medicamento

| Informação exigida pelo template | Campo canônico proposto | Fonte principal | Obrigatoriedade | Situação atual |
|---|---|---|---|---|
| Categoria: Genérico ou Similar | `sumario.categoria` | Parecer Técnico e DOU | Obrigatório | **Incorreto**: “Genérico” é assumido por padrão e o gerador também força Genérico. |
| Empresa solicitante | `sumario.empresa` | Parecer Técnico | Obrigatório | **Parcial**: existe, mas a expressão atual pode truncar palavras acentuadas. |
| Nome comercial do medicamento | `sumario.nome_medicamento` | Bula, Parecer Técnico e DOU | Obrigatório | **Incorreto**: na ausência do nome, o extrator e o gerador o substituem pelo princípio ativo. |
| Princípio(s) ativo(s) | `sumario.principios_ativos[]` | Bula e Parecer Técnico | Obrigatório | **Parcial**: existe apenas um texto simples; não contempla associações de ativos. |
| Forma farmacêutica do produto teste | `sumario.forma_farmaceutica` | Bula e Parecer Técnico | Obrigatório | **Parcial**: pode truncar palavras acentuadas e não diferencia produto teste e referência. |
| Concentração(ões) do produto teste | `sumario.concentracoes[]` | Bula, Parecer Técnico e apresentações | Obrigatório | **Parcial**: hoje é escolhida a primeira concentração encontrada no documento. |
| RDC vigente no pedido de registro | `sumario.base_registro.numero` e `.data` | Parecer Técnico | Obrigatório | **Incorreto**: `359/2020` é preenchida sem evidência quando nada é encontrado. |
| Composição por unidade/volume | `sumario.composicao.texto` | Bula | Obrigatório | **Parcial**: existe como texto livre; precisa preservar quantidade, unidade, sal e equivalência base/anidra. |
| Quantidade e equivalência do ativo | `sumario.composicao.componentes[]` | Bula | Obrigatório | **Ausente**: não há estrutura para ativo, quantidade, unidade e equivalente. |
| Excipientes, na ordem documental | `sumario.excipientes[]` | Bula | Obrigatório | **Parcial**: a lista existe, mas o uso de conjunto pode alterar a ordem e a separação pode quebrar nomes compostos. |
| Apresentações registradas | `sumario.apresentacoes[]` | Bula, DOU e Outros Documentos | Obrigatório | **Parcial**: hoje a busca ocorre somente em Outros Documentos e armazena texto livre. |
| Dados estruturais de cada apresentação | `sumario.apresentacoes[].{concentracao,forma,quantidade,recipiente,volume,via}` | Bula, DOU e Outros Documentos | Obrigatório | **Ausente**: o modelo não diferencia os componentes de cada apresentação. |
| Medicamento de referência | `sumario.medicamento_referencia.nome` | Parecer Técnico e Bula | Obrigatório | **Parcial**: existe como texto simples e pode truncar acentos. |
| Forma e concentração do medicamento de referência | `sumario.medicamento_referencia.{forma,concentracoes[]}` | Parecer Técnico e estudos | Condicional | **Ausente**: o gerador reutiliza indevidamente forma e concentração do produto teste. |
| Confirmação de equivalência terapêutica | `sumario.equivalencia_terapeutica` | Parecer Técnico | Obrigatório para manter a afirmação | **Ausente**: o texto é inserido como afirmação fixa, sem campo de evidência. |
| Confirmação de mesmas indicações, restrições, via e posologia | `sumario.correspondencia_referencia` | Parecer Técnico | Obrigatório para manter a afirmação | **Ausente**: a afirmação permanece no documento sem validação específica. |

## 2. Tecnologia farmacêutica

| Informação/condição do template | Campo canônico | Fonte principal | Situação atual |
|---|---|---|---|
| CADIFA aprovada | `tecnologia.cadifa.status` | Parecer Técnico e CADIFA | **Parcial**: existe, mas “não encontrado” pode ser tratado como falso e remover o parágrafo. |
| Controle de qualidade do IFA adequado | `tecnologia.controle_qualidade_ifa.status` | Parecer Técnico | **Incorreto**: começa como verdadeiro sem evidência. |
| Validação dos métodos do IFA satisfatória | `tecnologia.validacao_metodos_ifa.status` | Parecer Técnico e relatório analítico | **Parcial**: só reconhece formulações textuais limitadas. |
| Processo de fabricação e controles em processo adequados | `tecnologia.processo_fabricacao.status` | Parecer Técnico | **Parcial**: falso e não localizado não são diferenciados. |
| Consistência dos lotes | `tecnologia.consistencia_lotes.status` | Parecer Técnico | **Ausente**: a conclusão consta no template, mas não há campo próprio. |
| Controle de qualidade do produto terminado adequado | `tecnologia.controle_qualidade_produto.status` | Parecer Técnico | **Incorreto**: começa como verdadeiro sem evidência. |
| Validação dos métodos do medicamento satisfatória | `tecnologia.validacao_metodos_medicamento.status` | Parecer Técnico | **Parcial**: cobertura textual restrita. |
| Embalagem primária | `tecnologia.embalagem_primaria` | Bula e Parecer Técnico | **Parcial**: existe, mas a captura pode absorver texto vizinho e gerar conteúdo corrompido. |

Cada condição técnica deve guardar `status`, `fonte`, `página/seção`, `trecho de
evidência` e `confiança`. O texto afirmativo só poderá permanecer quando o status
for confirmado.

## 3. Segurança, eficácia e estudos

| Informação exigida | Campo canônico proposto | Fonte principal | Situação atual |
|---|---|---|---|
| Modalidade de comprovação | `seguranca.tipo_comprovacao` | Parecer Técnico | **Parcial**: reconhece poucos cenários e depende de frases exatas. |
| Certificado de Equivalência Farmacêutica | `seguranca.equivalencia.certificado_status` | Parecer Técnico e certificado | **Parcial**: a presença é inferida por palavras, sem identificar documento/evidência. |
| Centro de Equivalência Farmacêutica | `seguranca.equivalencia.centro` | Certificado e Parecer Técnico | **Parcial**: a captura atual é frágil. |
| Produto teste: nome, forma e concentração | `seguranca.produto_teste.{nome,forma,concentracoes[]}` | Parecer Técnico e estudo | **Ausente** na granularidade necessária. |
| Produto referência: nome, forma e concentração | `seguranca.produto_referencia.{nome,forma,concentracoes[]}` | Parecer Técnico e estudo | **Ausente** na granularidade necessária. |
| Certificado de Perfil de Dissolução Comparativo | `seguranca.perfil_dissolucao.status` | Parecer Técnico e certificado | **Parcial**: ausência e negativa podem ser confundidas. |
| Houve estudo de bioequivalência | `seguranca.bioequivalencia.status` | Parecer Técnico e relatório do estudo | **Incorreto**: começa como verdadeiro sem evidência. |
| Houve bioisenção | `seguranca.bioisencao.status` | Parecer Técnico | **Parcial**: hoje é inferida por um conjunto pequeno de expressões. |
| Base legal da bioisenção, com artigo/inciso | `seguranca.bioisencao.base_legal[]` | Parecer Técnico | **Parcial**: aceita somente três padrões e grava códigos internos no lugar da citação completa. |
| Aplicabilidade do estudo de desempenho | `seguranca.estudo_desempenho.aplicabilidade` | Parecer Técnico | **Parcial**: usa falso como padrão, mesmo quando não foi possível determinar. |
| Tipo de estudo/ensaio de desempenho | `seguranca.estudo_desempenho.ensaios[]` | Parecer Técnico e relatório | **Ausente**. |
| Medicamento de referência e fabricante | `seguranca.estudo_desempenho.referencia.{nome,forma,concentracao,fabricante}` | Relatório do estudo | **Parcial**: nome e fabricante existem no modelo, mas não são extraídos; forma e concentração não existem. |
| Medicamento teste e fabricante | `seguranca.estudo_desempenho.teste.{nome,forma,concentracao,fabricante}` | Relatório do estudo | **Parcial**: nome e fabricante existem no modelo, mas não são extraídos; forma e concentração não existem. |
| Critérios de aceitação | `seguranca.estudo_desempenho.criterios_aceitacao[]` | Relatório do estudo e Parecer Técnico | **Ausente**. |
| Resultado do estudo | `seguranca.estudo_desempenho.resultado` | Parecer Técnico e relatório | **Parcial**: hoje é reduzido a satisfatório/não satisfatório por uma frase específica. |

## 4. Publicação da decisão

| Informação exigida | Campo canônico proposto | Fonte principal | Situação atual |
|---|---|---|---|
| Número de registro MS | `publicacao.numero_registro_ms` | DOU | **Parcial**: existe, mas a normalização remove pontos e pode alterar a apresentação oficial. |
| Nome do produto publicado | `publicacao.nome_produto` | DOU | **Ausente**: necessário para validar que a publicação pertence ao produto processado. |
| Número/edição do DOU | `publicacao.dou_numero` | DOU | **Parcial**. |
| Data da publicação no DOU | `publicacao.dou_data` | DOU | **Parcial**: o padrão atual é amplo e pode capturar outra data. |
| Número da Resolução-RE | `publicacao.resolucao_re.numero` | DOU | **Parcial**: o padrão pode capturar outro número após a palavra Resolução. |
| Data da Resolução-RE | `publicacao.resolucao_re.data` | DOU | **Ausente na extração**, embora o campo já exista no modelo. |
| RDC aplicável à decisão | `publicacao.base_legal[]` | DOU | **Ausente na extração**, embora exista um campo simples no modelo. |
| Resultado da decisão: deferido/aprovado | `publicacao.decisao` | DOU | **Ausente**: deve impedir a geração de um parecer de aprovação quando a decisão não for de aprovação. |

## 5. Metadados necessários para confiabilidade

Os campos abaixo não aparecem como conteúdo final do template, mas são
necessários para que o preenchimento seja auditável e seguro:

| Metadado | Finalidade |
|---|---|
| `fonte_documento` | Identificar de qual arquivo veio o valor. |
| `pagina_ou_secao` | Permitir conferência rápida no original. |
| `trecho_evidencia` | Demonstrar por que o campo foi aceito. |
| `confianca` | Classificar como alta, média ou baixa, sem inventar valores. |
| `status` | Distinguir confirmado, negado, não localizado e não aplicável. |
| `candidatos[]` | Preservar múltiplos valores antes da desambiguação. |
| `divergencias[]` | Registrar conflito entre Parecer, Bula, DOU e Outros Documentos. |

## 6. Hierarquia de fontes e validação cruzada

1. **DOU** é a fonte autoritativa para decisão, registro MS, edição/data do DOU,
   Resolução-RE e base legal publicada.
2. **Bula** é a fonte preferencial para nome comercial, princípios ativos,
   composição, excipientes, forma, concentrações, apresentações e embalagem.
3. **Parecer Técnico** é a fonte preferencial para empresa, categoria, RDC do
   pedido e conclusões de tecnologia, segurança e eficácia.
4. **Outros Documentos** fornecem evidências complementares: apresentações,
   CADIFA, certificados e relatórios de estudos.
5. Divergências não devem ser resolvidas silenciosamente. O valor autoritativo
   pode preencher o template, mas o conflito deve aparecer na prévia e exigir
   confirmação quando afetar nome, concentração, apresentação, referência ou
   decisão.

## 7. O que é texto fixo e não precisa de extração

Podem permanecer fixos, enquanto este template for usado: cabeçalho Anvisa,
título do parecer, explicações gerais sobre medicamentos genéricos/similares,
referência ao Bulário Eletrônico, orientação de consulta à legislação e o aviso
geral sobre prazo de validade e condições de armazenamento.

As conclusões de adequação, equivalência, aprovação ou resultado satisfatório
**não são texto fixo**. Elas dependem de evidência e devem ser removidas ou
marcadas para revisão quando não forem confirmadas.

## 8. Critérios de aceite para considerar a extração completa

- Nenhum dado regulatório ou conclusão técnica pode ter valor padrão positivo.
- Nome comercial e princípio ativo devem ser campos independentes.
- Expressões devem aceitar caracteres Unicode e não truncar palavras acentuadas.
- Concentrações, princípios ativos, apresentações e bases legais devem aceitar
  múltiplos valores.
- Cada valor inserido deve guardar fonte e evidência rastreável.
- Blocos condicionais só devem aparecer quando a condição tiver sido confirmada.
- Campos não encontrados devem ficar destacados em vermelho na prévia; campos
  encontrados devem permanecer em preto.
- O gerador não pode reutilizar automaticamente forma ou concentração do produto
  teste para descrever o medicamento de referência.
- O nome do produto, registro MS e decisão do DOU devem ser comparados com os
  demais documentos antes da geração.
- Testes automatizados devem usar documentos controlados com valores esperados,
  cobrindo acentos, múltiplas apresentações, associação de ativos, bioisenção,
  bioequivalência, estudo de desempenho e divergência entre fontes.
- Conteúdo dos documentos não deve ser gravado em logs de diagnóstico.

## Ordem recomendada de correção

1. Remover valores inventados e adotar estados de quatro vias: confirmado,
   negado, não localizado e não aplicável.
2. Separar nome comercial, princípio ativo, produto teste e produto referência.
3. Estruturar múltiplos ativos, concentrações e apresentações.
4. Completar publicação/decisão e bloquear parecer de aprovação sem deferimento.
5. Completar evidências de tecnologia, equivalência e estudos.
6. Acrescentar proveniência por campo, validação cruzada e testes de regressão.
