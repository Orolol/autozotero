"""Classe principale de mise à jour des métadonnées."""

import os
from typing import Dict, List, Any, Optional
from docling.document_converter import DocumentConverter, InputFormat, PdfFormatOption

from pyzotero import zotero

from .config import DEFAULT_OCR_CONFIG, LLM_CONFIG
from .file_utils import calculate_file_hash, extract_metadata_from_filename
from .metadata import MetadataExtractor
from .zotero_utils import ZoteroClient

class ZoteroMetadataUpdater:
    def __init__(self, 
                 library_id: str, 
                 library_type: str, 
                 api_key: str, 
                 claude_api_key: str = None, 
                 use_local_model: bool = False,
                 use_openrouter: bool = False,
                 openrouter_config: Optional[Dict[str, str]] = None):
        """
        Initialise le gestionnaire de métadonnées Zotero.
        
        Args:
            library_id: ID de la bibliothèque Zotero
            library_type: Type de bibliothèque ('user' ou 'group')
            api_key: Clé API Zotero
            claude_api_key: Clé API Anthropic pour Claude (optionnel si use_local_model=True)
            use_local_model: Utiliser le modèle local au lieu de Claude
            use_openrouter: Utiliser OpenRouter au lieu de Claude
            openrouter_config: Configuration pour OpenRouter (optionnel)
        """

        # Initialiser la connexion Zotero
        self.zot = zotero.Zotero(library_id, library_type, api_key)
        
        # Initialiser les clients
        if use_local_model:
            try:
                self.metadata = MetadataExtractor(llm_type='llama')
            except ImportError:
                raise RuntimeError(
                    "Le modèle local nécessite l'installation des dépendances. "
                    "Installez-les avec : pip install transformers torch"
                )
        elif use_openrouter:
            if not openrouter_config or 'api_key' not in openrouter_config:
                raise ValueError("La clé API OpenRouter est requise")
            
            # Fusionner la configuration par défaut avec celle fournie
            config = LLM_CONFIG['openrouter'].copy()
            config.update(openrouter_config)
            
            self.metadata = MetadataExtractor(
                llm_type='openrouter',
                api_key=config['api_key'],
                base_url=config.get('base_url', LLM_CONFIG['openrouter']['base_url']),
                model_name=config.get('model_name', LLM_CONFIG['openrouter']['model_name'])
            )
        else:
            if not claude_api_key:
                raise ValueError("La clé API Claude est requise lorsque le modèle local n'est pas utilisé")
            self.metadata = MetadataExtractor(llm_type='anthropic', api_key=claude_api_key)
        
        self.use_local_model = use_local_model
        self.use_openrouter = use_openrouter
        
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
        
        # Rechercher dans les attachements existants
        for item in self.zot.items(itemType='attachment', format='json'):
            if item.get('data', {}).get('md5', '') == file_hash:
                parent = item.get('data', {}).get('parentItem')
                if parent:
                    raise ValueError(f"Ce PDF existe déjà dans Zotero (ID: {parent})")
        
        # Créer d'abord l'item parent
        parent_template = self.zot.item_template('report')
        parent_result = self.zot.create_items([parent_template])
        parent_key = parent_result['successful']['0']['key']
        
        # Récupérer l'item parent complet
        parent_item = self.zot.item(parent_key)
        
        # Créer l'attachement
        attachment_template = self.zot.item_template('attachment', linkmode='imported_file')
        attachment_template['itemType'] = 'attachment'
        attachment_template['contentType'] = 'application/pdf'
        attachment_template['filename'] = os.path.basename(pdf_path)
        attachment_template['parentItem'] = parent_key
        
        if collections:
            attachment_template['collections'] = collections
        
        # Créer l'attachement avec le fichier PDF
        self.zot.create_items([attachment_template], parent_key)
        
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
        
        # Mettre à jour l'item parent avec les métadonnées
        formatted_metadata = self._format_metadata_for_zotero(metadata)
        parent_item['data'].update(formatted_metadata)
        self.zot.update_item(parent_item)
        
        return parent_item

    def calculate_cost(self) -> Dict[str, Any]:
        """
        Calcule le coût total d'utilisation de l'API Claude.
        """
        return self.metadata.calculate_cost()

    def _format_metadata_for_zotero(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formate les métadonnées pour correspondre à la structure Zotero.
        
        Args:
            metadata: Métadonnées extraites du PDF
            
        Returns:
            Dict[str, Any]: Métadonnées formatées pour Zotero
        """
        formatted = {}
        
        # Copier les champs simples
        simple_fields = ['title', 'reportNumber', 'institution', 'place', 'date', 'language', 'accessDate']
        for field in simple_fields:
            if field in metadata:
                formatted[field] = metadata[field]
        
        # Traiter le scanTime spécifiquement pour le mettre dans extra
        if 'scanTime' in metadata:
            formatted['extra'] = f"Scan time: {metadata['scanTime']}"
        
        # Formater les auteurs
        if 'authors' in metadata:
            formatted['creators'] = []
            for author in metadata['authors']:
                creator = {'creatorType': 'author'}
                
                if author.get('lastName'):
                    if author.get('firstName'):
                        # Si on a firstName et lastName, on les utilise
                        creator['lastName'] = author['lastName']
                        creator['firstName'] = author['firstName']
                    else:
                        # Si on a que lastName, on l'utilise comme name
                        creator['name'] = author['lastName']
                elif author.get('denomination'):
                    # Utiliser denomination comme name si disponible
                    creator['name'] = author['denomination']
                else:
                    # Cas par défaut
                    creator['name'] = 'Unknown Author'
                
                formatted['creators'].append(creator)
        
        # Formater les tags
        if 'tags' in metadata:
            formatted['tags'] = metadata['tags']
        
        return formatted

    def check_and_update_metadata(self, item: Dict[str, Any], force_update: bool = False, use_ocr: bool = False) -> bool:
        """
        Vérifie et met à jour les métadonnées d'un item Zotero existant.
        
        Args:
            item: Item Zotero à mettre à jour
            force_update: Forcer la mise à jour même si les métadonnées existent
            use_ocr: Utiliser l'OCR pour l'extraction du texte
            
        Returns:
            bool: True si les métadonnées ont été mises à jour, False sinon
        """
        # Vérifier si une mise à jour est nécessaire
        if not force_update and item['data'].get('title') and item['data'].get('abstractNote'):
            print(f"Métadonnées déjà présentes pour l'item {item['key']}")
            return False

        # Récupérer les attachements PDF
        attachments = self.zot.children(item['key'], itemType='attachment')
        pdf_attachments = [a for a in attachments if a['data'].get('contentType') == 'application/pdf']
        
        if not pdf_attachments:
            print(f"Aucun PDF trouvé pour l'item {item['key']}")
            return False

        # Utiliser le premier PDF trouvé
        pdf_attachment = pdf_attachments[0]
        
        # Créer un dossier temporaire pour le PDF
        import tempfile
        import os
        
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Télécharger le PDF
            pdf_path = os.path.join(temp_dir, 'temp.pdf')
            self.zot.dump(pdf_attachment['key'], pdf_path)
            
            # Extraire le texte du PDF
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
            raw_metadata = self.metadata.extract_metadata(text)
            
            # Formater les métadonnées pour Zotero
            formatted_metadata = self._format_metadata_for_zotero(raw_metadata)
            
            # Mettre à jour l'item avec les nouvelles métadonnées
            item['data'].update(formatted_metadata)
            item['data']['itemType'] = 'report'
            self.zot.update_item(item)
            
            return True