# main.py
"""
Point d'entrée du programme : prints, questions (y/n), appels de fonctions...
"""

import os
import logging
from config import (
    BDD_NAME_PREFIX,
    EXCEL_FILE,
    LOG_FILE
)
from utils import (
    create_connection,
    create_tables,
    ensure_combinaisons_filtrees_columns,
    fix_null_columns,
    import_historique,
    process_historique_stats,
    write_histo_stats_summary,
    generate_combinations_in_filtrees,
    apply_all_filters_interactive,
    process_combinaisons_stats,
    write_combos_stats_summary,
    extraction_seuil,
    apply_heuristique_4sur5,
    apply_heuristique_3sur5,
    apply_heuristique_2sur5,
    final_tables_summary,
    random_draw_from_table
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, mode='w'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def main():
    print("=== Démarrage du programme ===\n")
    db_files = [f for f in os.listdir() if f.endswith(".db")]
    if db_files:
        print("Bases de données existantes :")
        for i,f in enumerate(db_files,start=1):
            print(f"  {i}. {f}")
    else:
        print("Aucune base de données existante.\n")

    act = input("\nVoulez-vous (edit) une base existante ou en (new) ? ").lower().strip()
    if act=="edit":
        idx=input("Entrez le numéro de la base à éditer : ").strip()
        try:
            val=int(idx)
            db_file=db_files[val-1]
        except:
            print("Index invalide. Fin.")
            return
    elif act=="new":
        ver=input("Entrez l'id pour la nouvelle base : ").strip()
        db_file=f"{BDD_NAME_PREFIX}{ver}.db"
    else:
        print("Aucune action, fin du programme.")
        return

    conn = create_connection(db_file)
    if not conn:
        return

    # Création des tables, etc.
    create_tables(conn)
    ensure_combinaisons_filtrees_columns(conn)
    fix_null_columns(conn)

    # Historique
    if input("\nImporter l'historique Excel ? (y/n) : ").lower().strip()=="y":
        import_historique(conn, EXCEL_FILE)

    # Stats historique
    if input("Calculer les stats sur l'historique ? (y/n) : ").lower().strip()=="y":
        process_historique_stats(conn)
        sum_histo = write_histo_stats_summary(conn)
        print("\n[Résumé des stats historiques]\n")
        print(sum_histo,"\n")

    # Génération de toutes les combinaisons
    if input("Générer les combinaisons dans Combinaisons_Filtrees ? (y/n) : ").lower().strip()=="y":
        generate_combinations_in_filtrees(conn)

    # Filtrage interactif
    if input("\nAppliquer les 13 filtres sur Combinaisons_Filtrees ? (y/n) : ").lower().strip()=="y":
        # Charger l'historique en python (pour mps, comparatif)
        c=conn.cursor()
        c.execute("SELECT bitmask FROM Historique ORDER BY id")
        hist_for_filters = [r[0] for r in c.fetchall()]
        apply_all_filters_interactive(conn, hist_for_filters)

    # Stats combos
    if input("Calculer les stats sur les combinaisons filtrées ? (y/n) : ").lower().strip()=="y":
        process_combinaisons_stats(conn)
        combo_sum = write_combos_stats_summary(conn)
        print("\n[Résumé des stats sur les combinaisons]\n")
        print(combo_sum,"\n")

    # Extraction par seuil
    tab_ex = extraction_seuil(conn)

    # Heuristiques
    if tab_ex and input("\nAppliquer heuristique 4sur5 sur le dernier tableau extrait ? (y/n) : ").lower().strip()=="y":
        apply_heuristique_4sur5(conn, table_name="CombinaisonsExtraites")

    if input("Appliquer heuristique 3sur5 ? (y/n) : ").lower().strip()=="y":
        apply_heuristique_3sur5(conn, table_name="Heuristique4sur5")

    if input("Appliquer heuristique 2sur5 ? (y/n) : ").lower().strip()=="y":
        apply_heuristique_2sur5(conn, table_name="Heuristique3sur5")

    # Résumé final
    final_tables_summary(conn)

    # Tirage aléatoire
    random_draw_from_table(conn)

    conn.close()
    print("\n=== Fin du programme ===\n")
    logger.info("=== Fin du programme ===")

if __name__=="__main__":
    main()
