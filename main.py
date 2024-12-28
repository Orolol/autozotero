#!/usr/bin/env python3
"""Point d'entrée principal du programme."""

import os
import sys
import argparse
import time
from datetime import timedelta
from dotenv import load_dotenv

from src.updater import ZoteroMetadataUpdater
from src.file_utils import find_pdf_files

def main():
    start_time = time.time()  # Début du chronomètre global
    
    parser = argparse.ArgumentParser(
        description='Mise à jour des métadonnées Zotero',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation :
  %(prog)s                     # Traite tous les documents
  %(prog)s ABC123XY            # Traite un document spécifique
  %(prog)s --folder /chemin --recursive --pattern "*.pdf"  # Traite tous les PDF récursivement
  %(prog)s --folder /chemin --collections ABC123,XYZ789    # Ajoute à plusieurs collections
  %(prog)s --folder /chemin --local-model                  # Utilise le modèle local au lieu de Claude
        """
    )
    parser.add_argument('item_id', nargs='?', help='ID spécifique d\'un document à traiter')
    parser.add_argument('--ocr', action='store_true', help='Utiliser l\'OCR pour l\'extraction du texte')
    parser.add_argument('--dry-run', action='store_true', help='Simuler l\'exécution sans modifier Zotero')
    parser.add_argument('--verbose', action='store_true', help='Afficher plus de détails pendant l\'exécution')
    parser.add_argument('--folder', help='Chemin vers un dossier contenant des PDF à traiter')
    parser.add_argument('--collections', help='Liste des clés de collections séparées par des virgules')
    parser.add_argument('--recursive', action='store_true', help='Traiter les sous-dossiers')
    parser.add_argument('--pattern', help='Pattern glob pour filtrer les noms de fichiers (ex: "2024*.pdf")')
    parser.add_argument('--keep-duplicates', action='store_true', help='Ne pas ignorer les doublons')
    parser.add_argument('--local-model', action='store_true', help='Utiliser le modèle local au lieu de Claude')
    parser.add_argument('--use-openrouter', action='store_true', help='Utiliser OpenRouter au lieu de Claude')
    args = parser.parse_args()

    # Charger les variables d'environnement
    if not os.path.exists('.env'):
        print("Erreur : Fichier .env manquant.")
        print("Veuillez créer un fichier .env avec les variables suivantes :")
        print("ZOTERO_LIBRARY_ID=votre_library_id")
        print("ZOTERO_LIBRARY_TYPE=user_ou_group")
        print("ZOTERO_API_KEY=votre_cle_api_zotero")
        if not args.local_model:
            print("CLAUDE_API_KEY=votre_cle_api_claude")
        sys.exit(1)

    load_dotenv()
    
    # Vérifier les variables requises
    required_vars = {
        "ZOTERO_LIBRARY_ID": "ID de votre bibliothèque Zotero",
        "ZOTERO_LIBRARY_TYPE": "Type de bibliothèque ('user' ou 'group')",
        "ZOTERO_API_KEY": "Clé API Zotero (https://www.zotero.org/settings/keys)",
    }
    
    if not args.local_model:
        if args.use_openrouter:
            required_vars["OPENROUTER_API_KEY"] = "Clé API OpenRouter"
        else:
            required_vars["CLAUDE_API_KEY"] = "Clé API Claude (https://console.anthropic.com/)"
    
    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"- {var}: {description}")
    
    if missing_vars:
        print("Erreur : Variables d'environnement manquantes :")
        print("\n".join(missing_vars))
        sys.exit(1)
    
    try:
        updater = ZoteroMetadataUpdater(
            os.getenv("ZOTERO_LIBRARY_ID"),
            os.getenv("ZOTERO_LIBRARY_TYPE"),
            os.getenv("ZOTERO_API_KEY"),
            os.getenv("CLAUDE_API_KEY") if not (args.local_model or args.use_openrouter) else None,
            use_local_model=args.local_model,
            use_openrouter=args.use_openrouter,
            openrouter_config={"api_key": os.getenv("OPENROUTER_API_KEY")} if args.use_openrouter else None
        )
        
        if args.verbose:
            print("✓ Connexion établie avec Zotero")
            if args.local_model:
                model_type = 'local'
            elif args.use_openrouter:
                model_type = 'OpenRouter'
            else:
                model_type = 'Claude'
            print(f"✓ Modèle utilisé : {model_type}")
            print(f"✓ Mode OCR : {'activé' if args.ocr else 'désactivé'}")
            print(f"✓ Mode simulation : {'activé' if args.dry_run else 'désactivé'}")
            if args.folder:
                print(f"✓ Mode récursif : {'activé' if args.recursive else 'désactivé'}")
                print(f"✓ Vérification doublons : {'désactivée' if args.keep_duplicates else 'activée'}")
                if args.pattern:
                    print(f"✓ Filtre : {args.pattern}")
        # Traitement d'un dossier de PDF
        if args.folder:
            if not os.path.isdir(args.folder):
                print(f"Erreur : Le dossier {args.folder} n'existe pas")
                sys.exit(1)
            
            # Trouver les PDF à traiter
            pdf_files = find_pdf_files(args.folder, args.recursive, args.pattern)
            if not pdf_files:
                print(f"Aucun fichier PDF trouvé dans {args.folder}")
                sys.exit(0)
            
            print(f"Traitement de {len(pdf_files)} fichiers PDF...")
            # Convertir la liste de collections
            collections = args.collections.split(',') if args.collections else None
            
            # Traiter chaque PDF
            processed = []
            skipped = []
            failed = []
            processing_times = []  # Liste pour stocker les temps de traitement
            
            for i, pdf_path in enumerate(pdf_files, 1):
                item_start_time = time.time()  # Début du chronomètre par item
                try:
                    print(f"\n[{i}/{len(pdf_files)}] Traitement de {os.path.basename(pdf_path)}")
                    
                    if not args.dry_run:
                        item = updater.process_pdf(pdf_path, collections, args.ocr)
                        processed.append(item['key'])
                        processing_time = time.time() - item_start_time
                        processing_times.append(processing_time)
                        print(f"✓ PDF importé et métadonnées mises à jour (en {processing_time:.1f}s)")
                    else:
                        print(f"✓ (Simulation) PDF serait importé")
                    
                except ValueError as e:
                    if "existe déjà" in str(e):
                        print(f"✓ {str(e)}")
                        skipped.append(pdf_path)
                    else:
                        print(f"✗ Erreur : {str(e)}")
                        failed.append(pdf_path)
                except Exception as e:
                    print(f"✗ Erreur : {str(e)}")
                    failed.append(pdf_path)
            
            # Afficher le résumé
            total_time = time.time() - start_time
            print(f"\nRésumé du traitement :")
            print(f"- Durée totale: {str(timedelta(seconds=int(total_time)))}")
            if processing_times:
                avg_time = sum(processing_times) / len(processing_times)
                print(f"- Temps moyen par document: {avg_time:.1f}s")
            print(f"- {len(processed)} documents traités avec succès")
            print(f"- {len(skipped)} documents ignorés (doublons)")
            print(f"- {len(failed)} documents en erreur")
            
            if failed:
                print("\nDocuments en erreur :")
                for path in failed:
                    print(f"- {path}")
            
            # Afficher les coûts
            if not args.dry_run and processed:
                cost_stats = updater.calculate_cost()
                print("\nStatistiques d'utilisation et coûts:")
                print(f"Tokens en entrée: {cost_stats['input_tokens']:,}")
                print(f"Tokens en sortie: {cost_stats['output_tokens']:,}")
                print(f"Coût total: ${cost_stats['total_cost']:.4f}")
        
        # Traitement d'un document spécifique
        elif args.item_id:
            try:
                print(f"Traitement de l'item {args.item_id}")
                # TODO: Implémenter le traitement d'un item existant
                print("Fonctionnalité non implémentée")
                sys.exit(1)
            except Exception as e:
                print(f"Erreur lors du traitement de l'item {args.item_id}: {str(e)}")
                sys.exit(1)
        
        # Traitement de tous les documents
        else:
            print("Traitement de tous les documents...")
            # Traiter tous les documents
            valid_types = ['document', 'journalArticle', 'bookSection', 'report', 'thesis', 'webpage']
            items = updater.zot_client.get_all_items(item_type="-attachment")
            print(f"Nombre total d'items trouvés: {len(items)}")
            
            # Filtrer les items par type
            items_to_process = [item for item in items if item['data'].get('itemType') in valid_types]
            print(f"Nombre d'items à traiter (types valides): {len(items_to_process)}")
            
            # Traiter chaque PDF
            processed = []
            skipped = []
            failed = []
            processing_times = []
            
            for item in items_to_process:
                item_start_time = time.time()
                try:
                    updated = updater.check_and_update_metadata(item, force_update=True, use_ocr=args.ocr)
                    processing_time = time.time() - item_start_time
                    processing_times.append(processing_time)
                    if updated:
                        print(f"✓ Métadonnées mises à jour pour l'item {item['key']} (en {processing_time:.1f}s)")
                        processed.append(item['key'])
                    else:
                        print(f"- Pas de mise à jour nécessaire pour l'item {item['key']} (en {processing_time:.1f}s)")
                        skipped.append(item['key'])
                except Exception as e:
                    print(f"✗ Erreur lors du traitement de l'item {item['key']}: {str(e)}")
                    failed.append(item['key'])
            
            # Afficher le résumé
            total_time = time.time() - start_time
            print(f"\nRésumé du traitement :")
            print(f"- Durée totale: {str(timedelta(seconds=int(total_time)))}")
            if processing_times:
                avg_time = sum(processing_times) / len(processing_times)
                print(f"- Temps moyen par document: {avg_time:.1f}s")
            print(f"- {len(processed)} documents traités avec succès")
            print(f"- {len(skipped)} documents ignorés")
            print(f"- {len(failed)} documents en erreur")
            
            if failed:
                print("\nDocuments en erreur :")
                for item_key in failed:
                    print(f"- {item_key}")
            
            # Afficher les coûts
            if not args.dry_run and processed:
                cost_stats = updater.calculate_cost()
                print("\nStatistiques d'utilisation et coûts:")
                print(f"Tokens en entrée: {cost_stats['input_tokens']:,}")
                print(f"Tokens en sortie: {cost_stats['output_tokens']:,}")
                print(f"Coût total: ${cost_stats['total_cost']:.4f}")
            
    except Exception as e:
        print(f"Erreur : {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()