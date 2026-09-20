# Validação PPAM Desktop 1.0.1

Data: 07/09/2026. Estado: **candidato de empacotamento; não homologado para distribuição**.

## Atualização de 08/09/2026 — teste na janela instalada

Após autorização do usuário, o servidor antigo PID 10856 foi encerrado. A cópia instalada em `installed-test/Instalação com espaços` abriu em janela WebView2 própria, servindo exclusivamente `127.0.0.1:7860`.

Com a skill de controle de aplicativos, foram executados seleção de DOCX sintético, upload, processamento, prévia, geração e download pelo diálogo nativo “Salvar como”. O indicador foi observado em 0% durante o pedido e oculto fora do processamento. A prévia exibiu campos ausentes em vermelho e só anunciou documento pronto após gerar o arquivo. A faixa de conteúdo do anexo ficou escura e com texto legível, embora o nome visível seja bastante truncado e os controles do canto ainda tenham fundo branco.

Arquivo de teste salvo: `tests/fixtures/download-validacao-20260908.docx`, 43.368 bytes, 91 parágrafos. O teste de integridade ZIP não encontrou erros e python-docx conseguiu reler o documento. SHA-256: `af2f29a5e17f0e6d1a69f0110dad5660acf60ae0079f1db8c8e42a68220b6ff0`. O arquivo permaneceu após fechar a janela; não foi encontrado listener na porta 7860 após o encerramento. Houve reabertura bem-sucedida nesta sessão. Isso aprova o cenário nominal de salvamento, não os cenários de cancelamento, sobrescrita, permissão negada ou toda a matriz de três ciclos.

### Falha de fidelidade encontrada — bloqueia homologação

A entrada sintética contém “Laboratório Fictício de Teste”, “substância fictícia” e “solução injetável”. A prévia apresentou “Laborat”, “subst” e “solu”. As expressões regulares de `extractor.py` para esses campos usam classes ASCII e param nos caracteres acentuados.

Também apareceu RDC `359/2020`, controle de qualidade do IFA/produto como `Sim` e bioequivalência como `Sim`, apesar de a entrada não informar esses dados. O código inicializa esses campos com valores predefinidos (`extract_sumario`, `extract_tecnologia`, `extract_seguranca`). Portanto, o sucesso do processamento ou do download não demonstra fidelidade do conteúdo. Não usar esse resultado sintético como parecer real.

As regras de extração não foram alteradas nesta rodada: o PRD exclui mudanças nessas regras. A correção precisa de autorização explícita para ampliar esse ponto do escopo. Há ainda logs diagnósticos do extrator que escrevem trechos de documentos; a política de logs do PRD permanece pendente nesse ponto.

As pendências da matriz abaixo continuam válidas, exceto pelos cenários nominais de janela, DOCX e download agora descritos. Windows limpo, instalador interativo/atalhos/registro, desinstalação, demais formatos e casos adversos ainda não estão homologados.

## Artefato identificado

- Pasta da compilação aprovada nos testes automáticos: `build-candidates/20260907-233624`.
- Instalador: `installer/PPAM-Instalador-1.0.1.exe` nessa pasta.
- Tamanho: 185.679.483 bytes.
- SHA-256: `7c46f9c558b3b9d0c62a4f2c38c418c22282564fbb139bc51a6a0e817f953330`.
- Configuração oficial: `packaging/build.spec`, `build_desktop.py`, `build_installer.ps1`, Python 3.11.9 x64, 77 dependências fixadas em `requirements-build.lock.txt`, ambiente `.venv-build` sem acesso aos pacotes globais.
- Nenhum instalador antigo foi substituído. A instalação de produção e o servidor antigo na porta 7860 foram preservados.

## Testes realizados e evidências

1. `pip check`: sem dependências inconsistentes.
2. **12 testes automatizados aprovados**, registrados em `build-candidates/20260907-233624/build.log`: recurso template, estado de processamento após falha, conflitos de porta e listener wildcard, caminhos inseguros, hash inválido, instalação com preservação de exportações em backup, rollback de arquivos diante de falha simulada de registro, destino não reconhecido, entradas vazias/corrompidas/legadas, prévia aninhada/False/ausências/indicador sem 45% fixo, duas apresentações pretas com numeração independente no XML do DOCX.
3. **Autoteste dentro do executável aprovado**: `frozen-self-test.json`. Verifica template, safehttpx/version.txt, frontend do Gradio, configuração e modelos OCR, biblioteca WebView; importa dependências; inicializa RapidOCR; gera e relê DOCX sintético; inicia servidor de teste em porta efêmera e confirma HTTP 200. Esse uso de porta efêmera é exclusivo do autoteste: a aplicação normal continua fixa em 7860.
4. **Verificação dentro do instalador final aprovada**: `installer-verification.json`, 4.672 arquivos com tamanho e SHA-256 conferidos. Não depende de tkinter.
5. **Instalação de teste em diretório novo e autoteste instalado aprovados**: `installed-self-test.json`. A cópia foi feita pelo mesmo mecanismo `install_payload`, em `installed-test/Instalação com espaços`, com diretório de trabalho diferente. Não corresponde a instalação via interface com atalhos/registro nem a máquina sem Python.
6. **Interface Windows do inicializador em código-fonte**: observados aviso de segunda execução durante inicialização e diálogo “PPAM — Porta ocupada” com Repetir/Cancelar. O cancelamento encerrou o diálogo. Validação realizada com a skill de controle de aplicativos. Não comprova restauração de janela carregada nem download via WebView.
7. **Bloqueio de build comprovado**: a primeira compilação em `20260907-233235` falhou ao importar `groovy`, por ausência de `version.txt`. O processo parou antes de criar instalador. A coleta de `groovy` e `hf_gradio` foi acrescentada e a compilação seguinte passou. Os logs da falha foram preservados como evidência; essa pasta não é uma entrega válida.

Os testes não utilizaram documentos privados como entradas; utilizaram arquivos sintéticos ou o template da própria aplicação. Processos de teste criados nesta execução foram encerrados; o servidor existente não foi encerrado.

## Pendências da matriz do PRD

| Testes | Estado / limite |
| --- | --- |
| T01, T02, T18 | Testes automatizados de recursos, regressão dos imports e interrupção de build aprovados. |
| T03 | Pendente instalação por usuário em Windows limpo sem Python, atalhos e registro reais. |
| T04 | WebView2 detectado nesta máquina; falta testar runtime ausente e compatibilidade .NET na matriz-alvo. |
| T05 | Espaços/acentos e diretório de trabalho diferente aprovados no autoteste instalado; reinício e abertura por atalho pendentes. |
| T06 | Conflito e segunda abertura em inicialização verificados no código-fonte; restauração da janela principal empacotada pendente. |
| T07, T08 | Fluxo completo visual, anexos e OCR real de imagem/PDF sintéticos e medição de rede offline pendentes. Inicialização de OCR e servidor não substituem esses testes. |
| T09, T10 | Entradas inválidas testadas no código; fluxo UI e cenários de falha/ausência de texto de OCR pendentes. |
| T11, T12 | Asserções de prévia e XML/DOCX aprovadas; renderização visual do documento e cenários completos pendentes. |
| T13 | Salvamento/download via WebView, cancelamento, sobrescrita e destino sem permissão pendentes. |
| T14, T15 | Preflight implementado; remoção deliberada em cópia congelada e ciclos completos de fechamento/reabertura pendentes. |
| T16 | Staging, integridade, preservação e rollback de arquivos testados; falta testar atualização real em uso, sem espaço e interrupções, incluindo efeitos de atalhos/registro. |
| T17 | Desinstalador implementado; falta executar em instalação de teste com atalhos/registro e exportações preservadas. |

## Limites conhecidos de implementação

- Temporários são isolados por sessão, mas retidos para diagnóstico; não há limpeza automática nesta versão.
- A instalação preserva versões anteriores inteiras em backups, em vez de eliminá-las automaticamente.
- O rollback automatizado cobre os arquivos; atomicidade dos efeitos externos de atalhos/registro ainda precisa de implementação/validação adicional.
- Log técnico principal tem rotação; saída de console é mantida em arquivo separado sem rotação.
- Pré-requisito WebView2 é detectado; falha de carregamento de .NET é capturada na abertura, mas não há preflight independente completo para cada versão de Windows.

Próximo passo: após autorização para encerrar a versão antiga na porta 7860, testar a janela do aplicativo empacotado e o ciclo de geração/download. Depois concluir as lacunas acima e homologar em ambiente Windows limpo. Não classificar pendências como aprovação.
