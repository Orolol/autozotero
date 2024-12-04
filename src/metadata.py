"""Gestion des métadonnées."""

import os
from typing import Dict, Any
from decimal import Decimal
from .config import LLM_CONFIG
from .llm_providers import LLMProvider, create_llm_provider

class MetadataExtractor:
    def __init__(self, llm_type: str = 'anthropic', **llm_kwargs):
        """
        Initialise l'extracteur de métadonnées.
        
        Args:
            llm_type: Type de LLM à utiliser ('anthropic', 'openrouter' ou 'llama')
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
        
        # Récupérer la configuration du modèle
        if llm_type not in LLM_CONFIG:
            raise ValueError(f"Type de LLM non supporté : {llm_type}")
            
        self.config = LLM_CONFIG[llm_type].copy()
        self.config.update(llm_kwargs)
        
        # Extraire les coûts de la configuration
        self.costs = self.config.pop('costs', {'input_tokens': Decimal('0'), 'output_tokens': Decimal('0')})
        
        # Créer le fournisseur LLM
        self.llm = create_llm_provider(llm_type, **self.config)
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
        
        Ne pas répéter le texte à analyser dans la réponse. 
        Répondre uniquement en JSON.
        """

        system_prompt = "Vous êtes un assistant spécialisé dans l'extraction de métadonnées de documents administratifs, suivant des règles strictes. Vous répondez en JSON, lu par du Python (null pour une valeur nulle)."
        
        try:
            # Générer la réponse
            result = self.llm.generate(prompt, system_prompt)
            
            # Mettre à jour les compteurs de tokens
            self.total_input_tokens += result['usage']['input_tokens']
            self.total_output_tokens += result['usage']['output_tokens']
            
            # Extraire et nettoyer le JSON
            json_str = self._extract_json_from_text(result['content'])
            
            # Remplacer "None" par "null" avant de parser
            json_str = json_str.replace(': None', ': null')
            json_str = json_str.replace(':None', ':null')
            
            # Parser le JSON
            try:
                import json
                metadata = json.loads(json_str)
                # Valider le format
                self._validate_output_format(metadata)
                
                return metadata
                
            except json.JSONDecodeError as e:
                print(f"Erreur de décodage JSON : {e}")
                print(f"JSON reçu : {json_str}")  # Debug
                raise ValueError(f"JSON invalide : {e}")
            
        except Exception as e:
            print("Sortie brute du LLM :")
            print(result['content'] if 'content' in result else "Pas de contenu disponible")
            raise ValueError(f"Erreur lors de l'extraction des métadonnées: {str(e)}")

    def _extract_json_from_text(self, text: str) -> str:
        """
        Extrait l'objet JSON d'un texte en prenant le contenu entre le premier { et le dernier }.
        
        Args:
            text: Texte contenant potentiellement un objet JSON
            
        Returns:
            str: Chaîne JSON extraite
            
        Raises:
            ValueError: Si aucun JSON valide n'est trouvé
        """
        start = text.find('{')
        end = text.rfind('}')
        
        if start == -1 or end == -1:
            raise ValueError("Aucun objet JSON n'a été trouvé dans la réponse")
            
        return text[start:end + 1]

    def _validate_output_format(self, data: Dict[str, Any]) -> None:
        """
        Valide le format des données extraites.
        
        Args:
            data: Données à valider
            
        Raises:
            ValueError: Si le format n'est pas valide
        """
        # Valider le format des auteurs si présent
        if 'authors' in data:
            if not isinstance(data['authors'], list):
                print(f"Type de authors reçu : {type(data['authors'])}")
                print(f"Contenu de authors : {data['authors']}")
                raise ValueError("Le champ 'authors' doit être une liste")
                
            for i, author in enumerate(data['authors']):
                if not isinstance(author, dict):
                    print(f"Type d'auteur invalide à l'index {i}: {type(author)}")
                    raise ValueError(f"Chaque auteur doit être un dictionnaire, reçu: {type(author)}")

        # Valider le format de la date si présente
        if 'date' in data and data['date'] is not None:
            import re
            if not re.match(r'^\d{2}/\d{2}/\d{4}$', data['date']):
                raise ValueError(f"Format de date invalide (doit être DD/MM/YYYY): {data['date']}")
                
        # Valider le format des tags si présents
        if 'tags' in data:
            if not isinstance(data['tags'], list):
                raise ValueError("Le champ 'tags' doit être une liste")
                
            for i, tag_obj in enumerate(data['tags']):
                if not isinstance(tag_obj, dict):
                    print(f"Type de tag invalide à l'index {i}: {type(tag_obj)}")
                    raise ValueError(f"Chaque tag doit être un dictionnaire, reçu: {type(tag_obj)}")
                    
                if 'tag' not in tag_obj:
                    raise ValueError(f"Format de tag invalide : champ 'tag' manquant dans l'objet {tag_obj}")
                    
                if not isinstance(tag_obj['tag'], str):
                    raise ValueError(f"Le tag doit être une chaîne de caractères, reçu: {type(tag_obj['tag'])}")
                    
                if not tag_obj['tag'].startswith("./"):
                    raise ValueError(f"Les tags doivent commencer par './', reçu: {tag_obj['tag']}")
                    
                if len(tag_obj['tag']) <= 2:  # Juste "./" n'est pas valide
                    raise ValueError(f"Tag invalide : trop court - {tag_obj['tag']}")

    def calculate_cost(self) -> Dict[str, Any]:
        """
        Calcule le coût total basé sur l'utilisation des tokens et les coûts du modèle.
        
        Returns:
            Dict contenant les coûts détaillés et le total
        """
        input_cost = (Decimal(self.total_input_tokens) / Decimal('1000000')) * self.costs['input_tokens']
        output_cost = (Decimal(self.total_output_tokens) / Decimal('1000000')) * self.costs['output_tokens']
        
        return {
            'input_tokens': self.total_input_tokens,
            'output_tokens': self.total_output_tokens,
            'input_cost': input_cost,
            'output_cost': output_cost,
            'total_cost': input_cost + output_cost
        } 

    def _convert_nulls_to_none(self, data: Any) -> Any:
        """
        Convertit récursivement les null JSON en None Python.
        
        Args:
            data: Données à convertir
            
        Returns:
            Données avec les null convertis en None
        """
        if isinstance(data, dict):
            return {k: self._convert_nulls_to_none(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_nulls_to_none(item) for item in data]
        elif data is None:
            return None
        return data 