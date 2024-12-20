"""Configuration du projet."""

from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
from decimal import Decimal

# Configuration OCR
DEFAULT_OCR_CONFIG = PdfPipelineOptions()
DEFAULT_OCR_CONFIG.do_ocr = True
DEFAULT_OCR_CONFIG.ocr_options = EasyOcrOptions(
    force_full_page_ocr=True,
    use_gpu=True
)

# Configuration des modèles de langage
LLM_CONFIG = {
    # Configuration pour Anthropic
    'anthropic': {
        'model_name': 'claude-3-5-haiku-latest',
        'costs': {
            'input_tokens': Decimal('1.00'),  # Coût par million de tokens
            'output_tokens': Decimal('5.00')
        }
    },
    
    # Configuration pour OpenRouter
    'openrouter': {
        'base_url': 'https://openrouter.ai/api/v1',
        'model_name': 'google/gemini-flash-1.5',  # Par défaut, à ajuster selon les besoins
        'costs': {
            'input_tokens': Decimal('0.075'),  # À ajuster selon le modèle
            'output_tokens': Decimal('0.3')
        }
    },
    
    # Configuration pour Llama local
    'llama': {
        'repo_id': 'bartowski/Qwen2.5-32B-Instruct-GGUF',
        'filename': 'Qwen2.5-32B-Instruct-Q4_K_M.gguf',
        'n_ctx': 10000,
        'verbose': False,
        'costs': {
            'input_tokens': Decimal('0'),  # Gratuit car local
            'output_tokens': Decimal('0')
        }
    }
}

# Types de documents valides
VALID_ITEM_TYPES = [
    'document',
    'journalArticle',
    'bookSection',
    'report',
    'thesis',
    'webpage'
] 