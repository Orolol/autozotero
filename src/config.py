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