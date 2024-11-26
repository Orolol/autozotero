"""Gestion des métadonnées."""

import os
from typing import Dict, Any
from anthropic import Anthropic
from decimal import Decimal
from .config import INPUT_COST_PER_MILLION, OUTPUT_COST_PER_MILLION

class MetadataExtractor:
    def __init__(self, claude_api_key: str):
        """
        Initialise l'extracteur de métadonnées.
        
        Args:
            claude_api_key: Clé API Anthropic pour Claude
        """
        self.anthropic = Anthropic(api_key=claude_api_key)
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def extract_metadata(self, text: str) -> Dict[str, Any]:
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
            - denomination: titre ou qualité de l'auteur si pas de nom/prénom, sinon None
          Note: un auteur doit avoir soit lastName+firstName, soit denomination, mais pas les deux)
        - reportNumber (vérifier les en-têtes)
        - institution (chercher dans l'en-tête en haut à gauche)
        - place (chercher dans l'en-tête en haut à droite, en anglais)
        - date (format DD/MM/YYYY)
        - language (garder la langue originale du document)

        Ignorer tout contenu après une page commençant par "Annexe".

        En cas de valeurs manquantes, utiliser None.
        La sortie doit être un JSON valide qui sera évalué en Python. Retourner uniquement le JSON.
        
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

    def calculate_cost(self) -> Dict[str, Decimal]:
        """
        Calcule le coût total basé sur l'utilisation des tokens.
        
        Returns:
            Dict contenant les coûts détaillés et le total
        """
        input_cost = (Decimal(self.total_input_tokens) / Decimal('1000000')) * Decimal(str(INPUT_COST_PER_MILLION))
        output_cost = (Decimal(self.total_output_tokens) / Decimal('1000000')) * Decimal(str(OUTPUT_COST_PER_MILLION))
        
        return {
            'input_tokens': self.total_input_tokens,
            'output_tokens': self.total_output_tokens,
            'input_cost': input_cost,
            'output_cost': output_cost,
            'total_cost': input_cost + output_cost
        } 