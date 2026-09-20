import os
import json
import logging
from extractor import PPAMExtractor
from document_processor import DocumentProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():

    # Caminhos dinâmicos encontrados nas pastas do gradio
    import glob
    gradio_files = glob.glob(r"C:\Users\crist\AppData\Local\Temp\gradio\**\*.*", recursive=True)
    
    parecer_path = None
    bula_path = None
    
    for f in sorted(gradio_files, key=os.path.getmtime, reverse=True):
        f_lower = os.path.basename(f).lower()
        if "parecer" in f_lower and f_lower.endswith(".docx") and not parecer_path:
            parecer_path = f
        elif "bula" in f_lower and f_lower.endswith(".pdf") and not bula_path:
            bula_path = f
            
    if not parecer_path:
        raise FileNotFoundError("Nenhum arquivo de Parecer Técnico encontrado na pasta temporária.")
        
    logger.info(f"Utilizando Parecer encontrado: {parecer_path}")
    if bula_path:
        logger.info(f"Utilizando Bula encontrada: {bula_path}")
    else:
        logger.warning("Bula não encontrada na pasta temporária do Gradio.")

    # 2. Processa os documentos no modo Local
    logger.info("Processando arquivos para extrair texto localmente...")
    parecer_text = DocumentProcessor.process_file(parecer_path)
    bula_text = ""
    if bula_path and os.path.exists(bula_path):
        bula_text = DocumentProcessor.process_file(bula_path)
    else:
        logger.warning("Bula não encontrada.")

    # 3. Inicializa o extrator local e processa os dados
    extractor = PPAMExtractor()
    
    logger.info("Executando extração local dos dados (extract_all)...")
    extracted_data = extractor.extract_all(parecer_text, bula_text, "")
    
    # 4. Salva o resultado JSON
    output_filename = "resultado_extraido.json"
    with open(output_filename, "w", encoding="utf-8") as out:
        json.dump(extracted_data.model_dump(), out, ensure_ascii=False, indent=2)
        
    logger.info(f"Extração concluída com sucesso! Resultado salvo em '{output_filename}'")
    
    # Imprime resumo
    print("\n--- RESUMO DOS DADOS EXTRAÍDOS (LOCAL) ---")
    print(json.dumps(extracted_data.model_dump(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
