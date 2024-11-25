from pyzotero import zotero
from anthropic import Anthropic
import os
from typing import Dict, Any
from dotenv import load_dotenv
import sys
import fitz  # PyMuPDF
import tempfile
from decimal import Decimal
import argparse
from docling.datamodel.pipeline_options import PdfPipelineOptions, TesseractOcrOptions, EasyOcrOptions
from docling.document_converter import DocumentConverter, InputFormat, PdfFormatOption

pipeline_options = PdfPipelineOptions()
pipeline_options.do_ocr = True
pipeline_options.ocr_options = TesseractOcrOptions(
    force_full_page_ocr=True,
    lang=["fra", "eng"]
    )  # Use Tesseract

# pipeline_options.ocr_options = EasyOcrOptions(
#     # language="fra",
#     force_full_page_ocr=True,
#     use_gpu=True
# )


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
        self.zot = zotero.Zotero(library_id, library_type, api_key)
        self.anthropic = Anthropic(api_key=claude_api_key)
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.doc_converter = DocumentConverter(
            allowed_formats=[
                InputFormat.PDF
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options
                )
            }
        )


    def calculate_cost(self) -> Dict[str, Decimal]:
        """
        Calcule le coût total basé sur l'utilisation des tokens.
        
        Returns:
            Dict contenant les coûts détaillés et le total
        """
        INPUT_COST_PER_MILLION = Decimal('1.00')
        OUTPUT_COST_PER_MILLION = Decimal('5.00')
        
        input_cost = (Decimal(self.total_input_tokens) / Decimal('1000000')) * INPUT_COST_PER_MILLION
        output_cost = (Decimal(self.total_output_tokens) / Decimal('1000000')) * OUTPUT_COST_PER_MILLION
        
        return {
            'input_tokens': self.total_input_tokens,
            'output_tokens': self.total_output_tokens,
            'input_cost': input_cost,
            'output_cost': output_cost,
            'total_cost': input_cost + output_cost
        }

    def extract_metadata_with_llm(self, text: str) -> Dict[str, Any]:
        """
        Utilise Claude pour extraire les métadonnées d'un texte selon des règles spécifiques.
        """
        if not os.path.exists('rules.txt'):
            raise FileNotFoundError("Le fichier rules.txt est requis mais n'a pas été trouvé")

        with open('rules.txt', 'r', encoding='utf-8') as f:
            rules = f.read()

        prompt = f"""En utilisant ces règles spécifiques pour l'analyse des documents:

        {rules}

        Analysez ce document et extrayez les métadonnées suivantes au format JSON:
        - title (chercher "objet:" ou "A/S:", sinon le titre en haut au milieu)
        - authors (liste d'objets avec les champs suivants pour chaque auteur:
            - lastName: nom de famille si connu, sinon None
            - firstName: prénom si connu, sinon None
            - denomination: titre ou qualité de l'auteur si pas de nom/prénom (ex: "Le Préfet coordonnateur", "Le Chef du Service"), sinon None
          Note: un auteur doit avoir soit lastName+firstName, soit denomination, mais pas les deux)
        - reportNumber (vérifier les en-têtes en haut à droite sous la date/lieu ou en haut à gauche sous l'institution/auteur)
        - institution (chercher dans l'en-tête en haut à gauche)
        - place (chercher dans l'en-tête en haut à droite avant la date, en anglais. Si c'est en Français, l'écrire en anglais)
        - date (format DD/MM/YYYY)
        - language (garder la langue originale du document)

        Ignorer tout contenu après une page commençant par "Annexe".

        En cas de valeurs manquantes, utiliser None.
        La sortie doit être un JSON valide qui sera évalué en Python. Retourner uniquement le JSON, rien d'autre.
        
        Texte à analyser:
        {text}
        
        """

        message = self.anthropic.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=1000,
            temperature=0,
            system="Vous êtes un assistant spécialisé dans l'extraction de métadonnées de documents administratifs, suivant des règles strictes.",
            messages=[{"role": "user", "content": prompt}]
        )
        
        self.total_input_tokens += message.usage.input_tokens
        self.total_output_tokens += message.usage.output_tokens
        
        try:
            return eval(message.content[0].text.replace('```json', '').replace('```', ''))
        except Exception as e:
            print(message.content[0].text)
            raise ValueError(f"Erreur lors de l'extraction des métadonnées: {str(e)}")


    def count_library_items(self) -> Dict[str, int]:
        """
        Compte le nombre total d'éléments dans la bibliothèque et par type.
        
        Returns:
            Dict contenant le nombre total d'items et le compte par type
        """
        try:
            # Récupérer tous les éléments
            items = self.zot.everything(self.zot.items())
            
            # Compter par type
            type_counts = {}
            for item in items:
                item_type = item['data'].get('itemType', 'unknown')
                type_counts[item_type] = type_counts.get(item_type, 0) + 1
            
            return {
                'total': len(items),
                'by_type': type_counts
            }
            
        except Exception as e:
            raise ValueError(f"Erreur lors du comptage des éléments: {str(e)}")

    def get_relevant_items(self, valid_types: list) -> list:
        """
        Récupère les éléments de la bibliothèque qui correspondent aux types spécifiés.
        
        Args:
            valid_types: Liste des types d'éléments à conserver
        
        Returns:
            Liste des éléments filtrés
        """
        try:
            # Récupérer tous les éléments
            items = self.zot.everything(self.zot.items())
            
            # Filtrer par type
            relevant_items = [item for item in items if item['data'].get('itemType') in valid_types]
            return relevant_items
            
        except Exception as e:
            raise ValueError(f"Erreur lors de la récupération des éléments: {str(e)}")

    def extract_text_from_pdf(self, attachment_path: str, use_ocr: bool = False) -> str:
        """
        Extrait le texte d'un fichier PDF, avec option OCR via docling.
        
        Args:
            attachment_path: Chemin vers le fichier PDF
            use_ocr: Si True, utilise docling pour l'OCR
        
        Returns:
            Texte extrait du PDF
        """
        try:
            if use_ocr:
                # Utiliser docling pour l'extraction avec OCR
                result = self.doc_converter.convert(attachment_path)
                return result.document.export_to_text()
            else:
                # Utiliser PyMuPDF comme avant
                with fitz.open(attachment_path) as doc:
                    text = ""
                    for page in doc:
                        text += page.get_text()
                return text
        except Exception as e:
            raise ValueError(f"Erreur lors de l'extraction du texte du PDF: {str(e)}")

    def download_pdf(self, attachment_key: str) -> str:
        """
        Télécharge le fichier PDF et retourne le chemin du fichier.
        
        Args:
            attachment_key: Clé de l'attachement Zotero
        
        Returns:
            Chemin vers le fichier PDF téléchargé
        """
        try:
            # Créer un fichier temporaire pour le PDF
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            temp_file.close()
            
            # Télécharger le PDF
            file_content = self.zot.file(attachment_key)
            
            # Écrire le contenu binaire dans le fichier temporaire
            with open(temp_file.name, 'wb') as f:
                f.write(file_content)
            
            return temp_file.name
        except Exception as e:
            raise ValueError(f"Erreur lors du téléchargement du PDF: {str(e)}")

    def check_and_update_metadata(self, item: dict, force_update: bool = False, use_ocr: bool = False) -> bool:
        """
        Vérifie et met à jour les métadonnées d'un élément si nécessaire.
        
        Args:
            item: L'élément Zotero à mettre à jour
            force_update: Si True, force la mise à jour même si les métadonnées existent
            use_ocr: Si True, utilise docling pour l'OCR
        """
        required_fields = ['title', 'creators', 'abstractNote', 'reportNumber', 'institution', 'place', 'date', 'language']
        missing_fields = [field for field in required_fields if not item['data'].get(field)] if not force_update else required_fields
        if not missing_fields and not force_update:
            return False
        
        # Récupérer l'attachement PDF
        attachments = self.zot.children(item['key'])
        pdf_attachment = next((att for att in attachments if att['data']['contentType'] == 'application/pdf'), None)
        
        if not pdf_attachment:
            print(f"Aucun PDF trouvé pour l'item {item['key']}")
            return False
        
        # Télécharger le PDF
        pdf_path = self.download_pdf(pdf_attachment['key'])
        
        # Extraire le texte du PDF avec l'option OCR
        content = self.extract_text_from_pdf(pdf_path, use_ocr=use_ocr)
        
        # Extraire et mettre à jour les métadonnées manquantes
        metadata = self.extract_metadata_with_llm(content)
        
        item['data']['itemType'] = "report"
        
        # Traitement spécial pour les auteurs
        if 'authors' in metadata and (force_update or 'creators' not in item['data'] or not item['data']['creators']):
            creators = []
            for author in metadata['authors']:
                if author.get('lastName') and author.get('firstName'):
                    # Cas d'un auteur avec nom et prénom
                    creators.append({
                        'creatorType': 'author',
                        'firstName': author['firstName'],
                        'lastName': author['lastName']
                    })
                elif author.get('denomination'):
                    # Cas d'un auteur institutionnel ou avec titre/qualité
                    creators.append({
                        'creatorType': 'author',
                        'firstName': '',
                        'lastName': author['denomination']
                    })
            
            if creators:
                item['data']['creators'] = creators
        
        # Mise à jour des autres champs
        for field in missing_fields:
            if field != 'creators' and field in metadata:
                item['data'][field] = metadata[field]
        
        # Mettre à jour l'élément dans Zotero
        self.zot.update_item(item)
        return True

def main():
    # Configurer l'analyseur d'arguments
    parser = argparse.ArgumentParser(description='Mise à jour des métadonnées Zotero')
    parser.add_argument('item_id', nargs='?', help='ID spécifique d\'un document à traiter')
    parser.add_argument('--ocr', action='store_true', help='Utiliser l\'OCR via docling pour l\'extraction du texte')
    args = parser.parse_args()

    # Charger les variables d'environnement
    load_dotenv()
    
    # Vérifier les variables requises
    required_vars = ["ZOTERO_LIBRARY_ID", "ZOTERO_LIBRARY_TYPE", 
                    "ZOTERO_API_KEY", "CLAUDE_API_KEY"]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Variables d'environnement manquantes: {', '.join(missing_vars)}")
    
    try:
        updater = ZoteroMetadataUpdater(
            os.getenv("ZOTERO_LIBRARY_ID"),
            os.getenv("ZOTERO_LIBRARY_TYPE"),
            os.getenv("ZOTERO_API_KEY"),
            os.getenv("CLAUDE_API_KEY")
        )
        
        # Traiter un document spécifique si un ID est fourni
        if args.item_id:
            try:
                item = updater.zot.item(args.item_id)
                print(f"Traitement de l'item {args.item_id}")
                updated = updater.check_and_update_metadata(item, force_update=True, use_ocr=args.ocr)
                if updated:
                    print(f"Métadonnées mises à jour pour l'item {args.item_id}")
                else:
                    print(f"Toutes les métadonnées sont présentes pour l'item {args.item_id}")
            except Exception as e:
                print(f"Erreur lors du traitement de l'item {args.item_id}: {str(e)}")
                sys.exit(1)
        else:
            # Traiter tous les documents
            valid_types = ['document', 'journalArticle', 'bookSection', 'report', 'thesis', 'webpage']
            items = updater.get_relevant_items(valid_types)
            print(f"Nombre d'items à traiter: {len(items)}")
            for item in items:
                print(f"Traitement de l'item {item['key']} ({item['data']['title']})")
                updated = updater.check_and_update_metadata(item, force_update=True, use_ocr=args.ocr)
                if updated:
                    print(f"Métadonnées mises à jour pour l'item {item['key']}")
                else:
                    print(f"Toutes les métadonnées sont présentes pour l'item {item['key']}")
        
        # Afficher les statistiques de coût
        cost_stats = updater.calculate_cost()
        print("\nStatistiques d'utilisation et coûts:")
        print(f"Tokens en entrée: {cost_stats['input_tokens']:,}")
        print(f"Tokens en sortie: {cost_stats['output_tokens']:,}")
        print(f"Coût des tokens en entrée: ${cost_stats['input_cost']:.4f}")
        print(f"Coût des tokens en sortie: ${cost_stats['output_cost']:.4f}")
        print(f"Coût total: ${cost_stats['total_cost']:.4f}")
            
    except Exception as e:
        print(f"Erreur: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()