#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
testBorne95.py

6 méthodes: Gaussienne, Quartile, KDE, QuartileShift, Manuel, SymGauss
Avec export Excel plus synthétisé (une seule paire de bornes par zone).
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde

WEIGHT_CENTRAL      = 1.0
WEIGHT_INTERMEDIATE = 0.4
WEIGHT_PERIPHERAL   = 0.0
GRID_POINTS         = 1500
MIN_BOULE           = 1
MAX_BOULE           = 50

MANUAL_INTERVALS = {
    1: {'central': (0,10),   'intermediate': (0,20),   'peripheral': (20,50)},
    2: {'central': (10,20),  'intermediate': (3,30),    'peripheral': (30,50)},
    3: {'central': (18,31),  'intermediate': (9,41),    'peripheral': (41,50)},
    4: {'central': (27,40),  'intermediate': (15,47),   'peripheral': (47,50)},
    5: {'central': (40,50),  'intermediate': (25,50),   'peripheral': (50,50)}
}

# -------------------------------------------------------------------------
# 1) Gaussienne
# -------------------------------------------------------------------------
def compute_gaussian_intervals(data):
    mu = np.mean(data)
    sigma = np.std(data)
    central = (mu - sigma/2, mu + sigma/2)
    intermediate = ((mu - sigma, mu - sigma/2),
                    (mu + sigma/2, mu + sigma))
    peripheral = ((mu - 2*sigma, mu - sigma),
                  (mu + sigma, mu + 2*sigma))
    return mu, sigma, central, intermediate, peripheral

def ball_weight_gaussian(value, mu, sigma):
    if mu - sigma/2 <= value <= mu + sigma/2:
        return WEIGHT_CENTRAL
    elif (mu - sigma <= value < mu - sigma/2) or (mu + sigma/2 < value <= mu + sigma):
        return WEIGHT_INTERMEDIATE
    elif (mu - 2*sigma <= value < mu - sigma) or (mu + sigma < value <= mu + 2*sigma):
        return WEIGHT_PERIPHERAL
    return 0.0

# -------------------------------------------------------------------------
# 2) Quartile
# -------------------------------------------------------------------------
def compute_quartile_intervals(data):
    p2_5= np.percentile(data, 2.5)
    p97_5= np.percentile(data, 97.5)
    Q1,Q3= np.percentile(data, [25,75])
    return p2_5,p97_5,Q1,Q3

def ball_weight_quartile(value, p2_5, p97_5, Q1, Q3):
    if Q1 <= value <= Q3:
        return 1.0
    elif (p2_5 <= value < Q1) or (Q3 < value <= p97_5):
        return 0.5
    return 0.2

# -------------------------------------------------------------------------
# 3) KDE
# -------------------------------------------------------------------------
def compute_kde_intervals(data, prob=0.95):
    lower= np.percentile(data, (100 - prob*100)/2)
    upper= np.percentile(data, 100 - (100 - prob*100)/2)
    q25, q75= np.percentile(data, [25, 75])
    return lower, upper, q25, q75

def ball_weight_kde(value, lower, upper, q25, q75):
    if q25 <= value <= q75:
        return 1.0
    elif (lower <= value < q25) or (q75 < value <= upper):
        return 0.5
    return 0.2

# -------------------------------------------------------------------------
# 4) QuartileShift
# -------------------------------------------------------------------------
def compute_quartile_shift_intervals(data):
    p2_5= np.percentile(data, 2.5)
    p97_5= np.percentile(data, 97.5)
    Q1,Q3= np.percentile(data, [25,75])
    mean_val= np.mean(data)
    median_val= np.median(data)
    delta= median_val - mean_val

    def clamp01(x):
        return min(max(x, MIN_BOULE), MAX_BOULE)

    p2_5s= clamp01(p2_5+ delta)
    p97_5s=clamp01(p97_5+ delta)
    Q1s   =clamp01(Q1+ delta)
    Q3s   =clamp01(Q3+ delta)
    return p2_5s, p97_5s, Q1s, Q3s

def ball_weight_quartile_shift(value, p2_5s, p97_5s, Q1s, Q3s):
    if Q1s <= value <= Q3s:
        return 1.0
    elif (p2_5s <= value < Q1s) or (Q3s < value <= p97_5s):
        return 0.5
    return 0.2

# -------------------------------------------------------------------------
# 5) Manuel
# -------------------------------------------------------------------------
def compute_manual_intervals_for_boule(b):
    c_lo,c_hi= MANUAL_INTERVALS[b]['central']
    i_lo,i_hi= MANUAL_INTERVALS[b]['intermediate']
    p_lo,p_hi= MANUAL_INTERVALS[b]['peripheral']
    i_tuple= ((i_lo,i_hi),(i_lo,i_hi))
    p_tuple= ((p_lo,p_hi),(p_lo,p_hi))
    return (0,0,(c_lo,c_hi), i_tuple, p_tuple)

def compute_manual_intervals():
    d= {}
    for pos in range(1,6):
        d[pos]= compute_manual_intervals_for_boule(pos)
    return d

def ball_weight_manual(value, intervals):
    _,_, c,i,p= intervals
    c_lo,c_hi= c
    (i1_lo,i1_hi),(i2_lo,i2_hi)= i
    (p1_lo,p1_hi),(p2_lo,p2_hi)= p

    if c_lo<= value<= c_hi:
        return 1.0
    in_i1= (i1_lo<=value<= i1_hi)
    in_i2= (i2_lo<=value<= i2_hi)
    if in_i1 or in_i2:
        return 0.5
    in_p1= (p1_lo<=value<= p1_hi)
    in_p2= (p2_lo<=value<= p2_hi)
    if in_p1 or in_p2:
        return 0.2
    return 0.0

# -------------------------------------------------------------------------
# 6) SymGauss
# -------------------------------------------------------------------------
def reflect_data(data, boundary):
    return [2*boundary - x for x in data]

def clamp(x, a,b):
    return max(a, min(x,b))

def reflect_interval(mir_low, mir_high, boundary):
    low= 2*boundary- mir_high
    high=2*boundary- mir_low
    if low>high:
        low,high= high,low
    low= clamp(low, MIN_BOULE,MAX_BOULE)
    high=clamp(high,MIN_BOULE,MAX_BOULE)
    return (low,high)

def compute_symmetric_gaussian_intervals(data, boundary=None):
    if boundary is None:
        return compute_gaussian_intervals(data)
    mirrored= reflect_data(data, boundary)
    data_ext= np.concatenate([data, mirrored])
    mu_e= np.mean(data_ext)
    sigma_e= np.std(data_ext)

    central_mir= (mu_e- sigma_e/2, mu_e+ sigma_e/2)
    inter_mir=  ((mu_e- sigma_e, mu_e- sigma_e/2),
                 (mu_e+ sigma_e/2, mu_e+ sigma_e))
    periph_mir= ((mu_e- 2*sigma_e, mu_e- sigma_e),
                 (mu_e+ sigma_e,  mu_e+ 2*sigma_e))

    c_lo,c_hi= reflect_interval(*central_mir, boundary)
    i1_lo,i1_hi= reflect_interval(*inter_mir[0], boundary)
    i2_lo,i2_hi= reflect_interval(*inter_mir[1], boundary)
    p1_lo,p1_hi= reflect_interval(*periph_mir[0], boundary)
    p2_lo,p2_hi= reflect_interval(*periph_mir[1], boundary)

    mu_final= np.mean(data)
    sigma_final= np.std(data)
    central= (c_lo,c_hi)
    intermediate= ((i1_lo,i1_hi),(i2_lo,i2_hi))
    peripheral=  ((p1_lo,p1_hi),(p2_lo,p2_hi))
    return mu_final, sigma_final, central, intermediate, peripheral

def ball_weight_symmetric_gaussian(value, intervals):
    _,_, c,i,p= intervals
    c_lo,c_hi= c
    (i1_lo,i1_hi),(i2_lo,i2_hi)= i
    (p1_lo,p1_hi),(p2_lo,p2_hi)= p

    if c_lo<=value<= c_hi:
        return 1.0
    in_i1= (i1_lo<=value<= i1_hi)
    in_i2= (i2_lo<=value<= i2_hi)
    if in_i1 or in_i2:
        return 0.5
    in_p1= (p1_lo<=value<= p1_hi)
    in_p2= (p2_lo<=value<= p2_hi)
    if in_p1 or in_p2:
        return 0.2
    return 0.0

# -------------------------------------------------------------------------
# Calcul du score
# -------------------------------------------------------------------------
def compute_total_weight_for_draw(draw, intervals_dict, method):
    total= 0.0
    for pos,value in enumerate(draw, start=1):
        if method=="gaussian":
            mu,sigma,_,_,_= intervals_dict[pos]
            total+= ball_weight_gaussian(value, mu,sigma)
        elif method=="quartile":
            p2_5,p97_5,Q1,Q3= intervals_dict[pos]
            total+= ball_weight_quartile(value, p2_5,p97_5,Q1,Q3)
        elif method=="kde":
            l,u,q25,q75= intervals_dict[pos]
            total+= ball_weight_kde(value, l,u,q25,q75)
        elif method=="quartileshift":
            p2_5s,p97_5s,Q1s,Q3s= intervals_dict[pos]
            total+= ball_weight_quartile_shift(value, p2_5s,p97_5s,Q1s,Q3s)
        elif method=="manual":
            total+= ball_weight_manual(value, intervals_dict[pos])
        elif method=="sym_gauss":
            total+= ball_weight_symmetric_gaussian(value, intervals_dict[pos])
        else:
            pass
    return total

# -------------------------------------------------------------------------
# Coverage
# -------------------------------------------------------------------------
def coverage_interval(arr, p=0.95):
    arr_s= np.sort(arr)
    n= len(arr_s)
    if n==0: return (0.0,0.0)
    window_size= int(np.floor(p*n))
    min_width= None
    best_start= None
    for i in range(n- window_size+1):
        start= arr_s[i]
        end= arr_s[i+window_size-1]
        width= end- start
        if (min_width is None) or (width< min_width):
            min_width= width
            best_start= start
    return best_start, best_start+ min_width

# ============================
# get_plot_intervals => histogram color
# ============================
def get_plot_intervals(method, intervals, pos, values):
    min_val, max_val= min(values), max(values)

    if method in ["gaussian","sym_gauss"]:
        _,_, c,i,p= intervals
        c_lo,c_hi= c
        i_lo= min(i[0][0], i[1][0])
        i_hi= max(i[0][1], i[1][1])
    elif method=="quartile":
        p2_5,p97_5,Q1,Q3= intervals
        c_lo,c_hi= Q1,Q3
        i_lo,i_hi= p2_5,p97_5
    elif method=="kde":
        l,u,q25,q75= intervals
        c_lo,c_hi= q25,q75
        i_lo,i_hi= l,u
    elif method=="quartileshift":
        p2_5s,p97_5s,Q1s,Q3s= intervals
        c_lo,c_hi= Q1s,Q3s
        i_lo,i_hi= p2_5s,p97_5s
    elif method=="manual":
        _,_, c,i,_= intervals
        c_lo,c_hi= c
        i_lo= min(i[0][0], i[1][0])
        i_hi= max(i[0][1], i[1][1])
    else:
        c_lo,c_hi= 0,0
        i_lo,i_hi= 0,0

    c_lo= max(c_lo, min_val)
    c_hi= min(c_hi, max_val)
    i_lo= max(i_lo, min_val)
    i_hi= min(i_hi, max_val)
    return c_lo,c_hi, i_lo,i_hi, min_val, max_val

def plot_method_results(method_name, intervals_per_ball, all_draws, total_scores, method):
    fig, axs= plt.subplots(2,3, figsize=(15,10))
    axs= axs.flatten()

    for pos in range(1,6):
        ax= axs[pos-1]
        values= [d[pos-1] for d in all_draws]
        edges= np.arange(0.5, MAX_BOULE+1.5,1)
        ax.hist(values, bins=edges, edgecolor='black', alpha=0.7, color='lightgray', zorder=1)
        ax.set_xlim(0.5, 50.5)

        c_low,c_high, i_low,i_high, val_min,val_max= get_plot_intervals(method, intervals_per_ball[pos], pos, values)

        ax.axvspan(val_min, val_max, facecolor='red', alpha=0.3, zorder=2)
        if i_low< i_high:
            ax.axvspan(i_low, i_high, facecolor='yellow', alpha=0.3, zorder=3)
        if c_low< c_high:
            ax.axvspan(c_low, c_high, facecolor='green', alpha=0.3, zorder=4)

        mval= np.mean(values)
        med=  np.median(values)
        ax.axvline(mval, color='blue', linewidth=2, zorder=5)
        ax.axvline(med,  color='orange', linewidth=2, zorder=5)

        ax.set_title(f"Boule {pos}")

    ax= axs[5]
    ax.hist(total_scores, bins=30, edgecolor='black', alpha=0.7, color='violet', zorder=1)
    ax.set_title("Distribution des scores")

    plt.suptitle(f"Méthode {method_name}", fontsize=16)
    plt.tight_layout()
    plt.show()

# ============================
# gather_method_stats => export synthétique
# ============================
def unify_intervals(lst):
    """
    Reçoit une liste de tuples (start, end).
    Retourne (minOfAll, maxOfAll) en ignorant ceux qui sont vides.
    """
    valid= [iv for iv in lst if iv[0]< iv[1]]
    if not valid:
        return None,None
    minv= min(iv[0] for iv in valid)
    maxv= max(iv[1] for iv in valid)
    return minv, maxv

def get_boule_simplified_zones(intervals, method):
    """
    Renvoie un dict:
      'central': (start, end)
      'intermediate': (start, end)
      'peripheral': (start, end)
    en fusionnant s'il y a 2 sousinterv.
    """
    if method in ["gaussian","sym_gauss"]:
        # intervals= (mu, sigma, c, i, p)
        _,_, c,i,p= intervals
        cstart,cend= c
        (i1start,i1end),(i2start,i2end)= i
        (p1start,p1end),(p2start,p2end)= p
        c_lo, c_hi= unify_intervals([ c ])
        i_lo, i_hi= unify_intervals([ (i1start,i1end), (i2start,i2end) ])
        p_lo, p_hi= unify_intervals([ (p1start,p1end), (p2start,p2end) ])
        return {
          'central':       (c_lo,c_hi),
          'intermediate':  (i_lo,i_hi),
          'peripheral':    (p_lo,p_hi)
        }
    elif method=="quartile":
        p2_5,p97_5, Q1,Q3= intervals
        # central => (Q1,Q3)
        # interm => (p2_5,Q1) et (Q3,p97_5) => on fusionne
        c_lo,c_hi= unify_intervals([(Q1,Q3)])
        i_lo,i_hi= unify_intervals([(p2_5,Q1),(Q3,p97_5)])
        return {
          'central': (c_lo,c_hi),
          'intermediate': (i_lo,i_hi),
          'peripheral': (None,None)
        }
    elif method=="kde":
        l,u, q25,q75= intervals
        c_lo,c_hi= unify_intervals([(q25,q75)])
        i_lo,i_hi= unify_intervals([(l,q25),(q75,u)])
        return {
          'central': (c_lo,c_hi),
          'intermediate': (i_lo,i_hi),
          'peripheral': (None,None)
        }
    elif method=="quartileshift":
        p2_5s,p97_5s, Q1s,Q3s= intervals
        c_lo,c_hi= unify_intervals([(Q1s,Q3s)])
        i_lo,i_hi= unify_intervals([(p2_5s,Q1s),(Q3s,p97_5s)])
        return {
          'central': (c_lo,c_hi),
          'intermediate': (i_lo,i_hi),
          'peripheral': (None,None)
        }
    elif method=="manual":
        _,_, c, i, p= intervals
        c_lo,c_hi= unify_intervals([ c ])
        i_lo,i_hi= unify_intervals([ i[0], i[1] ])
        p_lo,p_hi= unify_intervals([ p[0], p[1] ])
        return {
          'central': (c_lo,c_hi),
          'intermediate': (i_lo,i_hi),
          'peripheral': (p_lo,p_hi)
        }
    else:
        return {
          'central': (None,None),
          'intermediate': (None,None),
          'peripheral': (None,None)
        }

def gather_method_stats(method_name, intervals_dict, all_draws, final_scores, method):
    """
    Renvoie une liste de dicts, version plus synthétique:
     - pour chaque boule (1..5):
       'Method', 'Boule', 'ZoneName' in [Central,Intermediate,Peripheral,OutOfZone]
        IntervalStart, IntervalEnd => la zone unifiée
        Count, Pct
     - la couverture ScoreCoverage95
    """
    rows= []
    for pos in range(1,6):
        values= [d[pos-1] for d in all_draws]
        n= len(values)
        if n==0:
            rows.append({
                'Method': method_name,
                'Boule': pos,
                'ZoneName': 'NoData',
                'IntervalStart': None,
                'IntervalEnd': None,
                'Count': 0,
                'Pct': 0.0
            })
            continue
        # unify zone
        z= get_boule_simplified_zones(intervals_dict[pos], method)
        (c_lo,c_hi)= z['central']
        (i_lo,i_hi)= z['intermediate']
        (p_lo,p_hi)= z['peripheral']

        # compter
        count_c= count_i= count_p= count_out= 0
        for val in values:
            w=0.0
            if method=="gaussian":
                mu,sigma,_,_,_= intervals_dict[pos]
                w= ball_weight_gaussian(val, mu,sigma)
            elif method=="quartile":
                p2_5,p97_5,Q1,Q3= intervals_dict[pos]
                w= ball_weight_quartile(val, p2_5,p97_5,Q1,Q3)
            elif method=="kde":
                l,u,q25,q75= intervals_dict[pos]
                w= ball_weight_kde(val, l,u,q25,q75)
            elif method=="quartileshift":
                p2_5s,p97_5s,Q1s,Q3s= intervals_dict[pos]
                w= ball_weight_quartile_shift(val, p2_5s,p97_5s,Q1s,Q3s)
            elif method=="manual":
                w= ball_weight_manual(val, intervals_dict[pos])
            elif method=="sym_gauss":
                w= ball_weight_symmetric_gaussian(val, intervals_dict[pos])

            if   w==1.0: count_c+=1
            elif w==0.5: count_i+=1
            elif w==0.2: count_p+=1
            else:        count_out+=1

        pc_c= (count_c/n)*100
        pc_i= (count_i/n)*100
        pc_p= (count_p/n)*100
        pc_o= (count_out/n)*100

        # on stocke 4 lignes pour la boule: Central, Interm, Periph, OutOfZone
        rows.append({
            'Method': method_name,
            'Boule': pos,
            'ZoneName': 'Central',
            'IntervalStart': c_lo,
            'IntervalEnd': c_hi,
            'Count': count_c,
            'Pct': pc_c
        })
        rows.append({
            'Method': method_name,
            'Boule': pos,
            'ZoneName': 'Intermediate',
            'IntervalStart': i_lo,
            'IntervalEnd': i_hi,
            'Count': count_i,
            'Pct': pc_i
        })
        rows.append({
            'Method': method_name,
            'Boule': pos,
            'ZoneName': 'Peripheral',
            'IntervalStart': p_lo,
            'IntervalEnd': p_hi,
            'Count': count_p,
            'Pct': pc_p
        })
        rows.append({
            'Method': method_name,
            'Boule': pos,
            'ZoneName': 'OutOfZone',
            'IntervalStart': None,
            'IntervalEnd': None,
            'Count': count_out,
            'Pct': pc_o
        })

    # Score coverage
    n_tot= len(final_scores)
    low, high= coverage_interval(final_scores, 0.95)
    c_in= sum(1 for x in final_scores if low<= x<= high)
    pc_in= (c_in/n_tot)*100 if n_tot else 0
    rows.append({
        'Method': method_name,
        'Boule': 'Score',
        'ZoneName': 'ScoreCoverage95',
        'IntervalStart': low,
        'IntervalEnd': high,
        'Count': c_in,
        'Pct': pc_in
    })

    return rows

# ============================
# print_method_stats => console
# ============================
def print_method_stats(method_name, intervals_dict, all_draws, final_scores, method):
    """
    On réutilise gather_method_stats puis on l'imprime de façon "belle".
    """
    print(f"\n=== Statistiques pour la méthode '{method_name}' ===")

    # Récup => unify
    rows= gather_method_stats(method_name, intervals_dict, all_draws, final_scores, method)
    # On groupe par 'Boule' = 1..5 ou "Score"
    from collections import defaultdict
    group_b= defaultdict(list)
    for r in rows:
        group_b[r['Boule']].append(r)

    # trier
    def boule_order(x):
        if x=='Score': return 99
        else: return x

    for bkey in sorted(group_b.keys(), key=boule_order):
        sub= group_b[bkey]
        if bkey=='Score':
            # On a la coverage row
            rcov= sub[0]  # "ScoreCoverage95"
            print(f"  Intervalle 95% sur le score : [{rcov['IntervalStart']:.2f}..{rcov['IntervalEnd']:.2f}]")
            n_tot= len(final_scores)
            print(f"  Valeurs dans l'intervalle   : {rcov['Count']}/{n_tot} ({rcov['Pct']:.1f}%)\n")
        else:
            # c,i,p, outofzone
            print(f"  Boule {bkey}:")
            # on tri par zone
            zorder= {'Central':1, 'Intermediate':2, 'Peripheral':3, 'OutOfZone':4}
            sub_sorted= sorted(sub, key=lambda x: zorder[x['ZoneName']])
            for srow in sub_sorted:
                zn= srow['ZoneName']
                c= srow['Count']
                p= srow['Pct']
                st, en= srow['IntervalStart'], srow['IntervalEnd']

                if zn=='OutOfZone':
                    print(f"    Hors zone => {c} ({p:.1f}%)\n")
                elif zn=='ScoreCoverage95':
                    continue
                else:
                    if st is None or en is None or st>=en:
                        print(f"    {zn:<13s} = (aucun) => {c} ({p:.1f}%)\n")
                    else:
                        print(f"    {zn:<13s} = [{st:.2f}..{en:.2f}] => {c} ({p:.1f}%)\n")


# ============================
# plot_scores_comparison => final figure
# ============================
def plot_scores_comparison(method_labels, list_of_scores):
    import matplotlib.pyplot as plt
    nb= len(method_labels)
    cols=3
    rows= (nb+cols-1)//cols
    fig, axs= plt.subplots(rows, cols, figsize=(15,5*rows))
    axs= axs.flatten()

    for i,(lbl, sc) in enumerate(zip(method_labels, list_of_scores)):
        ax= axs[i]
        ax.hist(sc, bins=30, color='lightblue', edgecolor='black', alpha=0.7)
        n_tot= len(sc)
        low,high= coverage_interval(sc, 0.95)
        n_in= sum(1 for x in sc if low<= x<= high)
        pc_in= (n_in/n_tot)*100 if n_tot else 0
        ax.axvspan(low, high, color='yellow', alpha=0.3,
                   label=f"95% coverage: {n_in}/{n_tot} ({pc_in:.1f}%)")
        ax.legend()
        ax.set_title(f"{lbl} - scores")

    if len(axs)> nb:
        for k in range(nb,len(axs)):
            fig.delaxes(axs[k])

    plt.suptitle("Comparaison des distributions de scores (intervalle 95%)")
    plt.tight_layout()
    plt.show()

# ============================
# MAIN
# ============================
def main():
    import openpyxl  # pour to_excel (assuming installed)
    import os

    excel_file= "Historique loto.xlsx"
    try:
        df= pd.read_excel(excel_file)
    except Exception as e:
        print(f"Erreur lecture Excel : {e}")
        return

    for i in range(1,6):
        if f"boule_{i}" not in df.columns:
            print(f"Colonne boule_{i} manquante.")
            return

    # all_draws => [ [b1,b2,b3,b4,b5], ... ]
    all_draws=[]
    for _,row in df.iterrows():
        try:
            arr= [int(row[f"boule_{i}"]) for i in range(1,6)]
            all_draws.append(arr)
        except:
            pass

    # ball_data => {1: [...], 2: [...], ...}
    ball_data={}
    for pos in range(1,6):
        ball_data[pos]= df[f"boule_{pos}"].dropna().values

    all_stats_rows= []

    # 1) Gaussienne
    intervals_gauss={}
    for pos in range(1,6):
        intervals_gauss[pos]= compute_gaussian_intervals(ball_data[pos])
    scores_gauss= [
        compute_total_weight_for_draw(d, intervals_gauss, "gaussian")
        for d in all_draws
    ]
    plot_method_results("Gaussienne", intervals_gauss, all_draws, scores_gauss, "gaussian")
    print_method_stats("Gaussienne", intervals_gauss, all_draws, scores_gauss, "gaussian")
    all_stats_rows += gather_method_stats("Gaussienne", intervals_gauss, all_draws, scores_gauss, "gaussian")

    # 2) Quartile
    intervals_quart={}
    for pos in range(1,6):
        intervals_quart[pos]= compute_quartile_intervals(ball_data[pos])
    scores_quart= [
        compute_total_weight_for_draw(d, intervals_quart, "quartile")
        for d in all_draws
    ]
    plot_method_results("Quartile", intervals_quart, all_draws, scores_quart, "quartile")
    print_method_stats("Quartile", intervals_quart, all_draws, scores_quart, "quartile")
    all_stats_rows += gather_method_stats("Quartile", intervals_quart, all_draws, scores_quart, "quartile")

    # 3) KDE
    intervals_kde_={}
    for pos in range(1,6):
        intervals_kde_[pos]= compute_kde_intervals(ball_data[pos], prob=0.95)
    scores_kde_= [
        compute_total_weight_for_draw(d, intervals_kde_, "kde")
        for d in all_draws
    ]
    plot_method_results("KDE", intervals_kde_, all_draws, scores_kde_, "kde")
    print_method_stats("KDE", intervals_kde_, all_draws, scores_kde_, "kde")
    all_stats_rows += gather_method_stats("KDE", intervals_kde_, all_draws, scores_kde_, "kde")

    # 4) QuartileShift
    intervals_qs={}
    for pos in range(1,6):
        intervals_qs[pos]= compute_quartile_shift_intervals(ball_data[pos])
    scores_qs= [
        compute_total_weight_for_draw(d, intervals_qs, "quartileshift")
        for d in all_draws
    ]
    plot_method_results("QuartileShift", intervals_qs, all_draws, scores_qs, "quartileshift")
    print_method_stats("QuartileShift", intervals_qs, all_draws, scores_qs, "quartileshift")
    all_stats_rows += gather_method_stats("QuartileShift", intervals_qs, all_draws, scores_qs, "quartileshift")

    # 5) Manuel
    intervals_manuel= compute_manual_intervals()
    scores_manuel= [
        compute_total_weight_for_draw(d, intervals_manuel, "manual")
        for d in all_draws
    ]
    plot_method_results("Manuelle", intervals_manuel, all_draws, scores_manuel, "manual")
    print_method_stats("Manuelle", intervals_manuel, all_draws, scores_manuel, "manual")
    all_stats_rows += gather_method_stats("Manuelle", intervals_manuel, all_draws, scores_manuel, "manual")

    # 6) SymGauss
    intervals_sym={}
    for pos in range(1,6):
        if pos==1:
            intervals_sym[pos]= compute_symmetric_gaussian_intervals(ball_data[pos], boundary= MIN_BOULE)
        elif pos==5:
            intervals_sym[pos]= compute_symmetric_gaussian_intervals(ball_data[pos], boundary= MAX_BOULE)
        else:
            intervals_sym[pos]= compute_symmetric_gaussian_intervals(ball_data[pos], boundary=None)
    scores_sym= [
        compute_total_weight_for_draw(d, intervals_sym, "sym_gauss")
        for d in all_draws
    ]
    plot_method_results("SymGauss", intervals_sym, all_draws, scores_sym, "sym_gauss")
    print_method_stats("SymGauss", intervals_sym, all_draws, scores_sym, "sym_gauss")
    all_stats_rows += gather_method_stats("SymGauss", intervals_sym, all_draws, scores_sym, "sym_gauss")

    # Resume final
    all_methods= ["Gaussienne","Quartile","KDE","QuartileShift","Manuel","SymGauss"]
    all_scores= [scores_gauss,scores_quart,scores_kde_,scores_qs,scores_manuel,scores_sym]

    print("\n\n[Résumé final des scores] => intervalle 95%, nb, %")
    for lbl, sc in zip(all_methods, all_scores):
        n_tot= len(sc)
        low, high= coverage_interval(sc, 0.95)
        count_in= sum(1 for x in sc if low<= x<= high)
        pc_in= (count_in/n_tot)*100 if n_tot else 0
        print(f"{lbl:15s} : [{low:.2f}..{high:.2f}] => {count_in}/{n_tot} ({pc_in:.1f}%)")

    plot_scores_comparison(all_methods, all_scores)

    # Export Excel "synthétisé"
    df_stats= pd.DataFrame(all_stats_rows)  # keys: Method,Boule,ZoneName,IntervalStart,IntervalEnd,Count,Pct
    excel_out= "stats_export.xlsx"
    df_stats.to_excel(excel_out, index=False)
    print(f"\n[Export synthétisé] => {excel_out}")

if __name__=="__main__":
    main()
