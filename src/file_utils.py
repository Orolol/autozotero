"""Utilitaires de gestion des fichiers."""

import os
import hashlib
import fnmatch
from typing import List, Optional

def calculate_file_hash(file_path: str) -> str:
    """Calcule le hash MD5 d'un fichier."""
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()

def find_pdf_files(folder_path: str, recursive: bool = False, pattern: str = None) -> List[str]:
    """
    Trouve tous les fichiers PDF dans un dossier.
    
    Args:
        folder_path: Chemin vers le dossier
        recursive: Inclure les sous-dossiers
        pattern: Pattern glob pour filtrer les noms de fichiers
        
    Returns:
        Liste des chemins des PDF trouvés
    """
    pdf_files = []
    
    if recursive:
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    if pattern and not fnmatch.fnmatch(file, pattern):
                        continue
                    pdf_files.append(os.path.join(root, file))
    else:
        for file in os.listdir(folder_path):
            if file.lower().endswith('.pdf'):
                if pattern and not fnmatch.fnmatch(file, pattern):
                    continue
                pdf_files.append(os.path.join(folder_path, file))
                
    return pdf_files

def extract_metadata_from_filename(filename: str) -> Optional[dict]:
    """
    Extrait la date et l'heure d'un nom de fichier Camscanner.
    
    Args:
        filename: Nom du fichier (format: 'CamScanner DD-MM-YYYY HH.MM_hnOCR.pdf')
        
    Returns:
        Dictionnaire contenant la date au format ISO 8601 (YYYY-MM-DD) et l'heure
    """
    import re
    from datetime import datetime
    
    # Nouveau pattern qui correspond au format réel
    pattern = r"CamScanner (\d{2}-\d{2}-\d{4}) (\d{2}\.\d{2})_hnOCR\.pdf"
    match = re.match(pattern, filename)
    
    if match:
        date_str, time_str = match.groups()
        try:
            date_obj = datetime.strptime(date_str, "%d-%m-%Y")
            # Convertir le point en : pour le temps
            time_str = time_str.replace('.', ':')
            return {
                "accessDate": date_obj.strftime("%Y-%m-%d"),  # Format ISO 8601
                "extra": time_str
            }
        except ValueError as e:
            print(f"Erreur lors du parsing de la date: {e}")
            return None
    return None 