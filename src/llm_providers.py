"""Fournisseurs de modèles de langage."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from anthropic import Anthropic
from llama_cpp import Llama

class LLMProvider(ABC):
    """Classe abstraite pour les fournisseurs de LLM."""
    
    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = None) -> Dict[str, Any]:
        """
        Génère une réponse à partir d'un prompt.
        
        Args:
            prompt: Le prompt principal
            system_prompt: Le prompt système (optionnel)
            
        Returns:
            Dictionnaire contenant la réponse et les statistiques d'utilisation
        """
        pass

class AnthropicProvider(LLMProvider):
    """Fournisseur utilisant l'API Anthropic Claude."""
    
    def __init__(self, api_key: str, model_name: str = "claude-3-5-haiku-latest"):
        """
        Initialise le fournisseur Anthropic.
        
        Args:
            api_key: Clé API Anthropic
            model_name: Nom du modèle à utiliser
        """
        self.client = Anthropic(api_key=api_key)
        self.model_name = model_name

    def generate(self, prompt: str, system_prompt: str = None) -> Dict[str, Any]:
        message = self.client.messages.create(
            model=self.model_name,
            max_tokens=1000,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return {
            'content': message.content[0].text,
            'usage': {
                'input_tokens': message.usage.input_tokens,
                'output_tokens': message.usage.output_tokens
            }
        }

class LlamaProvider(LLMProvider):
    """Fournisseur utilisant un modèle Llama local."""
    
    def __init__(self, 
                 model_path: Optional[str] = None,
                 repo_id: Optional[str] = None,
                 filename: Optional[str] = None,
                 n_ctx: int = 8192,
                 **kwargs):
        """
        Initialise le fournisseur Llama.
        
        Args:
            model_path: Chemin vers le modèle local
            repo_id: ID du dépôt HuggingFace (si téléchargement)
            filename: Nom du fichier dans le dépôt
            n_ctx: Taille du contexte
            **kwargs: Arguments supplémentaires pour Llama
        """
        if model_path:
            self.model = Llama(model_path=model_path, n_ctx=n_ctx, **kwargs)
        else:
            self.model = Llama.from_pretrained(
                repo_id=repo_id,
                filename=filename,
                n_ctx=n_ctx,
                **kwargs
            )

    def generate(self, prompt: str, system_prompt: str = None) -> Dict[str, Any]:
        # Construire le prompt complet
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        else:
            full_prompt = prompt
            
        # Générer la réponse
        output = self.model(
            full_prompt,
            max_tokens=1000,
            temperature=0,
            echo=False
        )
        
        return {
            'content': output['choices'][0]['text'],
            'usage': {
                'input_tokens': output.get('usage', {}).get('prompt_tokens', 0),
                'output_tokens': output.get('usage', {}).get('completion_tokens', 0)
            }
        }

def create_llm_provider(provider_type: str, **kwargs) -> LLMProvider:
    """
    Crée un fournisseur LLM selon le type spécifié.
    
    Args:
        provider_type: Type de fournisseur ('anthropic' ou 'llama')
        **kwargs: Arguments spécifiques au fournisseur
        
    Returns:
        Instance de LLMProvider
    """
    providers = {
        'anthropic': AnthropicProvider,
        'llama': LlamaProvider
    }
    
    if provider_type not in providers:
        raise ValueError(f"Fournisseur non supporté : {provider_type}")
        
    return providers[provider_type](**kwargs) 