"""Classe principale de mise à jour des métadonnées."""

import os
from typing import Dict, List, Any
from docling.document_converter import DocumentConverter, InputFormat, PdfFormatOption
import pytesseract

from .config import DEFAULT_OCR_CONFIG
from .file_utils import calculate_file_hash, extract_metadata_from_filename
from .metadata import MetadataExtractor
from .zotero_utils import ZoteroClient

class ZoteroMetadataUpdater:
    def __init__(self, library_id: str, library_type: str, api_key: str, claude_api_key: str):
        """
        Initialise le gestionnaire de métadonnées Zotero.
        
        Args:
            library_id: ID de la bibliothèque Zotero
            library_type: Type de bibliothèque ('user' ou 'group')
            api_key: Clé API Zotero
            claude_api_key: Clé API Anthropic pour Claude
        """
        # Vérifier la présence de Tesseract
        try:
            pytesseract.get_tesseract_version()
        except Exception as e:
            raise RuntimeError(
                "Tesseract n'est pas correctement installé. Veuillez suivre les instructions d'installation : "
                "https://github.com/UB-Mannheim/tesseract/wiki\n"
                f"Erreur : {str(e)}"
            )
        
        # Initialiser les clients
        self.zotero = ZoteroClient(library_id, library_type, api_key)
        self.metadata = MetadataExtractor(claude_api_key)
        
        # Initialiser le convertisseur de documents
        self.doc_converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=DEFAULT_OCR_CONFIG
                )
            }
        )

    def process_pdf(self, pdf_path: str, collections: List[str] = None, use_ocr: bool = False) -> Dict[str, Any]:
        """
        Traite un fichier PDF et met à jour ses métadonnées dans Zotero.
        
        Args:
            pdf_path: Chemin vers le fichier PDF
            collections: Liste des clés de collections
            use_ocr: Utiliser l'OCR pour l'extraction du texte
            
        Returns:
            Item Zotero mis à jour
        """
        # Vérifier les doublons
        file_hash = calculate_file_hash(pdf_path)
        existing_item = self.zotero.check_duplicate(file_hash)
        if existing_item:
            raise ValueError(f"Ce PDF existe déjà dans Zotero (ID: {existing_item})")
        
        # Créer l'item dans Zotero
        item = self.zotero.create_item(collections=collections)
        
        # Attacher le PDF
        self.zotero.attach_pdf(item['key'], pdf_path)
        
        # Extraire le texte avec ou sans OCR
        if use_ocr:
            result = self.doc_converter.convert(pdf_path)
            text = result.document.export_to_text()
        else:
            import fitz
            with fitz.open(pdf_path) as doc:
                text = ""
                for page in doc:
                    text += page.get_text()
        
        # Extraire les métadonnées
        metadata = self.metadata.extract_metadata(text)
        
        # Ajouter les métadonnées du nom de fichier
        filename_metadata = extract_metadata_from_filename(os.path.basename(pdf_path))
        if filename_metadata:
            metadata.update(filename_metadata)
        
        # Mettre à jour l'item
        self.zotero.update_metadata(item['key'], metadata)
        
        return item

    def calculate_cost(self) -> Dict[str, Any]:
        """
        Calcule le coût total d'utilisation de l'API Claude.
        """
        return self.metadata.calculate_cost() 