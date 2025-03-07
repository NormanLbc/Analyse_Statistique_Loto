# config.py
import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

BDD_NAME_PREFIX = "CombinaisonLotoTest"
EXCEL_FILE       = os.path.join(ROOT_DIR, "Historique loto.xlsx")
LOG_FILE         = os.path.join(ROOT_DIR, "loto_log.txt")
SUMMARY_FILE     = os.path.join(ROOT_DIR, "summary_log.txt")

# Paramètres du Loto
BOULE_MIN, BOULE_MAX = 1, 50

# 13 filtres
SOMME_MIN, SOMME_MAX        = 60, 199
DIZAINES_MAX                = 3
SUITE_MAX                   = 3
MEDIAN_MIN, MEDIAN_MAX      = 2.5, 12.5
VARIANCE_MIN, VARIANCE_MAX  = 20, 355
ECART_MIN, ECART_MAX        = 1, 12
ECART_CONSECUTIF            = (1, 5, 2)
MPS_MIN, MPS_MAX            = 0.095, 0.107
SOMME3F_MIN, SOMME3F_MAX    = 13, 101
SOMME3C_MIN, SOMME3C_MAX    = 29, 122
SOMME3L_MIN, SOMME3L_MAX    = 49, 138

SIMILARITE_RECENTE_THRESHOLD = 3

LOG_INTERVAL      = 100000
LOG_INTERVAL_HEUR = 10000
CHUNK_SIZE_MPS    = 100000

# Nouveau "quartileshift_testBorne" => On stocke pour chaque boule
# un intervalle central => 1.0, un intervalle interm => 0.4, le reste => 0.0
# ------------------------------------------------------------------
# BORNES QUARTILESHIFT TESTBORNE95 
# (1.0 => central, 0.4 => intermediate, 0.0 => else)
# ------------------------------------------------------------------

QSHIFT_TESTBORNE_BOUNDS = {
    1: {
        'central':      (2.12, 10.33),
        'intermediate': (1.00, 19.75), 
        'peripheral':   None
    },
    2: {
        'central':      (9.20, 20.95),
        'intermediate': (3.25, 32.81),
        'peripheral':   None
    },
    3: {
        'central':      (18.12, 30.68),
        'intermediate': (9.55, 40.17),
        'peripheral':   None
    },
    4: {
        'central':      (28.72, 40.25),
        'intermediate': (16.10, 47.20),
        'peripheral':   None
    },
    5: {
        'central':      (39.85, 49.05),
        'intermediate': (25.00, 50.00),
        'peripheral':   None
    }
}

# Intervalle 95% du SCORE FINAL => 
# par exemple, testBorne95 t’indique que ~95% des scores 
# se situent entre 2.5 et 5.0
QSHIFT_TESTBORNE_SCORE_95 = (2.5, 5.0)
