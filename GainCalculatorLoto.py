#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GainCalculator.py

Ce programme permet de calculer et d'enregistrer les gains d’un tirage de Loto (5 numéros et 1 numéro chance).

Fonctionnement :
1. Se connecte à la base de résultats "Resultats.db" et, s'il existe déjà un tirage enregistré dans la table ResultatsTirage, 
   affiche la combinaison gagnante et les gains pour chacune des 12 combinaisons et demande si l'utilisateur veut les modifier.
2. Si aucun tirage n'existe ou si l'utilisateur souhaite modifier, il saisit les gains pour chaque combinaison (12 cas).
3. L'utilisateur saisit la combinaison gagnante (5 numéros et 1 numéro chance).
4. Le programme liste les bases de données SQLite existantes et l'utilisateur choisit la base source.
5. Il liste les tables de la base source et l'utilisateur choisit la table contenant les tirages.
6. Le programme s'assure que la table source possède la colonne "etoiles" et la complète si nécessaire.
7. Pour chaque tirage de la table source, le programme calcule le nombre de numéros corrects et de numéro chance correct,
   détermine le gain via le dictionnaire des gains, et insère ces résultats dans la table GainsCombinaisons.
8. Le tirage gagnant et les gains par combinaison sont enregistrés dans la table ResultatsTirage.
9. Le coût total (nombre de tirages × 2,20 €) est calculé, ainsi que la différence (gains - dépenses), et le bilan est affiché.
"""

import sqlite3
import random
import os
import sys
import ast

# -----------------------------------------
# 1. Définir les gains possibles (12 combinaisons)
# -----------------------------------------
def definir_gains_possibles():
    gains = {}
    print("\n[INFO] Définissez les gains pour chaque combinaison possible (12).")
    boules_possibles = [5, 4, 3, 2, 1, 0]
    etoiles_possibles = [1, 0]  # 1 = numéro chance correct, 0 = incorrect
    for b in boules_possibles:
        for e in etoiles_possibles:
            while True:
                gain_input = input(f"Gain pour {b} boules et {e} numéro chance : ").replace(",", ".")
                try:
                    val = float(gain_input)
                    gains[(b, e)] = val
                    break
                except ValueError:
                    print("[ERREUR] Entrez une valeur numérique valide.")
    if len(gains) != 12:
        print("[ERREUR] Nombre de gains définis incorrect. On attend 12 combinaisons.")
        sys.exit(1)
    return gains

# -----------------------------------------
# 2. Lister les bases de données SQLite existantes
# -----------------------------------------
def lister_bases_donnees():
    fichiers = [f for f in os.listdir() if f.endswith(".db")]
    if not fichiers:
        print("[ERREUR] Aucune base de données SQLite trouvée dans le répertoire.")
        sys.exit(1)
    return fichiers

# -----------------------------------------
# 3. Scanner une base de données pour lister ses tables
# -----------------------------------------
def scanner_base_donnees(nom_bdd):
    conn = sqlite3.connect(nom_bdd)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables

# -----------------------------------------
# 4. Vérifier et ajouter la colonne 'etoiles' dans la table source
# -----------------------------------------
def ajouter_etoiles_si_necessaire(conn, table):
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    colonnes = [col[1] for col in cursor.fetchall()]
    if "etoiles" not in colonnes:
        print(f"[INFO] La table {table} ne contient pas la colonne 'etoiles'. Ajout en cours...")
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN etoiles TEXT")
        conn.commit()
        cursor.execute(f"SELECT id FROM {table}")
        rows = cursor.fetchall()
        for row in rows:
            id_ligne = row[0]
            numero_chance = random.choice(range(1, 11))
            cursor.execute(f"UPDATE {table} SET etoiles=? WHERE id=?", (str([numero_chance]), id_ligne))
        conn.commit()

def ajouter_etoiles_si_absentes(conn, table):
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    colonnes = [col[1] for col in cursor.fetchall()]
    if "etoiles" not in colonnes:
        print(f"[INFO] La colonne 'etoiles' est absente de la table '{table}'. Ajout...")
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN etoiles TEXT")
        conn.commit()
    cursor.execute(f"SELECT id FROM {table} WHERE etoiles IS NULL OR etoiles = ''")
    rows = cursor.fetchall()
    if rows:
        print(f"[INFO] Génération du numéro chance pour {len(rows)} lignes manquantes...")
        for row in rows:
            id_ligne = row[0]
            numero_chance = random.choice(range(1, 11))
            cursor.execute(f"UPDATE {table} SET etoiles=? WHERE id=?", (str([numero_chance]), id_ligne))
        conn.commit()
    print("[INFO] Vérification de la colonne 'etoiles' terminée.")

# -----------------------------------------
# 5. Calculer les gains pour chaque tirage de la table source
# -----------------------------------------
def calculer_gains_combinaisons(conn_source, table, numero_gagnant, gains_possibles):
    cursor = conn_source.cursor()
    ajouter_etoiles_si_absentes(conn_source, table)
    cursor.execute(f"SELECT id, boules, etoiles FROM {table}")
    rows = cursor.fetchall()
    print(f"[DEBUG] Nombre de lignes extraites de {table} : {len(rows)}")
    boules_gagnantes = numero_gagnant["boules"]
    etoiles_gagnantes = numero_gagnant["etoiles"]
    resultats = []
    for row in rows:
        id_comb, boules_str, etoiles_str = row
        try:
            boules = ast.literal_eval(boules_str)
        except:
            print(f"[DEBUG] Ligne ignorée (boules non valide) : {boules_str}")
            continue
        try:
            etoiles = ast.literal_eval(etoiles_str)
            if isinstance(etoiles, int):
                etoiles = [etoiles]
        except:
            print(f"[DEBUG] Ligne ignorée (numéro chance non valide) : {etoiles_str}")
            continue
        b_communes = len(set(boules).intersection(boules_gagnantes))
        e_communes = len(set(etoiles).intersection(etoiles_gagnantes))
        gain = gains_possibles.get((b_communes, e_communes), 0.0)
        etoile_uni = etoiles[0] if etoiles else None
        resultats.append((boules_str, str(etoile_uni), gain, b_communes, e_communes))
    print(f"[DEBUG] Nombre de résultats calculés : {len(resultats)}")
    return resultats

# -----------------------------------------
# 6. Initialiser les tables de résultats dans la base "Resultats.db"
# -----------------------------------------
def initialiser_tables_resultats(conn):
    cursor = conn.cursor()
    # Pour ResultatsTirage, on crée la table si elle n'existe pas (on ne la réinitialise pas pour conserver le tirage précédent)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ResultatsTirage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boules_gagnantes TEXT,
            etoiles_gagnantes TEXT,
            date_tirage TEXT,
            gain_5_1 REAL, gain_5_0 REAL,
            gain_4_1 REAL, gain_4_0 REAL,
            gain_3_1 REAL, gain_3_0 REAL,
            gain_2_1 REAL, gain_2_0 REAL,
            gain_1_1 REAL, gain_1_0 REAL,
            gain_0_1 REAL, gain_0_0 REAL
        )
    """)
    conn.commit()
    # Pour garantir le schéma de GainsCombinaisons et Bilan, on les recrée à chaque lancement
    cursor.execute("DROP TABLE IF EXISTS GainsCombinaisons")
    cursor.execute("""
        CREATE TABLE GainsCombinaisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boules TEXT,
            etoiles TEXT,
            gain REAL,
            similarite_boules INTEGER,
            similarite_etoiles INTEGER
        )
    """)
    conn.commit()
    cursor.execute("DROP TABLE IF EXISTS Bilan")
    cursor.execute("""
        CREATE TABLE Bilan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_tirage TEXT,
            total_gains REAL,
            total_depenses REAL,
            difference REAL
        )
    """)
    conn.commit()

# -----------------------------------------
# 7. Charger le dernier tirage existant dans ResultatsTirage
# -----------------------------------------
def charger_gains_existants(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ResultatsTirage ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    if not row:
        return None, None, None, None
    try:
        boules_gagnantes = ast.literal_eval(row[1])
    except:
        boules_gagnantes = []
    try:
        etoiles_gagnantes = ast.literal_eval(row[2])
        if isinstance(etoiles_gagnantes, int):
            etoiles_gagnantes = [etoiles_gagnantes]
    except:
        etoiles_gagnantes = []
    date_tirage = row[3]
    gains_list = row[4:16]  # 12 valeurs attendues
    ordered_combos = [(5,1),(5,0),(4,1),(4,0),(3,1),(3,0),(2,1),(2,0),(1,1),(1,0),(0,1),(0,0)]
    gains_possibles = {combo: gain for combo, gain in zip(ordered_combos, gains_list)}
    return gains_possibles, boules_gagnantes, etoiles_gagnantes, date_tirage

# -----------------------------------------
# 8. Sauvegarder (insérer ou mettre à jour) le tirage gagnant dans ResultatsTirage
# -----------------------------------------
def sauvegarder_tirage(conn, numero_gagnant, gains_possibles, date_tirage):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM ResultatsTirage ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    ordered_combos = [(5,1),(5,0),(4,1),(4,0),(3,1),(3,0),(2,1),(2,0),(1,1),(1,0),(0,1),(0,0)]
    gains_a_inserer = [gains_possibles.get(c, 0.0) for c in ordered_combos]
    boules_str = str(numero_gagnant["boules"])
    etoiles_str = str(numero_gagnant["etoiles"])
    if row:
        id_exist = row[0]
        sql = """
            UPDATE ResultatsTirage
            SET boules_gagnantes = ?,
                etoiles_gagnantes = ?,
                date_tirage = ?,
                gain_5_1 = ?, gain_5_0 = ?,
                gain_4_1 = ?, gain_4_0 = ?,
                gain_3_1 = ?, gain_3_0 = ?,
                gain_2_1 = ?, gain_2_0 = ?,
                gain_1_1 = ?, gain_1_0 = ?,
                gain_0_1 = ?, gain_0_0 = ?
            WHERE id = ?
        """
        cursor.execute(sql, (boules_str, etoiles_str, date_tirage, *gains_a_inserer, id_exist))
    else:
        sql = """
            INSERT INTO ResultatsTirage (
                boules_gagnantes, etoiles_gagnantes, date_tirage,
                gain_5_1, gain_5_0,
                gain_4_1, gain_4_0,
                gain_3_1, gain_3_0,
                gain_2_1, gain_2_0,
                gain_1_1, gain_1_0,
                gain_0_1, gain_0_0
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(sql, (boules_str, etoiles_str, date_tirage, *gains_a_inserer))
    conn.commit()

# -----------------------------------------
# 9. Insérer les gains calculés dans GainsCombinaisons
# -----------------------------------------
def inserer_gains_combinaisons(conn_res, resultats):
    cursor = conn_res.cursor()
    cursor.execute("DELETE FROM GainsCombinaisons")
    cursor.executemany("""
        INSERT INTO GainsCombinaisons (boules, etoiles, gain, similarite_boules, similarite_etoiles)
        VALUES (?, ?, ?, ?, ?)
    """, resultats)
    conn_res.commit()

# -----------------------------------------
# 10. Calculer le bilan et l'enregistrer dans Bilan, puis l'afficher
# -----------------------------------------
def calculer_bilan(conn_res, date_tirage):
    cursor = conn_res.cursor()
    cursor.execute("SELECT SUM(gain), COUNT(*) FROM GainsCombinaisons")
    row = cursor.fetchone()
    total_gains = row[0] if row[0] is not None else 0.0
    nb_combinaisons = row[1]
    total_depenses = nb_combinaisons * 2.2
    difference = total_gains - total_depenses
    cursor.execute("DELETE FROM Bilan")
    cursor.execute("""
        INSERT INTO Bilan(date_tirage, total_gains, total_depenses, difference)
        VALUES (?, ?, ?, ?)
    """, (date_tirage, total_gains, total_depenses, difference))
    conn_res.commit()

def afficher_bilan(conn_res):
    cursor = conn_res.cursor()
    cursor.execute("SELECT date_tirage, total_gains, total_depenses, difference FROM Bilan ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        dt, gains, depenses, diff = row
        print("\n[INFO] Bilan du tirage :")
        print(f"Date du tirage : {dt}")
        print(f"Total des gains : {gains:.2f} €")
        print(f"Total des dépenses : {depenses:.2f} €")
        print(f"Différence (gains - dépenses) : {diff:.2f} €")
    else:
        print("[INFO] Aucun bilan disponible.")

# -----------------------------------------
# 11. Main
# -----------------------------------------
def main():
    print("[LOG] Démarrage du programme...")

    # Connexion à la base de résultats "Resultats.db"
    resultat_bdd = "Resultats.db"
    conn_res = sqlite3.connect(resultat_bdd)
    initialiser_tables_resultats(conn_res)

    # Vérifier si un tirage existe déjà et proposer de conserver ou modifier les gains
    gains_existants, bg_exist, eg_exist, dt_exist = charger_gains_existants(conn_res)
    if gains_existants:
        print("\n[INFO] Tirage précédent trouvé dans la base de résultats :")
        print(f"Boules gagnantes : {bg_exist}")
        print(f"Numéro chance : {eg_exist}")
        print(f"Date : {dt_exist}")
        print("Gains enregistrés :")
        ordered_combos = [(5,1),(5,0),(4,1),(4,0),(3,1),(3,0),(2,1),(2,0),(1,1),(1,0),(0,1),(0,0)]
        for combo in ordered_combos:
            print(f"{combo[0]} boules, {combo[1]} chance : {gains_existants.get(combo, 0.0)} €")
        rep = input("Voulez-vous modifier ces valeurs ? (o/N) : ").strip().lower()
        if rep == 'o':
            gains_possibles = definir_gains_possibles()
            try:
                print("[INFO] Saisir 5 boules gagnantes (ex: 2 15 23 31 48) :")
                bg = list(map(int, input("> ").split()))
                print("[INFO] Saisir 1 numéro chance gagnant (ex: 7) :")
                eg = list(map(int, input("> ").split()))
            except ValueError:
                print("[ERREUR] Entrée invalide.")
                sys.exit(1)
            if len(bg) != 5 or len(eg) != 1:
                print("[ERREUR] Nombre de boules ou de numéro chance invalide.")
                sys.exit(1)
            dt = input("Date du tirage (YYYY-MM-DD) : ").strip()
            numero_gagnant = {"boules": bg, "etoiles": eg}
            sauvegarder_tirage(conn_res, numero_gagnant, gains_possibles, dt)
        else:
            gains_possibles = gains_existants
            numero_gagnant = {"boules": bg_exist, "etoiles": eg_exist}
            dt = dt_exist
    else:
        gains_possibles = definir_gains_possibles()
        try:
            print("[INFO] Saisir 5 boules gagnantes (ex: 2 15 23 31 48) :")
            bg = list(map(int, input("> ").split()))
            print("[INFO] Saisir 1 numéro chance gagnant (ex: 7) :")
            eg = list(map(int, input("> ").split()))
        except ValueError:
            print("[ERREUR] Entrée invalide.")
            sys.exit(1)
        if len(bg) != 5 or len(eg) != 1:
            print("[ERREUR] Nombre de boules ou de numéro chance invalide.")
            sys.exit(1)
        dt = input("Date du tirage (YYYY-MM-DD) : ").strip()
        numero_gagnant = {"boules": bg, "etoiles": eg}
        sauvegarder_tirage(conn_res, numero_gagnant, gains_possibles, dt)

    # Sélectionner la base source parmi les bases existantes
    bases = lister_bases_donnees()
    print("\nBases de données disponibles :")
    for i, b in enumerate(bases, start=1):
        print(f"{i}. {b}")
    ch_bdd = input("Sélectionnez la base source par son numéro : ").strip()
    if not ch_bdd.isdigit():
        print("[ERREUR] Vous devez entrer un nombre.")
        sys.exit(1)
    idx_bdd = int(ch_bdd) - 1
    if idx_bdd < 0 or idx_bdd >= len(bases):
        print("[ERREUR] Sélection invalide.")
        sys.exit(1)
    nom_bdd = bases[idx_bdd]

    # Lister les tables de la base source
    tables = scanner_base_donnees(nom_bdd)
    print("\nTables disponibles dans la base source :")
    for i, t in enumerate(tables, start=1):
        print(f"{i}. {t}")
    ch_table = input("Sélectionnez la table par son numéro : ").strip()
    if not ch_table.isdigit():
        print("[ERREUR] Vous devez entrer un nombre.")
        sys.exit(1)
    idx_table = int(ch_table) - 1
    if idx_table < 0 or idx_table >= len(tables):
        print("[ERREUR] Sélection invalide.")
        sys.exit(1)
    table = tables[idx_table]

    # Connexion à la base source et vérification de la colonne 'etoiles'
    conn_source = sqlite3.connect(nom_bdd)
    ajouter_etoiles_si_necessaire(conn_source, table)

    # Calculer les gains pour chaque tirage de la table source
    resultats = calculer_gains_combinaisons(conn_source, table, numero_gagnant, gains_possibles)
    print(f"[DEBUG] Nombre de lignes de gains calculées : {len(resultats)}")
    if not resultats:
        print("[ERREUR] Aucun résultat de gain calculé. Vérifiez les données de la table source.")
        conn_source.close()
        conn_res.close()
        sys.exit(1)

    # Insérer les résultats dans GainsCombinaisons
    inserer_gains_combinaisons(conn_res, resultats)

    # Calculer et afficher le bilan
    calculer_bilan(conn_res, dt)
    afficher_bilan(conn_res)

    print("[LOG] Fin du calcul des gains. Les résultats ont été enregistrés dans la base de résultats.")
    conn_source.close()
    conn_res.close()

if __name__ == "__main__":
    main()
