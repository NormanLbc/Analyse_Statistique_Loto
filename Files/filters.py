# filters.py
"""
Contient l'ensemble des fonctions de filtrage calculatoire (13 filtres) et heuristiques,
dont le nouveau "filtre_quartileshift_testBorne" qui remplace 'bornes'.
"""

import logging
import numpy as np
from statistics import median
from config import (
    SOMME_MIN, SOMME_MAX, DIZAINES_MAX, SUITE_MAX,
    MEDIAN_MIN, MEDIAN_MAX, VARIANCE_MIN, VARIANCE_MAX,
    ECART_MIN, ECART_MAX, ECART_CONSECUTIF,
    MPS_MIN, MPS_MAX,
    SOMME3F_MIN, SOMME3F_MAX,
    SOMME3C_MIN, SOMME3C_MAX,
    SOMME3L_MIN, SOMME3L_MAX,
    SIMILARITE_RECENTE_THRESHOLD,
    LOG_INTERVAL_HEUR,
    QSHIFT_TESTBORNE_BOUNDS,
    QSHIFT_TESTBORNE_SCORE_95
)

logger = logging.getLogger(__name__)

def filtre_somme(comb):
    s = sum(comb)
    return 1 if SOMME_MIN <= s <= SOMME_MAX else 0

def filtre_dizaines(comb):
    d = [x // 10 for x in comb]
    for dz in set(d):
        if d.count(dz) > DIZAINES_MAX:
            return 0
    return 1

def filtre_suite(comb):
    diffs = [comb[i+1] - comb[i] for i in range(len(comb)-1)]
    count = 1
    for i in range(1, len(diffs)):
        if diffs[i] == 1:
            count += 1
            if count > SUITE_MAX:
                return 0
        else:
            count = 1
    return 1

def filtre_mediane(comb):
    diffs = [comb[i+1] - comb[i] for i in range(len(comb)-1)]
    if not diffs:
        return 0
    med = np.median(diffs)
    return 1 if MEDIAN_MIN <= med <= MEDIAN_MAX else 0

def filtre_variance(comb):
    var = np.var(comb)
    return 1 if VARIANCE_MIN <= var <= VARIANCE_MAX else 0

def filtre_ecart(comb):
    diffs = [comb[i+1] - comb[i] for i in range(len(comb)-1)]
    if not diffs:
        return 0
    m = median(diffs)
    return 1 if ECART_MIN <= m <= ECART_MAX else 0

def filtre_ecart_consecutif(comb):
    diffs = [comb[i+1] - comb[i] for i in range(len(comb)-1)]
    length = 1
    for i in range(1, len(diffs)):
        if diffs[i] == diffs[i-1] and ECART_CONSECUTIF[0] <= diffs[i] <= ECART_CONSECUTIF[1]:
            length += 1
            if length > ECART_CONSECUTIF[2]:
                return 0
        else:
            length = 1
    return 1

# ----- NO bornes, on fait quartileshift_testBorne
def filtre_quartileshift_testBorne(comb):
    """
    Logique type testBorne:
      - On regarde la boule i => zone central (1.0), inter (0.4) ou else (0.0)
      - On somme => 'score'
      - On compare [score_min..score_max] (QSHIFT_TESTBORNE_SCORE_95)
      => 1 si OK, 0 sinon
    """
    score= 0.0
    for pos in range(1,6):
        val= comb[pos-1]
        bdict= QSHIFT_TESTBORNE_BOUNDS[pos]

        c_lo,c_hi= bdict['central'] if bdict['central'] else (None,None)
        i_lo,i_hi= bdict['intermediate'] if bdict['intermediate'] else (None,None)
        # on ignore 'peripheral' => c'est la zone non couverte ?

        weight= 0.0
        if c_lo is not None and c_hi is not None and (c_lo<= val<= c_hi):
            weight= 1.0
        elif i_lo is not None and i_hi is not None and (i_lo<= val<= i_hi):
            weight= 0.4
        else:
            weight= 0.0
        score+= weight

    (score_min, score_max)= QSHIFT_TESTBORNE_SCORE_95
    return 1 if (score_min<= score <= score_max) else 0

def filtre_mps(list_of_combos, list_of_hist, exclude_self=True):
    results = []
    nb_hist = len(list_of_hist)
    if nb_hist==0:
        return [1]*len(list_of_combos)
    for c_mask in list_of_combos:
        s=0
        c_h=0
        for h_mask in list_of_hist:
            if exclude_self and h_mask==c_mask:
                continue
            pop= bin(c_mask & h_mask).count("1")
            s+= pop/5.0
            c_h+=1
        if c_h==0:
            avg=1.0
        else:
            avg= s/c_h
        val= 1 if (MPS_MIN<= avg <= MPS_MAX) else 0
        results.append(val)
    return results

def filtre_somme3f(comb):
    return 1 if SOMME3F_MIN <= sum(comb[:3]) <= SOMME3F_MAX else 0

def filtre_somme3c(comb):
    return 1 if SOMME3C_MIN <= sum(comb[1:-1]) <= SOMME3C_MAX else 0

def filtre_somme3l(comb):
    return 1 if SOMME3L_MIN <= sum(comb[-3:]) <= SOMME3L_MAX else 0

def filtre_comparatif(comb_mask, last4_bitmasks, threshold=3):
    for h_mask in last4_bitmasks:
        intersect_bits= comb_mask & h_mask
        pop= bin(intersect_bits).count("1")
        if pop>= threshold:
            return 0
    return 1

# Heuristiques
def heuristic_4sur5(combos):
    combos_sorted= sorted(combos)
    coverage=[]
    temp= combos_sorted[0]
    total= len(combos_sorted)
    for i,c in enumerate(combos_sorted[1:], start=1):
        if len(set(temp).intersection(c))>=4:
            if c< temp:
                temp= c
        else:
            coverage.append(temp)
            temp= c
    coverage.append(temp)
    return coverage

def heuristic_3sur5(combos):
    combos_sorted= sorted(combos)
    coverage=[]
    temp= combos_sorted[0]
    for c in combos_sorted[1:]:
        if len(set(temp).intersection(c))>=3:
            if c<temp:
                temp= c
        else:
            coverage.append(temp)
            temp= c
    coverage.append(temp)
    return coverage

def heuristic_2sur5(combos):
    combos_sorted= sorted(combos)
    coverage=[]
    temp= combos_sorted[0]
    for c in combos_sorted[1:]:
        if len(set(temp).intersection(c))>=2:
            if c<temp:
                temp= c
        else:
            coverage.append(temp)
            temp= c
    coverage.append(temp)
    return coverage
