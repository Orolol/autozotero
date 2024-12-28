"""Utilitaires pour l'interaction avec Zotero."""

import time
from typing import Dict, List, Optional
from pyzotero import zotero
import os

class RateLimitHandler:
    def __init__(self):
        """Initialise le gestionnaire de rate limiting."""
        self.backoff_until = 0
        self.retry_after_until = 0

    def handle_response_headers(self, headers: Dict[str, str]) -> None:
        """
        Gère les en-têtes de rate limiting de l'API Zotero.
        
        Args:
            headers: En-têtes de la réponse HTTP
        """
        # Gérer le backoff
        if 'Backoff' in headers:
            backoff_seconds = int(headers['Backoff'])
            self.backoff_until = time.time() + backoff_seconds

        # Gérer le Retry-After
        if 'Retry-After' in headers:
            retry_seconds = int(headers['Retry-After'])
            self.retry_after_until = time.time() + retry_seconds

    def should_wait(self) -> float:
        """
        Vérifie s'il faut attendre avant la prochaine requête.
        
        Returns:
            Nombre de secondes à attendre (0 si aucune attente nécessaire)
        """
        now = time.time()
        wait_time = max(
            self.backoff_until - now,
            self.retry_after_until - now,
            0
        )
        return wait_time

    def wait_if_needed(self) -> None:
        """Attend si nécessaire avant la prochaine requête."""
        wait_time = self.should_wait()
        if wait_time > 0:
            time.sleep(wait_time)

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
        self.rate_limiter = RateLimitHandler()

    def _handle_request(self, func, *args, **kwargs):
        """
        Wrapper pour gérer le rate limiting sur les requêtes Zotero.
        
        Args:
            func: Fonction Zotero à exécuter
            *args: Arguments positionnels
            **kwargs: Arguments nommés
            
        Returns:
            Résultat de la fonction
            
        Raises:
            Exception: Si une erreur survient après plusieurs tentatives
        """
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Attendre si nécessaire avant la requête
                self.rate_limiter.wait_if_needed()
                
                # Exécuter la requête
                response = func(*args, **kwargs)
                
                # Gérer les en-têtes de rate limiting
                if hasattr(response, 'headers'):
                    self.rate_limiter.handle_response_headers(response.headers)
                
                return response
                
            except Exception as e:
                if hasattr(e, 'response'):
                    # Gérer le rate limiting (429)
                    if e.response.status_code == 429:
                        self.rate_limiter.handle_response_headers(e.response.headers)
                        retry_count += 1
                        continue
                        
                    # Gérer le backoff
                    if 'Backoff' in e.response.headers:
                        self.rate_limiter.handle_response_headers(e.response.headers)
                        retry_count += 1
                        continue
                
                # Autres erreurs
                raise e
        
        raise Exception(f"Échec après {max_retries} tentatives")

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
        attachments = self._handle_request(self.zot.everything, self.zot.attachments())
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
        
        result = self._handle_request(self.zot.create_items, [template])
        return self._handle_request(self.zot.item, result['successful']['0']['key'])

    def attach_pdf(self, item_key: str, pdf_path: str) -> None:
        """
        Attache un fichier PDF à un item Zotero.
        
        Args:
            item_key: Clé de l'item Zotero
            pdf_path: Chemin vers le fichier PDF
        """
        # Créer l'attachement
        template = self.zot.item_template('attachment', linkmode='imported_file')
        template['itemType'] = 'attachment'
        template['contentType'] = 'application/pdf'
        template['filename'] = os.path.basename(pdf_path)
        template['parentItem'] = item_key
        
        # Créer l'attachement avec le fichier PDF
        with open(pdf_path, 'rb') as pdf_file:
            self._handle_request(self.zot.upload_attachment, pdf_file, item_key)

    def update_metadata(self, item_key: str, metadata: Dict) -> None:
        """
        Met à jour les métadonnées d'un item Zotero.
        
        Args:
            item_key: Clé de l'item Zotero
            metadata: Nouvelles métadonnées
        """
        item = self._handle_request(self.zot.item, item_key)
        item['data'].update(metadata)
        self._handle_request(self.zot.update_item, item)

    def children(self, item_key: str, **kwargs) -> List[Dict]:
        """
        Récupère les enfants d'un item.
        
        Args:
            item_key: Clé de l'item parent
            **kwargs: Arguments supplémentaires pour le filtrage
            
        Returns:
            Liste des items enfants
        """
        return self._handle_request(self.zot.children, item_key, **kwargs)

    def dump(self, attachment_key: str, path: str) -> None:
        """
        Télécharge un fichier attaché.
        
        Args:
            attachment_key: Clé de l'attachement
            path: Chemin où sauvegarder le fichier
        """
        self._handle_request(self.zot.dump, attachment_key, path)

    def get_all_items(self, item_type: Optional[str] = None) -> List[Dict]:
        """
        Récupère tous les items de la bibliothèque.
        
        Args:
            item_type: Type d'item à récupérer (optionnel)
            
        Returns:
            Liste des items
        """
        if item_type:
            items = self._handle_request(self.zot.items, itemType=item_type)
        else:
            items = self._handle_request(self.zot.items)
            
        return self._handle_request(self.zot.everything, items) 