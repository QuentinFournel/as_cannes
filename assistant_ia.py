import io
import json
import os
import re
import time
import unicodedata
from datetime import datetime
from difflib import get_close_matches
import pandas as pd
import streamlit as st
from anthropic import Anthropic

# Persistance des conversations sur Google Drive (mêmes identifiants que l'app)
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
except ImportError:
    service_account = None

# ============================================================
# Configuration
# ============================================================
MODELE = "claude-sonnet-5"

MAX_TOKENS = 4000
MAX_ITERATIONS_OUTILS = 6   # garde-fou de la boucle agentique
TOP_N_RESULTATS = 15        # nb max de lignes renvoyées au modèle par outil

EXEMPLES_QUESTIONS = [
    "Trouve-moi un ailier rapide qui centre beaucoup",
    "Fais-moi un rapport complet sur Ousmane Dembélé",
    "Quels joueurs ressemblent à notre meilleur milieu ?",
    "Quels sont les points forts et faibles de Caen ?",
    "Quels joueurs sont en fin de contrat cet été ?",
    "Compare les deux meilleurs latéraux droits de Ligue 3",
]


# ============================================================
# Utilitaires
# ============================================================
# Caractères cyrilliques visuellement identiques à des latins,
# présents dans certains exports Wyscout (ex. "Сentres précises, %")
_CYRILLIQUES_SOSIES = str.maketrans("СсЕеАаОоРрХхВвМмТтКкНн", "CcEeAaOoPpXxBbMmTtKkHh")


def _normaliser(texte):
    """Minuscules + suppression des accents + translittération des sosies cyrilliques."""
    texte = str(texte).translate(_CYRILLIQUES_SOSIES)
    texte = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in texte if not unicodedata.combining(c)).lower().strip()


def _resoudre_colonne(nom, colonnes_valides):
    """Retrouve le nom exact d'une colonne (ou d'une équipe, d'un rôle...)
    à partir d'un nom approximatif.

    Retourne (nom_exact, None) si trouvé, sinon (None, suggestions).
    """
    normalise_vers_exact = {_normaliser(c): c for c in colonnes_valides}
    cle = _normaliser(nom)

    # 1. Correspondance exacte
    if cle in normalise_vers_exact:
        return normalise_vers_exact[cle], None

    # 2. Sous-chaîne : acceptée seulement si une unique correspondance ('frejus' -> 'Fréjus St-Raphaël')
    partiels = [exact for norm, exact in normalise_vers_exact.items() if cle in norm]
    if len(partiels) == 1:
        return partiels[0], None
    if partiels:
        return None, partiels[:5]

    # 3. Correspondance approximative
    suggestions = get_close_matches(cle, list(normalise_vers_exact.keys()), n=5, cutoff=0.6)
    return None, [normalise_vers_exact[s] for s in suggestions]


def _df_vers_json(df, n=TOP_N_RESULTATS):
    """Compacte un DataFrame en JSON (top n lignes) pour l'envoyer à Claude."""
    extrait = df.head(n).copy()
    return json.dumps(
        {
            "nb_resultats_total": int(len(df)),
            "nb_resultats_affiches": int(min(n, len(df))),
            "joueurs": extrait.to_dict(orient="records"),
        },
        ensure_ascii=False,
        default=str,
    )


def _colonnes_metriques(df):
    """Colonnes numériques du DataFrame utilisables comme critères de recherche."""
    exclues = [
        "Minutes jouées", "Âge", "Taille", "Poids", "Valeur marchande",
        "Matchs joués", "Cartons jaunes", "Cartons rouges",
    ]
    return [c for c in df.select_dtypes(include="number").columns if c not in exclues]


def _appliquer_filtres(df_resultats, params):
    """Filtres transverses (âge, taille, minutes, contrat) sur un DataFrame de résultats.

    Chaque filtre n'est appliqué que si la colonne correspondante existe
    (ex. compute_similarity ne renvoie pas de colonne Taille).
    """
    res = df_resultats

    if params.get("age_min") is not None and "Âge" in res.columns:
        res = res[res["Âge"] >= params["age_min"]]
    if params.get("age_max") is not None and "Âge" in res.columns:
        res = res[res["Âge"] <= params["age_max"]]
    if params.get("taille_min") is not None and "Taille" in res.columns:
        res = res[(res["Taille"] >= params["taille_min"]) | (res["Taille"] == 0)]
    if params.get("minutes_min") is not None and "Minutes jouées" in res.columns:
        res = res[res["Minutes jouées"] >= params["minutes_min"]]
    if params.get("contrat_annee_max") is not None and "Contrat expiration" in res.columns:
        contrats = pd.to_datetime(res["Contrat expiration"], errors="coerce")
        res = res[(contrats.dt.year <= params["contrat_annee_max"]) | contrats.isna()]

    return res


def _tokens_nom(texte):
    """Tokens significatifs d'un nom : initiales et particules retirées.

    'O. Dembélé'       -> ['dembele']
    'Ousmane Dembélé'  -> ['ousmane', 'dembele']
    """
    brut = _normaliser(texte).replace("-", " ").replace("'", " ")
    tokens = [t.strip(".") for t in brut.split()]
    return [t for t in tokens if len(t) > 1 and t not in ("de", "da", "du", "le", "la", "el", "al", "van", "von", "dos", "den")]


def _initiale_prenom(identifiant):
    """Initiale du prénom d'un identifiant de base : 'O. Dembélé - PSG' -> 'o'."""
    premier = _normaliser(str(identifiant).split(" - ")[0]).split()
    if premier and len(premier[0].strip(".")) == 1:
        return premier[0].strip(".")
    return ""


def _resoudre_joueur(df, nom):
    """Retrouve l'identifiant exact 'Joueur + Information' à partir d'un nom
    libre : 'Dembélé', 'Ousmane Dembélé', 'O. Dembélé', 'Dembélé PSG'...

    La base ne stocke que l'initiale du prénom ('O. Dembélé - PSG (Ligue 1)') :
    le matching se fait donc sur les tokens du nom de famille, pas sur la chaîne
    entière.

    Retourne (identifiant_exact, None) si un seul candidat,
    sinon (None, liste_de_candidats).
    """
    valeurs = list(df["Joueur + Information"].dropna().unique())
    cible = _normaliser(nom)
    tokens_cible = set(_tokens_nom(nom))

    # 1. Correspondance exacte sur l'identifiant complet
    for v in valeurs:
        if _normaliser(v) == cible:
            return v, None

    # 2. Tokens du nom de famille : ceux de la base doivent être contenus
    #    dans la demande ('dembele' ⊆ {'ousmane', 'dembele'})
    correspondances = []
    for v in valeurs:
        partie_nom = str(v).split(" - ")[0]
        tokens_base = set(_tokens_nom(partie_nom))
        if tokens_base and tokens_base <= tokens_cible:
            correspondances.append(v)
    if len(correspondances) == 1:
        return correspondances[0], None

    # 3. Plusieurs homonymes : départager par l'initiale du prénom
    #    ('Ousmane Dembélé' -> 'O. Dembélé' plutôt que 'M. Dembélé')
    if len(correspondances) > 1:
        prenoms = tokens_cible - set().union(
            *[set(_tokens_nom(str(v).split(" - ")[0])) for v in correspondances]
        )
        if prenoms:
            initiales = [
                v for v in correspondances
                if any(p.startswith(_initiale_prenom(v)) for p in prenoms if _initiale_prenom(v))
            ]
            if len(initiales) == 1:
                return initiales[0], None
            if initiales:
                correspondances = initiales

    # 4. Toujours ambigu : départager avec l'équipe ou la compétition citée
    #    dans la demande ('Dembélé PSG')
    if len(correspondances) > 1:
        affines = [
            v for v in correspondances
            if any(t in _normaliser(str(v).split(" - ", 1)[-1]) for t in tokens_cible)
        ]
        if len(affines) == 1:
            return affines[0], None
        return None, (affines or correspondances)[:10]
    if len(correspondances) == 1:
        return correspondances[0], None

    # 4. Demande plus courte que le nom en base ('traore' pour 'traore diakite')
    partiels = [
        v for v in valeurs
        if tokens_cible and tokens_cible <= set(_tokens_nom(str(v).split(" - ")[0]))
    ]
    if len(partiels) == 1:
        return partiels[0], None
    if partiels:
        return None, partiels[:10]

    # 5. Correspondance approximative (fautes de frappe)
    noms_normalises = {}
    for v in valeurs:
        noms_normalises.setdefault(_normaliser(str(v).split(" - ")[0]), v)
    proches = get_close_matches(cible, list(noms_normalises), n=5, cutoff=0.6)
    return None, [noms_normalises[p] for p in proches]


def _erreur_joueur(nom, candidats):
    """Message d'erreur JSON standard quand un joueur n'est pas résolu."""
    if candidats:
        return json.dumps(
            {"erreur": f"Plusieurs joueurs ou aucun joueur exact pour '{nom}'.",
             "candidats": candidats,
             "conseil": "Choisis le candidat pertinent (identifiant complet) et rappelle l'outil, ou demande une précision à l'utilisateur si l'ambiguïté est réelle."},
            ensure_ascii=False,
        )
    return json.dumps(
        {"erreur": f"Aucun joueur trouvé pour '{nom}' dans la base sélectionnée.",
         "conseil": "Vérifie l'orthographe ou indique à l'utilisateur que le joueur n'est pas dans cette base."},
        ensure_ascii=False,
    )


def _poste_du_joueur(df, joueur):
    return df.loc[df["Joueur + Information"] == joueur, "Poste"].iloc[0]


def _valider_poste(registre, poste):
    """Retourne (poste_exact, None) ou (None, message_erreur_json)."""
    exact, _ = _resoudre_colonne(poste, list(registre["kpi_by_position"].keys()))
    if exact is None:
        return None, json.dumps(
            {"erreur": f"Poste inconnu : {poste}.",
             "postes_valides": list(registre["kpi_by_position"].keys())},
            ensure_ascii=False,
        )
    return exact, None


# ============================================================
# Outils exposés à Claude
# ============================================================
def outil_rechercher_joueurs(df, registre, params):
    """Recherche par seuils de percentiles — réutilise search_recommended_players
    et la logique de la page Scouting (métriques brutes + KPI mappés)."""
    poste = params["poste"]
    criteres = params.get("criteres", {})

    if poste not in registre["kpi_by_position"]:
        return json.dumps({"erreur": f"Poste inconnu : {poste}. Postes valides : {list(registre['kpi_by_position'].keys())}"}, ensure_ascii=False)
    if not criteres:
        return json.dumps({"erreur": "Aucun critère fourni. Fournis au moins une métrique ou un KPI avec un percentile minimum."}, ensure_ascii=False)

    noms_kpi = list(registre["kpi_by_position"][poste].keys()) + ["Note globale"]
    noms_metriques = _colonnes_metriques(df)

    # Résolution des noms de critères (KPI prioritaire, puis métrique)
    criteres_resolus = {}   # nom exact -> (source, seuil)
    for nom, seuil in criteres.items():
        exact, _ = _resoudre_colonne(nom, noms_kpi)
        if exact is not None:
            criteres_resolus[exact] = ("kpi", float(seuil))
            continue
        exact, suggestions = _resoudre_colonne(nom, noms_metriques)
        if exact is not None:
            criteres_resolus[exact] = ("metrique", float(seuil))
            continue
        return json.dumps(
            {"erreur": f"Critère inconnu : '{nom}'.",
             "suggestions": suggestions or [],
             "conseil": "Utilise exactement un nom de la liste des métriques ou des KPI fournie dans les instructions."},
            ensure_ascii=False,
        )

    # KPI -> colonnes mappées dans une copie de travail (même logique que la page Scouting)
    df_travail = df.copy()
    besoin_kpi = any(src == "kpi" for src, _ in criteres_resolus.values())
    if besoin_kpi:
        scores_df = registre["calcul_scores_par_kpi"](df, "", poste)
        scores_indexe = scores_df.drop_duplicates(subset="Joueur + Information").set_index("Joueur + Information")
        for nom, (src, _) in criteres_resolus.items():
            if src == "kpi":
                df_travail[nom] = df_travail["Joueur + Information"].map(scores_indexe[nom])

    thresholds = {nom: seuil for nom, (_, seuil) in criteres_resolus.items()}
    resultats = registre["search_recommended_players"](df_travail, poste, thresholds)

    resultats = _appliquer_filtres(resultats, params)
    resultats = resultats.sort_values(by=list(thresholds.keys()), ascending=[False] * len(thresholds))

    st.session_state.assistant_dfs_courants.append(
        (f"Recherche {poste} — " + ", ".join(thresholds.keys()), resultats.reset_index(drop=True))
    )
    return _df_vers_json(resultats)


def outil_classement_par_role(df, registre, params):
    """Classement des joueurs d'un poste selon un rôle tactique
    — réutilise calcul_scores_par_kpi (colonnes de rôles)."""
    poste = params["poste"]
    role = params["role"]

    roles_valides = registre["kpi_coefficients_by_role"].get(poste, {})
    if poste not in registre["kpi_by_position"]:
        return json.dumps({"erreur": f"Poste inconnu : {poste}. Postes valides : {list(registre['kpi_by_position'].keys())}"}, ensure_ascii=False)

    role_exact, suggestions = _resoudre_colonne(role, list(roles_valides.keys()))
    if role_exact is None:
        return json.dumps(
            {"erreur": f"Rôle inconnu pour le poste {poste} : '{role}'.",
             "roles_valides": list(roles_valides.keys()),
             "suggestions": suggestions or []},
            ensure_ascii=False,
        )

    df_scores = registre["calcul_scores_par_kpi"](df, "", poste)
    df_scores = _appliquer_filtres(df_scores, params)
    df_scores = df_scores.sort_values(by=role_exact, ascending=False)

    colonnes_kpi = list(registre["kpi_by_position"][poste].keys())
    colonnes = (
        ["Joueur + Information", "Équipe dans la période sélectionnée", "Âge", "Taille",
         "Pied", "Minutes jouées", "Contrat expiration", role_exact, "Note globale"]
        + colonnes_kpi
    )
    resultats = df_scores[[c for c in colonnes if c in df_scores.columns]].reset_index(drop=True)

    st.session_state.assistant_dfs_courants.append((f"{role_exact} — {poste}", resultats))
    return _df_vers_json(resultats)


# Colonnes à exclure des points forts/faibles (valeurs brutes, pas des percentiles)
_COLONNES_HORS_PERCENTILES = [
    "Minutes jouées", "Âge", "Taille", "Poids", "Valeur marchande", "Matchs joués",
]


def _extraire_profil(df, registre, joueur, poste):
    """Notes KPI + rôles + infos d'un joueur — réutilise calcul_scores_par_kpi.

    Retourne (dict_profil, ligne_scores_df) pour le JSON et l'affichage.
    """
    df_scores = registre["calcul_scores_par_kpi"](df, joueur, poste)
    ligne = df_scores[df_scores["Joueur + Information"] == joueur].iloc[0]

    colonnes_kpi = list(registre["kpi_by_position"][poste].keys()) + ["Note globale"]
    colonnes_roles = list(registre["kpi_coefficients_by_role"][poste].keys())

    profil = {
        "joueur": joueur,
        "poste_analyse": poste,
        "infos": {
            "equipe": ligne.get("Équipe dans la période sélectionnée"),
            "age": ligne.get("Âge"),
            "taille": ligne.get("Taille"),
            "pied": ligne.get("Pied"),
            "passeport": ligne.get("Passeport pays"),
            "minutes_jouees": ligne.get("Minutes jouées"),
            "contrat_expiration": str(ligne.get("Contrat expiration")),
        },
        "notes_kpi": {k: float(ligne[k]) for k in colonnes_kpi if k in ligne.index},
        "notes_roles": {r: float(ligne[r]) for r in colonnes_roles if r in ligne.index},
    }

    colonnes_ligne = (
        ["Joueur + Information", "Équipe dans la période sélectionnée", "Âge",
         "Minutes jouées"] + colonnes_kpi + colonnes_roles
    )
    ligne_df = df_scores[df_scores["Joueur + Information"] == joueur][
        [c for c in colonnes_ligne if c in df_scores.columns]
    ].reset_index(drop=True)

    return profil, ligne_df


def outil_profil_joueur(df, registre, params):
    """Profil complet d'un joueur : notes KPI/rôles + points forts et faibles
    — réutilise calcul_scores_par_kpi et points_forts_faibles."""
    joueur, candidats = _resoudre_joueur(df, params["joueur"])
    if joueur is None:
        return _erreur_joueur(params["joueur"], candidats)

    if params.get("poste"):
        poste, erreur = _valider_poste(registre, params["poste"])
        if erreur:
            return erreur
    else:
        poste = _poste_du_joueur(df, joueur)

    profil, ligne_df = _extraire_profil(df, registre, joueur, poste)

    forts, faibles = registre["points_forts_faibles"](df, joueur, poste)
    forts = {k: v for k, v in forts.items() if k not in _COLONNES_HORS_PERCENTILES}
    faibles = {k: v for k, v in faibles.items() if k not in _COLONNES_HORS_PERCENTILES}
    profil["points_forts"] = dict(sorted(forts.items(), key=lambda x: -x[1])[:15])
    profil["points_faibles"] = dict(sorted(faibles.items(), key=lambda x: x[1])[:15])
    profil["contexte"] = (
        f"Percentiles calculés parmi les joueurs du poste {poste} avec au moins 500 minutes. "
        "Points forts : percentile >= 80. Points faibles : percentile <= 20 (listes tronquées à 15)."
    )

    st.session_state.assistant_dfs_courants.append((f"Profil — {joueur}", ligne_df))
    return json.dumps(profil, ensure_ascii=False, default=str)


def outil_joueurs_similaires(df, registre, params):
    """Joueurs au profil statistique proche — réutilise compute_similarity."""
    joueur, candidats = _resoudre_joueur(df, params["joueur"])
    if joueur is None:
        return _erreur_joueur(params["joueur"], candidats)

    if params.get("poste"):
        poste, erreur = _valider_poste(registre, params["poste"])
        if erreur:
            return erreur
    else:
        poste = _poste_du_joueur(df, joueur)

    resultats = registre["compute_similarity"](df, joueur, poste)
    resultats = _appliquer_filtres(resultats, params)
    resultats = resultats.reset_index(drop=True)

    st.session_state.assistant_dfs_courants.append((f"Joueurs similaires à {joueur}", resultats))
    return _df_vers_json(resultats)


def outil_comparer_joueurs(df, registre, params):
    """Comparaison KPI/rôles de deux joueurs sur une même base de poste."""
    joueur_1, candidats_1 = _resoudre_joueur(df, params["joueur_1"])
    if joueur_1 is None:
        return _erreur_joueur(params["joueur_1"], candidats_1)
    joueur_2, candidats_2 = _resoudre_joueur(df, params["joueur_2"])
    if joueur_2 is None:
        return _erreur_joueur(params["joueur_2"], candidats_2)

    poste_1 = _poste_du_joueur(df, joueur_1)
    poste_2 = _poste_du_joueur(df, joueur_2)

    # Même logique que la page Analyse comparative : un gardien ne se compare qu'à un gardien
    if (poste_1 == "Gardien") != (poste_2 == "Gardien"):
        return json.dumps(
            {"erreur": "Un gardien ne peut être comparé qu'à un autre gardien.",
             "postes": {joueur_1: poste_1, joueur_2: poste_2}},
            ensure_ascii=False,
        )

    if poste_1 == "Gardien":
        poste = "Gardien"
    elif params.get("poste"):
        poste, erreur = _valider_poste(registre, params["poste"])
        if erreur:
            return erreur
    else:
        poste = poste_1

    profil_1, ligne_1 = _extraire_profil(df, registre, joueur_1, poste)
    profil_2, ligne_2 = _extraire_profil(df, registre, joueur_2, poste)

    kpis = list(registre["kpi_by_position"][poste].keys()) + ["Note globale"]
    bilan = {joueur_1: 0, joueur_2: 0}
    for kpi in kpis:
        n1, n2 = profil_1["notes_kpi"].get(kpi), profil_2["notes_kpi"].get(kpi)
        if n1 is None or n2 is None or n1 == n2:
            continue
        bilan[joueur_1 if n1 > n2 else joueur_2] += 1

    comparaison_df = pd.concat([ligne_1, ligne_2], ignore_index=True)
    st.session_state.assistant_dfs_courants.append(
        (f"Comparaison — {joueur_1} vs {joueur_2} (base {poste})", comparaison_df)
    )

    return json.dumps(
        {"poste_de_comparaison": poste,
         "joueur_1": profil_1,
         "joueur_2": profil_2,
         "kpis_remportes": bilan,
         "contexte": "Notes 0-100 calculées sur la même base de poste (>= 500 minutes), pondérées par la ligue."},
        ensure_ascii=False,
        default=str,
    )


# ---- Analyse collective ----
COMPETITION_LIGUE = "France. National 2"   # même filtre que la page Analyse collective
NB_DERNIERS_MATCHS = 5


def _nom_fichier_equipe(equipe):
    """Les fichiers Team Stats des saisons != 24-25 sont nommés en Unicode NFD
    (même logique que la page Analyse collective)."""
    if st.session_state.get("saison") != "24-25":
        return unicodedata.normalize("NFD", equipe)
    return equipe


def _chemin_stats_equipe(equipe):
    return f"data/Data {st.session_state.get('saison')}/Team Stats {_nom_fichier_equipe(equipe)}.xlsx"


def _stats_moyennes_ligue(registre, equipes_saison):
    """Moyennes par match de chaque équipe du championnat
    — réplique la construction de df_stats_moyennes de la page Analyse collective."""
    lignes = []
    for equipe in equipes_saison:
        if not os.path.exists(_chemin_stats_equipe(equipe)):
            continue
        d = registre["collect_collective_data"](_nom_fichier_equipe(equipe))
        d = d[d["Compétition"] == COMPETITION_LIGUE]
        d = d[d["Équipe"] == equipe]
        if d.empty:
            continue
        ligne = d.mean(numeric_only=True).to_frame().T.round(2)
        ligne["Équipe"] = equipe
        ligne["Matchs analysés"] = len(d)
        lignes.append(ligne)

    if not lignes:
        return pd.DataFrame()

    df_moy = pd.concat(lignes, ignore_index=True)
    return df_moy.drop(columns=["Championnat"], errors="ignore")


def outil_analyse_equipe(df, registre, params):
    """Analyse collective d'une équipe : score de performance moyen, derniers
    matchs, forces et faiblesses par rapport au reste du championnat
    — réutilise collect_collective_data, construire_df_moyenne et evaluer_match."""
    saison = st.session_state.get("saison")
    equipes_saison = registre["equipes"].get(saison, [])

    equipe, suggestions = _resoudre_colonne(params["equipe"], equipes_saison)
    if equipe is None:
        return json.dumps(
            {"erreur": f"Équipe inconnue : '{params['equipe']}'.",
             "equipes_valides": equipes_saison,
             "suggestions": suggestions or []},
            ensure_ascii=False,
        )

    if not os.path.exists(_chemin_stats_equipe(equipe)):
        return json.dumps(
            {"erreur": f"Fichier de statistiques collectives introuvable pour {equipe} (saison {saison})."},
            ensure_ascii=False,
        )

    df_collectif = registre["collect_collective_data"](_nom_fichier_equipe(equipe))
    df_ligue = df_collectif[df_collectif["Compétition"] == COMPETITION_LIGUE]
    if df_ligue.empty:
        return json.dumps(
            {"erreur": f"Aucun match trouvé pour {equipe} avec le filtre '{COMPETITION_LIGUE}'.",
             "competitions_disponibles": sorted(df_collectif["Compétition"].dropna().unique().tolist())},
            ensure_ascii=False,
        )

    # 1. Score de performance moyen (equipe vs moyenne des adversaires)
    try:
        df_moyenne, nb_matchs = registre["construire_df_moyenne"](df_ligue, equipe)
        res = registre["evaluer_match"](df_moyenne, equipe, moyenne=True, nb_matchs=nb_matchs)
        score_performance = {
            "score_total_sur_100": res["total"],
            "verdict": res["verdict"],
            "nb_matchs_analyses": res["nb_matchs"],
            "dimensions": {d["nom"]: f"{d['points']}/{d['max']}" for d in res["dimensions"].values()},
            "kpis": [
                {"nom": k["nom"], "valeur": k["valeur"], "points": f"{k['points']}/{k['points_max']}"}
                for k in res["kpis"]
            ],
        }
    except ValueError as e:
        score_performance = {"indisponible": str(e)}

    # 2. Derniers matchs
    lignes_equipe = df_ligue[df_ligue["Équipe"] == equipe].copy()
    lignes_equipe["_date"] = pd.to_datetime(lignes_equipe["Date"], errors="coerce", dayfirst=True)
    derniers = (
        lignes_equipe.sort_values("_date", ascending=False)
        .head(NB_DERNIERS_MATCHS)[["Date", "Match", "Buts", "Buts concédés"]]
        .to_dict(orient="records")
    )

    # 3. Forces / faiblesses par rapport au championnat
    df_moy = _stats_moyennes_ligue(registre, equipes_saison)
    forces, faiblesses = [], []
    if not df_moy.empty and equipe in df_moy["Équipe"].values:
        colonnes_bas_mieux = registre["colonnes_bas_mieux"]
        colonnes_a_ranker = [c for c in df_moy.columns if c not in ("Équipe", "Matchs analysés")]
        n_equipes = len(df_moy)

        rangs = {}
        for col in colonnes_a_ranker:
            ascending = col in colonnes_bas_mieux
            rangs[col] = df_moy[col].rank(ascending=ascending, method="min")

        idx = df_moy.index[df_moy["Équipe"] == equipe][0]
        lignes_rang = []
        for col in colonnes_a_ranker:
            rang = rangs[col].loc[idx]
            if pd.isna(rang):
                continue
            lignes_rang.append(
                {"metrique": col,
                 "valeur_moyenne_par_match": df_moy.loc[idx, col],
                 "classement": f"{int(rang)}/{n_equipes}"}
            )
            if rang <= 3:
                forces.append(lignes_rang[-1])
            elif rang >= n_equipes - 2:
                faiblesses.append(lignes_rang[-1])

        forces = sorted(forces, key=lambda x: int(x["classement"].split("/")[0]))[:20]
        faiblesses = sorted(faiblesses, key=lambda x: -int(x["classement"].split("/")[0]))[:20]

        df_affichage = pd.DataFrame(
            [{"Type": "Point fort", **f} for f in forces]
            + [{"Type": "Point faible", **f} for f in faiblesses]
        )
        if not df_affichage.empty:
            df_affichage.columns = ["Type", "Métrique", "Valeur moyenne / match", "Classement"]
            st.session_state.assistant_dfs_courants.append(
                (f"Forces et faiblesses — {equipe} ({saison})", df_affichage)
            )

    return json.dumps(
        {"equipe": equipe,
         "saison": saison,
         "score_performance_moyen": score_performance,
         "derniers_matchs": derniers,
         "points_forts": forces,
         "points_faibles": faiblesses,
         "contexte": (
             f"Classements calculés sur les moyennes par match des {len(df_moy)} équipes du championnat "
             f"(filtre '{COMPETITION_LIGUE}'). Point fort : top 3. Point faible : 3 derniers. "
             "Attention au sens des métriques : pour certaines (pertes, buts concédés, PPDA...), "
             "une valeur basse est meilleure — le classement en tient déjà compte."
         )},
        ensure_ascii=False,
        default=str,
    )


def outil_chercher_joueur(df, registre, params):
    """Recherche d'identité : retrouve les joueurs correspondant à un nom libre.
    Sert à lever une ambiguïté avant d'appeler un autre outil."""
    nom = params["nom"]
    tokens = set(_tokens_nom(nom))

    if not tokens:
        return json.dumps({"erreur": "Nom vide ou non exploitable."}, ensure_ascii=False)

    lignes = []
    for _, ligne in df.iterrows():
        identifiant = ligne.get("Joueur + Information")
        if not isinstance(identifiant, str):
            continue
        tokens_base = set(_tokens_nom(identifiant.split(" - ")[0]))
        if not tokens_base:
            continue
        if tokens_base <= tokens or tokens <= tokens_base:
            lignes.append(ligne)

    if not lignes:
        joueur, candidats = _resoudre_joueur(df, nom)   # repli sur l'approximatif
        if joueur is not None:
            lignes = [df[df["Joueur + Information"] == joueur].iloc[0]]
        elif candidats:
            lignes = [df[df["Joueur + Information"] == c].iloc[0] for c in candidats]

    if not lignes:
        return json.dumps(
            {"resultats": [], "conseil": f"Aucun joueur ne correspond à '{nom}' dans cette base. "
                                         "Signale-le à l'utilisateur et propose une autre base de données."},
            ensure_ascii=False,
        )

    colonnes = ["Joueur + Information", "Équipe dans la période sélectionnée", "Poste",
                "Âge", "Minutes jouées", "Contrat expiration"]
    resultats = pd.DataFrame(lignes)[
        [c for c in colonnes if c in df.columns]
    ].head(20)

    return json.dumps(
        {"nb_resultats": int(len(resultats)),
         "resultats": resultats.to_dict(orient="records"),
         "conseil": "Utilise la valeur exacte de 'Joueur + Information' dans les autres outils."},
        ensure_ascii=False,
        default=str,
    )


_OPERATEURS = {">=": "ge", "<=": "le", ">": "gt", "<": "lt", "==": "eq", "!=": "ne"}


def outil_explorer_donnees(df, registre, params):
    """Exploration libre de la base : filtres, tri, colonnes au choix.

    Complète les outils spécialisés pour toutes les questions non prévues
    (moyennes d'âge, joueurs en fin de contrat, effectifs d'une équipe...).
    """
    colonnes_valides = list(df.columns)
    travail = df

    # --- Filtres ---
    for filtre in params.get("filtres", []) or []:
        nom_col = filtre.get("colonne")
        operateur = filtre.get("operateur")
        valeur = filtre.get("valeur")

        colonne, suggestions = _resoudre_colonne(nom_col, colonnes_valides)
        if colonne is None:
            return json.dumps(
                {"erreur": f"Colonne inconnue : '{nom_col}'.", "suggestions": suggestions or []},
                ensure_ascii=False,
            )
        if operateur not in _OPERATEURS and operateur != "contient":
            return json.dumps(
                {"erreur": f"Opérateur invalide : '{operateur}'.",
                 "operateurs_valides": list(_OPERATEURS) + ["contient"]},
                ensure_ascii=False,
            )

        try:
            if operateur == "contient":
                masque = travail[colonne].astype(str).apply(_normaliser).str.contains(
                    _normaliser(valeur), na=False
                )
            else:
                serie = travail[colonne]
                if pd.api.types.is_numeric_dtype(serie):
                    valeur = float(valeur)
                masque = getattr(serie, _OPERATEURS[operateur])(valeur)
            travail = travail[masque]
        except Exception as e:
            return json.dumps(
                {"erreur": f"Filtre impossible sur '{colonne}' : {type(e).__name__} : {e}"},
                ensure_ascii=False,
            )

    if travail.empty:
        return json.dumps(
            {"nb_resultats_total": 0,
             "conseil": "Aucun joueur ne correspond. Propose d'assouplir les filtres."},
            ensure_ascii=False,
        )

    # --- Colonnes affichées ---
    demandees = params.get("colonnes") or []
    colonnes_sortie = []
    for nom_col in demandees:
        colonne, suggestions = _resoudre_colonne(nom_col, colonnes_valides)
        if colonne is None:
            return json.dumps(
                {"erreur": f"Colonne inconnue : '{nom_col}'.", "suggestions": suggestions or []},
                ensure_ascii=False,
            )
        colonnes_sortie.append(colonne)

    base = ["Joueur + Information", "Équipe dans la période sélectionnée", "Poste", "Âge", "Minutes jouées"]
    colonnes_finales = [c for c in base if c in travail.columns]
    colonnes_finales += [c for c in colonnes_sortie if c not in colonnes_finales]

    # --- Tri ---
    tri = params.get("trier_par")
    if tri:
        colonne_tri, suggestions = _resoudre_colonne(tri, colonnes_valides)
        if colonne_tri is None:
            return json.dumps(
                {"erreur": f"Colonne de tri inconnue : '{tri}'.", "suggestions": suggestions or []},
                ensure_ascii=False,
            )
        travail = travail.sort_values(colonne_tri, ascending=bool(params.get("croissant", False)))
        if colonne_tri not in colonnes_finales:
            colonnes_finales.append(colonne_tri)

    resultats = travail[colonnes_finales].reset_index(drop=True)
    limite = int(params.get("limite") or TOP_N_RESULTATS)

    # --- Statistiques d'ensemble sur les colonnes numériques demandées ---
    stats = {}
    for colonne in colonnes_sortie:
        if pd.api.types.is_numeric_dtype(travail[colonne]):
            stats[colonne] = {
                "moyenne": round(float(travail[colonne].mean()), 2),
                "mediane": round(float(travail[colonne].median()), 2),
                "min": round(float(travail[colonne].min()), 2),
                "max": round(float(travail[colonne].max()), 2),
            }

    st.session_state.assistant_dfs_courants.append(
        (params.get("titre") or "Exploration de la base", resultats.head(50))
    )

    return json.dumps(
        {"nb_resultats_total": int(len(resultats)),
         "nb_resultats_affiches": int(min(limite, len(resultats))),
         "statistiques": stats,
         "joueurs": resultats.head(limite).to_dict(orient="records"),
         "contexte": "Valeurs brutes (non converties en percentiles)."},
        ensure_ascii=False,
        default=str,
    )


# Schémas d'outils au format Anthropic
def _schemas_outils():
    return [
        {
            "name": "rechercher_joueurs",
            "description": (
                "Recherche des joueurs d'un poste donné dont les percentiles dépassent des seuils "
                "sur des métriques brutes et/ou des KPI. Chaque critère est un percentile minimum "
                "entre 0 et 100 (ex. 70 = top 30 % du poste). Seuls les joueurs avec au moins "
                "500 minutes jouées sont considérés (filtre interne). À utiliser pour les demandes "
                "de profils par caractéristiques (ex. ailier qui centre beaucoup : 'Centres par 90' "
                "et 'Сentres précises, %')."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "poste": {"type": "string", "description": "Poste exact parmi la liste fournie dans les instructions."},
                    "criteres": {
                        "type": "object",
                        "description": "Dictionnaire {nom exact de métrique ou de KPI: percentile minimum 0-100}.",
                        "additionalProperties": {"type": "number"},
                    },
                    "age_min": {"type": "integer"},
                    "age_max": {"type": "integer"},
                    "taille_min": {"type": "integer", "description": "Taille minimum en cm."},
                    "minutes_min": {"type": "integer"},
                    "contrat_annee_max": {"type": "integer", "description": "Année maximum d'expiration de contrat."},
                },
                "required": ["poste", "criteres"],
            },
        },
        {
            "name": "classement_par_role",
            "description": (
                "Classe les joueurs d'un poste selon leur note sur un rôle tactique prédéfini "
                "(ex. Buteur → 'Attaquant de profondeur', Ailier → 'Ailier percutant', "
                "Milieu → 'Box-to-box'). À utiliser dès que la demande correspond à un profil "
                "tactique existant plutôt qu'à des métriques individuelles."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "poste": {"type": "string"},
                    "role": {"type": "string", "description": "Rôle tactique exact parmi ceux du poste (liste dans les instructions)."},
                    "age_min": {"type": "integer"},
                    "age_max": {"type": "integer"},
                    "taille_min": {"type": "integer"},
                    "minutes_min": {"type": "integer"},
                    "contrat_annee_max": {"type": "integer"},
                },
                "required": ["poste", "role"],
            },
        },
        {
            "name": "profil_joueur",
            "description": (
                "Profil complet d'un joueur : infos (âge, taille, pied, contrat), notes KPI et notes "
                "par rôle tactique (0-100), points forts (percentile >= 80) et points faibles "
                "(percentile <= 20) parmi les joueurs de son poste. Le nom peut être partiel "
                "('Corchia') : l'outil le résout automatiquement. À utiliser pour 'quels sont les "
                "points forts/faibles de X', 'que vaut X', 'parle-moi de X'."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "joueur": {"type": "string", "description": "Nom du joueur, même partiel."},
                    "poste": {"type": "string", "description": "Optionnel : base de comparaison. Par défaut, le poste du joueur."},
                },
                "required": ["joueur"],
            },
        },
        {
            "name": "joueurs_similaires",
            "description": (
                "Trouve les joueurs au profil statistique le plus proche d'un joueur donné "
                "(similarité cosinus pondérée par les KPI du poste, score 0-100). "
                "À utiliser pour 'quels joueurs ressemblent à X', 'trouve-moi un remplaçant pour X', "
                "'un profil comparable à X'."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "joueur": {"type": "string", "description": "Joueur de référence, nom même partiel."},
                    "poste": {"type": "string", "description": "Optionnel : par défaut, le poste du joueur."},
                    "age_min": {"type": "integer"},
                    "age_max": {"type": "integer"},
                    "minutes_min": {"type": "integer"},
                    "contrat_annee_max": {"type": "integer"},
                },
                "required": ["joueur"],
            },
        },
        {
            "name": "comparer_joueurs",
            "description": (
                "Compare deux joueurs sur la même base de poste : infos, notes KPI, notes par rôle, "
                "et bilan des KPI remportés par chacun. Un gardien ne se compare qu'à un autre gardien. "
                "À utiliser pour 'compare X et Y', 'qui est meilleur entre X et Y'."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "joueur_1": {"type": "string"},
                    "joueur_2": {"type": "string"},
                    "poste": {"type": "string", "description": "Optionnel : base de comparaison commune. Par défaut, le poste du joueur 1."},
                },
                "required": ["joueur_1", "joueur_2"],
            },
        },
        {
            "name": "analyse_equipe",
            "description": (
                "Analyse collective d'une équipe du championnat (données par match, indépendantes de "
                "la base joueurs sélectionnée) : score de performance moyen sur 100 (Fidélité au style, "
                "Efficacité offensive, Solidité défensive), derniers résultats, et points forts/faibles "
                "par rapport aux autres équipes (classement sur chaque métrique moyenne par match). "
                "À utiliser pour 'points forts et faibles de cette équipe', 'comment joue X', "
                "'analyse notre prochain adversaire'."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "equipe": {"type": "string", "description": "Nom de l'équipe, même approximatif (liste des équipes valides dans les instructions)."},
                },
                "required": ["equipe"],
            },
        },
        {
            "name": "chercher_joueur",
            "description": (
                "Retrouve l'identifiant exact d'un ou plusieurs joueurs à partir d'un nom libre "
                "('Dembélé', 'Ousmane Dembélé', 'Dembélé PSG'). Renvoie équipe, poste, âge et minutes "
                "pour chaque correspondance. À utiliser EN PREMIER dès qu'un autre outil renvoie une "
                "ambiguïté de nom, ou pour vérifier qu'un joueur figure bien dans la base."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Nom recherché, sous n'importe quelle forme."},
                },
                "required": ["nom"],
            },
        },
        {
            "name": "explorer_donnees",
            "description": (
                "Exploration libre de la base joueurs : filtres sur n'importe quelle colonne, tri, "
                "choix des colonnes affichées, et statistiques (moyenne, médiane, min, max) sur les "
                "colonnes numériques demandées. À utiliser pour toutes les questions que les outils "
                "spécialisés ne couvrent pas : effectif d'une équipe, joueurs en fin de contrat, "
                "moyenne d'âge, meilleur total de buts, valeurs brutes d'une métrique... "
                "Attention : renvoie des valeurs BRUTES, pas des percentiles — pour comparer des "
                "joueurs entre eux au sein d'un poste, préfère rechercher_joueurs ou classement_par_role."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "filtres": {
                        "type": "array",
                        "description": "Conditions combinées par ET.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "colonne": {"type": "string"},
                                "operateur": {"type": "string", "enum": [">=", "<=", ">", "<", "==", "!=", "contient"]},
                                "valeur": {"type": "string", "description": "Valeur comparée (nombre ou texte)."},
                            },
                            "required": ["colonne", "operateur", "valeur"],
                        },
                    },
                    "colonnes": {
                        "type": "array",
                        "description": "Colonnes supplémentaires à afficher et à résumer statistiquement.",
                        "items": {"type": "string"},
                    },
                    "trier_par": {"type": "string"},
                    "croissant": {"type": "boolean", "description": "Faux par défaut (tri décroissant)."},
                    "limite": {"type": "integer", "description": "Nombre de lignes renvoyées (15 par défaut)."},
                    "titre": {"type": "string", "description": "Titre du tableau affiché à l'utilisateur."},
                },
            },
        },
    ]


EXECUTEURS = {
    "rechercher_joueurs": outil_rechercher_joueurs,
    "classement_par_role": outil_classement_par_role,
    "profil_joueur": outil_profil_joueur,
    "joueurs_similaires": outil_joueurs_similaires,
    "comparer_joueurs": outil_comparer_joueurs,
    "analyse_equipe": outil_analyse_equipe,
    "chercher_joueur": outil_chercher_joueur,
    "explorer_donnees": outil_explorer_donnees,
}


# ============================================================
# System prompt (généré dynamiquement depuis les données réelles)
# ============================================================
def _construire_system_prompt(df, registre, nom_base):
    postes = list(registre["kpi_by_position"].keys())

    lignes_roles = []
    for poste, roles in registre["kpi_coefficients_by_role"].items():
        lignes_roles.append(f"- {poste} : {', '.join(roles.keys())}")

    lignes_kpi = []
    for poste, kpis in registre["kpi_by_position"].items():
        lignes_kpi.append(f"- {poste} : {', '.join(kpis.keys())}, Note globale")

    metriques = _colonnes_metriques(df)

    equipes_saison = registre.get("equipes", {}).get(st.session_state.get("saison"), [])
    bloc_equipes = ""
    if equipes_saison:
        bloc_equipes = f"\n\nÉQUIPES DU CHAMPIONNAT (pour analyse_equipe) :\n{', '.join(equipes_saison)}"

    return f"""Tu es l'assistant data de l'AS Cannes, intégré à l'application d'analyse du club.
Tu aides le staff (recruteurs, analystes, entraîneurs) à explorer les données joueurs en langage naturel.

Base de données active : "{nom_base}" ({len(df)} lignes). Saison : {st.session_state.get('saison', '?')}.
Les données proviennent de Wyscout. L'identifiant joueur est "Joueur + Information" au format "Nom - Équipe (Compétition)".

TON RÔLE
Tu n'es pas un moteur de recherche : tu es un analyste. Ton interlocuteur ne connaît ni les noms de
colonnes, ni les postes, ni les rôles de l'application. C'est à TOI de traduire sa demande en requêtes,
pas à lui d'être précis. Ne lui demande jamais un identifiant exact, un nom de métrique ou un nom de poste :
utilise les outils pour le trouver toi-même.

MÉTHODE (à suivre à chaque demande)
1. Identifie l'intention réelle. "Un ailier rapide qui centre" = un profil, pas une liste de colonnes.
2. Lève les ambiguïtés avec les outils : chercher_joueur pour une identité, explorer_donnees pour vérifier
   ce que contient la base. Un nom d'utilisateur ne correspond jamais exactement à la base : cherche d'abord.
3. Enchaîne plusieurs outils si nécessaire. Une bonne réponse demande souvent 2 à 4 appels
   (ex. chercher_joueur -> profil_joueur -> joueurs_similaires).
4. Si un outil renvoie une erreur ou des suggestions, corrige-toi et rappelle-le. Ne renvoie jamais
   l'erreur brute à l'utilisateur.
5. RÉDIGE une analyse. Ne te contente pas de recopier les chiffres : explique ce qu'ils signifient sur le
   terrain, hiérarchise, prends position, signale les limites (faible temps de jeu, niveau de la ligue,
   âge, fin de contrat). Termine par une recommandation ou une piste d'approfondissement.

CHOIX DES OUTILS
- Profil par caractéristiques ("rapide", "qui centre", "bon dans les duels") : rechercher_joueurs.
- Profil tactique existant ("attaquant de profondeur", "box-to-box") : classement_par_role.
- Un joueur précis (points forts/faibles, rapport, "que vaut X") : profil_joueur.
- "Qui ressemble à X", "un remplaçant pour X" : joueurs_similaires.
- "Compare X et Y" : comparer_joueurs.
- Une équipe (style, forme, forces/faiblesses collectives) : analyse_equipe.
- Identité d'un joueur, vérifier sa présence dans la base : chercher_joueur.
- Tout le reste (effectifs, fins de contrat, moyennes d'âge, totaux bruts, questions imprévues) : explorer_donnees.

RÈGLES DE DONNÉES
- Utilise UNIQUEMENT les noms exacts de postes, rôles, KPI et métriques listés ci-dessous. N'invente jamais un nom.
- Les critères de rechercher_joueurs sont des percentiles minimums (0-100) au sein du poste : 70 = top 30 %.
  Commence autour de 70-75 ; descends si la recherche ne renvoie rien.
- Certains noms de métriques Wyscout ont une orthographe inhabituelle, copie-les exactement
  (ex. "Сentres précises, %" commence par un caractère cyrillique).
- Distingue percentile (comparaison entre joueurs du poste) et valeur brute (explorer_donnees).
- Un percentile élevé sur peu de minutes jouées est peu fiable : signale-le.

STYLE
- Réponds en français, en prose structurée, sans jargon technique de l'application (ne cite pas les noms
  d'outils ni de colonnes bruts). Les tableaux de résultats s'affichent automatiquement sous ta réponse :
  ne les recopie pas intégralement, commente-les.
- Cite les joueurs avec leur équipe et leur compétition.
- Précise le nombre total de résultats et les critères retenus.
- Sois concis : va à l'essentiel, pas de remplissage.

POSTES : {', '.join(postes)}

RÔLES TACTIQUES PAR POSTE :
{chr(10).join(lignes_roles)}

KPI PAR POSTE (notes 0-100 déjà pondérées par la ligue) :
{chr(10).join(lignes_kpi)}

MÉTRIQUES BRUTES DISPONIBLES ({len(metriques)}) :
{', '.join(metriques)}{bloc_equipes}"""


# ============================================================
# Boucle agentique
# ============================================================
def _executer_tour_anthropic(client, system_prompt, df, registre, on_texte=None, on_outil=None,
                             on_attente=None):
    """Envoie l'historique API à Claude et exécute les outils jusqu'à la réponse finale.

    on_texte(buffer)       : callback appelé à chaque delta avec le texte accumulé (streaming).
    on_outil(nom, params)  : callback appelé à chaque appel d'outil (affichage en direct).

    Retourne (texte_final, liste_appels_outils).
    """
    appels_outils = []
    texte_complet = ""

    # Le prompt système (catalogue de métriques) et les schémas d'outils sont
    # identiques à chaque appel : on les met en cache pour ne les facturer
    # qu'une fois par tranche de 5 minutes au lieu de 3 à 5 fois par question.
    systeme_cache = [{
        "type": "text",
        "text": system_prompt,
        "cache_control": {"type": "ephemeral"},
    }]

    for _ in range(MAX_ITERATIONS_OUTILS):
        depart = texte_complet

        def _appel():
            nonlocal texte_complet
            texte_complet = depart          # repart du même point si l'appel est rejoué
            with client.messages.stream(
                model=MODELE,
                max_tokens=MAX_TOKENS,
                system=systeme_cache,
                tools=_schemas_outils(),
                messages=st.session_state.assistant_api_history,
            ) as stream:
                for delta in stream.text_stream:
                    texte_complet += delta
                    if on_texte:
                        on_texte(texte_complet)
                return stream.get_final_message()

        reponse = _appeler_avec_reprise(_appel, on_attente)

        st.session_state.assistant_api_history.append(
            {"role": "assistant", "content": reponse.content}
        )

        if reponse.stop_reason != "tool_use":
            return texte_complet, appels_outils

        # Séparer l'éventuelle narration pré-outil du texte du tour suivant
        if texte_complet and not texte_complet.endswith("\n"):
            texte_complet += "\n\n"
            if on_texte:
                on_texte(texte_complet)

        resultats_blocs = []
        for bloc in reponse.content:
            if bloc.type != "tool_use":
                continue
            appels_outils.append({"nom": bloc.name, "params": bloc.input})
            if on_outil:
                on_outil(bloc.name, bloc.input)
            try:
                sortie = EXECUTEURS[bloc.name](df, registre, bloc.input)
            except Exception as e:
                sortie = json.dumps({"erreur": f"Erreur d'exécution : {type(e).__name__} : {e}"}, ensure_ascii=False)
            resultats_blocs.append(
                {"type": "tool_result", "tool_use_id": bloc.id, "content": sortie}
            )

        st.session_state.assistant_api_history.append(
            {"role": "user", "content": resultats_blocs}
        )

    return (
        texte_complet
        or "Je n'ai pas réussi à aboutir à une réponse (trop d'étapes de recherche). Reformule ta demande.",
        appels_outils,
    )


# Reprise automatique en cas de limite de débit (429) ou de surcharge du
# service (529) : une question consomme plusieurs appels API.
MAX_REPRISES = 3
DELAI_REPRISE_DEFAUT = 10
DELAI_REPRISE_MAX = 60


def _est_erreur_debit(erreur):
    """Limite de débit atteinte (429)."""
    return getattr(erreur, "status_code", None) == 429 or "429" in str(erreur)


def _est_erreur_temporaire(erreur):
    """Surcharge passagère du service (500 / 529) : un nouvel essai suffit."""
    return (getattr(erreur, "status_code", None) in (500, 529)
            or "overloaded" in str(erreur).lower())


def _delai_reprise(erreur, tentative=0):
    """Délai conseillé par l'API si présent, sinon backoff exponentiel."""
    trouve = re.search(r"retry-after['\"]?\s*[:=]\s*['\"]?(\d+)", str(erreur), re.IGNORECASE)
    if trouve:
        return min(int(trouve.group(1)) + 1, DELAI_REPRISE_MAX)
    return min(DELAI_REPRISE_DEFAUT * (2 ** tentative), DELAI_REPRISE_MAX)


def _appeler_avec_reprise(appel, on_attente=None):
    """Exécute un appel API en réessayant sur limite de débit ou surcharge."""
    for tentative in range(MAX_REPRISES + 1):
        try:
            return appel()
        except Exception as e:
            reessayable = _est_erreur_debit(e) or _est_erreur_temporaire(e)
            if not reessayable or tentative == MAX_REPRISES:
                raise
            attente = _delai_reprise(e, tentative)
            if on_attente:
                on_attente(attente, tentative + 1)
            time.sleep(attente)


# ============================================================
# Historique persistant des conversations
# ============================================================
MAX_CONVERSATIONS = 30       # conversations conservées par utilisateur
MAX_LIGNES_TABLEAU = 30      # lignes de tableau conservées par message
DOSSIER_LOCAL = "data/conversations"


def _utilisateur():
    return st.session_state.get("username") or "invite"


def _nom_fichier_conversations():
    return f"conversations_{_utilisateur()}.json"


def _drive_actif():
    return service_account is not None and "DRIVE_CONVERSATIONS_FOLDER_ID" in st.secrets


@st.cache_resource(show_spinner=False)
def _service_drive():
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["GOOGLE_SERVICE_ACCOUNT_JSON"],
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds)


def _id_fichier_drive(service, nom):
    dossier = st.secrets["DRIVE_CONVERSATIONS_FOLDER_ID"]
    reponse = service.files().list(
        q=f"'{dossier}' in parents and name='{nom}' and trashed=false",
        spaces="drive", fields="files(id, name)",
    ).execute()
    fichiers = reponse.get("files", [])
    return fichiers[0]["id"] if fichiers else None


def _lire_conversations():
    """Charge les conversations de l'utilisateur (Drive si configuré, sinon disque local)."""
    nom = _nom_fichier_conversations()

    if _drive_actif():
        service = _service_drive()
        identifiant = _id_fichier_drive(service, nom)
        if identifiant is None:
            return []
        tampon = io.BytesIO()
        telechargement = MediaIoBaseDownload(tampon, service.files().get_media(fileId=identifiant))
        termine = False
        while not termine:
            _, termine = telechargement.next_chunk()
        return json.loads(tampon.getvalue().decode("utf-8")).get("conversations", [])

    chemin = os.path.join(DOSSIER_LOCAL, nom)
    if not os.path.exists(chemin):
        return []
    with open(chemin, encoding="utf-8") as fichier:
        return json.load(fichier).get("conversations", [])


def _ecrire_conversations(conversations):
    """Enregistre les conversations (Drive si configuré, sinon disque local)."""
    nom = _nom_fichier_conversations()
    contenu = json.dumps(
        {"conversations": conversations[:MAX_CONVERSATIONS]}, ensure_ascii=False, default=str
    ).encode("utf-8")

    if _drive_actif():
        service = _service_drive()
        support = MediaIoBaseUpload(io.BytesIO(contenu), mimetype="application/json", resumable=False)
        identifiant = _id_fichier_drive(service, nom)
        if identifiant:
            service.files().update(fileId=identifiant, media_body=support).execute()
        else:
            service.files().create(
                body={"name": nom, "parents": [st.secrets["DRIVE_CONVERSATIONS_FOLDER_ID"]]},
                media_body=support, fields="id",
            ).execute()
        return

    os.makedirs(DOSSIER_LOCAL, exist_ok=True)
    with open(os.path.join(DOSSIER_LOCAL, nom), "wb") as fichier:
        fichier.write(contenu)


def _serialiser_messages(messages):
    """Convertit l'historique affiché en structure JSON (DataFrames -> enregistrements)."""
    sortie = []
    for message in messages:
        sortie.append({
            "role": message["role"],
            "text": message.get("text", ""),
            "outils": message.get("outils", []),
            "tableaux": [
                {"titre": titre, "lignes": tableau.head(MAX_LIGNES_TABLEAU).to_dict(orient="records")}
                for titre, tableau in message.get("dataframes", [])
            ],
        })
    return sortie


def _deserialiser_messages(messages):
    """Reconstruit l'historique affichable à partir du JSON stocké."""
    sortie = []
    for message in messages:
        sortie.append({
            "role": message.get("role", "assistant"),
            "text": message.get("text", ""),
            "outils": message.get("outils", []),
            "dataframes": [
                (tableau.get("titre", ""), pd.DataFrame(tableau.get("lignes", [])))
                for tableau in message.get("tableaux", [])
            ],
        })
    return sortie


def _historique_api_depuis_messages(messages):
    """Reconstruit un historique API neutre (texte seul) à partir des messages affichés.

    Les appels d'outils ne sont pas rejoués : le modèle reprend le fil de la
    conversation à partir des échanges rédigés.
    """
    historique = []
    for message in messages:
        texte = (message.get("text") or "").strip()
        if texte:
            historique.append({"role": message["role"], "content": texte})
    return historique


def _titre_conversation(question):
    titre = " ".join(str(question).split())
    return titre[:60] + ("..." if len(titre) > 60 else "")


def _charger_liste_conversations():
    """Charge la liste une seule fois par session."""
    if "assistant_conversations" in st.session_state:
        return
    try:
        st.session_state.assistant_conversations = _lire_conversations()
        st.session_state.assistant_stockage_ko = None
    except Exception as e:
        st.session_state.assistant_conversations = []
        st.session_state.assistant_stockage_ko = str(e)


def _enregistrer_conversation_courante(nom_base):
    """Crée ou met à jour la conversation en cours, puis persiste l'ensemble."""
    messages = st.session_state.assistant_display
    if not messages:
        return

    premiere_question = next((m["text"] for m in messages if m["role"] == "user"), "Conversation")
    conversation = {
        "id": st.session_state.get("assistant_conv_id") or datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "titre": _titre_conversation(premiere_question),
        "date": datetime.now().isoformat(timespec="seconds"),
        "base": nom_base,
        "messages": _serialiser_messages(messages),
    }
    st.session_state.assistant_conv_id = conversation["id"]

    conversations = [
        c for c in st.session_state.assistant_conversations if c.get("id") != conversation["id"]
    ]
    conversations.insert(0, conversation)
    st.session_state.assistant_conversations = conversations[:MAX_CONVERSATIONS]

    try:
        _ecrire_conversations(st.session_state.assistant_conversations)
        st.session_state.assistant_stockage_ko = None
    except Exception as e:
        st.session_state.assistant_stockage_ko = str(e)


def _ouvrir_conversation(conversation):
    st.session_state.assistant_conv_id = conversation.get("id")
    st.session_state.assistant_display = _deserialiser_messages(conversation.get("messages", []))
    st.session_state.assistant_api_history = _historique_api_depuis_messages(
        st.session_state.assistant_display
    )


def _nouvelle_conversation():
    st.session_state.assistant_conv_id = None
    st.session_state.assistant_display = []
    st.session_state.assistant_api_history = []


def _supprimer_conversation(identifiant):
    st.session_state.assistant_conversations = [
        c for c in st.session_state.assistant_conversations if c.get("id") != identifiant
    ]
    if st.session_state.get("assistant_conv_id") == identifiant:
        _nouvelle_conversation()
    try:
        _ecrire_conversations(st.session_state.assistant_conversations)
    except Exception as e:
        st.session_state.assistant_stockage_ko = str(e)


def _afficher_historique_conversations(nom_base):
    """Barre d'historique affichée dans la page Assistant IA (pas dans le menu)."""
    conversations = st.session_state.assistant_conversations

    colonne_info, colonne_bouton = st.columns([3, 1])
    with colonne_info:
        st.caption(
            f"Base analysée : **{nom_base}** — saison {st.session_state.get('saison', '')} "
            f"· modèle `{MODELE}`"
        )
    with colonne_bouton:
        if st.button("Nouvelle conversation", use_container_width=True, key="assistant_nouvelle"):
            _nouvelle_conversation()
            st.rerun()

    with st.expander(f"Mes conversations ({len(conversations)})", expanded=False):
        if not conversations:
            st.caption("Aucune conversation enregistrée pour le moment.")

        for conversation in conversations:
            colonne_titre, colonne_date, colonne_suppr = st.columns([6, 2, 1])
            actuelle = conversation.get("id") == st.session_state.get("assistant_conv_id")
            libelle = ("● " if actuelle else "") + conversation.get("titre", "Conversation")

            if colonne_titre.button(libelle, key=f"conv_{conversation['id']}", use_container_width=True):
                _ouvrir_conversation(conversation)
                st.rerun()

            date = str(conversation.get("date", ""))[:10]
            colonne_date.caption(date)

            if colonne_suppr.button("🗑", key=f"suppr_{conversation['id']}", help="Supprimer"):
                _supprimer_conversation(conversation["id"])
                st.rerun()

        if st.session_state.get("assistant_stockage_ko"):
            st.caption("Historique non sauvegardé (stockage indisponible).")
        elif not _drive_actif():
            st.caption("Historique local : perdu au redémarrage de l'application.")


# ============================================================
# Point d'entrée — appelé depuis ams.py
# ============================================================
def afficher_assistant(df, registre, nom_base):
    """Affiche la page Assistant IA.

    df        : DataFrame joueurs sélectionné (une des bases de all_df)
    registre  : dict de callables/structures injectés depuis ams.py
    nom_base  : nom de la base sélectionnée (pour le contexte et le reset)
    """
    if "ANTHROPIC_API_KEY" not in st.secrets:
        st.error("Clé API manquante : ajoutez ANTHROPIC_API_KEY dans les secrets Streamlit.")
        st.stop()

    if "assistant_api_history" not in st.session_state:
        st.session_state.assistant_api_history = []
    if "assistant_display" not in st.session_state:
        st.session_state.assistant_display = []
    st.session_state.setdefault("assistant_conv_id", None)

    # Changement de base : on repart d'une conversation vierge
    if st.session_state.get("assistant_nom_base") != nom_base:
        st.session_state.assistant_nom_base = nom_base
        _nouvelle_conversation()

    _charger_liste_conversations()
    _afficher_historique_conversations(nom_base)

    # Historique affiché
    for message in st.session_state.assistant_display:
        with st.chat_message(message["role"]):
            if message.get("outils"):
                with st.expander("Détail des recherches effectuées"):
                    for appel in message["outils"]:
                        st.markdown(f"**{appel['nom']}**")
                        st.json(appel["params"])
            st.markdown(message["text"])
            for titre, df_resultat in message.get("dataframes", []):
                st.caption(titre)
                st.dataframe(df_resultat, use_container_width=True, hide_index=True)

    # Exemples cliquables tant que la conversation est vide
    if not st.session_state.assistant_display:
        st.caption("Exemples de questions — cliquez ou écrivez la vôtre")
        colonnes = st.columns(2)
        for i, exemple in enumerate(EXEMPLES_QUESTIONS):
            if colonnes[i % 2].button(exemple, key=f"assistant_ex_{i}", use_container_width=True):
                st.session_state.assistant_question_suggeree = exemple
                st.rerun()

    question = st.chat_input("Posez votre question en langage naturel")
    if not question:
        question = st.session_state.pop("assistant_question_suggeree", None)
    if not question:
        return

    st.session_state.assistant_display.append({"role": "user", "text": question})
    st.session_state.assistant_api_history.append({"role": "user", "content": question})

    with st.chat_message("user"):
        st.markdown(question)

    # Collecteur des DataFrames produits par les outils pendant ce tour
    st.session_state.assistant_dfs_courants = []

    client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    system_prompt = _construire_system_prompt(df, registre, nom_base)

    # Snapshot pour restaurer proprement l'historique API en cas d'erreur en cours de boucle
    historique_avant = list(st.session_state.assistant_api_history[:-1])

    with st.chat_message("assistant"):
        statut = st.status("Analyse de la demande...", expanded=False)
        zone_texte = st.empty()

        def on_outil(nom, params):
            statut.update(label=f"Recherche en cours — {nom}")
            with statut:
                st.markdown(f"**{nom}**")
                st.json(params)

        def on_texte(buffer):
            zone_texte.markdown(buffer + " ▌")

        def on_attente(secondes, tentative):
            statut.update(
                label=f"Service momentanément indisponible — reprise dans {secondes} s "
                      f"(tentative {tentative}/{MAX_REPRISES})"
            )

        try:
            texte, appels_outils = _executer_tour_anthropic(
                client, system_prompt, df, registre, on_texte, on_outil, on_attente
            )
        except Exception as e:
            statut.update(label="Erreur", state="error")
            if _est_erreur_debit(e):
                st.error(
                    "Limite de débit de l'API atteinte. Patientez quelques instants avant de relancer."
                )
            elif "credit balance" in str(e).lower():
                st.error(
                    "Crédit Anthropic épuisé. Rechargez le compte depuis console.anthropic.com "
                    "(rubrique Billing)."
                )
            else:
                st.error(f"Erreur lors de l'appel à l'API Anthropic : {e}")
            st.session_state.assistant_api_history = historique_avant
            st.session_state.assistant_display.pop()
            return

        if appels_outils:
            statut.update(
                label=f"Détail des recherches effectuées ({len(appels_outils)})",
                state="complete",
                expanded=False,
            )
        else:
            statut.update(label="Réponse directe (aucune recherche nécessaire)", state="complete")

        zone_texte.markdown(texte)

        dataframes = st.session_state.assistant_dfs_courants
        for titre, df_resultat in dataframes:
            st.caption(titre)
            st.dataframe(df_resultat, use_container_width=True, hide_index=True)

    st.session_state.assistant_display.append(
        {"role": "assistant", "text": texte, "outils": appels_outils, "dataframes": dataframes}
    )
    st.session_state.assistant_dfs_courants = []

    _enregistrer_conversation_courante(nom_base)
    st.rerun()   # rafraîchit la liste des conversations dans la barre latérale