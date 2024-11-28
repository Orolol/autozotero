# Zotero Metadata Updater

Outil d'extraction et de mise à jour automatique des métadonnées pour une bibliothèque Zotero, spécialisé dans le traitement des documents administratifs PDF.

## Description

Ce script permet d'automatiser la mise à jour des métadonnées de vos PDF dans Zotero. Il est particulièrement utile si vous avez :
- Un grand nombre de PDF à traiter
- Des documents avec une structure similaire (rapports administratifs, documents officiels, etc.)
- Besoin d'une extraction cohérente des métadonnées (titre, auteurs, dates, etc.)
- Besoin d'un tagging automatique des documents

Fonctionnalités principales :
- Extraction automatique des métadonnées selon des règles prédéfinies
- Support de l'OCR via Tesseract ou EasyOCR pour les documents scannés
- Tagging automatique des documents avec préfixe "./"
- Harmonisation des noms d'institutions
- Extraction des métadonnées depuis les noms de fichiers Camscanner
- Capitalisation automatique des champs
- Support de multiples modèles de langage (Claude, OpenRouter, Llama local)
- Gestion des coûts d'utilisation des API

## Prérequis

1. **Python** : Version 3.8 ou supérieure
2. **Zotero** :
   - Une bibliothèque Zotero (personnelle ou groupe)
   - Une [clé API Zotero](https://www.zotero.org/settings/keys)
   - Votre ID de bibliothèque (visible dans les paramètres Zotero)
3. **Modèles de Langage** (au choix) :
   - [Claude API (Anthropic)](https://console.anthropic.com/) - Modèle claude-3-5-haiku-latest
   - [OpenRouter API](https://openrouter.ai/) - Modèle gpt-4o-mini
   - Llama local (Qwen2.5-7B)
4. **OCR** (au choix) :
   - Tesseract-OCR (français et anglais par défaut)
   - EasyOCR (avec support GPU)

## Installation

1. Cloner le dépôt :
```bash
git clone https://github.com/votre-username/autozotero.git
cd autozotero
```

2. Installer les dépendances :
```bash
pip install -r requirements.txt
```

3. Créer un fichier `.env` à la racine du projet :
```env
ZOTERO_LIBRARY_ID=votre_library_id  # ex: 123456
ZOTERO_LIBRARY_TYPE=user            # ou 'group'
ZOTERO_API_KEY=votre_cle_api_zotero # ex: HGf91kNhas8917Jk...
CLAUDE_API_KEY=votre_cle_api_claude # ex: sk-ant-api03-...
OPENROUTER_API_KEY=votre_cle_api_openrouter # Si utilisation d'OpenRouter
```

## Configuration

1. **Modèles de Langage** : Trois options sont disponibles :
   - Claude (Anthropic) : Modèle claude-3-5-haiku-latest
   - OpenRouter : Modèle gpt-4o-mini-2024-07-18
   - Llama local : Modèle Qwen2.5-7B avec contexte de 5000 tokens

2. **OCR** : Deux options sont disponibles :
   - Tesseract (par défaut) : Configuré pour le français et l'anglais
   - EasyOCR : Support GPU activé par défaut

3. **Types de documents supportés** :
   - document
   - journalArticle
   - bookSection
   - report
   - thesis
   - webpage

## Utilisation

### 1. Traitement d'un document spécifique

Pour traiter un seul document, utilisez son ID Zotero :
```bash
python main.py ZOTERO_ITEM_ID
```

Exemple :
```bash
python main.py ABC123XY --ocr  # Avec OCR
```

### 2. Traitement de tous les documents

Pour traiter tous les documents de votre bibliothèque :
```bash
python main.py
```

Options disponibles :
- `--ocr` : Active l'OCR pour les documents scannés
- Plus d'options à venir...

### 3. Vérification des résultats

Après l'exécution, le script :
1. Affiche les documents traités
2. Indique les métadonnées mises à jour
3. Montre les coûts d'utilisation de l'API Claude

## Exemples de métadonnées extraites

Pour un document typique, le script extrait :
```
Titre: "Note relative à la libre circulation des personnes"
Auteur: "Le Chef du Service de Coopération Économique"
N° rapport: "MLC/2023/42"
Institution: "Service de Coopération Économique, Direction des Affaires Européennes (France)"
Lieu: "Paris"
Date: "15/03/2023"
Tags: ["./MLC", "./Libre Circulation", "./Coopération"]
```

## Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :
1. Fork le projet
2. Créer une branche pour votre fonctionnalité
3. Soumettre une Pull Request

## Auteur

Gaétan Martin

## Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.