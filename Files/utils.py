# utils.py
"""
Fichier très long (700+ lignes), reprenant l'ancien code, 
mais on retire 'filtre_bornes' et on ajoute 'filtre_quartileshift_testBorne' 
à la place.

Structure:

1) BDD
2) Import historique
3) StatsHistorique
4) Génération combos
5) Filtrage interactif (MPS chunk)
6) StatsCombinaisons
7) extraction + heuristiques
8) ...
"""

import logging
import sqlite3
import pandas as pd
import itertools
import random
import numpy as np
from math import comb, ceil
from config import (
    LOG_FILE,
    LOG_INTERVAL,
    CHUNK_SIZE_MPS,
    EXCEL_FILE
)
from filters import (
    # les 13 filtres
    filtre_somme,
    filtre_dizaines,
    filtre_suite,
    filtre_mediane,
    filtre_variance,
    filtre_ecart,
    filtre_ecart_consecutif,
    filtre_quartileshift_testBorne,  # remplace bornes
    filtre_mps,
    filtre_somme3f,
    filtre_somme3c,
    filtre_somme3l,
    filtre_comparatif,
    # heuristiques
    heuristic_4sur5,
    heuristic_3sur5,
    heuristic_2sur5
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# BDD
# ---------------------------------------------------------------------

def create_connection(db_file):
    try:
        conn = sqlite3.connect(db_file)
        logger.info(f"Connexion à '{db_file}' établie.")
        return conn
    except sqlite3.Error as e:
        logger.error(f"Erreur connexion: {e}")
        return None

def create_tables(conn):
    cursor = conn.cursor()
    cursor.execute("""
       CREATE TABLE IF NOT EXISTS Historique(
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         date TEXT,
         boule1 INTEGER,
         boule2 INTEGER,
         boule3 INTEGER,
         boule4 INTEGER,
         boule5 INTEGER,
         bitmask INTEGER
       )
    """)
    cursor.execute("""
       CREATE TABLE IF NOT EXISTS StatsHistorique(
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         date TEXT,
         combinaison TEXT,
         filtre_somme INTEGER,
         filtre_dizaines INTEGER,
         filtre_suite INTEGER,
         filtre_mediane INTEGER,
         filtre_variance INTEGER,
         filtre_ecart INTEGER,
         filtre_ecart_consecutif INTEGER,
         filtre_quartileshift_testBorne INTEGER, 
         filtre_mps INTEGER,
         filtre_somme3f INTEGER,
         filtre_somme3c INTEGER,
         filtre_somme3l INTEGER,
         filtre_comparatif INTEGER,
         nb_filtres_passes INTEGER
       )
    """)
    cursor.execute("""
       CREATE TABLE IF NOT EXISTS Combinaisons_Filtrees(
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         boules TEXT,
         bitmask INTEGER,
         filtre_somme INTEGER DEFAULT 0,
         filtre_dizaines INTEGER DEFAULT 0,
         filtre_suite INTEGER DEFAULT 0,
         filtre_mediane INTEGER DEFAULT 0,
         filtre_variance INTEGER DEFAULT 0,
         filtre_ecart INTEGER DEFAULT 0,
         filtre_ecart_consecutif INTEGER DEFAULT 0,
         filtre_quartileshift_testBorne INTEGER DEFAULT 0,
         filtre_mps INTEGER DEFAULT 0,
         filtre_somme3f INTEGER DEFAULT 0,
         filtre_somme3c INTEGER DEFAULT 0,
         filtre_somme3l INTEGER DEFAULT 0,
         filtre_comparatif INTEGER DEFAULT 0,
         nb_filtres_passes INTEGER DEFAULT 0
       )
    """)
    cursor.execute("""
       CREATE TABLE IF NOT EXISTS StatsCombinaisons(
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         boules TEXT,
         filtre_somme INTEGER,
         filtre_dizaines INTEGER,
         filtre_suite INTEGER,
         filtre_mediane INTEGER,
         filtre_variance INTEGER,
         filtre_ecart INTEGER,
         filtre_ecart_consecutif INTEGER,
         filtre_quartileshift_testBorne INTEGER,
         filtre_mps INTEGER,
         filtre_somme3f INTEGER,
         filtre_somme3c INTEGER,
         filtre_somme3l INTEGER,
         filtre_comparatif INTEGER,
         nb_filtres_passes INTEGER
       )
    """)
    cursor.execute("""
       CREATE TABLE IF NOT EXISTS CombinaisonsExtraites(
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         boules TEXT
       )
    """)
    cursor.execute("CREATE TABLE IF NOT EXISTS Heuristique4sur5(id INTEGER PRIMARY KEY AUTOINCREMENT, boules TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS Heuristique3sur5(id INTEGER PRIMARY KEY AUTOINCREMENT, boules TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS Heuristique2sur5(id INTEGER PRIMARY KEY AUTOINCREMENT, boules TEXT)")

    conn.commit()
    logger.info("Tables créées ou déjà existantes.")

def ensure_historique_columns(conn):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(Historique)")
    existing = [row[1] for row in cursor.fetchall()]
    if "bitmask" not in existing:
        cursor.execute("ALTER TABLE Historique ADD COLUMN bitmask INTEGER")
        conn.commit()
        logger.info("Colonne bitmask ajoutée dans Historique.")

def ensure_combinaisons_filtrees_columns(conn):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(Combinaisons_Filtrees)")
    existing = [row[1] for row in cursor.fetchall()]
    needed = [
        "bitmask", 
        "filtre_somme",
        "filtre_dizaines",
        "filtre_suite",
        "filtre_mediane",
        "filtre_variance",
        "filtre_ecart",
        "filtre_ecart_consecutif",
        "filtre_quartileshift_testBorne",  # à la place de 'filtre_bornes'
        "filtre_mps",
        "filtre_somme3f",
        "filtre_somme3c",
        "filtre_somme3l",
        "filtre_comparatif",
        "nb_filtres_passes"
    ]
    for col in needed:
        if col not in existing:
            if col=="bitmask":
                cursor.execute(f"ALTER TABLE Combinaisons_Filtrees ADD COLUMN {col} INTEGER")
            else:
                cursor.execute(f"ALTER TABLE Combinaisons_Filtrees ADD COLUMN {col} INTEGER DEFAULT 0")
            conn.commit()
            logger.info(f"Colonne {col} ajoutée dans Combinaisons_Filtrees.")
    # Fix null => 0
    for col in needed:
        cursor.execute(f"UPDATE Combinaisons_Filtrees SET {col}=0 WHERE {col} IS NULL")
    conn.commit()

def fix_null_columns(conn):
    # Au cas où, rien de plus
    pass

# ---------------------------------------------------------------------
# Import historique
# ---------------------------------------------------------------------

def import_historique(conn, excel_file=EXCEL_FILE):
    """
    Lit le fichier Excel, convertit chaque tirage en bitmask, insère dans Historique.
    """
    ensure_historique_columns(conn)
    try:
        df = pd.read_excel(excel_file)
        df['date_de_tirage'] = df['date_de_tirage'].astype(str)
    except Exception as e:
        logger.error(f"Erreur lecture Excel: {e}")
        return

    data=[]
    for _,row in df.iterrows():
        try:
            dt = row["date_de_tirage"]
            b1 = int(row["boule_1"])
            b2 = int(row["boule_2"])
            b3 = int(row["boule_3"])
            b4 = int(row["boule_4"])
            b5 = int(row["boule_5"])
            mask=0
            for x in [b1,b2,b3,b4,b5]:
                mask |= (1<<(x-1))
            data.append((dt,b1,b2,b3,b4,b5,mask))
        except:
            logger.error("Erreur conversion row => skipping.")
            continue

    cursor = conn.cursor()
    cursor.execute("DELETE FROM Historique")
    cursor.executemany("""
      INSERT INTO Historique(date,boule1,boule2,boule3,boule4,boule5,bitmask)
      VALUES(?,?,?,?,?,?,?)
    """, data)
    conn.commit()
    logger.info(f"{len(data)} tirages importés dans Historique.")

# ---------------------------------------------------------------------
# StatsHistorique (13 filtres) => StatsHistorique
# ---------------------------------------------------------------------

def process_historique_stats(conn):
    """
    Calcule les 13 filtres sur chaque tirage de Historique, insère dans StatsHistorique.
     - somme, dizaines, suite, mediane, variance,
       ecart, ecart_consecutif, quartileshift_testBorne,
       mps, somme3f, somme3c, somme3l, comparatif
    """
    from filters import (
        filtre_somme,
        filtre_dizaines,
        filtre_suite,
        filtre_mediane,
        filtre_variance,
        filtre_ecart,
        filtre_ecart_consecutif,
        filtre_quartileshift_testBorne,  # le nouveau
        filtre_mps,
        filtre_somme3f,
        filtre_somme3c,
        filtre_somme3l,
        filtre_comparatif
    )

    cursor = conn.cursor()
    cursor.execute("SELECT id, date, boule1,boule2,boule3,boule4,boule5, bitmask FROM Historique ORDER BY date")
    rows = cursor.fetchall()
    if not rows:
        logger.info("Aucun tirage dans Historique.")
        return

    # liste bitmasks pour MPS
    hist_bitmasks = [r[7] for r in rows]

    data_insert = []
    for idx, r in enumerate(rows):
        hid, dt, b1,b2,b3,b4,b5, me_mask = r
        comb = [b1,b2,b3,b4,b5]

        # MPS => un mini-liste
        from filters import filtre_mps
        res_mps = filtre_mps([me_mask], hist_bitmasks, exclude_self=True)
        val_mps = res_mps[0]

        # calculer les autres
        fs   = filtre_somme(comb)
        fd   = filtre_dizaines(comb)
        fsu  = filtre_suite(comb)
        fme  = filtre_mediane(comb)
        fva  = filtre_variance(comb)
        fec  = filtre_ecart(comb)
        feco = filtre_ecart_consecutif(comb)
        ftb  = filtre_quartileshift_testBorne(comb)  # remplace bornes
        fs3f = filtre_somme3f(comb)
        fs3c = filtre_somme3c(comb)
        fs3l = filtre_somme3l(comb)

        # comparatif => usage bitwise
        c_mask = 0
        for x in comb:
            c_mask |= (1<<(x-1))
        # On prend 3 tirages précédents
        prev_10 = [rows[j][7] for j in range(max(0,idx-10), idx)]
        val_cmp = filtre_comparatif(c_mask, prev_10, threshold=3)

        nbp = fs + fd + fsu + fme + fva + fec + feco + ftb + val_mps + fs3f + fs3c + fs3l + val_cmp

        data_insert.append((
            dt,
            str(comb),
            fs,
            fd,
            fsu,
            fme,
            fva,
            fec,
            feco,
            ftb,
            val_mps,
            fs3f,
            fs3c,
            fs3l,
            val_cmp,
            nbp
        ))

    # on vide StatsHistorique puis insert
    cursor.execute("DELETE FROM StatsHistorique")
    cursor.executemany("""
      INSERT INTO StatsHistorique(
        date, combinaison,
        filtre_somme, filtre_dizaines, filtre_suite, filtre_mediane,
        filtre_variance, filtre_ecart, filtre_ecart_consecutif,
        filtre_quartileshift_testBorne,
        filtre_mps, filtre_somme3f, filtre_somme3c, filtre_somme3l,
        filtre_comparatif,
        nb_filtres_passes
      ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, data_insert)
    conn.commit()
    logger.info(f"{len(data_insert)} stats insérées dans StatsHistorique.")
    logger.info("Stats sur l'historique calculées.")

def write_histo_stats_summary(conn):
    """
    Lit StatsHistorique et écrit un résumé :
    - nb total
    - pourcentage passant par chaque filtre
    - min, max, moyenne
    - % >=13, >=12, >=11
    """
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM StatsHistorique")
    total = cursor.fetchone()[0]
    if not total:
        return "Aucune stats calculée sur l'historique."

    def count_filter(col):
        cursor.execute(f"SELECT COUNT(*) FROM StatsHistorique WHERE {col}=1")
        return cursor.fetchone()[0]

    c_somme= count_filter("filtre_somme")
    c_diz  = count_filter("filtre_dizaines")
    c_su   = count_filter("filtre_suite")
    c_me   = count_filter("filtre_mediane")
    c_va   = count_filter("filtre_variance")
    c_ec   = count_filter("filtre_ecart")
    c_eco  = count_filter("filtre_ecart_consecutif")
    c_tb   = count_filter("filtre_quartileshift_testBorne")
    c_mps  = count_filter("filtre_mps")
    c_s3f  = count_filter("filtre_somme3f")
    c_s3c  = count_filter("filtre_somme3c")
    c_s3l  = count_filter("filtre_somme3l")
    c_cmp  = count_filter("filtre_comparatif")

    cursor.execute("SELECT MIN(nb_filtres_passes), MAX(nb_filtres_passes), AVG(nb_filtres_passes) FROM StatsHistorique")
    mn,mx,avg_val = cursor.fetchone()

    def count_at_least(x):
        cursor.execute("SELECT COUNT(*) FROM StatsHistorique WHERE nb_filtres_passes>=?", (x,))
        return cursor.fetchone()[0]

    c13 = count_at_least(13)
    c12 = count_at_least(12)
    c11 = count_at_least(11)

    lines=[]
    lines.append(f"Tirages historiques : {total}")
    lines.append(f"Filtre Somme (60..199)           : {c_somme} ({(c_somme/total)*100:.2f}%)")
    lines.append(f"Filtre Dizaine (max 3 par dizaine): {c_diz} ({(c_diz/total)*100:.2f}%)")
    lines.append(f"Filtre Suite                     : {c_su} ({(c_su/total)*100:.2f}%)")
    lines.append(f"Filtre Median                    : {c_me} ({(c_me/total)*100:.2f}%)")
    lines.append(f"Filtre Variance                  : {c_va} ({(c_va/total)*100:.2f}%)")
    lines.append(f"Filtre Ecart                     : {c_ec} ({(c_ec/total)*100:.2f}%)")
    lines.append(f"Filtre Ecart Consecutif          : {c_eco} ({(c_eco/total)*100:.2f}%)")
    lines.append(f"Filtre QuartileShiftTestBorne    : {c_tb} ({(c_tb/total)*100:.2f}%)")
    lines.append(f"Filtre MPS                       : {c_mps} ({(c_mps/total)*100:.2f}%)")
    lines.append(f"Filtre Somme3F                   : {c_s3f} ({(c_s3f/total)*100:.2f}%)")
    lines.append(f"Filtre Somme3C                   : {c_s3c} ({(c_s3c/total)*100:.2f}%)")
    lines.append(f"Filtre Somme3L                   : {c_s3l} ({(c_s3l/total)*100:.2f}%)")
    lines.append(f"Filtre Comparatif                : {c_cmp} ({(c_cmp/total)*100:.2f}%)")
    lines.append("")
    lines.append(f"Nb filtres passés : min={mn}, max={mx}, moyenne={avg_val:.2f}")
    lines.append(f"Pourcentage de tirages avec au moins 13 filtres : {(c13/total)*100:.2f}%")
    lines.append(f"Pourcentage de tirages avec au moins 12 filtres : {(c12/total)*100:.2f}%")
    lines.append(f"Pourcentage de tirages avec au moins 11 filtres : {(c11/total)*100:.2f}%")

    summary= "\n".join(lines)

    with open("summary_log.txt", "w", encoding="utf-8") as f:
        f.write(summary)

    logger.info("Résumé des stats historiques enregistré dans summary_log.txt")
    return summary

# ---------------------------------------------------------------------
# Génération des combinaisons
# ---------------------------------------------------------------------

def generate_combinations_in_filtrees(conn):
    """
    Génère toutes les combinaisons (5 boules sur 49) dans Combinaisons_Filtrees,
    stocke bitmask
    """
    from math import comb
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Combinaisons_Filtrees")
    total = comb(49,5)
    print(f"Génération de {total} combinaisons (5 boules sur 49)...")

    def comb_to_bitmask(lst):
        m=0
        for x in lst:
            m |= (1<<(x-1))
        return m

    count=0
    combos=[]
    for c5 in itertools.combinations(range(1,50),5):
        mask= comb_to_bitmask(c5)
        combos.append((str(c5), mask, 0,0,0,0,0,0,0,0,0,0,0,0,0,0))
        count+=1
        if count%100000==0:
            cursor.executemany("""
              INSERT INTO Combinaisons_Filtrees(
                boules, bitmask,
                filtre_somme, filtre_dizaines, filtre_suite, filtre_mediane,
                filtre_variance, filtre_ecart, filtre_ecart_consecutif,
                filtre_quartileshift_testBorne,
                filtre_mps, filtre_somme3f, filtre_somme3c,
                filtre_somme3l, filtre_comparatif, nb_filtres_passes
              ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, combos)
            conn.commit()
            combos=[]
            print(f"{count} combos insérées.")
    if combos:
        cursor.executemany("""
          INSERT INTO Combinaisons_Filtrees(
            boules, bitmask,
            filtre_somme, filtre_dizaines, filtre_suite, filtre_mediane,
            filtre_variance, filtre_ecart, filtre_ecart_consecutif,
            filtre_quartileshift_testBorne,
            filtre_mps, filtre_somme3f, filtre_somme3c,
            filtre_somme3l, filtre_comparatif, nb_filtres_passes
          ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, combos)
        conn.commit()
    print(f"{count} combinaisons insérées dans Combinaisons_Filtrees.")

# ---------------------------------------------------------------------
# Application interactive des filtres => mps chunk python, comparatif
# ---------------------------------------------------------------------

def apply_filter(conn, filter_name, filter_func, historique):
    """
    Applique le filtre 'filter_name'.
    - si 'mps', chunk python => recalc nb_filtres_passes
    - si 'comparatif', on compare bitwise...
    - si 'quartileshift_testBorne', on applique la pondération 1.0/0.4/0.0
      + coverage 95 => 1 ou 0
    - sinon => "filtres rapides"
    """
    cursor= conn.cursor()
    col = f"filtre_{filter_name}"

    if filter_name=="mps":
        compute_mps_in_python(conn, historique)
        # résumé
        cursor.execute("SELECT COUNT(*) FROM Combinaisons_Filtrees")
        tot= cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM Combinaisons_Filtrees WHERE filtre_mps=1")
        acc= cursor.fetchone()[0]
        ratio= (acc/tot)*100 if tot else 0
        print(f"Filtre 'mps' appliqué => {acc} ({ratio:.2f}%)")
        return

    elif filter_name=="comparatif":
        from filters import filtre_comparatif
        last10_bitmasks= historique[-10:] if len(historique)>=10 else []
        cursor.execute(f"SELECT id, bitmask, {col}, nb_filtres_passes FROM Combinaisons_Filtrees")
        rows= cursor.fetchall()
        tot= len(rows)
        accepted=0
        updates=[]
        for (cid, c_mask, old_val, old_nb) in rows:
            old_val= old_val or 0
            old_nb = old_nb or 0
            val= filtre_comparatif(c_mask, last10_bitmasks, threshold=3)
            new_nb= old_nb - old_val + val
            updates.append((val,new_nb,cid))
            if val==1:
                accepted+=1
        cursor.executemany(f"""
          UPDATE Combinaisons_Filtrees
          SET {col}=?, nb_filtres_passes=?
          WHERE id=?
        """, updates)
        conn.commit()
        ratio= (accepted/tot)*100 if tot else 0
        print(f"Filtre 'comparatif' => {accepted} ({ratio:.2f}%) sur {tot}")
        return

    elif filter_name=="quartileshift_testborne":
        from filters import filtre_quartileshift_testBorne
        cursor.execute(f"SELECT id,boules,{col},nb_filtres_passes FROM Combinaisons_Filtrees")
        rows= cursor.fetchall()
        tot= len(rows)
        accepted=0
        updates=[]
        for (cid,bstr,old_val,old_nb) in rows:
            old_val= old_val or 0
            old_nb= old_nb or 0
            comb= eval(bstr)
            val= filtre_quartileshift_testBorne(comb)
            new_nb= old_nb - old_val + val
            updates.append((val,new_nb,cid))
            if val==1:
                accepted+=1
        cursor.executemany(f"""
          UPDATE Combinaisons_Filtrees
          SET {col}=?, nb_filtres_passes=?
          WHERE id=?
        """, updates)
        conn.commit()
        ratio= (accepted/tot)*100 if tot else 0
        print(f"Filtre 'quartileshift_testborne' => {accepted} ({ratio:.2f}%) sur {tot}")
        return

    else:
        # filtres "rapides"
        cursor.execute(f"SELECT id,boules,{col},nb_filtres_passes FROM Combinaisons_Filtrees")
        rows= cursor.fetchall()
        tot= len(rows)
        accepted=0
        updates=[]
        for (cid,bstr,old_val,old_nb) in rows:
            old_val= old_val or 0
            old_nb= old_nb or 0
            comb= eval(bstr)
            val= filter_func(comb)
            new_nb= old_nb - old_val + val
            updates.append((val,new_nb,cid))
            if val==1:
                accepted+=1
        cursor.executemany(f"""
          UPDATE Combinaisons_Filtrees
          SET {col}=?, nb_filtres_passes=?
          WHERE id=?
        """, updates)
        conn.commit()
        ratio= (accepted/tot)*100 if tot else 0
        print(f"Filtre '{filter_name}' => {accepted} ({ratio:.2f}%) sur {tot}")

def compute_mps_in_python(conn, historique, chunk_size=None):
    """
    Lit Combinaisons_Filtrees en chunk, calcule MPS en python, 
    update filtre_mps => 0/1, recalc nb_filtres_passes
    """
    from filters import filtre_mps
    if chunk_size is None:
        from config import CHUNK_SIZE_MPS
        chunk_size= CHUNK_SIZE_MPS

    cursor= conn.cursor()
    hist_bitmasks= [bm for bm in historique]
    cursor.execute("SELECT COUNT(*) FROM Combinaisons_Filtrees")
    total= cursor.fetchone()[0]
    if total==0:
        print("Aucune combinaison.")
        return

    print(f"Calcul MPS (chunk python) sur {total} combos, hist={len(hist_bitmasks)}.")
    offset=0
    processed=0
    accepted_global=0
    chunk_idx=0

    while True:
        cursor.execute("""
          SELECT id, bitmask, filtre_mps, nb_filtres_passes
          FROM Combinaisons_Filtrees
          ORDER BY id
          LIMIT ? OFFSET ?
        """,(chunk_size, offset))
        rows= cursor.fetchall()
        if not rows:
            break
        offset+= len(rows)
        chunk_idx+=1
        combos_chunk= [r[1] for r in rows]
        ids_chunk= [r[0] for r in rows]

        results= filtre_mps(combos_chunk, hist_bitmasks, exclude_self=False)
        ups=[]
        for i,res_mps in enumerate(results):
            cid= ids_chunk[i]
            ups.append((res_mps, cid))
            if res_mps==1:
                accepted_global+=1

        cursor.executemany("""
          UPDATE Combinaisons_Filtrees
          SET filtre_mps=?
          WHERE id=?
        """, ups)
        conn.commit()

        processed+= len(rows)
        print(f"Chunk {chunk_idx}: {len(rows)} combos => MPS calculé, total={processed}/{total}")
        if len(rows)<chunk_size:
            break

    # recalc nb_filtres_passes
    cursor.execute("""
      UPDATE Combinaisons_Filtrees
      SET nb_filtres_passes = (
         filtre_somme + filtre_dizaines + filtre_suite + filtre_mediane +
         filtre_variance + filtre_ecart + filtre_ecart_consecutif +
         filtre_quartileshift_testborne + filtre_mps +
         filtre_somme3f + filtre_somme3c + filtre_somme3l + filtre_comparatif
      )
    """)
    conn.commit()

    ratio_final= (accepted_global/ processed)*100 if processed else 0
    print(f"Filtre MPS terminé => {accepted_global} ({ratio_final:.2f}%).")

def apply_all_filters_interactive(conn, historique):
    """
    Propose 13 filtres: somme, dizaines, suite, mediane, variance,
    ecart, ecart_consecutif, quartileshift_testborne, mps,
    somme3f, somme3c, somme3l, comparatif
    """
    from filters import (
        filtre_somme, filtre_dizaines, filtre_suite, filtre_mediane,
        filtre_variance, filtre_ecart, filtre_ecart_consecutif,
        filtre_quartileshift_testBorne,
        filtre_mps, filtre_somme3f, filtre_somme3c, filtre_somme3l, filtre_comparatif
    )
    filters_list= {
        "somme": filtre_somme,
        "dizaines": filtre_dizaines,
        "suite": filtre_suite,
        "mediane": filtre_mediane,
        "variance": filtre_variance,
        "ecart": filtre_ecart,
        "ecart_consecutif": filtre_ecart_consecutif,
        "quartileshift_testborne": None,
        "mps": None,
        "somme3f": filtre_somme3f,
        "somme3c": filtre_somme3c,
        "somme3l": filtre_somme3l,
        "comparatif": filtre_comparatif
    }
    order= [
      "somme","dizaines","suite","mediane","variance",
      "ecart","ecart_consecutif","quartileshift_testborne","mps",
      "somme3f","somme3c","somme3l","comparatif"
    ]
    for key in order:
        rep= input(f"Appliquer le filtre '{key}' ? (y/n) : ").lower().strip()
        if rep=="y":
            apply_filter(conn, key, filters_list[key], historique)
        else:
            print(f"Filtre '{key}' ignoré.")

# ---------------------------------------------------------------------
# StatsCombinaisons, extraction, heuristiques
# ---------------------------------------------------------------------

def process_combinaisons_stats(conn):
    """
    Copie Combinaisons_Filtrees => StatsCombinaisons
    """
    cursor=conn.cursor()
    cursor.execute("DELETE FROM StatsCombinaisons")
    cursor.execute("""
      SELECT
        boules,
        filtre_somme, filtre_dizaines, filtre_suite, filtre_mediane,
        filtre_variance, filtre_ecart, filtre_ecart_consecutif,
        filtre_quartileshift_testborne,
        filtre_mps, filtre_somme3f, filtre_somme3c, filtre_somme3l,
        filtre_comparatif, nb_filtres_passes
      FROM Combinaisons_Filtrees
    """)
    rows= cursor.fetchall()
    data= [r for r in rows]
    cursor.executemany("""
      INSERT INTO StatsCombinaisons(
        boules,
        filtre_somme, filtre_dizaines, filtre_suite, filtre_mediane,
        filtre_variance, filtre_ecart, filtre_ecart_consecutif,
        filtre_quartileshift_testborne,
        filtre_mps, filtre_somme3f, filtre_somme3c, filtre_somme3l,
        filtre_comparatif, nb_filtres_passes
      ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, data)
    conn.commit()
    logger.info(f"{len(data)} stats dans StatsCombinaisons.")

def write_combos_stats_summary(conn):
    """
    Lit StatsCombinaisons (ou fallback sur Combinaisons_Filtrees) => résumé
    """
    cursor=conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM StatsCombinaisons")
    total= cursor.fetchone()[0]
    table_used= "StatsCombinaisons"
    if total==0:
        cursor.execute("SELECT COUNT(*) FROM Combinaisons_Filtrees")
        total= cursor.fetchone()[0]
        if total==0:
            return "Aucune combinaison filtrée."
        table_used= "Combinaisons_Filtrees"

    filter_cols= [
        ("filtre_somme","Filtre Somme (60..199)"),
        ("filtre_dizaines","Filtre Dizaine (max 3)"),
        ("filtre_suite","Filtre Suite (max 3 cons)"),
        ("filtre_mediane","Filtre Median"),
        ("filtre_variance","Filtre Variance"),
        ("filtre_ecart","Filtre Ecart"),
        ("filtre_ecart_consecutif","Filtre EcartConsecutif"),
        ("filtre_quartileshift_testborne","Filtre QuartileShiftTestBorne"),
        ("filtre_mps","Filtre MPS"),
        ("filtre_somme3f","Filtre Somme3F"),
        ("filtre_somme3c","Filtre Somme3C"),
        ("filtre_somme3l","Filtre Somme3L"),
        ("filtre_comparatif","Filtre Comparatif")
    ]
    lines=[]
    lines.append(f"Nombre total de combinaisons filtrées : {total}")
    for col,label in filter_cols:
        cursor.execute(f"SELECT COUNT(*) FROM {table_used} WHERE {col}=1")
        acc= cursor.fetchone()[0]
        rej= total- acc
        perc= (acc/ total)*100 if total else 0
        lines.append(f"{label:40s} : {acc} ({perc:.2f}%) acceptées, {rej} rejetées")

    # stats nb_filtres_passes
    cursor.execute(f"SELECT MIN(nb_filtres_passes), MAX(nb_filtres_passes), AVG(nb_filtres_passes) FROM {table_used}")
    mn,mx,avg_val= cursor.fetchone()
    lines.append("")
    lines.append(f"Nb filtres passés : min={mn}, max={mx}, moyenne={avg_val:.2f}")

    def count_at_least(x):
        cursor.execute(f"SELECT COUNT(*) FROM {table_used} WHERE nb_filtres_passes>=?", (x,))
        return cursor.fetchone()[0]

    c13= count_at_least(13)
    c12= count_at_least(12)
    c11= count_at_least(11)
    lines.append(f"Pourcentage combos avec >=13 filtres : {(c13/total)*100:.2f}%")
    lines.append(f"Pourcentage combos avec >=12 filtres : {(c12/total)*100:.2f}%")
    lines.append(f"Pourcentage combos avec >=11 filtres : {(c11/total)*100:.2f}%")

    summary="\n".join(lines)
    with open("summary_log.txt","w",encoding="utf-8") as f:
        f.write(summary)
    logger.info("Résumé combos écrit dans summary_log.txt")
    return summary

def extraction_seuil(conn):
    """
    Demande un seuil (13,12,11 ou 'aucun'), 
    copie dans CombinaisonsExtraites
    """
    rep= input("Extraire les combos avec au moins combien de filtres validés ? (13,12,11 ou 'aucun') : ").strip()
    if rep.lower()=="aucun":
        return True
    try:
        thr= int(rep)
    except:
        print("Extraction annulée.")
        return None
    cursor= conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM Combinaisons_Filtrees")
    tot= cursor.fetchone()[0]
    cursor.execute("DELETE FROM CombinaisonsExtraites")
    cursor.execute("""
      INSERT INTO CombinaisonsExtraites(boules)
      SELECT boules FROM Combinaisons_Filtrees
      WHERE nb_filtres_passes >= ?
    """,(thr,))
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM CombinaisonsExtraites")
    cpt= cursor.fetchone()[0]
    ratio= (cpt/tot)*100 if tot else 0
    print(f"Extraction => {cpt} combos ({ratio:.2f}%) vers CombinaisonsExtraites.")
    return "CombinaisonsExtraites"

def apply_heuristique_4sur5(conn, table_name="CombinaisonsExtraites"):
    """
    Applique la fonction heuristic_4sur5 => coverage
    """
    cursor= conn.cursor()
    cursor.execute(f"SELECT boules FROM {table_name}")
    rows= cursor.fetchall()
    combos= [eval(r[0]) for r in rows]
    print(f"Itération 1, combos restant={len(combos)}")
    coverage= heuristic_4sur5(combos)
    ratio= (len(coverage)/ len(combos))*100 if combos else 0
    cursor.execute("DELETE FROM Heuristique4sur5")
    data= [(str(c),) for c in coverage]
    cursor.executemany("INSERT INTO Heuristique4sur5(boules) VALUES(?)", data)
    conn.commit()
    print(f"Heuristique4sur5 => {len(coverage)} combos ({ratio:.2f}%).")

def apply_heuristique_3sur5(conn, table_name="Heuristique4sur5"):
    cursor= conn.cursor()
    cursor.execute(f"SELECT boules FROM {table_name}")
    rows= cursor.fetchall()
    combos= [eval(r[0]) for r in rows]
    coverage= heuristic_3sur5(combos)
    ratio= (len(coverage)/ len(combos))*100 if combos else 0
    cursor.execute("DELETE FROM Heuristique3sur5")
    data= [(str(c),) for c in coverage]
    cursor.executemany("INSERT INTO Heuristique3sur5(boules) VALUES(?)", data)
    conn.commit()
    print(f"Heuristique3sur5 => {len(coverage)} combos ({ratio:.2f}%).")

def apply_heuristique_2sur5(conn, table_name="Heuristique3sur5"):
    cursor= conn.cursor()
    cursor.execute(f"SELECT boules FROM {table_name}")
    rows= cursor.fetchall()
    combos= [eval(r[0]) for r in rows]
    coverage= heuristic_2sur5(combos)
    ratio= (len(coverage)/ len(combos))*100 if combos else 0
    cursor.execute("DELETE FROM Heuristique2sur5")
    data= [(str(c),) for c in coverage]
    cursor.executemany("INSERT INTO Heuristique2sur5(boules) VALUES(?)", data)
    conn.commit()
    print(f"Heuristique2sur5 => {len(coverage)} combos ({ratio:.2f}%).")

def final_tables_summary(conn):
    cursor= conn.cursor()
    def count_table(tab):
        cursor.execute(f"SELECT COUNT(*) FROM {tab}")
        return cursor.fetchone()[0]
    c1= count_table("Combinaisons_Filtrees")
    c2= count_table("CombinaisonsExtraites")
    c3= count_table("Heuristique4sur5")
    c4= count_table("Heuristique3sur5")
    c5= count_table("Heuristique2sur5")
    print("\n[Résumé final des tableaux]")
    print(f"1. Combinaisons_Filtrees : {c1}")
    print(f"2. CombinaisonsExtraites : {c2}")
    print(f"3. Heuristique4sur5     : {c3}")
    print(f"4. Heuristique3sur5     : {c4}")
    print(f"5. Heuristique2sur5     : {c5}\n")

def random_draw_from_table(conn):
    """
    Tirage aléatoire de combos
    """
    tabs= [
      "Combinaisons_Filtrees",
      "CombinaisonsExtraites",
      "Heuristique4sur5",
      "Heuristique3sur5",
      "Heuristique2sur5"
    ]
    rep= input("Tirer au sort un certain nb combos d'un tableau ? (y/n) : ").lower().strip()
    if rep!="y":
        return
    idx= input("Quel tableau ? (1..5) : ").strip()
    try:
        val= int(idx)
        tab= tabs[val-1]
    except:
        print("Index invalide.")
        return
    nb= input("Combien de combos ? ").strip()
    try:
        nb_val= int(nb)
    except:
        print("Invalide.")
        return
    cursor= conn.cursor()
    cursor.execute(f"SELECT boules FROM {tab}")
    rows= cursor.fetchall()
    combos= [r[0] for r in rows]
    if not combos:
        print(f"Aucune combinaison dans {tab}.")
        return
    if nb_val> len(combos):
        nb_val= len(combos)
    random.shuffle(combos)
    draw= combos[:nb_val]
    print(f"\nTirage aléatoire ({nb_val} combos) dans '{tab}' :")
    for i,cmb in enumerate(draw, start=1):
        print(f"{i}. {cmb}")
