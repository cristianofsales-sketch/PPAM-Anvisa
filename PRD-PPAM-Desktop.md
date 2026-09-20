# PRD — PPAM Desktop para Windows

Versão: 1.0 · Data: 07/09/2026 · Idioma: português do Brasil

Status: especificação para a próxima implementação. O instalador existente apresenta falha de inicialização e não está homologado. Este documento não certifica nem corrige o executável atual.

## 1. Objetivo e resultado esperado

Transformar a aplicação Python/Gradio existente em um aplicativo Windows instalável, com janela própria, preservando o fluxo e o layout acordados. O usuário deve conseguir instalar, abrir, anexar documentos, acompanhar o processamento local, revisar os dados e salvar o parecer DOCX sem instalar Python, executar comandos ou abrir manualmente um navegador.

Um PRD não garante ausência absoluta de erros. O compromisso verificável desta entrega será: corrigir as falhas conhecidas, tratar falhas previsíveis com mensagens claras e somente liberar um instalador que tenha passado pelos testes de instalação e uso descritos aqui.

Usuário principal: profissional que prepara e revisa PPAM a partir de documentos técnicos. O documento gerado continua sujeito à revisão humana; fidelidade de apresentação dos dados não equivale a garantia de acerto da extração.

## 2. Diagnóstico baseado no projeto atual

As verificações desta seção foram feitas por leitura do código, da distribuição em `dist/PPAM Anvisa` e das capturas fornecidas. Não foi executada uma nova instalação nesta etapa.

| ID | Evidência | Consequência | Situação |
| --- | --- | --- | --- |
| D01 | Captura anterior: `No module named 'tkinter'`. O `installer.py` atual utiliza `ctypes`/`MessageBoxW`. | O primeiro instalador falhava antes da instalação. | Alteração no código confirmada; o ciclo completo ainda precisa de teste. |
| D02 | Captura atual: ausência de `_internal/safehttpx/version.txt`. Esse arquivo não existe em `dist/PPAM Anvisa/_internal`; o `safehttpx` instalado lê `version.txt` ao importar. | O aplicativo encerra durante os imports, antes de abrir a janela. | Falha de recurso empacotado confirmada. |
| D03 | O template `templates/FORM-754.POP-F-ANVISA-083_V.03_1_2.docx` é exigido por `config.py`, mas não existe na distribuição `PPAM Anvisa`. | A geração do parecer falharia mesmo após corrigir a inicialização. | Ausência confirmada; não é a causa do erro da captura atual. |
| D04 | `desktop_app.py` chama `app.launch(theme=None)` sem passar `CUSTOM_CSS`; o modo navegador passa tema e CSS explicitamente. | Há risco de diferença visual entre navegador e aplicativo. | Divergência de configuração confirmada; efeito visual ainda não testado. |
| D05 | O desktop utiliza a porta 7860 sem tratamento de conflito e importa a aplicação antes de configurar tratamento geral de falhas. | Porta ocupada ou erro de importação pode encerrar o aplicativo com traceback. | Lacuna de tratamento confirmada. |
| D06 | `PPAM.spec` inclui templates; `PPAM Anvisa.spec` coleta três pacotes e não declara o template local. `installer.iss` aponta para `dist/PPAM`; `installer.py` usa o pacote `PPAM Anvisa`. | Processos de build diferentes podem produzir versões incompatíveis. | Mais de uma configuração concorrente confirmada. |
| D07 | `requirements.txt` tem limites mínimos sem travamento completo de versões. `build_installer.ps1` não verifica explicitamente `$LASTEXITCODE` após cada executável. | Um build pode variar ou continuar após falha, empacotando artefatos antigos. | Risco de reprodutibilidade e de entrega confirmado no código. |
| D08 | O instalador atual copia arquivos diretamente sobre o destino e verifica apenas a presença do executável; não cria atalhos nem implementa desinstalação. | Cópia parcial pode ser confundida com instalação válida; uso posterior não corresponde a uma instalação completa. | Lacunas confirmadas. |
| D09 | `app.py` importa fonte do Google; a inicialização desktop não define política explícita de telemetria e recursos externos. | A alegação de execução offline exige verificação de rede e ajuste de recursos. | Fonte externa confirmada; demais conexões precisam ser medidas. |
| D10 | `render_results` ignora `estudo_desempenho` e `campos_baixa_confianca`, não apresenta divergências e usa mensagem de sucesso antes de o DOCX ser produzido. | A prévia não cobre todo o modelo e o status pode antecipar uma conclusão. | Divergência confirmada com os requisitos já solicitados. |
| D11 | A versão local de pywebview define `ALLOW_DOWNLOADS=False`; seu backend WebView2 cancela downloads nessa condição. `desktop_app.py` não altera essa opção. | O botão de baixar documento requer configuração e teste específicos na janela desktop. | Configuração confirmada; efeito no fluxo instalado ainda não testado nesta etapa. |

A solução de D02 deve incluir o arquivo real fornecido pela dependência, no caminho esperado, e validar sua leitura no executável. Criar um arquivo vazio ou apenas esconder a exceção não satisfaz o requisito. A documentação do PyInstaller distingue a coleta de módulos, arquivos de dados, binários e metadados; a configuração precisa contemplar os recursos utilizados em execução. [Referência: hooks do PyInstaller](https://pyinstaller.org/en/latest/hooks.html).

## 3. Escopo e decisões de produto

### Incluído

- Aplicativo Windows x64 com janela própria, mantendo Gradio para a interface e pywebview para a janela.
- Instalador por usuário, executável independente do Python instalado no computador e acesso pelo menu Iniciar.
- Correção do empacotamento, inicialização, salvamento de documentos, encerramento e recuperação de erros.
- Preservação da primeira página, dos cartões de anexos legíveis e dos estados do indicador já acordados.
- Validação da segunda página, dos dados exibidos e das apresentações em itens separados no DOCX.

### Fora desta versão

- Novos modelos de IA, alterações nas regras de extração ou novos pareceres regulatórios.
- Exportação em PDF, macOS, Linux, Windows 32 bits e suporte nativo ARM.
- Contas, autenticação em nuvem, sincronização, serviço permanente ou inicialização automática com o Windows.
- Novo desenho da primeira página ou mudanças no conteúdo técnico do template.
- Garantia de reconhecimento perfeito por OCR.

### Premissas propostas para a implementação

| Item | Definição |
| --- | --- |
| Plataforma-alvo | Windows 10/11 x64; declarar compatibilidade somente com as versões efetivamente testadas. |
| Porta | Manter 7860, conforme última instrução do usuário. Sem troca silenciosa e sem encerrar processos de terceiros. |
| Acesso local | Servidor interno restrito a `127.0.0.1:7860`, compartilhamento público desativado. |
| Instalação | Pasta do usuário em `%LOCALAPPDATA%/PPAM Anvisa`, com atalhos e desinstalação. |
| Formato de saída | DOCX. Formato, tamanho e demais informações devem corresponder ao arquivo real. |
| Funcionamento offline | Após resolver os pré-requisitos do Windows, anexar, extrair, revisar e exportar sem internet. |
| Motor da janela | WebView2, com pré-requisito detectado e caminho de instalação claro quando ausente. |

A presença das DLLs de integração pywebview no pacote não comprova a disponibilidade do runtime necessário no Windows de destino. A escolha deve ser validada em máquina sem ambiente de desenvolvimento. [Referências: instalação](https://pywebview.flowrl.com/guide/installation.html) e [empacotamento do pywebview](https://pywebview.flowrl.com/guide/freezing.html).

## 4. Jornada e requisitos funcionais

Todos os requisitos abaixo são obrigatórios para liberar a versão descrita neste PRD. Eles definem comportamento futuro, não funcionalidades já verificadas.

### RF01 — Instalar e voltar a abrir

O instalador deve identificar a versão, informar o destino, mostrar progresso e verificar pré-requisitos e espaço necessário antes de concluir. Deve criar entrada no menu Iniciar e oferecer atalho na área de trabalho. Abrir por qualquer atalho deve funcionar sem terminal e sem depender da pasta de trabalho do projeto.

O instalador só poderá informar que a instalação foi concluída após verificar a integridade do pacote instalado. A abertura da aplicação é uma etapa separada: se falhar, apresentar o erro e não afirmar que ela está pronta para uso.

### RF02 — Atualização, reparo e remoção

Uma reinstalação deve detectar arquivos em uso, oferecer fechar a aplicação ou cancelar, e não produzir mistura entre versões. Copiar e verificar em área temporária antes de substituir a versão instalada; em caso de falha, preservar ou restaurar a instalação anterior.

A desinstalação deve remover somente arquivos e atalhos da aplicação. Documentos exportados pelo usuário devem ser preservados. Dados locais e logs devem ter política explícita de retenção, sem exclusão silenciosa dos documentos de trabalho.

### RF03 — Inicialização confiável

O inicializador deve registrar erros desde antes dos imports pesados, validar recursos essenciais e pré-requisitos, iniciar o servidor e aguardar sua prontidão antes de carregar a interface. Durante a espera, apresentar um estado de abertura perceptível.

Recurso ausente deve gerar mensagem identificável e acionável, por exemplo: “A instalação está incompleta. Reinstale esta versão do PPAM. Código: RECURSO_AUSENTE.” O detalhe técnico fica no log, não como único diálogo de erro do usuário.

### RF04 — Porta ocupada e segunda execução

Se a própria instância desktop estiver aberta, um novo clique deve ativar a janela existente. Se a porta 7860 pertencer a outra aplicação ou à versão de navegador, informar o conflito e permitir tentar novamente após a liberação. Não conectar a um servidor apenas porque responde na porta, não matar processos e não alterar a porta automaticamente.

### RF05 — Aparência e anexos

Compartilhar tema e CSS entre os modos navegador e desktop. Manter as quatro categorias de arquivos e a leitura de nomes/tamanhos sobre fundo escuro. Validar anexos por seleção, arrastar e soltar, múltiplos arquivos e remoção.

O selo “Processamento local” fica visível. O ícone/painel permanece fixo; círculo, percentual e mensagens de processamento aparecem somente durante o pedido. O progresso deve avançar por etapas concluídas, sem temporizador simulado ou 45% fixo.

### RF06 — Processar e tratar entradas inválidas

Sem Parecer Técnico obrigatório, permanecer na primeira página com mensagem de validação. Documento ilegível, corrompido, sem texto ou com falha de OCR não pode ser contado como processado com sucesso nem convertido silenciosamente em informação clínica extraída.

Preservar a leitura de PDF pesquisável, DOCX e imagens suportadas. O `.doc` legado atualmente é encaminhado ao leitor DOCX, e o PDF escaneado não recebe OCR completo: não anunciar suporte validado sem teste; enquanto não suportados, orientar conversão explicitamente. Adicionar conversores é evolução separada, não obrigação de ampliar a extração nesta entrega.

### RF07 — Prévia fiel e alertas

Apresentar todos os campos do modelo `PPAMData`, inclusive campos aninhados de estudo de desempenho, com o valor processado. “100% das informações” significa cobertura do modelo e correspondência com os valores extraídos, não inventar valores ausentes.

Campos ausentes devem ter texto “Não localizado” e alerta vermelho. `False` deve aparecer como “Não”, sem ser confundido com ausência. “Não aplicável” só será usado quando a aplicabilidade estiver determinada. Campos de baixa confiança e divergências devem ser identificáveis, com motivo, sem ocultar o valor encontrado. Listas e dados longos devem poder ser lidos por completo.

### RF08 — Status e dados de processamento

Separar os estados “prévia disponível”, “gerando documento” e “documento pronto”. “Pronto para download” só aparece quando o DOCX existe e foi validado. Mostrar duração medida e distinguir quantidade enviada, quantidade processada e falhas.

Exibir apenas informações verdadeiras: formato DOCX e tamanho real após a geração. Não copiar da referência números de arquivos, duração, páginas ou tamanho; omitir contagem de páginas se não houver cálculo confiável.

### RF09 — Exportar em janela desktop

Gerar o DOCX com o template incluído no pacote e permitir salvar em local escolhido pelo usuário, com tratamento para cancelamento, destino sem permissão e arquivo existente. Validar o download dentro do WebView, inclusive depois que o usuário encerra a aplicação.

Configurar explicitamente o mecanismo de download/salvamento da janela. A configuração padrão de pywebview hoje presente no projeto não deve ser presumida compatível com o botão de exportação.

Cada apresentação extraída deve corresponder a um parágrafo de lista com sua própria marcação, texto preto e ordem preservada. Para duas apresentações, duas marcações; para outras quantidades, uma por item, sem concatenar tudo em uma marcação. Preservar os demais estilos e conteúdo do documento. Ausências continuam identificadas na prévia.

### RF10 — Encerrar e começar outro pedido

Ao fechar, liberar a porta e encerrar somente o servidor e os processos pertencentes à aplicação. Se houver trabalho em curso, avisar sobre a interrupção. Reabrir deve funcionar. “Novo Processamento” deve iniciar um pedido sem misturar valores, resultados ou arquivos exportados de outro pedido.

## 5. Arquitetura e requisitos de distribuição

Fluxo proposto: instalador → diretório verificado → inicializador desktop → verificação de recursos/porta/runtime → servidor local pronto → janela WebView → processamento → prévia → salvamento → encerramento.

| ID | Requisito técnico verificável |
| --- | --- |
| RT01 | Usar ambiente de build isolado, versões travadas das dependências diretas e transitivas, Python e PyInstaller registrados. |
| RT02 | Consolidar uma configuração oficial de aplicativo e uma de instalador. Eliminar a ambiguidade entre `PPAM`, `PPAM Anvisa` e seus destinos, sem reutilizar artefatos antigos por engano. |
| RT03 | Manifesto de recursos: template DOCX; `safehttpx/version.txt`; dados e metadados exigidos por Gradio e dependências; frontend; OCR/modelos/configurações; bibliotecas nativas e recursos da janela. Verificar conteúdo e hashes, não só nomes. |
| RT04 | Resolver recursos relativos ao pacote e dados graváveis relativos à pasta do usuário. Não depender de caminhos de `crist`, Python instalado, diretório de desenvolvimento ou cache da sessão anterior. |
| RT05 | Registrar saída e código de retorno de cada etapa de build. Falha interrompe a sequência; impedir criação/entrega de instalador a partir de um executável incompleto ou antigo. |
| RT06 | Validar o executável em pasta primeiro; somente depois incorporá-lo no instalador. Testar novamente a cópia instalada pelo instalador final. |
| RT07 | Desativar telemetria desnecessária e dependências de rede na operação local. Fonte e recursos visuais devem funcionar offline; usar recurso local licenciado ou fallback compatível. |
| RT08 | Definir suporte e verificação de WebView2/.NET na combinação escolhida. Runtime ausente gera orientação de instalação; não baixar nem instalar pré-requisitos silenciosamente. |
| RT09 | Permitir diagnóstico de inicialização, operação e exportação com versão, horário, etapa e traceback. Logs técnicos não devem copiar o texto dos documentos. Auditoria com dados do parecer é um artefato local separado. |
| RT10 | Entregar versão identificada, SHA-256, tamanho, instruções de instalação/remoção e relatório dos testes realizados. Hash identifica o arquivo; não prova que ele funciona. |

Preferência técnica: distribuição do aplicativo em pasta, embutida em um instalador único com instalação por usuário. A ferramenta do instalador pode ser mantida ou substituída por uma apropriada se cumprir RF01/RF02; a decisão deve ser registrada antes do build. Não há obrigação de manter o copiador Python atual.

O aplicativo deve guardar temporários em local gravável próprio e limpar apenas temporários sob seu controle. Não apagar documentos originais, downloads salvos ou arquivos de outras aplicações. A distribuição não deve conter documentos reais usados no desenvolvimento.

## 6. Metas de qualidade

- Zero falhas críticas conhecidas de instalação, abertura, processamento ou salvamento na matriz homologada.
- Nenhuma dependência de Python/pip/ambiente de desenvolvimento no computador de destino.
- Nenhuma conexão externa necessária no fluxo local validado, após instalação dos pré-requisitos.
- Meta inicial proposta: interface utilizável em até 30 segundos após iniciar o aplicativo instalado, em Windows x64 com SSD e 8 GB de RAM; medir e registrar primeira abertura e aberturas seguintes. Este valor é meta, não desempenho medido.
- Não estabelecer tempo fixo de OCR para qualquer documento; registrar tamanho, páginas e duração do conjunto de teste.
- Operação legível em 1366×768 e 1920×1080, escalas de 100% e 125%, com rolagem quando necessária.

## 7. Matriz obrigatória de validação

Preparar dados sintéticos/fictícios com resultados esperados, incluindo duas apresentações, campos ausentes, booleanos e campos aninhados. Não depender de documentos privados encontrados no cache do computador.

| Teste | Cenário | Critério de aprovação |
| --- | --- | --- |
| T01 | Inventário da distribuição | Todos os recursos de RT03 presentes, legíveis e coerentes com o manifesto; falta de recurso bloqueia a entrega. |
| T02 | Regressão dos dois erros reportados | Instalador não depende de `tkinter`; importação de `safehttpx` funciona dentro do executável empacotado, sem buscar arquivos no Python do desenvolvedor. |
| T03 | Instalação limpa, usuário comum | Instala, cria atalhos e abre em Windows sem Python e sem o código-fonte. Registrar versão do Windows e runtimes. |
| T04 | WebView2/runtime ausente | Fluxo claro de pré-requisito, sem tela branca, traceback ou sucesso indevido. Repetir com runtime presente. |
| T05 | Caminhos diferentes | Executar por atalho com outra pasta de trabalho, perfil com espaços/acentos e após reiniciar o computador. |
| T06 | Porta e múltiplas instâncias | 7860 livre abre; segunda instância do PPAM ativa a existente; ocupação por terceiro informa conflito sem encerrar o terceiro. |
| T07 | Layout e anexos | Duas páginas com estilos carregados; nome/tamanho legíveis; círculo/textos só durante o processo; zero 45% fixo. |
| T08 | Fluxo nominal offline | Anexar DOCX, PDF pesquisável e imagem sintética, extrair, revisar e salvar DOCX/auditoria; verificar ausência de dependência externa no fluxo. |
| T09 | Entradas inválidas | Sem parecer, arquivo vazio/corrompido e formato não suportado não levam a “sucesso”; mensagem orienta correção. |
| T10 | OCR sem texto/falha | Falha identificada por arquivo; nenhum texto de erro entra como dado extraído; usuário pode tentar outro arquivo. |
| T11 | Dados completos e incompletos | Prévia cobre campos simples, listas, campos aninhados, baixa confiança e divergências; ausentes em vermelho; `False` continua “Não”. |
| T12 | Geração e apresentações | Template disponível no instalado; DOCX abre sem reparação e tem dois itens independentes pretos no caso de teste com duas apresentações. Inspecionar conteúdo e renderização. |
| T13 | Download/salvamento | Arquivo salvo pelo WebView é o DOCX gerado e permanece após encerrar; cancelar, negar escrita e substituir arquivo têm comportamento definido. |
| T14 | Recurso deliberadamente removido em cópia de teste | Falha de template/modelo/recurso é diagnosticada com mensagem e log; sem falso “documento pronto”. |
| T15 | Fechar e reabrir | Porta é liberada, não ficam processos órfãos; repetir três ciclos e testar fechamento durante processamento. |
| T16 | Reinstalar/atualizar | Aplicação aberta, cópia interrompida e destino sem espaço não deixam instalação parcial marcada como pronta; preservar versão anterior e exportações. |
| T17 | Desinstalar | Remove arquivos/atalhos do programa e preserva documentos exportados. |
| T18 | Falha de build | Forçar falha de etapa impede a próxima e impede anúncio de sucesso; artefato antigo não é entregue. |

Para cada teste registrar versão/hash do instalador, ambiente, entrada, resultado esperado, resultado observado e evidência apropriada (log, captura ou documento). Comparações de integridade do DOCX devem considerar texto, listas, estilos e conteúdo, sem exigir identidade binária entre arquivos com metadados de geração diferentes.

## 8. Sequência de execução e condições de liberação

1. Consolidar o diagnóstico, configuração oficial e dependências travadas a partir deste PRD.
2. Corrigir recursos ausentes e inicialização desktop; garantir tema/CSS e tratamento da porta.
3. Preparar testes sintéticos e validar o executável empacotado, inclusive leitura/OCR e geração de DOCX.
4. Concluir instalação, reparo/atualização, atalhos e desinstalação; gerar candidato versionado.
5. Instalar o candidato em ambiente Windows limpo e executar T01–T18, com evidências. Corrigir e repetir testes afetados em caso de falha.
6. Entregar o instalador homologado, checksum, instruções e relatório de validação.

Não liberar se existir falha de recurso/importação, perda de documento, download inoperante, ausência de teste em ambiente limpo ou falso status de sucesso. Os testes críticos não podem ser substituídos por `py_compile`, HTTP 200, existência do `.exe` ou aumento de CPU durante o build.

Se um ambiente necessário não estiver disponível, registrar o teste como pendente e a compatibilidade como não verificada. Não considerar pendência aprovada. A execução do instalador pelo usuário final não deve ser a primeira validação de ponta a ponta.

## 9. Rastreabilidade e limites desta etapa

Arquivos revisados: `desktop_app.py`, `installer.py`, `build_installer.ps1`, `PPAM Anvisa.spec`, `PPAM-Instalador.spec`, `PPAM.spec`, `installer.iss`, `requirements.txt`, `config.py`, `app.py`, `document_processor.py`, `models.py`, `audit.py` e conteúdo pontual da distribuição.

A definição anterior da porta 7860 prevalece sobre as solicitações antigas de portas alternativas. O layout e o conteúdo técnico existente são a base; este PRD não autoriza mudanças adicionais em regras de extração ou pareceres.

Entrega desta etapa: este PRD, com causas verificadas, requisitos e critérios de aceite. As correções e uma nova versão do instalador constituem a etapa de implementação posterior.
