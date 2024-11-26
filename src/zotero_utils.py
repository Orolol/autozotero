"""Utilitaires pour l'interaction avec Zotero."""

from typing import Dict, List, Optional
from pyzotero import zotero

class ZoteroClient:
    def __init__(self, library_id: str, library_type: str, api_key: str):
        """
        Initialise le client Zotero.
        
        Args:
            library_id: ID de la bibliothèque Zotero
            library_type: Type de bibliothèque ('user' ou 'group')
            api_key: Clé API Zotero
        """
        self.zot = zotero.Zotero(library_id, library_type, api_key)
        self.duplicate_cache = {}

    def check_duplicate(self, file_hash: str) -> Optional[str]:
        """
        Vérifie si un fichier existe déjà dans la bibliothèque.
        
        Args:
            file_hash: Hash MD5 du fichier
            
        Returns:
            ID de l'item existant si trouvé, None sinon
        """
        # Vérifier dans le cache
        if file_hash in self.duplicate_cache:
            return self.duplicate_cache[file_hash]
            
        # Chercher dans Zotero
        attachments = self.zot.everything(self.zot.attachments())
        for attachment in attachments:
            if attachment.get('data', {}).get('md5', '') == file_hash:
                parent_item = attachment.get('data', {}).get('parentItem')
                self.duplicate_cache[file_hash] = parent_item
                return parent_item
                
        return None

    def create_item(self, item_type: str = 'report', collections: List[str] = None) -> Dict:
        """
        Crée un nouvel item dans Zotero.
        
        Args:
            item_type: Type de l'item Zotero
            collections: Liste des clés de collections
            
        Returns:
            Item créé
        """
        template = self.zot.item_template(item_type)
        if collections:
            template['collections'] = collections
        
        result = self.zot.create_items([template])
        return self.zot.item(result['successful']['0']['key'])

    def attach_pdf(self, item_key: str, pdf_path: str) -> None:
        """
        Attache un fichier PDF à un item Zotero.
        
        Args:
            item_key: Clé de l'item Zotero
            pdf_path: Chemin vers le fichier PDF
        """
        with open(pdf_path, 'rb') as pdf_file:
            self.zot.upload_attachment(pdf_file, item_key)

    def update_metadata(self, item_key: str, metadata: Dict) -> None:
        """
        Met à jour les métadonnées d'un item Zotero.
        
        Args:
            item_key: Clé de l'item Zotero
            metadata: Nouvelles métadonnées
        """
        item = self.zot.item(item_key)
        item['data'].update(metadata)
        self.zot.update_item(item) 