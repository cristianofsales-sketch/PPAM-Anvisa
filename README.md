# 📋 Automação do PPAM — Parecer Público de Avaliação de Medicamentos

> **Desktop 1.0.1:** consulte [DESKTOP.md](DESKTOP.md) para a configuração e compilação oficiais. A porta atual é **7860**, restrita a `127.0.0.1`. As instruções abaixo são históricas, anteriores à versão local, e não devem ser usadas para compilar o instalador nem configurar a porta.

Este módulo de texto registra e explica de forma resumida o funcionamento da aplicação e o endereço de rede onde ela é disponibilizada.

No PowerShell, execute:
cd "C:\Users\crist\Desktop\pos IA\PPAM 4 - backup\ppam_app"

python -c "import app; app.app.launch(server_name='0.0.0.0', server_port=7060, share=False, debug=False, theme=__import__('gradio').themes.Base(), css=app.CUSTOM_CSS)"

Depois acesse:
http://localhost:7060

Para encerrar, pressione Ctrl+C no terminal.

## Aplicativo instalável para Windows

O projeto também inclui um launcher desktop (`desktop_app.py`) que abre a interface
Gradio em uma janela própria, sem exigir que o usuário abra o navegador manualmente.

Para gerar o executável e o instalador:

1. Instale o [Inno Setup](https://jrsoftware.org/isinfo.php) e mantenha o `ISCC.exe` no PATH.
2. Abra o PowerShell nesta pasta.
3. Execute:

```powershell
.\build_installer.ps1
```

O instalador será criado em `dist-installer\PPAM-Setup.exe`. O script também pode
ser usado sem Inno Setup: nesse caso, ele gera o aplicativo distribuível em
`dist\PPAM\PPAM.exe`.

## 🌐 Endereço e Porta de Execução

A aplicação é executada localmente utilizando a biblioteca **Gradio** como interface web.

- **Endereço Padrão:** `http://localhost:7860` (ou `http://0.0.0.0:7860`)
- **Porta Padrão:** `7860`

### 🔧 Customização de Porta
É possível passar uma porta alternativa de duas maneiras:
1. **Pela Linha de Comando:**
   ```bash
   python app.py 8080
   ```
2. **Por Variável de Ambiente (`PORT`):**
   ```bash
   set PORT=8080 && python app.py
   ```

---

## 🛠️ Como a Aplicação Funciona (Fluxo de Execução)

A aplicação automatiza a extração, validação, conformidade regulatória e geração de relatórios de Parecer Público de Avaliação de Medicamentos (PPAM) a partir de documentos técnicos (Parecer, Bula, DOU, etc.). O processo é composto por 4 etapas principais:

```
[Documentos de Entrada] ➔ [Processamento de Documento] ➔ [Extração por IA com Validação] ➔ [Preenchimento do Template DOCX] ➔ [Auditoria e Download]
```

### 1. Processamento e Leitura (`document_processor.py`)
- Recebe arquivos em múltiplos formatos (**PDF, Word (DOCX/DOC) ou Imagens (PNG/JPG)**).
- Realiza extração inteligente: se o PDF for legível por código, extrai usando `pdfplumber`. 
- Caso o arquivo seja digitalizado (PDF escaneado ou Imagem), realiza a leitura via **Gemini File API/Vision** para transcrição automática por OCR de alta fidelidade.

### 2. Extração Estruturada e Validação por IA (`extractor.py` & `models.py`)
- O texto extraído é enviado ao modelo **Google Gemini** (padrão: `gemini-2.5-flash`), com suporte a múltiplos modelos.
- Há um mecanismo de **decaimiento/fallback de modelo** e **retry exponencial** para evitar falhas ou erros (como 404/429).
- A extração é mapeada para modelos de dados rígidos utilizando **Pydantic** (`PPAMData`), divididos em seções:
  - **Sumário**: Dados do fabricante, medicamento, apresentações e excipientes.
  - **Tecnologia Farmacêutica**: Validação da Cadifa, controle de qualidade e embalagem primária.
  - **Segurança e Eficácia**: Tipo de comprovação, equivalência farmacêutica e perfil de dissolução.
  - **Publicação da Decisão**: Número de registro MS e resoluções publicadas no DOU.
- **Validação de Sigilo & Alertas**: O texto é confrontado com uma lista de termos proibidos (blacklist confidencial em `config.py`), garantindo que segredos industriais (ex: quantidade exata de excipientes) não sejam expostos. Os campos não extraídos ou de baixa confiança são marcados.

### 3. Preenchimento de Relatório e Template (`template_filler.py`)
- Preenche de modo automatizado e dinâmico um arquivo template no formato **Word (.docx)**.
- Remove as frases e textos puramente instrutivos contidos no template original.
- Trata seções condicionais (como Bioequivalência ou Cadifa aprovada), mantendo apenas as seções aplicáveis.
- Destaca visualmente no documento Word gerado os dados que o sistema marcou como "baixa confiança", facilitando a revisão do auditor humano.

### 4. Interface Web e Logs de Auditoria (`app.py` & `audit.py`)
- Apresenta uma interface visual moderna baseada no tema `Soft Teal` do **Gradio**, permitindo que o usuário informe sua API Key, selecione o modelo do Gemini, faça o upload de documentos e interaja diretamente com o JSON extraído antes de exportar o Word.
- Cria um log de auditoria completo (`auditoria.json`) para fins de rastreabilidade (em compliance com as normas regulatórias), registrando metadados, divergências dinâmicas localizadas e os campos sob baixa confiança.

---

## 📂 Estrutura de Arquivos Principais

- **`app.py`**: Ponto de partida. Define a interface do Gradio e o servidor web.
- **`config.py`**: Armazena as constantes, padrões de exclusão de texto, formatos suportados e a blacklist de termos sigilosos.
- **`document_processor.py`**: Trata a leitura e o OCR de imagens/documentos PDF.
- **`extractor.py`**: Interage com o Gemini para estruturar e validar as informações das seções.
- **`models.py`**: Estruturas de dados Pydantic utilizadas para tipágem e validação.
- **`template_filler.py`**: Lógica de manipulação Word/docx e aplicação de estilos/linhas condicionais.
- **`audit.py`**: Criação de logs de auditoria e conformidade.
