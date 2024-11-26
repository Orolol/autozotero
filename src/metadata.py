"""Gestion des métadonnées."""

import os
from typing import Dict, Any
from decimal import Decimal
from .config import INPUT_COST_PER_MILLION, OUTPUT_COST_PER_MILLION, LLM_CONFIG
from .llm_providers import LLMProvider, create_llm_provider

class MetadataExtractor:
    def __init__(self, llm_type: str = 'anthropic', **llm_kwargs):
        """
        Initialise l'extracteur de métadonnées.
        
        Args:
            llm_type: Type de LLM à utiliser ('anthropic' ou 'llama')
            **llm_kwargs: Arguments spécifiques au LLM
        """
        # Vérifier la présence des fichiers nécessaires
        required_files = ['rules.txt', 'output.txt']
        missing_files = [f for f in required_files if not os.path.exists(f)]
        if missing_files:
            raise FileNotFoundError(
                f"Fichiers requis manquants : {', '.join(missing_files)}. "
                "Ces fichiers sont nécessaires pour l'extraction des métadonnées."
            )
        
        # Fusionner la configuration par défaut avec les arguments fournis
        config = LLM_CONFIG.get(llm_type, {}).copy()
        config.update(llm_kwargs)
        
        # Créer le fournisseur LLM
        self.llm = create_llm_provider(llm_type, **config)
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def extract_metadata(self, text: str) -> Dict[str, Any]:
        """
        Utilise le LLM pour extraire les métadonnées d'un texte selon des règles spécifiques.
        """
        # Charger les règles et le format de sortie
        with open('rules.txt', 'r', encoding='utf-8') as f:
            rules = f.read()
            
        with open('output.txt', 'r', encoding='utf-8') as f:
            output_format = f.read()

        prompt = f"""En utilisant ces règles spécifiques pour l'analyse des documents:

{rules}

Le format de sortie attendu est le suivant:

{output_format}

Texte à analyser:
{text}
"""

        system_prompt = "Vous êtes un assistant spécialisé dans l'extraction de métadonnées de documents administratifs, suivant des règles strictes."
        
        try:
            # Générer la réponse
            result = self.llm.generate(prompt, system_prompt)
            
            # Mettre à jour les compteurs de tokens
            self.total_input_tokens += result['usage']['input_tokens']
            self.total_output_tokens += result['usage']['output_tokens']
            
            # Nettoyer la sortie
            clean_output = result['content'].replace('```json', '').replace('```', '').strip()
            
            # Évaluer le JSON
            metadata = eval(clean_output)
            
            # Valider le format
            self._validate_output_format(metadata)
            
            return metadata
            
        except Exception as e:
            print("Sortie brute du LLM :")
            print(result['content'] if 'content' in result else "Pas de contenu disponible")
            raise ValueError(f"Erreur lors de l'extraction des métadonnées: {str(e)}")

    def _validate_output_format(self, data: Dict[str, Any]) -> None:
        """
        Valide le format des données extraites.
        
        Args:
            data: Données à valider
            
        Raises:
            ValueError: Si le format n'est pas valide
        """
        required_fields = ['title', 'authors', 'reportNumber', 'institution', 'place', 'date', 'language', 'tags']
        
        # Vérifier la présence de tous les champs
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Champ manquant : {field}")
        
        # Valider le format des auteurs
        if not isinstance(data['authors'], list):
            raise ValueError("Le champ 'authors' doit être une liste")
            
        for author in data['authors']:
            if not isinstance(author, dict):
                raise ValueError("Chaque auteur doit être un dictionnaire")
                
            if 'lastName' not in author or 'firstName' not in author or 'denomination' not in author:
                raise ValueError("Format d'auteur invalide : champs manquants")
                
            # Vérifier la règle lastName+firstName XOR denomination
            has_name = author['lastName'] is not None or author['firstName'] is not None
            has_denom = author['denomination'] is not None
            
            if has_name and has_denom:
                raise ValueError("Un auteur ne peut pas avoir à la fois un nom/prénom et une dénomination")
            if not has_name and not has_denom:
                raise ValueError("Un auteur doit avoir soit un nom/prénom, soit une dénomination")
        
        # Valider le format de la date
        if data['date'] is not None:
            import re
            if not re.match(r'^\d{2}/\d{2}/\d{4}$', data['date']):
                raise ValueError("Format de date invalide (doit être DD/MM/YYYY)")
                
        # Valider le format des tags
        if not isinstance(data['tags'], list):
            raise ValueError("Le champ 'tags' doit être une liste")
            
        for tag_obj in data['tags']:
            if not isinstance(tag_obj, dict):
                raise ValueError("Chaque tag doit être un dictionnaire")
                
            if 'tag' not in tag_obj:
                raise ValueError("Format de tag invalide : champ 'tag' manquant")
                
            if not isinstance(tag_obj['tag'], str):
                raise ValueError("Le tag doit être une chaîne de caractères")
                
            if not tag_obj['tag'].startswith("./"):
                raise ValueError("Les tags doivent commencer par './'")
                
            if len(tag_obj['tag']) <= 2:  # Juste "./" n'est pas valide
                raise ValueError("Tag invalide : trop court")

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