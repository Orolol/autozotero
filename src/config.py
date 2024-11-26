"""Configuration du projet."""

from docling.datamodel.pipeline_options import PdfPipelineOptions, TesseractOcrOptions, EasyOcrOptions

# Configuration OCR
DEFAULT_OCR_CONFIG = PdfPipelineOptions()
DEFAULT_OCR_CONFIG.do_ocr = True
DEFAULT_OCR_CONFIG.ocr_options = TesseractOcrOptions(
    force_full_page_ocr=True,
    lang=["fra", "eng"]
)

# Configuration alternative avec EasyOCR
EASYOCR_CONFIG = PdfPipelineOptions()
EASYOCR_CONFIG.do_ocr = True
EASYOCR_CONFIG.ocr_options = EasyOcrOptions(
    force_full_page_ocr=True,
    use_gpu=True
)

# Configuration des modèles de langage
LLM_CONFIG = {
    # Configuration par défaut pour Anthropic
    'anthropic': {
        'model_name': 'claude-3-5-haiku-latest'
    },
    
    # Configuration par défaut pour Llama
    'llama': {
        'repo_id': 'bartowski/Meta-Llama-3.1-8B-Instruct-GGUF',
        'filename': 'Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf',
        'n_ctx': 8192,
        'verbose': True
    }
}

# Coûts API Claude
INPUT_COST_PER_MILLION = 1.00
OUTPUT_COST_PER_MILLION = 5.00

# Types de documents valides
VALID_ITEM_TYPES = [
    'document',
    'journalArticle',
    'bookSection',
    'report',
    'thesis',
    'webpage'
] 