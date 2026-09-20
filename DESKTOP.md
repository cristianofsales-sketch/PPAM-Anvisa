# PPAM Desktop 1.0.1 — candidato em validação

O aplicativo usa janela própria (WebView2), servidor exclusivo em `127.0.0.1:7860` e processamento local. Não encerra outros programas quando a porta está ocupada. O computador de destino não precisa instalar Python; precisa do Microsoft Edge WebView2 Runtime e do .NET Framework compatível com pywebview.

## Compilação oficial

Use Windows x64 e Python 3.11.9:

```powershell
python -m venv .venv-build
.venv-build\Scripts\python.exe -m pip install -r requirements-build.lock.txt
.\build_installer.ps1
```

`requirements-build.lock.txt` trava a árvore de dependências usada no build. `packaging/build.spec` é a configuração oficial; os arquivos `.spec` antigos e `installer.iss` são históricos e não são usados pelo novo processo. Não execute os instaladores antigos em `dist` como se fossem esta versão.

Cada compilação cria uma pasta nova em `build-candidates`, executa testes de código, compila o aplicativo, testa importação/recursos/OCR/geração de DOCX/servidor dentro do executável, e só então cria o instalador. O instalador verifica os hashes SHA-256 de todos os arquivos do pacote. Falha de qualquer etapa interrompe a sequência. Os testes automáticos não substituem a homologação de uso em Windows limpo.

## Instalar e remover

O instalador copia e verifica os arquivos em uma área temporária, antes de substituir `%LOCALAPPDATA%\PPAM Anvisa`. Uma versão anterior é preservada em uma pasta irmã `PPAM Anvisa-backup-*`, inclusive documentos que tenham sido salvos nela. Essas pastas não são removidas automaticamente.

Cria atalho no menu Iniciar e oferece atalho na área de trabalho. A desinstalação fica disponível nos aplicativos instalados do Windows e em `uninstall.ps1`. Remove somente arquivos do programa que ainda correspondem ao manifesto. Documentos exportados, arquivos modificados, backups e logs são preservados. Diretórios vazios podem permanecer.

Os logs ficam em `%LOCALAPPDATA%\PPAM Anvisa-data\logs`; o log principal tem rotação de três arquivos de até 2 MB. Temporários ficam em `PPAM Anvisa-data\cache`, separados por sessão, e são retidos nesta versão para diagnóstico. Salve seus documentos pelo botão de download; o cache não é uma pasta de documentos permanentes.

## Limites de validação

A versão não está homologada para distribuição enquanto houver pendências na matriz T01–T18 do PRD. Em especial, testar instalação em Windows sem Python, interface/download nativos, ausência de runtime, reinício, desinstalação e funcionamento offline. A existência do executável, seu hash e o autoteste não comprovam esses cenários.

O reconhecimento de documentos não garante correção clínica ou regulatória. Revise o parecer antes de utilizar. `.doc` legado e PDF escaneado sem texto devem ser convertidos para DOCX ou PDF pesquisável; imagens usam OCR local.
