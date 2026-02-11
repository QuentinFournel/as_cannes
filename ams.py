import pandas as pd 
import numpy as np
import os
from mplsoccer import PyPizza
import io
from mplsoccer import Radar, FontManager, grid
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import plotly.express as px
import plotly.graph_objects as go
import requests
import unicodedata
import zipfile
from streamlit_option_menu import option_menu
import math
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics.pairwise import cosine_distances
import seaborn as sns
from scipy import stats
from pathlib import Path
from bs4 import BeautifulSoup

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.http import MediaFileUpload

import warnings
warnings.filterwarnings('ignore')

# Authentification avec Google Drive via compte de service
def authenticate_google_drive():
    SCOPES = ['https://www.googleapis.com/auth/drive']
    service_account_info = st.secrets["GOOGLE_SERVICE_ACCOUNT_JSON"]
    creds = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    service = build('drive', 'v3', credentials=creds)
    return service

# Lister tous les fichiers présents directement dans un dossier Google Drive (non récursif)
def list_files_in_folder(service, folder_id):
    files = []
    page_token = None

    while True:
        response = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            spaces='drive',
            fields='nextPageToken, files(id, name)',
            pageToken=page_token,
            pageSize=1000
        ).execute()

        files.extend(response.get('files', []))
        page_token = response.get('nextPageToken', None)

        if page_token is None:
            break

    return files

# Télécharger un fichier depuis Google Drive et le sauvegarder dans ./<output_folder>/
def download_file(service, file_id, file_name, output_folder="data"):
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False

    while not done:
        _, done = downloader.next_chunk()

    os.makedirs(output_folder, exist_ok=True)
    file_path = os.path.join(output_folder, file_name)
    with open(file_path, 'wb') as f:
        f.write(fh.getbuffer())

# Fonction principale : télécharge les fichiers de deux dossiers Drive dans deux dossiers locaux distincts
def load_all_files_from_drive():
    # Mapping des folder_id vers les dossiers de destination
    folder_targets = {
        '1MS5J8AdY785pxf7LEZdG38bkciijlZm_': 'data/Data 24-25',
        '1PQgcChI1Lb9rAGgpHCsGnaBQtuFo6FJ8': 'data/Data 25-26',
    }

    service = authenticate_google_drive()

    for folder_id, local_dir in folder_targets.items():
        files = list_files_in_folder(service, folder_id)

        if not files:
            continue

        # Téléchargement fichier par fichier dans le dossier correspondant
        for file in files:
            download_file(service, file['id'], file['name'], output_folder=local_dir)

league_rating = {
    "Ligue 1": 82.9,
    "Ligue 2": 73.1,
    "National 1": 67.5,
    "National 2": 62.9,
    "National 3": 57.8
}

smart_goal = {
    "24-25": {
        "Gardien": [
            "J. Aymes",
            "F. Vanni"
        ],
        "Défenseur central": [
            "J. Smith",
            "H. Abderrahmane",
            "G. Pineau",
            "M. Mamadou Kamissoko"
        ],
        "Latéral": [
            "M. Fischer",
            "L. Vinci"
        ],
        "Milieu":
        [
            "C. N'Doye",
            "H. Hafidi",
            "C. Gonçalves",
            "A. N'Diaye"
        ],
        "Milieu offensif":
        [
            "T. Trinker",
            "M. Blanc"
        ],
        "Ailier":
        [
            "C. Abbas",
            "J. Mambu",
            "Alexis Gonçalves",
            "D. Mai",
            "M. Lopes"
        ],
        "Buteur":
        [
            "J. Domingues",
            "D. Segbe-Azankpo"
        ]
    },
    "25-26": {
        "Gardien": [
            "J. Aymes",
            "F. Vanni"
        ],
        "Défenseur central": [
            "J. Smith",
            "L. Gueho",
            "G. Pineau"
        ],
        "Latéral": [
            "H. Abderrahmane",
            "S. Corchia",
            "R. Sylva",
            "J. Mambu",
            "I. Umbdenstock"
        ],
        "Milieu":
        [
            "C. N'Doye",
            "H. Hafidi",
            "C. Gonçalves",
            "A. N'Diaye",
            "E. Caumont"
        ],
        "Milieu offensif":
        [
            "M. Boussaïd",
            "M. Blanc"
        ],
        "Ailier":
        [
            "C. Abbas",
            "A. Gonçalves",
            "E. Bonnaure",
            "B. Oggad",
            "M. Noc"
        ],
        "Buteur":
        [
            "S. Doumbouya",
            "B. M'Backé N'Diayé",
            "A. Fernandes",
            "R. Gerbeaud",
            "G. Morgan"
        ]
    }
}

analyse_par_poste = [
    {
        "position" : "Gardien",
        "animation_offensive": {
            "Passes": "Passes",
            "Pourcentage de passes réussies": "Passes précises / Passes",
            "Passes longues": "Passes longues",
            "Pourcentage de passes longues réussies": "Passes longues précises / Passes longues"
        },
        "animation_défensive": {
            "Buts concédés": "Buts concédés",
            "xCG": "xCG",
            "Tirs concédés": "Tirs contre",
            "Arrêts": "Arrêts",
            "Arrêts réflexes": "Arrêts réflexes",
            "Sorties": "Sorties",
            "Duels aériens": "Duels aériens",
            "Duels aériens gagnés (%)": "Duels aériens gagnés / Duels aériens"
        },
    },
    {   
        "position": "Défenseur central",
        "animation_offensive": {
            "Passes": "Passes",
            "Pourcentage de passes réussies": "Passes précises / Passes",
            "Passes en avant": "Passes en avant",
            "Pourcentage de passes en avant réussies": "Passes en avant précises / Passes en avant",
            "Passes longues": "Passes longues",
            "Pourcentage de passes longues réussies": "Passes longues précises / Passes longues",
            "Passes en profondeur": "Passes en profondeur",
            "Pourcentage de passes en profondeur réussies": "Passes en profondeur précises / Passes en profondeur",
            "xA": "xA",
            "Courses progressives": "Courses progressives",
            "Touches de balle dans la surface adverse": "Touches de balle dans la surface de réparation"
        },
        "animation_défensive": {
            "Duels défensifs": "Duels défensifs",
            "Duels défensifs gagnés (%)": "Duels défensifs gagnés / Duels défensifs",
            "Duels aériens": "Duels aériens",
            "Duels aériens gagnés (%)": "Duels aériens gagnés / Duels aériens",
            "Interceptions": "Interceptions",
            "Tacles glissés": "Tacles glissés",
            "Faute": "Faute"
        }
    },
    {
        "position" : "Latéral",
        "animation_offensive": {
            "Passes": "Passes",
            "Pourcentage de passes réussies": "Passes précises / Passes",
            "Passes en avant": "Passes en avant",
            "Pourcentage de passes en avant réussies": "Passes en avant précises / Passes en avant",
            "Passes dans 3ème tiers": "Passes dans 3ème tiers",
            "Pourcentage de passes dans tiers adverse réussies": "Passes dans 3ème tiers précises / Passes dans 3ème tiers",
            "Centres": "Centres",
            "Pourcentage de centres réussis": "Centres précis / Centres",
            "xA": "xA",
            "Courses progressives": "Courses progressives",
            "Dribbles": "Dribbles",
            "Pourcentage de dribbles réussis": "Dribbles réussis / Dribbles",
            "Fautes subies": "Fautes subies",
            "Touches de balle dans la surface adverse": "Touches de balle dans la surface de réparation",
        },
        "animation_défensive": {
            "Duels défensifs": "Duels défensifs",
            "Duels défensifs gagnés (%)": "Duels défensifs gagnés / Duels défensifs",
            "Duels aériens": "Duels aériens",
            "Duels aériens gagnés (%)": "Duels aériens gagnés / Duels aériens",
            "Interceptions": "Interceptions",
            "Tacles glissés": "Tacles glissés",
            "Faute": "Faute"
        }
    },
    {
        "position" : "Milieu",
        "animation_offensive": {
            "Passes": "Passes",
            "Pourcentage de passes réussies": "Passes précises / Passes",
            "Passes en avant": "Passes en avant",
            "Pourcentage de passes en avant réussies": "Passes en avant précises / Passes en avant",
            "Passes longues": "Passes longues",
            "Pourcentage de passes longues réussies": "Passes longues précises / Passes longues",
            "Passes en profondeur": "Passes en profondeur",
            "Pourcentage de passes en profondeur réussies": "Passes en profondeur précises / Passes en profondeur",
            "Secondes passes décisives": "Secondes passes décisives",
            "xA": "xA",
            "Courses progressives": "Courses progressives",
            "Tirs": "Tirs",
            "Pourcentage de tirs cadrés": "Tirs cadrés / Tirs",
            "xG": "xG"
        },
        "animation_défensive": {
            "Duels défensifs": "Duels défensifs",
            "Duels défensifs gagnés (%)": "Duels défensifs gagnés / Duels défensifs",
            "Duels aériens": "Duels aériens",
            "Duels aériens gagnés (%)": "Duels aériens gagnés / Duels aériens",
            "Interceptions": "Interceptions",
            "Tacles glissés": "Tacles glissés",
            "Faute": "Faute"
        }
    },
    {
        "position" : "Milieu offensif",
        "animation_offensive": {
            "Passes": "Passes",
            "Pourcentage de passes réussies": "Passes précises / Passes",
            "Passes en avant": "Passes en avant",
            "Pourcentage de passes en avant réussies": "Passes en avant précises / Passes en avant",
            "Passes longues": "Passes longues",
            "Pourcentage de passes longues réussies": "Passes longues précises / Passes longues",
            "Passes en profondeur": "Passes en profondeur",
            "Pourcentage de passes en profondeur réussies": "Passes en profondeur précises / Passes en profondeur",
            "Passes vers la surface de réparation": "Passes vers la surface de réparation",
            "Pourcentage de passes vers la surface de réparation réussies": "Passes vers la surface de réparation précises / Passes vers la surface de réparation",
            "Secondes passes décisives": "Secondes passes décisives",
            "xA": "xA",
            "Courses progressives": "Courses progressives",
            "Tirs": "Tirs",
            "Pourcentage de tirs cadrés": "Tirs cadrés / Tirs",
            "xG": "xG",
            "Touches de balle dans la surface adverse": "Touches de balle dans la surface de réparation"
        },
        "animation_défensive": {
            "Duels défensifs": "Duels défensifs",
            "Duels défensifs gagnés (%)": "Duels défensifs gagnés / Duels défensifs",
            "Interceptions": "Interceptions",
            "Faute": "Faute"
        }
    },
    {
        "position" : "Ailier",
        "animation_offensive": {
            "Passes": "Passes",
            "Pourcentage de passes réussies": "Passes précises / Passes",
            "Passes en avant": "Passes en avant",
            "Pourcentage de passes en avant réussies": "Passes en avant précises / Passes en avant",
            "Passes vers la surface de réparation": "Passes vers la surface de réparation",
            "Pourcentage de passes vers la surface de réparation réussies": "Passes vers la surface de réparation précises / Passes vers la surface de réparation",
            "Centres": "Centres",
            "Pourcentage de centres réussis": "Centres précis / Centres",
            "xA": "xA",
            "Courses progressives": "Courses progressives",
            "Dribbles": "Dribbles",
            "Pourcentage de dribbles réussis": "Dribbles réussis / Dribbles",
            "Fautes subies": "Fautes subies",
            "Tirs": "Tirs",
            "Pourcentage de tirs cadrés": "Tirs cadrés / Tirs",
            "xG": "xG",
            "Touches de balle dans la surface adverse": "Touches de balle dans la surface de réparation"
        },
        "animation_défensive": {
            "Duels défensifs": "Duels défensifs",
            "Duels défensifs gagnés (%)": "Duels défensifs gagnés / Duels défensifs",
            "Interceptions": "Interceptions",
            "Faute": "Faute"
        }
    },
    {
        "position" : "Buteur",
        "animation_offensive": {
            "Passes": "Passes",
            "Pourcentage de passes réussies": "Passes précises / Passes",
            "Passes en avant": "Passes en avant",
            "Pourcentage de passes en avant réussies": "Passes en avant précises / Passes en avant",
            "xA": "xA",
            "Courses progressives": "Courses progressives",
            "Dribbles": "Dribbles",
            "Pourcentage de dribbles réussis": "Dribbles réussis / Dribbles",
            "Tirs": "Tirs",
            "Pourcentage de tirs cadrés": "Tirs cadrés / Tirs",
            "xG": "xG",
            "Touches de balle dans la surface adverse": "Touches de balle dans la surface de réparation",
            "Duels aériens": "Duels aériens",
            "Duels aériens gagnés (%)": "Duels aériens gagnés / Duels aériens"
        },
        "animation_défensive": {
            "Duels défensifs": "Duels défensifs",
            "Duels défensifs gagnés (%)": "Duels défensifs gagnés / Duels défensifs",
            "Interceptions": "Interceptions",
            "Faute": "Faute"
        }
    }
]

metrics_by_position = [
    {
        "position": "Buteur",
        "metrics": {
            "Attaques\nréussies": "Attaques réussies par 90",
            "Buts\nhors penalty": "Buts hors penalty par 90",
            "Buts - xG": "Buts - xG",
            "Buts\n/ Tirs": "Taux de conversion but/tir",
            "Tirs cadrés\n/ Tirs": "Tirs à la cible, %",
            "Touches\ndans la surface": "Touches de balle dans la surface de réparation sur 90",
            "Ballons\nreçus": "Passes réceptionnées par 90",
            "Précision\npasses": "Passes précises, %",
            "xA": "xA par 90",
            "Passes\nclés": "Passes quasi décisives par 90",
            "Passes\navant un tir": "Passes décisives avec tir par 90",
            "Courses\nprogressives": "Courses progressives par 90",
            "Accélérations": "Accélérations par 90",
            "Duels\noffensifs": "Duels offensifs par 90",
            "Duels\noffensifs gagnés (%)": "Duels de marquage, %",
            "Duels\naériens": "Duels aériens par 90",
            "Duels\naériens gagnés (%)": "Duels aériens gagnés, %",
            "Actions déf.\nréussies": "Actions défensives réussies par 90"
        }
    },
    {
        "position": "Ailier",
        "metrics": {
            "Attaques\nréussies": "Attaques réussies par 90",
            "Buts - xG": "Buts - xG",
            "Ballons\nreçus": "Passes réceptionnées par 90",
            "Précision\npasses": "Passes précises, %",
            "xA": "xA par 90",
            "Passes\nclés": "Passes quasi décisives par 90",
            "Passes\njudicieuses": "Passes judicieuses par 90",
            "Passes\nvers la surface": "Passes vers la surface de réparation par 90",
            "Passes\ndans le tiers adverse": "Passes dans tiers adverse par 90",
            "Passes\navant un tir": "Passes décisives avec tir par 90",
            "Passes\nprogressives": "Passes progressives par 90",
            "Centres": "Centres par 90",
            "Centres\nréussis (%)": "Сentres précises, %",
            "Courses\nprogressives": "Courses progressives par 90",
            "Accélérations": "Accélérations par 90",
            "Dribbles": "Dribbles par 90",
            "Dribbles\nréussis (%)": "Dribbles réussis, %",
            "Actions déf.\nréussies": "Actions défensives réussies par 90"
        }
    },
    {
        "position": "Milieu offensif",
        "metrics": {
            "Attaques\nréussies": "Attaques réussies par 90",
            "xG": "xG par 90",
            "Ballons\nreçus": "Passes réceptionnées par 90",
            "Précision\npasses": "Passes précises, %",
            "xA": "xA par 90",
            "Passes\nclés": "Passes quasi décisives par 90",
            "Passes\njudicieuses": "Passes judicieuses par 90",
            "Passes\nvers la surface": "Passes vers la surface de réparation par 90",
            "Passes\ndans le tiers adverse": "Passes dans tiers adverse par 90",
            "Passes\navant un tir": "Passes décisives avec tir par 90",
            "Passes\nprogressives": "Passes progressives par 90",
            "Courses\nprogressives": "Courses progressives par 90",
            "Accélérations": "Accélérations par 90",
            "Dribbles": "Dribbles par 90",
            "Dribbles\nréussis (%)": "Dribbles réussis, %",
            "Duels": "Duels par 90",
            "Duels\ngagnés (%)": "Duels gagnés, %",
            "Actions déf.\nréussies": "Actions défensives réussies par 90"
        }
    },
    {
        "position": "Milieu",
        "metrics": {
            "Attaques\nréussies": "Attaques réussies par 90",
            "Ballons\nreçus": "Passes réceptionnées par 90",
            "Précision\npasses": "Passes précises, %",
            "xA": "xA par 90",
            "Passes\navant": "Passes avant par 90",
            "Passes\nclés": "Passes quasi décisives par 90",
            "Passes\ndans le tiers adverse": "Passes dans tiers adverse par 90",
            "Passes\nprogressives": "Passes progressives par 90",
            "Courses\nprogressives": "Courses progressives par 90",
            "Accélérations": "Accélérations par 90",
            "Duels\ndéfensifs": "Duels défensifs par 90",
            "Duels\ndéfensifs gagnés (%)": "Duels défensifs gagnés, %",
            "Duels\naériens": "Duels aériens par 90",
            "Duels\naériens gagnés (%)": "Duels aériens gagnés, %",
            "Tacles\nglissés": "Tacles glissés PAdj",
            "Interceptions": "Interceptions PAdj",
            "Tirs\ncontrés": "Tirs contrés par 90",
            "Actions\ndéf. réussies": "Actions défensives réussies par 90"
        }
    },
    {
        "position": "Latéral",
        "metrics": {
            "Attaques\nréussies": "Attaques réussies par 90",
            "Ballons\nreçus": "Passes réceptionnées par 90",
            "Précision\npasses": "Passes précises, %",
            "xA": "xA par 90",
            "Passes\navant": "Passes avant par 90",
            "Passes\nvers la surface": "Passes vers la surface de réparation par 90",
            "Centres": "Centres par 90",
            "Centres\nréussis (%)": "Сentres précises, %",
            "Courses\nprogressives": "Courses progressives par 90",
            "Accélérations": "Accélérations par 90",
            "Duels\ndéfensifs": "Duels défensifs par 90",
            "Duels\ndéfensifs gagnés (%)": "Duels défensifs gagnés, %",
            "Duels\naériens": "Duels aériens par 90",
            "Duels\naériens gagnés (%)": "Duels aériens gagnés, %",
            "Tacles\nglissés": "Tacles glissés PAdj",
            "Interceptions": "Interceptions PAdj",
            "Tirs\ncontrés": "Tirs contrés par 90",
            "Actions\ndéf. réussies": "Actions défensives réussies par 90"
        }
    },
    {
        "position": "Défenseur central",
        "metrics": {
            "Ballons\nreçus": "Passes réceptionnées par 90",
            "Précision\npasses": "Passes précises, %",
            "Passes\navant": "Passes avant par 90",
            "Passes\navant réussies (%)": "Passes en avant précises, %",
            "Passes\nlongues": "Passes longues par 90",
            "Passes\nlongues réussies (%)": "Longues passes précises, %",
            "Passes\nprogressives": "Passes progressives par 90",
            "Passes\nprog. réussies (%)": "Passes progressives précises, %",
            "Courses\nprogressives": "Courses progressives par 90",
            "Accélérations": "Accélérations par 90",
            "Duels\ndéfensifs": "Duels défensifs par 90",
            "Duels\ndéfensifs gagnés (%)": "Duels défensifs gagnés, %",
            "Duels\naériens": "Duels aériens par 90",
            "Duels\naériens gagnés (%)": "Duels aériens gagnés, %",
            "Tacles\nglissés": "Tacles glissés PAdj",
            "Interceptions": "Interceptions PAdj",
            "Tirs\ncontrés": "Tirs contrés par 90",
            "Actions\ndéf. réussies": "Actions défensives réussies par 90"
        }
    },
    {
        "position": "Gardien",
        "metrics": {
            "Ballons\nreçus": "Passes réceptionnées par 90",
            "Précision\npasses": "Passes précises, %",
            "Passes\ncourtes": "Passes courtes / moyennes par 90",
            "Passes\ncourtes réussies (%)": "Passes courtes / moyennes précises, %",
            "Passes\nlongues": "Passes longues par 90",
            "Passes\nlongues réussies (%)": "Longues passes précises, %",
            "Buts\nconcédés": "Buts concédés par 90",
            "xG\nconcédés": "xG contre par 90",
            "Buts\névités": "Buts évités par 90",
            "Tirs\nconcédés": "Tirs contre par 90",
            "Arrêts": "Enregistrer, %",
            "Sorties": "Sorties par 90",
            "Duels\naériens": "Duels aériens par 90",
            "Duels\naériens gagnés (%)": "Duels aériens gagnés, %"
        }
    }
]

kpi_by_position = {
    "Buteur": {
        "Finition": {
            "Buts - xG": 0.75,
            "Tirs à la cible, %": 0.15,
            "Taux de conversion but/tir": 0.1
        },
        "Apport offensif": {
            "xG par 90": 0.3,
            "Attaques réussies par 90": 0.2,
            "Touches de balle dans la surface de réparation sur 90": 0.2,
            "Tirs par 90": 0.1,
            "Centres par 90": 0.1,
            "Duels offensifs par 90": 0.05,
            "Duels de marquage, %": 0.05
        },
        "Qualité de passe": {
            "Passes intelligentes précises, %": 0.3,
            "Longues passes précises, %": 0.25,
            "Passes courtes / moyennes précises, %": 0.15,
            "Passes vers la surface de réparation précises, %": 0.1,
            "Passes dans tiers adverse précises, %": 0.08,
            "Passes progressives précises, %": 0.06,
            "Passes en profondeur précises, %": 0.06
        },
        "Vision du jeu": {
            "xA par 90": 0.25,
            "Passes quasi décisives par 90": 0.2,
            "Passes décisives avec tir par 90": 0.15,
            "Passes judicieuses par 90": 0.15,
            "Réalisations en profondeur par 90": 0.1,
            "Passes vers la surface de réparation par 90": 0.05,
            "Passes dans tiers adverse par 90": 0.04,
            "Passes progressives par 90": 0.03,
            "Passes pénétrantes par 90": 0.03
        },
        "Percussion": {
            "Courses progressives par 90": 0.3,
            "Accélérations par 90": 0.3,
            "Dribbles par 90": 0.2,
            "Dribbles réussis, %": 0.2
        },
        "Jeu aérien": {
            "Duels aériens par 90": 0.4,
            "Duels aériens gagnés, %": 0.6
        }
    },

    "Ailier": {
        "Finition": {
            "Buts - xG": 0.75,
            "Tirs à la cible, %": 0.15,
            "Taux de conversion but/tir": 0.1
        },
        "Apport offensif": {
            "xG par 90": 0.3,
            "Attaques réussies par 90": 0.2,
            "Touches de balle dans la surface de réparation sur 90": 0.2,
            "Tirs par 90": 0.1,
            "Centres par 90": 0.1,
            "Duels offensifs par 90": 0.05,
            "Duels de marquage, %": 0.05
        },
        "Qualité de passe": {
            "Сentres précises, %": 0.3,
            "Longues passes précises, %": 0.25,
            "Passes courtes / moyennes précises, %": 0.15,
            "Passes intelligentes précises, %": 0.15,
            "Passes vers la surface de réparation précises, %": 0.05,
            "Passes dans tiers adverse précises, %": 0.04,
            "Passes progressives précises, %": 0.03,
            "Passes en profondeur précises, %": 0.03
        },
        "Vision du jeu": {
            "xA par 90": 0.25,
            "Passes quasi décisives par 90": 0.2,
            "Passes décisives avec tir par 90": 0.15,
            "Passes judicieuses par 90": 0.15,
            "Réalisations en profondeur par 90": 0.1,
            "Passes vers la surface de réparation par 90": 0.05,
            "Passes dans tiers adverse par 90": 0.04,
            "Passes progressives par 90": 0.03,
            "Passes pénétrantes par 90": 0.03
        },
        "Percussion": {
            "Courses progressives par 90": 0.3,
            "Accélérations par 90": 0.3,
            "Dribbles par 90": 0.2,
            "Dribbles réussis, %": 0.2
        },
        "Jeu défensif": {
            "Actions défensives réussies par 90": 0.35,
            "Interceptions PAdj": 0.25,
            "Duels défensifs gagnés, %": 0.2,
            "Duels défensifs par 90": 0.1,
            "Tacles glissés PAdj": 0.05,
            "Tirs contrés par 90": 0.05
        }
    },

    "Milieu offensif": {
        "Finition": {
            "Buts - xG": 0.75,
            "Tirs à la cible, %": 0.15,
            "Taux de conversion but/tir": 0.1
        },
        "Apport offensif": {
            "xG par 90": 0.3,
            "Attaques réussies par 90": 0.2,
            "Touches de balle dans la surface de réparation sur 90": 0.2,
            "Tirs par 90": 0.1,
            "Centres par 90": 0.1,
            "Duels offensifs par 90": 0.05,
            "Duels de marquage, %": 0.05
        },
        "Qualité de passe": {
            "Passes intelligentes précises, %": 0.3,
            "Longues passes précises, %": 0.25,
            "Passes courtes / moyennes précises, %": 0.15,
            "Passes vers la surface de réparation précises, %": 0.1,
            "Passes dans tiers adverse précises, %": 0.08,
            "Passes progressives précises, %": 0.06,
            "Passes en profondeur précises, %": 0.06
        },
        "Vision du jeu": {
            "xA par 90": 0.25,
            "Passes quasi décisives par 90": 0.2,
            "Passes décisives avec tir par 90": 0.15,
            "Passes judicieuses par 90": 0.15,
            "Réalisations en profondeur par 90": 0.1,
            "Passes vers la surface de réparation par 90": 0.05,
            "Passes dans tiers adverse par 90": 0.04,
            "Passes progressives par 90": 0.03,
            "Passes pénétrantes par 90": 0.03
        },
        "Percussion": {
            "Courses progressives par 90": 0.3,
            "Accélérations par 90": 0.3,
            "Dribbles par 90": 0.2,
            "Dribbles réussis, %": 0.2
        },
        "Jeu défensif": {
            "Actions défensives réussies par 90": 0.35,
            "Interceptions PAdj": 0.25,
            "Duels défensifs gagnés, %": 0.2,
            "Duels défensifs par 90": 0.1,
            "Tacles glissés PAdj": 0.05,
            "Tirs contrés par 90": 0.05
        }
    },

    "Milieu": {
        "Apport offensif": {
            "xG par 90": 0.3,
            "Attaques réussies par 90": 0.2,
            "Touches de balle dans la surface de réparation sur 90": 0.2,
            "Tirs par 90": 0.1,
            "Centres par 90": 0.1,
            "Duels offensifs par 90": 0.05,
            "Duels de marquage, %": 0.05
        },
        "Qualité de passe": {
            "Passes intelligentes précises, %": 0.3,
            "Longues passes précises, %": 0.25,
            "Passes courtes / moyennes précises, %": 0.15,
            "Passes vers la surface de réparation précises, %": 0.1,
            "Passes dans tiers adverse précises, %": 0.08,
            "Passes progressives précises, %": 0.06,
            "Passes en profondeur précises, %": 0.06
        },
        "Vision du jeu": {
            "xA par 90": 0.25,
            "Passes quasi décisives par 90": 0.2,
            "Passes décisives avec tir par 90": 0.15,
            "Passes judicieuses par 90": 0.15,
            "Réalisations en profondeur par 90": 0.1,
            "Passes vers la surface de réparation par 90": 0.05,
            "Passes dans tiers adverse par 90": 0.04,
            "Passes progressives par 90": 0.03,
            "Passes pénétrantes par 90": 0.03
        },
        "Percussion": {
            "Courses progressives par 90": 0.3,
            "Accélérations par 90": 0.3,
            "Dribbles par 90": 0.2,
            "Dribbles réussis, %": 0.2
        },
        "Jeu défensif": {
            "Actions défensives réussies par 90": 0.35,
            "Interceptions PAdj": 0.25,
            "Duels défensifs gagnés, %": 0.2,
            "Duels défensifs par 90": 0.1,
            "Tacles glissés PAdj": 0.05,
            "Tirs contrés par 90": 0.05
        },
        "Jeu aérien": {
            "Duels aériens par 90": 0.4,
            "Duels aériens gagnés, %": 0.6
        }
    },

    "Latéral": {
        "Apport offensif": {
            "xG par 90": 0.3,
            "Attaques réussies par 90": 0.2,
            "Touches de balle dans la surface de réparation sur 90": 0.2,
            "Tirs par 90": 0.1,
            "Centres par 90": 0.1,
            "Duels offensifs par 90": 0.05,
            "Duels de marquage, %": 0.05
        },
        "Qualité de passe": {
            "Сentres précises, %": 0.3,
            "Longues passes précises, %": 0.25,
            "Passes courtes / moyennes précises, %": 0.15,
            "Passes intelligentes précises, %": 0.15,
            "Passes vers la surface de réparation précises, %": 0.05,
            "Passes dans tiers adverse précises, %": 0.04,
            "Passes progressives précises, %": 0.03,
            "Passes en profondeur précises, %": 0.03
        },
        "Vision du jeu": {
            "xA par 90": 0.25,
            "Passes quasi décisives par 90": 0.2,
            "Passes décisives avec tir par 90": 0.15,
            "Passes judicieuses par 90": 0.15,
            "Réalisations en profondeur par 90": 0.1,
            "Passes vers la surface de réparation par 90": 0.05,
            "Passes dans tiers adverse par 90": 0.04,
            "Passes progressives par 90": 0.03,
            "Passes pénétrantes par 90": 0.03
        },
        "Percussion": {
            "Courses progressives par 90": 0.3,
            "Accélérations par 90": 0.3,
            "Dribbles par 90": 0.2,
            "Dribbles réussis, %": 0.2
        },
        "Jeu défensif": {
            "Actions défensives réussies par 90": 0.35,
            "Interceptions PAdj": 0.25,
            "Duels défensifs gagnés, %": 0.2,
            "Duels défensifs par 90": 0.1,
            "Tacles glissés PAdj": 0.05,
            "Tirs contrés par 90": 0.05
        },
        "Jeu aérien": {
            "Duels aériens par 90": 0.4,
            "Duels aériens gagnés, %": 0.6
        }
    },

    "Défenseur central": {
        "Discipline": {
            "Fautes par 90": 0.5,
            "Cartons jaunes par 90": 0.3,
            "Cartons rouges par 90": 0.2
        },
        "Qualité de passe": {
            "Passes intelligentes précises, %": 0.3,
            "Longues passes précises, %": 0.25,
            "Passes courtes / moyennes précises, %": 0.15,
            "Passes vers la surface de réparation précises, %": 0.1,
            "Passes dans tiers adverse précises, %": 0.08,
            "Passes progressives précises, %": 0.06,
            "Passes en profondeur précises, %": 0.06
        },
        "Vision du jeu": {
            "xA par 90": 0.25,
            "Passes quasi décisives par 90": 0.2,
            "Passes décisives avec tir par 90": 0.15,
            "Passes judicieuses par 90": 0.15,
            "Réalisations en profondeur par 90": 0.1,
            "Passes vers la surface de réparation par 90": 0.05,
            "Passes dans tiers adverse par 90": 0.04,
            "Passes progressives par 90": 0.03,
            "Passes pénétrantes par 90": 0.03
        },
        "Percussion": {
            "Courses progressives par 90": 0.3,
            "Accélérations par 90": 0.3,
            "Dribbles par 90": 0.2,
            "Dribbles réussis, %": 0.2
        },
        "Jeu défensif": {
            "Actions défensives réussies par 90": 0.35,
            "Interceptions PAdj": 0.25,
            "Duels défensifs gagnés, %": 0.2,
            "Duels défensifs par 90": 0.1,
            "Tacles glissés PAdj": 0.05,
            "Tirs contrés par 90": 0.05
        },
        "Jeu aérien": {
            "Duels aériens par 90": 0.4,
            "Duels aériens gagnés, %": 0.6
        }
    },

    "Gardien": {
        "Participe au jeu": {
            "Passes réceptionnées par 90": 1
        },
        "Jeu court": {
            "Passes courtes / moyennes par 90": 0.5,
            "Passes courtes / moyennes précises, %": 0.5,
        },
        "Jeu long": {
            "Passes longues par 90": 0.5,
            "Longues passes précises, %": 0.5
        },
        "Sortie": {
            "Sorties par 90": 1
        },
        "Présence aérienne": {
            "Duels aériens par 90": 0.4,
            "Duels aériens gagnés, %": 0.6
        },
        "Efficacité sur sa ligne": {
            "Buts évités par 90": 0.75,
            "Enregistrer, %": 0.25
        }
    }
}

kpi_coefficients_by_position = {
    "Buteur": {
        "Finition": 5,
        "Apport offensif": 4,
        "Qualité de passe": 2,
        "Vision du jeu": 2,
        "Percussion": 1,
        "Jeu aérien": 1
    },
    "Ailier": {
        "Finition": 3,
        "Apport offensif": 4,
        "Qualité de passe": 3,
        "Vision du jeu": 5,
        "Percussion": 5,
        "Jeu défensif": 1
    },
    "Milieu offensif": {
        "Finition": 2,
        "Apport offensif": 3,
        "Qualité de passe": 4,
        "Vision du jeu": 5,
        "Percussion": 2,
        "Jeu défensif": 1
    },
    "Milieu": {
        "Apport offensif": 1,
        "Qualité de passe": 3,
        "Vision du jeu": 3,
        "Percussion": 1,
        "Jeu défensif": 4,
        "Jeu aérien": 4
    },
    "Latéral": {
        "Apport offensif": 4,
        "Qualité de passe": 2,
        "Vision du jeu": 2,
        "Percussion": 4,
        "Jeu défensif": 4,
        "Jeu aérien": 1
    },
    "Défenseur central": {
        "Discipline": 1,
        "Qualité de passe": 2,
        "Vision du jeu": 1,
        "Percussion": 1,
        "Jeu défensif": 5,
        "Jeu aérien": 5
    },
    "Gardien": {
        "Participe au jeu": 1,
        "Jeu court": 1,
        "Jeu long": 2,
        "Sortie": 1,
        "Présence aérienne": 3,
        "Efficacité sur sa ligne": 6
    }
}

kpi_coefficients_by_role = {
    "Buteur": {
        "Attaquant de profondeur": {
            "Finition": 5,
            "Apport offensif": 4,
            "Qualité de passe": 1,
            "Vision du jeu": 1,
            "Percussion": 5,
            "Jeu aérien": 1
        },
        "Faux neuf": {
            "Finition": 3,
            "Apport offensif": 2,
            "Qualité de passe": 4,
            "Vision du jeu": 5,
            "Percussion": 2,
            "Jeu aérien": 1
        },
        "Renard des surfaces": {
            "Finition": 6,
            "Apport offensif": 3,
            "Qualité de passe": 1,
            "Vision du jeu": 1,
            "Percussion": 1,
            "Jeu aérien": 3
        },
        "Attaquant pivot": {
            "Finition": 4,
            "Apport offensif": 3,
            "Qualité de passe": 2,
            "Vision du jeu": 1,
            "Percussion": 1,
            "Jeu aérien": 6
        }
    },
    "Ailier": {
        "Ailier percutant": {
            "Finition": 2,
            "Apport offensif": 4,
            "Qualité de passe": 2,
            "Vision du jeu": 3,
            "Percussion": 5,
            "Jeu défensif": 1
        },
        "Ailier créateur": {
            "Finition": 3,
            "Apport offensif": 4,
            "Qualité de passe": 4,
            "Vision du jeu": 5,
            "Percussion": 2,
            "Jeu défensif": 1
        }
    },
    "Milieu offensif": {
        "Milieu offensif": {
            "Finition": 2,
            "Apport offensif": 3,
            "Qualité de passe": 4,
            "Vision du jeu": 5,
            "Percussion": 2,
            "Jeu défensif": 1
        }
    },
    "Milieu": {
        "Milieu défensif": {
            "Apport offensif": 1,
            "Qualité de passe": 2,
            "Vision du jeu": 1,
            "Percussion": 1,
            "Jeu défensif": 5,
            "Jeu aérien": 5
        },
        "Milieu relayeur": {
            "Apport offensif": 2,
            "Qualité de passe": 3,
            "Vision du jeu": 2,
            "Percussion": 2,
            "Jeu défensif": 4,
            "Jeu aérien": 3
        },
        "Milieu créateur": {
            "Apport offensif": 2,
            "Qualité de passe": 5,
            "Vision du jeu": 5,
            "Percussion": 1,
            "Jeu défensif": 1,
            "Jeu aérien": 1
        },
        "Box-to-box": {
            "Apport offensif": 4,
            "Qualité de passe": 2,
            "Vision du jeu": 2,
            "Percussion": 5,
            "Jeu défensif": 4,
            "Jeu aérien": 1
        }
    },
    "Latéral": {
        "Latéral offensif": {
            "Apport offensif": 6,
            "Qualité de passe": 4,
            "Vision du jeu": 2,
            "Percussion": 4,
            "Jeu défensif": 3,
            "Jeu aérien": 1
        },
        "Latéral défensif": {
            "Apport offensif": 2,
            "Qualité de passe": 2,
            "Vision du jeu": 1,
            "Percussion": 1,
            "Jeu défensif": 5,
            "Jeu aérien": 2
        }
    },
    "Défenseur central": {
        "Défenseur stoppeur": {
            "Discipline": 1,
            "Qualité de passe": 1,
            "Vision du jeu": 1,
            "Percussion": 1,
            "Jeu défensif": 6,
            "Jeu aérien": 6
        },
        "Défenseur relanceur": {
            "Discipline": 1,
            "Qualité de passe": 5,
            "Vision du jeu": 5,
            "Percussion": 1,
            "Jeu défensif": 3,
            "Jeu aérien": 3
        }
    },
    "Gardien": {
        "Gardien de ligne": {
            "Participe au jeu": 1,
            "Jeu court": 2,
            "Jeu long": 2,
            "Sortie": 1,
            "Présence aérienne": 2,
            "Efficacité sur sa ligne": 5
        },
        "Gardien libéro": {
            "Participe au jeu": 5,
            "Jeu court": 2,
            "Jeu long": 2,
            "Sortie": 3,
            "Présence aérienne": 3,
            "Efficacité sur sa ligne": 5
        }
  }
}

metrics_x_y = {
    "Apport offensif": {
        "metrics": ["xG par 90", "xA par 90"],
        "names": ["xG par 90", "xA par 90"],
        "descriptions": [
            "Se procure peu d'occasions<br>mais crée en crée beaucoup",
            "Se procure beaucoup d'occasions<br>et crée en crée beaucoup",
            "Se procure peu d'occasions<br>et crée en crée peu",
            "Se procure beaucoup d'occasions<br>mais crée en crée peu"
        ]
    },
    "Finition": {
        "metrics": ["xG par 90", "Buts par 90"],
        "names": ["xG par 90", "Buts par 90"],
        "descriptions": [
            "Se procure peu d'occasions<br>mais marque beaucoup",
            "Se procure beaucoup d'occasions<br>et marque beaucoup",
            "Se procure peu d'occasions<br>et marque peu",
            "Se procure beaucoup d'occasions<br>mais marque peu"
        ]
    },
    "Apport par la passe": {
        "metrics": ["Passes judicieuses par 90", "Passes intelligentes précises, %"],
        "names": ["Passes judicieuses par 90", "Passes judicieuses réussies, %"],
        "descriptions": [
            "Tente peu de passes<br>judicieuses mais<br>en réussit beaucoup",
            "Tente beaucoup de passes<br>judicieuses et<br>en réussit beaucoup",
            "Tente peu de passes<br>judicieuses et<br>en réussit peu",
            "Tente beaucoup de passes<br>judicieuses mais<br>en réussit peu"
        ]
    },
    "Progression du ballon": {
        "metrics": ["Courses progressives par 90", "Passes progressives par 90"],
        "names": ["Courses progressives par 90", "Passes progressives par 90"],
        "descriptions": [
            "Progresse peu par la course<br>mais beaucoup par la passe",
            "Progresse beaucoup par la course<br>et par la passe",
            "Progresse peu par la course<br>et par la passe",
            "Progresse beaucoup par la course<br>mais peu par la passe"
        ]
    },
    "Dribble": {
        "metrics": ["Dribbles par 90", "Dribbles réussis, %"],
        "names": ["Dribbles par 90", "Dribbles réussis, %"],
        "descriptions": [
            "Dribble peu<br>mais réussit beaucoup",
            "Dribble beaucoup<br>et réussit beaucoup",
            "Dribble peu<br>et réussit peu",
            "Dribble beaucoup<br>mais réussit peu"
        ]
    },
    "Qualité de centre": {
        "metrics": ["Centres par 90", "Сentres précises, %"],
        "names": ["Centres par 90", "Centres réussis, %"],
        "descriptions": [
            "Centre peu<br>mais en réussit beaucoup",
            "Centre beaucoup<br>et en réussit beaucoup",
            "Centre peu<br>et en réussit peu",
            "Centre beaucoup<br>mais en réussit peu"
        ]
    },
    "Apport défensif/offensif": {
        "metrics": ["Actions défensives réussies par 90", "Attaques réussies par 90"],
        "names": ["Actions défensives réussies par 90", "Attaques réussies par 90"],
        "descriptions": [
            "Apporte peu défensivement<br>mais beaucoup offensivement",
            "Apporte beaucoup défensivement<br>et offensivement",
            "Apporte peu défensivement<br>et offensivement",
            "Apporte beaucoup défensivement<br>mais peu offensivement"
        ]
    },
    "Duel": {
        "metrics": ["Duels par 90", "Duels gagnés, %"],
        "names": ["Duels par 90", "Duels gagnés, %"],
        "descriptions": [
            "Joue peu de duels<br>mais en remporte beaucoup",
            "Joue beaucoup de duels<br>et en remporte beaucoup",
            "Joue peu de duels<br>et en remporte peu",
            "Joue beaucoup de duels<br>mais en remporte peu"
        ]
    },
    "Duel offensif": {
        "metrics": ["Duels offensifs par 90", "Duels de marquage, %"],
        "names": ["Duels offensifs par 90", "Duels offensifs gagnés, %"],
        "descriptions": [
            "Joue peu de duels offensifs<br>mais en remporte beaucoup",
            "Joue beaucoup de duels offensifs<br>et en remporte beaucoup",
            "Joue peu de duels offensifs<br>et en remporte peu",
            "Joue beaucoup de duels offensifs<br>mais en remporte peu"
        ]
    },
    "Duel défensif": {
        "metrics": ["Duels défensifs par 90", "Duels défensifs gagnés, %"],
        "names": ["Duels défensifs par 90", "Duels défensifs gagnés, %"],
        "descriptions": [
            "Joue peu de duels défensifs<br>mais en remporte beaucoup",
            "Joue beaucoup de duels défensifs<br>et en remporte beaucoup",
            "Joue peu de duels défensifs<br>et en remporte peu",
            "Joue beaucoup de duels défensifs<br>mais en remporte peu"
        ]
    },
    "Duel aérien": {
        "metrics": ["Duels aériens par 90", "Duels aériens gagnés, %"],
        "names": ["Duels aériens par 90", "Duels aériens gagnés, %"],
        "descriptions": [
            "Joue peu de duels aériens<br>mais en remporte beaucoup",
            "Joue beaucoup de duels aériens<br>et en remporte beaucoup",
            "Joue peu de duels aériens<br>et en remporte peu",
            "Joue beaucoup de duels aériens<br>mais en remporte peu"
        ]
    },
    "Buts évités": {
        "metrics": ["xG contre par 90", "Buts concédés par 90"],
        "names": ["xG contre par 90", "Buts concédés par 90"],
        "descriptions": [
            "Concède peu d'occasions<br>mais encaise beaucoup de buts",
            "Concède beaucoup d'occasions<br>et encaise beaucoup de buts",
            "Concède peu d'occasions<br>et encaise peu de buts",
            "Concède beaucoup d'occasions<br>mais encaise peu de buts",
        ]
    }
}

indicateurs_general = [
    'Buts',
    'xG',
    'Possession %',
    'Corners',
    'Coups francs'
]

indicateurs_general_moyens = [
    'Buts',
    'xG',
    'Buts concédés',
    'Possession %',
    'Corners',
    'Coups francs'
]

indicateurs_attaques = [
    'Tirs',
    'Tirs cadrés',
    'Tirs ext. surface',
    'Distance moyenne de tir',
    'Duels offensifs gagnés %',
    'Attaques positionnelles',
    'Contre-attaques',
    'Entrées surface',
    'Touches de balle surface'
]

indicateurs_defense = [
    'Duels défensifs gagnés %',
    'Tacles glissés réussis %',
    'Interceptions',
    'Dégagements',
    'Fautes'
]

indicateurs_defense_moyens = [
    'Tirs contre',
    'Tirs contre cadrés',
    'Duels défensifs gagnés %',
    'Tacles glissés réussis %',
    'Interceptions',
    'Dégagements',
    'Fautes'
]

indicateurs_passes = [
    'Rythme du match',
    'Passes',
    'Passes précises',
    'Passes avant précises',
    'Passes longues précises',
    'Passes 3e tiers précises',
    'Passes progressives précises',
    'Passes astucieuses précises',
    'Passes par possession',
    'Longueur moyenne des passes',
    'Centres',
    'Centres précis'
]

indicateurs_pressing = [
    'PPDA',
    'Récupérations élevé',
    'Récupérations moyen',
    'Pertes bas'
]

points_forts = {
    "Duels par 90": "Participe à beaucoup de duels",
    "Duels gagnés, %": "Gagne un fort pourcentage de ses duels",
    "Actions défensives réussies par 90": "Réalise beaucoup d'actions défensives réussies",
    "Duels défensifs par 90": "Participe à beaucoup de duels défensifs",
    "Duels défensifs gagnés, %": "Gagne un fort pourcentage de ses duels défensifs",
    "Duels aériens par 90": "Participe à beaucoup de duels aériens",
    "Duels aériens gagnés, %": "Gagne un fort pourcentage de ses duels aériens",
    "Tacles glissés PAdj": "Réalise beaucoup de tacles glissés",
    "Tirs contrés par 90": "Contre beaucoup de tirs",
    "Interceptions PAdj": "Intercepte beaucoup le ballon",
    "Fautes par 90": "Commets peu de fautes",
    "Cartons jaunes par 90": "Reçoit peu de cartons jaunes",
    "Cartons rouges par 90": "Reçoit peu de cartons rouges",
    "Attaques réussies par 90": "Réalise beaucoup d'attaques réussies",
    "Buts par 90": "Marque beaucoup",
    "Buts hors penalty par 90": "Marque beaucoup hors penalty",
    "xG par 90": "Se crée beaucoup d'occasions",
    "Buts de la tête par 90": "Marque beaucoup de la tête",
    "Tirs par 90": "Tire beaucoup",
    "Tirs à la cible, %": "Cadre un fort pourcentage de ses tirs",
    "Taux de conversion but/tir": "Convertit bien ses tirs en buts",
    "Passes décisives par 90": "Effectue beaucoup de passes décisives",
    "Centres par 90": "Centre beaucoup",
    "Сentres précises, %": "Précis dans ses centres",
    "Centres du flanc gauche par 90": "Centre beaucoup depuis le flanc gauche",
    "Centres du flanc gauche précises, %": "Précis dans ses centres depuis le flanc gauche",
    "Centres du flanc droit par 90": "Centre beaucoup depuis le flanc droit",
    "Centres du flanc droit précises, %": "Précis dans ses centres depuis le flanc droit",
    "Centres dans la surface de but par 90": "Centre beaucoup dans la surface",
    "Dribbles par 90": "Dribble beaucoup",
    "Dribbles réussis, %": "Réussit un fort pourcentage de dribbles",
    "Duels offensifs par 90": "Participe à beaucoup de duels offensifs",
    "Duels de marquage, %": "Gagne un fort pourcentage de ses duels offensifs",
    "Touches de balle dans la surface de réparation sur 90": "Touche beaucoup de ballons dans la surface",
    "Courses progressives par 90": "Effectue beaucoup des courses progressives",
    "Accélérations par 90": "Accélère beaucoup",
    "Passes réceptionnées par 90": "Reçoit beaucoup des passes",
    "Longues passes réceptionnées par 90": "Reçoit beaucoup des longues passes",
    "Fautes subies par 90": "Obtient beaucoup des fautes",
    "Passes par 90": "Effectue beaucoup de passes",
    "Passes précises, %": "Passe avec précision",
    "Passes avant par 90": "Effectue beaucoup de passes vers l'avant",
    "Passes en avant précises, %": "Précis dans ses passes vers l'avant",
    "Passes arrière par 90": "Effectue beaucoup de passes vers l'arrière",
    "Passes arrière précises, %": "Précis dans ses passes vers l'arrière",
    "Passes latérales par 90": "Effectue beaucoup de passes latérales",
    "Passes latérales précises, %": "Précis dans ses passes latérales",
    "Passes courtes / moyennes par 90": "Effectue beaucoup de passes courtes/moyennes",
    "Passes courtes / moyennes précises, %": "Précis dans ses passes courtes/moyennes",
    "Passes longues par 90": "Effectue beaucoup de passes longues",
    "Longues passes précises, %": "Précis dans ses passes longues",
    "xA par 90": "Crée beaucoup d'occasions",
    "Passes décisives avec tir par 90": "Effectue beaucoup la dernière passe avant un tir",
    "Secondes passes décisives par 90": "Participe beaucoup à l'avant-dernière passe",
    "Troisièmes passes décisives par 90": "Contribue beaucoup à la phase de préparation",
    "Passes judicieuses par 90": "Effectue beaucoup de passes intelligentes",
    "Passes intelligentes précises, %": "Précis dans ses passes intelligentes",
    "Passes quasi décisives par 90": "Effectue beaucoup de passes dangereuses",
    "Passes dans tiers adverse par 90": "Effectue beaucoup de passes dans le dernier tiers adverse",
    "Passes dans tiers adverse précises, %": "Précis dans ses passes dans le dernier tiers",
    "Passes vers la surface de réparation par 90": "Effectue beaucoup de passes vers la surface",
    "Passes vers la surface de réparation précises, %": "Précis dans ses passes vers la surface",
    "Passes pénétrantes par 90": "Effectue beaucoup de passes pénétrantes",
    "Passes en profondeur précises, %": "Précis dans ses passes en profondeur",
    "Réalisations en profondeur par 90": "Effectue beaucoup de passes en profondeur",
    "Centres en profondeur, par 90": "Centre beaucoup en profondeur",
    "Passes progressives par 90": "Effectue beaucoup de passes progressives",
    "Passes progressives précises, %": "Précis dans ses passes progressives",
    "Transformation des penalties, %": "Transforme un fort pourcentage de penalties",
    "Buts - xG": "Marque plus que prévu par ses xG"
}

points_faibles = {
    "Duels par 90": "Participe à peu de duels",
    "Duels gagnés, %": "Gagne un faible pourcentage de ses duels",
    "Actions défensives réussies par 90": "Réalise peu d'actions défensives réussies",
    "Duels défensifs par 90": "Participe à peu de duels défensifs",
    "Duels défensifs gagnés, %": "Gagne un faible pourcentage de ses duels défensifs",
    "Duels aériens par 90": "Participe à peu de duels aériens",
    "Duels aériens gagnés, %": "Gagne un faible pourcentage de ses duels aériens",
    "Tacles glissés PAdj": "Réalise peu de tacles glissés",
    "Tirs contrés par 90": "Contre peu de tirs",
    "Interceptions PAdj": "Intercepte peu le ballon",
    "Fautes par 90": "Commets beaucoup de fautes",
    "Cartons jaunes par 90": "Reçoit beaucoup de cartons jaunes",
    "Cartons rouges par 90": "Reçoit beaucoup de cartons rouges",
    "Attaques réussies par 90": "Réalise peu d'attaques réussies",
    "Buts par 90": "Marque peu",
    "Buts hors penalty par 90": "Marque peu hors penalty",
    "xG par 90": "Se crée peu d'occasions",
    "Buts de la tête par 90": "Marque peu de la tête",
    "Tirs par 90": "Tire peu",
    "Tirs à la cible, %": "Cadre un faible pourcentage de ses tirs",
    "Taux de conversion but/tir": "Convertit mal ses tirs en buts",
    "Passes décisives par 90": "Effectue peu de passes décisives",
    "Centres par 90": "Centre peu",
    "Сentres précises, %": "Imprécis dans ses centres",
    "Centres du flanc gauche par 90": "Centre peu depuis le flanc gauche",
    "Centres du flanc gauche précises, %": "Imprécis dans ses centres depuis le flanc gauche",
    "Centres du flanc droit par 90": "Centre peu depuis le flanc droit",
    "Centres du flanc droit précises, %": "Imprécis dans ses centres depuis le flanc droit",
    "Centres dans la surface de but par 90": "Centre peu dans la surface",
    "Dribbles par 90": "Dribble peu",
    "Dribbles réussis, %": "Réussit un faible pourcentage de dribbles",
    "Duels offensifs par 90": "Participe à peu de duels offensifs",
    "Duels de marquage, %": "Gagne un faible pourcentage de ses duels offensifs",
    "Touches de balle dans la surface de réparation sur 90": "Touche peu de ballons dans la surface",
    "Courses progressives par 90": "Effectue peu de courses progressives",
    "Accélérations par 90": "Accélère peu",
    "Passes réceptionnées par 90": "Reçoit peu de passes",
    "Longues passes réceptionnées par 90": "Reçoit peu de longues passes",
    "Fautes subies par 90": "Obtient peu de fautes",
    "Passes par 90": "Effectue peu de passes",
    "Passes précises, %": "Passe avec imprécision",
    "Passes avant par 90": "Effectue peu de passes vers l'avant",
    "Passes en avant précises, %": "Imprécis dans ses passes vers l'avant",
    "Passes arrière par 90": "Effectue peu de passes vers l'arrière",
    "Passes arrière précises, %": "Imprécis dans ses passes vers l'arrière",
    "Passes latérales par 90": "Effectue peu de passes latérales",
    "Passes latérales précises, %": "Imprécis dans ses passes latérales",
    "Passes courtes / moyennes par 90": "Effectue peu de passes courtes/moyennes",
    "Passes courtes / moyennes précises, %": "Imprécis dans ses passes courtes/moyennes",
    "Passes longues par 90": "Effectue peu de passes longues",
    "Longues passes précises, %": "Imprécis dans ses passes longues",
    "xA par 90": "Crée peu d'occasions",
    "Passes décisives avec tir par 90": "Effectue rarement la dernière passe avant un tir",
    "Secondes passes décisives par 90": "Participe peu à l'avant-dernière passe",
    "Troisièmes passes décisives par 90": "Contribue peu à la phase de préparation",
    "Passes judicieuses par 90": "Effectue peu de passes intelligentes",
    "Passes intelligentes précises, %": "Imprécis dans ses passes intelligentes",
    "Passes quasi décisives par 90": "Effectue peu de passes dangereuses",
    "Passes dans tiers adverse par 90": "Effectue peu de passes dans le dernier tiers adverse",
    "Passes dans tiers adverse précises, %": "Imprécis dans ses passes dans le dernier tiers",
    "Passes vers la surface de réparation par 90": "Effectue peu de passes vers la surface",
    "Passes vers la surface de réparation précises, %": "Imprécis dans ses passes vers la surface",
    "Passes pénétrantes par 90": "Effectue peu de passes pénétrantes",
    "Passes en profondeur précises, %": "Imprécis dans ses passes en profondeur",
    "Réalisations en profondeur par 90": "Effectue peu de passes en profondeur",
    "Centres en profondeur, par 90": "Centre peu en profondeur",
    "Passes progressives par 90": "Effectue peu de passes progressives",
    "Passes progressives précises, %": "Imprécis dans ses passes progressives",
    "Transformation des penalties, %": "Transforme un faible pourcentage de penalties",
    "Buts - xG": "Marque moins que prévu par ses xG"
}

métriques_par_catégorie = {
    "Général": [
        "Équipe", "Équipe dans la période sélectionnée", "Compétition", "Poste", "Place",
        "Âge", "Valeur sur le marché", "Contrat expiration", "Matchs joués", "Minutes jouées",
        "Buts", "xG", "Passes décisives", "xA", "Duels par 90", "Duels gagnés, %",
        "Pays de naissance", "Passeport pays", "Pied", "Taille", "Poids", "Sur prêt"
    ],
    "Attaque": [
        "Attaques réussies par 90", "Buts", "Buts par 90", "Buts hors penalty",
        "Buts hors penalty par 90", "xG", "xG par 90", "Buts de la tête", "Buts de la tête par 90",
        "Tir", "Tirs par 90", "Tirs à la cible, %", "Taux de conversion but/tir",
        "Passes décisives", "Passes décisives par 90", "Centres par 90", "Сentres précises, %",
        "Centres du flanc gauche par 90", "Centres du flanc gauche précises, %",
        "Centres du flanc droit par 90", "Centres du flanc droit précises, %",
        "Centres dans la surface de but par 90", "Dribbles par 90", "Dribbles réussis, %",
        "Duels offensifs par 90", "Duels de marquage, %", "Touches de balle dans la surface de réparation sur 90",
        "Courses progressives par 90", "Accélérations par 90", "Passes réceptionnées par 90",
        "Longues passes réceptionnées par 90", "Fautes subies par 90"
    ],
    "Passe": [
        "Passes par 90", "Passes précises, %", "Passes avant par 90", "Passes en avant précises, %",
        "Passes arrière par 90", "Passes arrière précises, %", "Passes latérales par 90",
        "Passes latérales précises, %", "Passes courtes / moyennes par 90",
        "Passes courtes / moyennes précises, %", "Passes longues par 90", "Longues passes précises, %",
        "Longueur moyenne des passes, m", "Longueur moyenne des passes longues, m"
    ],
    "Passe clé": [
        "xA", "xA par 90", "Passes décisives", "Passes décisives par 90",
        "Passes décisives avec tir par 90", "Secondes passes décisives par 90",
        "Troisièmes passes décisives par 90", "Passes judicieuses par 90",
        "Passes intelligentes précises, %", "Passes quasi décisives par 90",
        "Passes dans tiers adverse par 90", "Passes dans tiers adverse précises, %",
        "Passes vers la surface de réparation par 90", "Passes vers la surface de réparation précises, %",
        "Passes pénétrantes par 90", "Passes en profondeur précises, %",
        "Réalisations en profondeur par 90", "Centres en profondeur, par 90",
        "Passes progressives par 90", "Passes progressives précises, %"
    ],
    "Défense": [
        "Actions défensives réussies par 90", "Duels défensifs par 90", "Duels défensifs gagnés, %",
        "Duels aériens par 90", "Duels aériens gagnés, %", "Tacles glissés par 90",
        "Tacles glissés PAdj", "Tirs contrés par 90", "Interceptions par 90", "Interceptions PAdj",
        "Fautes par 90", "Cartons jaunes", "Cartons jaunes par 90", "Cartons rouges", "Cartons rouges par 90"
    ],
    "CPA": [
        "Coups francs par 90", "Coups francs directs par 90", "Coups francs directs à la cible, %",
        "Corners par 90", "Penalties pris", "Transformation des penalties, %"
    ]
}

def read_with_competition(filepath):
    # Extrait la compétition depuis le nom du fichier
    competition = filepath.split('/')[-1].split(' - ')[0].strip()

    # Extrait le poste depuis le nom du fichier
    poste = filepath.split('/')[-1].split(' - ')[1].split('.')[0].strip()
    
    # Lecture du fichier
    df = pd.read_excel(filepath)

    # Ajout de la colonne "Compétition" à la 4e position
    df.insert(3, 'Compétition', competition)

    # Ajout de la colonne "Poste" à la 5e position
    df.insert(4, 'Poste', poste)

    info_col = df['Joueur'] + ' - ' + df['Équipe dans la période sélectionnée'] + ' (' + df['Compétition'] + ')'
    df.insert(1, 'Joueur + Information', info_col)

    return df

def collect_collective_data(équipe):
    # Chargement des données
    df_collective = pd.read_excel(f"data/Data {st.session_state['saison']}/Team Stats {équipe}.xlsx")

    # Suppression des deux premières lignes
    df_collective = df_collective.drop([0, 1]).reset_index(drop=True)

    colonnes = [
        'Date', 'Match', 'Compétition', 'Championnat', 'Équipe', 'Projet',
        'Buts', 'xG',
        'Tirs', 'Tirs cadrés',
        'Tirs cadrés %',
        'Passes', 'Passes précises',
        'Passes précises %',
        'Possession %',
        
        'Pertes', 'Pertes bas', 'Pertes moyen', 'Pertes élevé',
        'Récupérations', 'Récupérations bas', 'Récupérations moyen', 'Récupérations élevé',
        
        'Duels', 'Duels gagnés', 'Duels gagnés %',
        
        'Tirs ext. surface', 'Tirs cadrés ext. surface', 'Tirs cadrés ext. surface %',
        
        'Attaques positionnelles', 'Attaques positionnelles avec tirs', 'Attaques positionnelles %',
        'Contre-attaques', 'Contre-attaques avec tirs', 'Contre-attaques %',
        'CPA', 'CPA avec tirs', 'CPA %',
        'Corners', 'Corners avec tirs', 'Corners %',
        'Coups francs', 'Coups francs avec tirs', 'Coups francs %',
        'Penaltys', 'Penaltys convertis', 'Penaltys %',
        
        'Centres', 'Centres précis', 'Centres précis %',
        'Centres en profondeur terminés',
        'Passes en profondeur terminées',
        
        'Entrées surface', 'Entrées surface par la course', 'Entrées surface par le centre',
        'Touches de balle surface',
        
        'Duels offensifs', 'Duels offensifs gagnés', 'Duels offensifs gagnés %',
        
        'Hors-jeu',
        
        'Buts concédés', 'Tirs contre', 'Tirs contre cadrés', 'Tirs contre cadrés %',
        
        'Duels défensifs', 'Duels défensifs gagnés', 'Duels défensifs gagnés %',
        'Duels aériens', 'Duels aériens gagnés', 'Duels aériens gagnés %',
        
        'Tacles glissés', 'Tacles glissés réussis', 'Tacles glissés réussis %',
        
        'Interceptions', 'Dégagements', 'Fautes', 'Cartons jaunes', 'Cartons rouges',
        
        'Passes avant', 'Passes avant précises', 'Passes avant précises %',
        'Passes arrière', 'Passes arrière précises', 'Passes arrière précises %',
        'Passes latérales', 'Passes latérales précises', 'Passes latérales précises %',
        'Passes longues', 'Passes longues précises', 'Passes longues précises %',
        'Passes 3e tiers', 'Passes 3e tiers précises', 'Passes 3e tiers précises %',
        'Passes progressives', 'Passes progressives précises', 'Passes progressives précises %',
        'Passes astucieuses', 'Passes astucieuses précises', 'Passes astucieuses précises %',
        'Remises en jeu', 'Remises en jeu précises', 'Remises en jeu précises %',
        
        'But sur coup franc', 'Rythme du match',
        'Passes par possession', '% passes longues',
        'Distance moyenne de tir', 'Longueur moyenne des passes', 'PPDA'
    ]

    # Renommer les colonnes
    df_collective.columns = colonnes
    df_collective.columns = df_collective.columns.str.strip()

    return df_collective

def add_new_columns(all_df):
    for name, df in all_df.items():
        if df is None or df.empty:
            continue

        new_columns = {
            'Buts - xG': df['Buts par 90'] - df['xG par 90']
        }

        all_df[name] = pd.concat([df, pd.DataFrame(new_columns, index=df.index)], axis=1)

    return all_df

@st.cache_data
def collect_individual_data():
    load_all_files_from_drive()

    saisons = ["24-25", "25-26"]
    competitions = ["Ligue 1", "Ligue 2", "National 1", "National 2", "Français", "Top 5 Européen"]
    positions = ["Ailier", "Buteur", "Défenseur central", "Latéral", "Milieu", "Milieu offensif", "Gardien"]

    all_df_dict = {}

    def safe_read(path_str):
        path = Path(path_str)
        if not path.exists():
            return None
        try:
            return read_with_competition(str(path))
        except:
            return None

    def safe_concat(list_df):
        valid_df = [df for df in list_df if df is not None and not df.empty]
        return pd.concat(valid_df, ignore_index=True) if valid_df else pd.DataFrame()

    for saison in saisons:
        base_dir = Path(f"data") / f"Data {saison}"
        dfs = {comp: {} for comp in competitions}

        # Lecture sécurisée
        for comp in competitions:
            for pos in positions:
                fichier = base_dir / f"{comp} - {pos}.xlsx"
                dfs[comp][pos] = safe_read(fichier)

        # Concat selon tes regroupements
        df_championnat_de_france = safe_concat(
            [*dfs["Ligue 1"].values(),
             *dfs["Ligue 2"].values(),
             *dfs["National 1"].values(),
             *dfs["National 2"].values()]
        )
        df_n1_n2 = safe_concat(
            [*dfs["National 1"].values(),
             *dfs["National 2"].values()]
        )
        df_français = safe_concat(dfs["Français"].values())
        df_top5européen = safe_concat(dfs["Top 5 Européen"].values())

        # Nettoyage
        for df in (df_championnat_de_france, df_n1_n2, df_français, df_top5européen):
            if not df.empty:
                df.columns = df.columns.str.strip()
                df.rename(columns={"Buts hors penaltyButs hors penalty": "Buts hors penalty"}, inplace=True)
                if "Contrat expiration" in df.columns:
                    df["Contrat expiration"] = pd.to_datetime(df["Contrat expiration"], errors="coerce").dt.date

        all_df = {
            'Joueur du championnat de France': df_championnat_de_france,
            'Joueur de National 1 et National 2': df_n1_n2,
            'Joueur français': df_français,
            'Joueur du top 5 européen': df_top5européen
        }

        all_df = add_new_columns(all_df)
        all_df_dict[f"all_df_{saison.replace('-', '_')}"] = all_df

    return all_df_dict

def bordered_metric(container, label, value, size, color="#3d3a2a"):
    style = f"""
        <div style='
            border: 1px solid {color};
            border-radius: 6px;
            padding: 12px;
            background-color: #f4f3ed;
            width: {size}px;
            height: 110px;
            margin: auto;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        '>
            <div style='font-size: 14px; color: {color}; font-weight: 500; text-align: center;'>{label}</div>
            <div style='font-size: 24px; font-weight: bold; color: {color};'>{value}</div>
        </div>
    """
    container.markdown(style, unsafe_allow_html=True)

def clean_values(values):
    return [int(v) if isinstance(v, float) and v.is_integer() else v for v in values]

def assign_color(value):
    if value <= 25:
        return 'red'
    elif value <= 50:
        return 'orange'
    elif value <= 75:
        return 'yellowgreen'
    else:
        return 'green'
    
def compute_weighted_stats_by_minutes(df_joueur):
    if df_joueur.empty:
        return pd.DataFrame()

    # Colonnes à additionner (en plus de 'Minutes jouées')
    colonnes_a_additioner = ['Buts', 'Matchs joués', 'Passes décisives', 'Minutes jouées']

    # Colonnes numériques à pondérer par les minutes, sauf celles à additionner
    colonnes_a_ponderee = [
        col for col in df_joueur.columns
        if df_joueur[col].dtype in ['float64', 'int64']
        and col not in colonnes_a_additioner
    ]

    resultat = {}

    # Additionner les colonnes concernées
    for col in colonnes_a_additioner:
        if col in df_joueur.columns:
            resultat[col] = df_joueur[col].sum()

    # Pondérer les autres colonnes numériques par les minutes jouées
    total_minutes = resultat.get('Minutes jouées', df_joueur['Minutes jouées'].sum())
    for col in colonnes_a_ponderee:
        if total_minutes > 0:
            resultat[col] = (df_joueur[col] * df_joueur['Minutes jouées']).sum() / total_minutes
        else:
            resultat[col] = 0

    # Ajouter les colonnes non numériques depuis la première ligne
    colonnes_non_numeriques = [
        col for col in df_joueur.columns
        if col not in colonnes_a_ponderee and col not in colonnes_a_additioner
    ]
    for col in colonnes_non_numeriques:
        resultat[col] = df_joueur.iloc[0][col]

    return pd.DataFrame([resultat])

def rank_columns(df):
    df_copy = df.copy()

    # Colonnes numériques sauf 'Minutes jouées', 'Âge' et 'Taille'
    numeric_cols = df_copy.select_dtypes(include=['number']).columns
    numeric_cols = numeric_cols.drop(['Minutes jouées', 'Âge', 'Taille'], errors='ignore')

    # Colonnes où un score plus faible est meilleur
    lower_is_better = [
        'Buts concédés par 90', 'Fautes par 90',
        'Cartons jaunes', 'Cartons rouges',
        'Cartons jaunes par 90', 'Cartons rouges par 90'
    ]

    # Calculer tous les rangs d'un coup dans un dict
    ranked_data = {
        col: df_copy[col].rank(
            pct=True,
            ascending=False if col in lower_is_better else True,
            method='average'
        ) * 100
        for col in numeric_cols
    }

    # Création du DataFrame de rangs d'un coup (évite la fragmentation)
    ranked_df = pd.DataFrame(ranked_data, index=df_copy.index)
    ranked_df = ranked_df.fillna(0).astype(int)

    # Remplacer les colonnes originales
    df_copy[numeric_cols] = ranked_df

    return df_copy

def create_plot_stats(indicateurs, équipe_analysée, nom_équipe_analysée, adversaire, nom_adversaire):
    fig_width, fig_height = 6, 9
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), facecolor='#f4f3ed')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.set_facecolor('#f4f3ed')
    text_color = '#3d3a2a'

    x_positions = [0.05, 0.5, 0.85]

    total_slots = 15
    top_margin = 1
    bottom_margin = 0.05
    spacing = (top_margin - bottom_margin) / total_slots

    def format_value(value, label):
        if "%" in label and not str(value).strip().endswith("%"):
            return f"{value}%"
        return str(value)

    for i in range(total_slots):
        y = top_margin - i * spacing

        if i == 0:
            ax.text(x_positions[0], y, "Indicateur", fontsize=10, fontweight='bold', va='center', color=text_color)
            ax.text(x_positions[1], y, nom_équipe_analysée, fontsize=10, fontweight='bold', va='center', ha='center', color=text_color)
            ax.text(x_positions[2], y, nom_adversaire, fontsize=10, fontweight='bold', va='center', ha='center', color=text_color)

            ax.hlines(y - spacing / 2, 0.05, 0.95, colors='#3d3a2a', linestyles='solid', linewidth=1)

        elif i - 1 < len(indicateurs):
            idx = i - 1
            label = indicateurs[idx]
            éq_val = format_value(équipe_analysée[idx], label)
            if nom_adversaire != 'Classement':
                adv_val = format_value(adversaire[idx], label)
            else:
                adv_val = adversaire[idx]

            ax.text(x_positions[0], y, label, fontsize=10, va='center', color=text_color)
            ax.text(x_positions[1], y, éq_val, fontsize=10, va='center', ha='center', color=text_color)
            ax.text(x_positions[2], y, adv_val, fontsize=10, va='center', ha='center', color=text_color)

            if i < len(indicateurs):
                ax.hlines(y - spacing / 2, 0.05, 0.95, colors='#3d3a2a', linestyles='dotted', linewidth=1)

    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    return fig

# Fonction de calcul des scores à partir de df_ranked, avec Note globale pondérée
def calcul_scores_par_kpi(df, joueur, poste):
    joueur_infos = df[df['Joueur + Information'] == joueur]

    if len(joueur_infos) > 1:
        joueur_infos = compute_weighted_stats_by_minutes(joueur_infos)

    df_filtré = df[(df['Poste'] == poste) & (df['Minutes jouées'] >= 500)]
    df_filtré = df_filtré[df_filtré['Joueur + Information'] != joueur]
    df_filtré = pd.concat([df_filtré, joueur_infos], ignore_index=True)

    df_ranked = rank_columns(df_filtré)

    # Initialisation du DataFrame des scores
    df_scores = df_ranked[['Joueur + Information', 'Poste', 'Âge', 'Taille', 'Minutes jouées', 'Contrat expiration']].copy()

    # Récupération des KPI spécifiques au poste
    kpi_metrics = kpi_by_position[poste]
    kpi_coefficients = kpi_coefficients_by_position[poste]
    total_coeff = sum(kpi_coefficients.values())

    # Calcul des scores par KPI
    for kpi, metrics in kpi_metrics.items():
        # Extraire la ligue et remplacer les valeurs absentes par 1
        coeffs = df_scores["Joueur + Information"].str.extract(r'\((.*?)\)')[0].apply(lambda x: league_rating.get(x, league_rating["Ligue 1"]) / league_rating["Ligue 1"])

        # Appliquer le calcul du score avec la pondération
        df_scores[kpi] = (
            df_ranked[list(metrics.keys())].mul(list(metrics.values()), axis=1).sum(axis=1)
            * (1 - 0.5 + 0.5 * coeffs)
        ).round(1)

    # Calcul de la note globale pondérée
    df_scores["Note globale"] = sum(
        df_scores[kpi] * coef for kpi, coef in kpi_coefficients.items()
    ) / total_coeff

    df_scores["Note globale"] = df_scores["Note globale"].round(1)

    # Calcul de la note des rôles
    for role, coeffs in kpi_coefficients_by_role[poste].items():
        total_coeff = sum(coeffs.values())
        df_scores[role] = df_scores.apply(lambda row: sum(row[kpi] * coeffs[kpi] for kpi in coeffs) / total_coeff, axis=1).round(1)

    return df_scores

def create_individual_radar(df, joueur, poste):
    joueur_infos = df[df['Joueur + Information'] == joueur]

    if len(joueur_infos) > 1:
        joueur_infos = compute_weighted_stats_by_minutes(joueur_infos)

    df_filtré = df[(df['Poste'] == poste) & (df['Minutes jouées'] >= 500)]
    df_filtré = df_filtré[df_filtré['Joueur + Information'] != joueur]
    df_filtré = pd.concat([df_filtré, joueur_infos], ignore_index=True)

    df_ranked = rank_columns(df_filtré)

    metrics = next(item["metrics"] for item in metrics_by_position if item["position"] == poste)

    player = df_ranked[df_ranked["Joueur + Information"] == joueur].iloc[0]
    values = [player[metrics[abbr]] for abbr in metrics]

    slice_colors = [assign_color(player[col]) for col in metrics.values()]

    pizza = PyPizza(
        params=metrics,
        background_color="#f4f3ed",
        straight_line_color="#3d3a2a",
        straight_line_lw=1,
        last_circle_lw=2,
        last_circle_color="#3d3a2a",
        other_circle_lw=0,
        inner_circle_size=20
    )

    fig, _ = pizza.make_pizza(
        values,
        figsize=(8, 8),
        color_blank_space="same",
        slice_colors=slice_colors,
        value_bck_colors=slice_colors,
        blank_alpha=0.4,
        kwargs_slices=dict(edgecolor="#3d3a2a", zorder=2, linewidth=1),
        kwargs_params=dict(
            color="#3d3a2a", fontsize=9, va="center"
        ),
        kwargs_values=dict(
            color="#f4f3ed", fontsize=9, zorder=3,
            bbox=dict(
                edgecolor="#3d3a2a", facecolor="cornflowerblue",
                boxstyle="round,pad=0.2", lw=1
            )
        )
    )

    fig.set_facecolor('#f4f3ed')

    return fig

def create_comparison_radar(df, joueur_1, joueur_2, poste):
    joueur_1_infos = df[df['Joueur + Information'] == joueur_1]

    if len(joueur_1_infos) > 1:
        joueur_1_infos = compute_weighted_stats_by_minutes(joueur_1_infos)

    joueur_2_infos = df[df['Joueur + Information'] == joueur_2]

    if len(joueur_2_infos) > 1:
        joueur_2_infos = compute_weighted_stats_by_minutes(joueur_2_infos)

    df_filtré = df[(df['Poste'] == poste) & (df['Minutes jouées'] >= 500)]
    df_filtré = df_filtré[(df_filtré['Joueur + Information'] != joueur_1) & (df_filtré['Joueur + Information'] != joueur_2)]
    df_filtré = pd.concat([df_filtré, joueur_1_infos, joueur_2_infos], ignore_index=True)

    df_ranked = rank_columns(df_filtré)

    # Récupération des bonnes métriques selon le poste
    metrics_dict = next(item["metrics"] for item in metrics_by_position if item["position"] == poste)
    metrics_abbr = list(metrics_dict.keys())
    metrics_cols = [metrics_dict[m] for m in metrics_abbr]

    low = [0] * len(metrics_abbr)
    high = [100] * len(metrics_abbr)

    radar = Radar(metrics_abbr, low, high,
                  round_int=[True] * len(metrics_abbr),
                  num_rings=4,
                  ring_width=1, center_circle_radius=1)

    URL = 'https://raw.githubusercontent.com/googlefonts/roboto/main/src/hinted/Roboto-Thin.ttf'
    robotto_thin = FontManager(URL)

    URL2 = 'https://raw.githubusercontent.com/google/fonts/main/apache/robotoslab/RobotoSlab%5Bwght%5D.ttf'
    robotto_bold = FontManager(URL2)

    fig, axs = grid(figheight=14, grid_height=0.915, title_height=0.06, endnote_height=0.025,
                    title_space=0, endnote_space=0, grid_key='radar', axis=False)

    radar.setup_axis(ax=axs['radar'], facecolor='None')
    radar.draw_circles(ax=axs['radar'], facecolor='#ecebe3', lw=1.5)

    player_values_1 = df_ranked[df_ranked['Joueur + Information'] == joueur_1][metrics_cols].mean().values.flatten()
    player_values_2 = df_ranked[df_ranked['Joueur + Information'] == joueur_2][metrics_cols].mean().values.flatten()

    radar.draw_radar_compare(player_values_1, player_values_2, ax=axs['radar'],
                             kwargs_radar={'facecolor': '#1440AC', 'alpha': 0.6},
                             kwargs_compare={'facecolor': '#ac141a', 'alpha': 0.6})

    radar.draw_range_labels(ax=axs['radar'], fontsize=20, color='#3d3a2a', fontproperties=robotto_thin.prop)
    radar.draw_param_labels(ax=axs['radar'], fontsize=20, color='#3d3a2a', fontproperties=robotto_thin.prop)

    axs['title'].text(0.01, 0.60, f"{joueur_1.split(' - ')[0]}", fontsize=25, color='#1440AC',
                      fontproperties=robotto_bold.prop, ha='left', va='center')
    axs['title'].text(0.01, 0.20,
                      f"{df_ranked[df_ranked['Joueur + Information'] == joueur_1]['Équipe dans la période sélectionnée'].iloc[0]} | {df_ranked[df_ranked['Joueur + Information'] == joueur_1]['Minutes jouées'].iloc[0]} minutes jouées",
                      fontsize=20, fontproperties=robotto_thin.prop, ha='left', va='center', color='#3d3a2a')

    axs['title'].text(0.99, 0.60, f"{joueur_2.split(' - ')[0]}", fontsize=25,
                      fontproperties=robotto_bold.prop, ha='right', va='center', color='#ac141a')
    axs['title'].text(0.99, 0.20,
                      f"{df_ranked[df_ranked['Joueur + Information'] == joueur_2]['Équipe dans la période sélectionnée'].iloc[0]} | {df_ranked[df_ranked['Joueur + Information'] == joueur_2]['Minutes jouées'].iloc[0]} minutes jouées",
                      fontsize=20, fontproperties=robotto_thin.prop, ha='right', va='center', color='#3d3a2a')

    fig.set_facecolor('#f4f3ed')

    return fig

def plot_kpi_comparison(df, joueur_1, joueur_2, poste, kpis_panel):
    scores_df_1 = calcul_scores_par_kpi(df, joueur_1, poste)
    joueur_1_scores = scores_df_1[scores_df_1['Joueur + Information'] == joueur_1]

    scores_df_2 = calcul_scores_par_kpi(df, joueur_2, poste)
    joueur_2_scores = scores_df_2[scores_df_2['Joueur + Information'] == joueur_2]

    # Colonnes communes entre les deux DataFrames
    colonnes_communes = joueur_1_scores.columns.intersection(joueur_2_scores.columns)

    # Sélection des colonnes numériques en excluant 'Minutes jouées'
    colonnes_kpi = [col for col in kpis_panel if col in colonnes_communes]

    # Récupération des valeurs
    values_1 = joueur_1_scores[colonnes_kpi].values.flatten()
    values_2 = joueur_2_scores[colonnes_kpi].values.flatten()

    y_pos = np.arange(len(colonnes_kpi))
    bar_height = 0.35

    fig, ax = plt.subplots(figsize=(10, 10))
    _ = ax.barh(y_pos - bar_height / 2, values_1, bar_height,
                         label=f"{joueur_1.split(' - ')[0]}", color='#1440AC', edgecolor='#3d3a2a')
    _ = ax.barh(y_pos + bar_height / 2, values_2, bar_height,
                         label=f"{joueur_2.split(' - ')[0]}", color='#AC141A', edgecolor='#3d3a2a')

    # Ajouter les valeurs à la fin des barres
    for i, (v1, v2) in enumerate(zip(values_1, values_2)):
        ax.text(v1 + 1, y_pos[i] - bar_height / 2, f"{v1:.1f}", 
                va='center', fontsize=9, fontweight="bold")
        ax.text(v2 + 1, y_pos[i] + bar_height / 2, f"{v2:.1f}", 
                va='center', fontsize=9, fontweight="bold")

    ax.set_xticks([])
    ax.set_yticks(y_pos)
    ax.set_yticklabels(colonnes_kpi)
    ax.invert_yaxis()
    ax.legend()

    for spine in ax.spines.values():
        spine.set_visible(False)

    plt.tight_layout()

    # Transparence
    fig.patch.set_alpha(0)
    ax.patch.set_alpha(0)

    return fig

def plot_stat_comparison(df, joueur_1, joueur_2, poste):
    # même palette que ta fonction précédente
    bg, ink = "#f4f3ed", "#3d3a2a"

    # --- sélection du joueur 1 ---
    joueur1_infos = df[df['Joueur + Information'] == joueur_1]
    if len(joueur1_infos) > 1:
        joueur1_infos = compute_weighted_stats_by_minutes(joueur1_infos)

    # --- sélection du joueur 2 ---
    joueur2_infos = df[df['Joueur + Information'] == joueur_2]
    if len(joueur2_infos) > 1:
        joueur2_infos = compute_weighted_stats_by_minutes(joueur2_infos)

    # --- pool de comparaison (même poste, minutes >= 500) ---
    df_filtré = df[(df['Poste'] == poste) & (df['Minutes jouées'] >= 500)].copy()

    # On enlève les versions brutes des deux joueurs pour éviter les doublons
    df_filtré = df_filtré[
        (df_filtré['Joueur + Information'] != joueur_1) &
        (df_filtré['Joueur + Information'] != joueur_2)
    ]

    # On ajoute les versions consolidées des deux joueurs
    df_filtré = pd.concat([df_filtré, joueur1_infos, joueur2_infos], ignore_index=True)

    # --- colonnes numériques brutes ---
    exclude = {
        'Joueur + Information','Poste','Minutes jouées','Âge','Valeur sur le marché',
        'Matchs joués','Taille','Poids'
    }
    numeric_cols = [
        c for c in df_filtré.columns
        if c not in exclude and pd.api.types.is_numeric_dtype(df_filtré[c])
    ]

    # Stats brutes des deux joueurs
    p1_raw = df_filtré[df_filtré["Joueur + Information"] == joueur_1].iloc[0]
    p2_raw = df_filtré[df_filtré["Joueur + Information"] == joueur_2].iloc[0]

    # ordre des catégories : "Général" en premier
    ordered_keys = list(métriques_par_catégorie.keys())
    if "Général" in ordered_keys:
        ordered_keys = ["Général"] + [k for k in ordered_keys if k != "Général"]

    table_data = []
    header_rows_idx = []   # indices (dans table_data) des lignes de catégorie
    metric_rows_info = []  # (row_idx, metric_name) pour colorer ensuite

    # 1) Ligne "header" avec juste les noms (sans bordure ensuite)
    table_data.append(["", joueur_1, joueur_2])
    row_idx = 1  # les catégories commencent à la ligne 1

    # 2) Catégories + métriques
    for catégorie in ordered_keys:
        metrics_list = métriques_par_catégorie[catégorie]

        métriques_valides = []
        for m in metrics_list:
            if m in numeric_cols:
                v1 = p1_raw.get(m, np.nan)
                v2 = p2_raw.get(m, np.nan)
                if not (pd.isna(v1) and pd.isna(v2)):  # garder seulement si au moins une valeur non NaN
                    métriques_valides.append((m, v1, v2))

        if not métriques_valides:
            continue

        # Ligne de catégorie
        table_data.append([catégorie, "", ""])
        header_rows_idx.append(row_idx)
        row_idx += 1

        # Lignes de métriques
        for m, v1, v2 in métriques_valides:
            table_data.append([m, f"{v1:.2f}", f"{v2:.2f}"])
            metric_rows_info.append((row_idx, m))
            row_idx += 1

    fig, ax = plt.subplots(figsize=(11, 2 + len(table_data) * 0.25))
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)
    ax.axis("off")

    # Tableau (sans colLabels)
    table = ax.table(
        cellText=table_data,
        loc="center",
        cellLoc="center"
    )

    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.2)

    # Styling de base
    for (r, c), cell in table.get_celld().items():
        cell.set_facecolor(bg)
        cell.set_edgecolor("#3d3a2a")
        cell.get_text().set_color(ink)

    # 1) LIGNE DES NOMS : pas de bordure → visuellement "en dehors" du tableau
    name_row = 0
    for col in range(3):
        cell = table[name_row, col]
        cell.set_edgecolor(bg)       # même couleur que le fond → bordure invisible
        cell.set_linewidth(0.0)
        if col == 0:
            cell.get_text().set_text("")  # pas de texte en colonne catégorie
        else:
            cell.get_text().set_fontweight("bold")

    # 2) Lignes de catégories (fond gris + gras)
    cat_bg = "#ecebe3"
    for row_i in header_rows_idx:
        for col_i in range(3):
            cell = table[row_i, col_i]
            cell.set_facecolor(cat_bg)
            cell.get_text().set_fontweight("bold")

    lower_is_better = {
        "Fautes par 90", "Cartons jaunes", "Cartons jaunes par 90",
        "Cartons rouges", "Cartons rouges par 90"
    }

    couleur_meilleur = "#d4edda"   # vert clair
    couleur_moins_bon = "#f8d7da"  # rouge clair

    for row_i, metric_name in metric_rows_info:
        v1 = p1_raw.get(metric_name, np.nan)
        v2 = p2_raw.get(metric_name, np.nan)

        if pd.isna(v1) and pd.isna(v2):
            continue
        if v1 == v2:
            continue

        if metric_name in lower_is_better:
            v1_comp = -v1
            v2_comp = -v2
        else:
            v1_comp = v1
            v2_comp = v2

        best = "player1" if v1_comp > v2_comp else "player2"

        if best == "player1":
            table[row_i, 1].set_facecolor(couleur_meilleur)
            table[row_i, 2].set_facecolor(couleur_moins_bon)
        else:
            table[row_i, 2].set_facecolor(couleur_meilleur)
            table[row_i, 1].set_facecolor(couleur_moins_bon)

    plt.tight_layout()
    plt.show()
    
    return fig

def plot_player_metrics(df, joueur, poste, x_metric, y_metric, nom_x_metric, nom_y_metric, description_1, description_2, description_3, description_4):
    joueur_infos = df[df['Joueur + Information'] == joueur]

    if len(joueur_infos) > 1:
        joueur_infos = compute_weighted_stats_by_minutes(joueur_infos)

    df_filtré = df[(df['Poste'] == poste) & (df['Minutes jouées'] >= 500) & (df[x_metric] != 0) & (df[y_metric] != 0)]
    df_filtré = df_filtré[df_filtré['Joueur + Information'] != joueur]
    df_filtré = pd.concat([df_filtré, joueur_infos], ignore_index=True)

    x_mean = df_filtré[x_metric].mean()
    y_mean = df_filtré[y_metric].mean()

    df_filtré["Catégorie"] = df_filtré["Joueur + Information"].apply(
        lambda x: "Joueur sélectionné" if x == joueur else "Autres joueurs"
    )

    fig = px.scatter(
        df_filtré,
        x=x_metric,
        y=y_metric,
        color="Catégorie",
        color_discrete_map={
            "Autres joueurs": "rgba(61,58,42,0.2)",
            "Joueur sélectionné": "#ac141a"
        },
        hover_name="Joueur + Information",
        hover_data={
            "Catégorie": False,
            x_metric: False,
            y_metric: False,
            "Âge": True,
            "Minutes jouées": True,
            "Contrat expiration": True
        },
        opacity=0.7
    )

    # Ajoute les lignes de moyenne
    fig.add_vline(x=x_mean, line=dict(color="rgba(61,58,42,0.5)", dash='dash'))
    fig.add_hline(y=y_mean, line=dict(color="rgba(61,58,42,0.5)", dash='dash'))

    # Ajoute les 4 textes descriptifs
    x_min, x_max = df_filtré[x_metric].min(), df_filtré[x_metric].max()
    y_min, y_max = df_filtré[y_metric].min(), df_filtré[y_metric].max()
    x_offset = (x_max - x_min) * 0.02
    y_offset = (y_max - y_min) * 0.02

    annotations = [
        dict(x=x_min + x_offset, y=y_max - y_offset, text=description_1, showarrow=False, font=dict(color="#3d3a2a", size=11), xanchor="left", yanchor="top"),
        dict(x=x_max - x_offset, y=y_max - y_offset, text=description_2, showarrow=False, font=dict(color="#3d3a2a", size=11), xanchor="right", yanchor="top"),
        dict(x=x_min + x_offset, y=y_min + y_offset, text=description_3, showarrow=False, font=dict(color="#3d3a2a", size=11), xanchor="left", yanchor="bottom"),
        dict(x=x_max - x_offset, y=y_min + y_offset, text=description_4, showarrow=False, font=dict(color="#3d3a2a", size=11), xanchor="right", yanchor="bottom")
    ]

    fig.update_layout(
        template="plotly_white",
        plot_bgcolor="#f4f3ed",
        annotations=annotations,
        showlegend=False,
        xaxis_title=nom_x_metric,
        yaxis_title=nom_y_metric,
        width=1000,
        height=600,
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(61,58,42,0.1)",
            gridwidth=0.5,
            griddash="dot",
            zeroline=False
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(61,58,42,0.1)",
            gridwidth=0.5,
            griddash="dot",
            zeroline=False
        )
    )

    return fig

def plot_team_metrics(df, x_metric, y_metric):
    colonnes_bas_mieux = {
        'Pertes', 'Pertes bas', 'Pertes Moyen', 'Pertes élevé', 'Hors-jeu',
        'Tirs contre', 'Tirs contre cadrés', 'Buts concédés', 'Fautes',
        'Cartons jaunes', 'Cartons rouges', 'PPDA'
    }

    df = df.copy()
    x_mean = df[x_metric].mean()
    y_mean = df[y_metric].mean()

    logos_dict = {
        "Andrézieux": "https://upload.wikimedia.org/wikipedia/fr/thumb/d/d1/Logo_Andr%C3%A9zieux-Bouth%C3%A9on_FC_2019.svg/langfr-1024px-Logo_Andr%C3%A9zieux-Bouth%C3%A9on_FC_2019.svg.png",
        "Anglet Genets": "https://upload.wikimedia.org/wikipedia/fr/thumb/8/84/Logo_Les_Gen%C3%AAts_d%27Anglet_-_2018.svg/langfr-1024px-Logo_Les_Gen%C3%AAts_d%27Anglet_-_2018.svg.png",
        "Angoulême": "https://upload.wikimedia.org/wikipedia/fr/thumb/c/c5/Angoul%C3%AAme_CFC_2020.svg/langfr-1024px-Angoul%C3%AAme_CFC_2020.svg.png",
        "Bergerac": "https://upload.wikimedia.org/wikipedia/fr/thumb/6/67/Logo_Bergerac_P%C3%A9rigord_FC.svg/langfr-800px-Logo_Bergerac_P%C3%A9rigord_FC.svg.png",
        "Cannes": "https://upload.wikimedia.org/wikipedia/fr/thumb/7/72/AS_Cannes_foot_Logo_2017.svg/langfr-800px-AS_Cannes_foot_Logo_2017.svg.png",
        "Fréjus St-Raphaël": "https://upload.wikimedia.org/wikipedia/fr/thumb/5/55/Logo_%C3%89FC_Fr%C3%A9jus_Saint-Rapha%C3%ABl_-_2020.svg/langfr-1024px-Logo_%C3%89FC_Fr%C3%A9jus_Saint-Rapha%C3%ABl_-_2020.svg.png",
        "GOAL FC": "https://upload.wikimedia.org/wikipedia/fr/thumb/d/de/Logo_GOAL_FC_-_2020.svg/langfr-800px-Logo_GOAL_FC_-_2020.svg.png",
        "Grasse": "https://upload.wikimedia.org/wikipedia/fr/thumb/f/f8/Logo_RC_Pays_Grasse_2022.svg/langfr-1024px-Logo_RC_Pays_Grasse_2022.svg.png",
        "Hyères FC": "https://upload.wikimedia.org/wikipedia/fr/thumb/3/3f/Logo_Hy%C3%A8res_83_Football_Club_-_2021.svg/langfr-800px-Logo_Hy%C3%A8res_83_Football_Club_-_2021.svg.png",
        "Istres": "https://upload.wikimedia.org/wikipedia/fr/thumb/b/b0/Logo_Istres_FC_-_2022.svg/langfr-800px-Logo_Istres_FC_-_2022.svg.png",
        "Jura Sud Foot": "https://upload.wikimedia.org/wikipedia/fr/thumb/b/ba/Logo_Jura_Sud_Foot.svg/langfr-1280px-Logo_Jura_Sud_Foot.svg.png",
        "Le Puy F.43 Auvergne": "https://upload.wikimedia.org/wikipedia/fr/thumb/8/88/Logo_Puy_Foot_43_Auvergne_2017.svg/langfr-800px-Logo_Puy_Foot_43_Auvergne_2017.svg.png",
        "Marignane Gignac CB": "https://upload.wikimedia.org/wikipedia/fr/thumb/b/bb/Logo_Marignane_Gignac_C%C3%B4te_Bleue_FC_-_2022.svg/langfr-800px-Logo_Marignane_Gignac_C%C3%B4te_Bleue_FC_-_2022.svg.png",
        "Rumilly Vallières": "https://upload.wikimedia.org/wikipedia/fr/thumb/4/40/Logo_Groupement_Football_Albanais_74_-_2021.svg/langfr-800px-Logo_Groupement_Football_Albanais_74_-_2021.svg.png",
        "Saint-Priest": "https://upload.wikimedia.org/wikipedia/fr/thumb/4/46/Logo_AS_St_Priest.svg/langfr-800px-Logo_AS_St_Priest.svg.png",
        "Toulon": "https://upload.wikimedia.org/wikipedia/fr/thumb/d/d6/Logo_SC_Toulon.svg/langfr-800px-Logo_SC_Toulon.svg.png",
        "Créteil": "https://upload.wikimedia.org/wikipedia/fr/thumb/9/99/Logo_US_Cr%C3%A9teil_Lusitanos_2015.svg/langfr-800px-Logo_US_Cr%C3%A9teil_Lusitanos_2015.svg.png",
        "St Maur Lusitanos": "https://upload.wikimedia.org/wikipedia/fr/thumb/8/89/Logo_US_Lusitanos_Saint-Maur_2018.svg/langfr-1024px-Logo_US_Lusitanos_Saint-Maur_2018.svg.png",
        "Nîmes": "https://upload.wikimedia.org/wikipedia/fr/thumb/f/f0/N%C3%AEmes_Olympique_logo_2018.svg/langfr-800px-N%C3%AEmes_Olympique_logo_2018.svg.png",
        "FC 93 Bobigny BG": "https://upload.wikimedia.org/wikipedia/fr/d/d7/Logo_Football_Club_93-2024.png",
        "Rousset-Ste Victoire": "https://fcroussetsvo.fr/img/rousset.png",
        "Limonest": "https://upload.wikimedia.org/wikipedia/fr/thumb/7/7c/Logo_FC_Limonest_Dardilly_Saint_Didier_-_2021.svg/langfr-1024px-Logo_FC_Limonest_Dardilly_Saint_Didier_-_2021.svg.png"
    }

    fig = go.Figure()

    for _, row in df.iterrows():
        logo_url = logos_dict.get(row["Équipe"])
        if not logo_url:
            continue
        fig.add_layout_image(
            dict(
                source=logo_url,
                xref="x",
                yref="y",
                x=row[x_metric],
                y=row[y_metric],
                sizex=(df[x_metric].max() - df[x_metric].min()) * 0.05,
                sizey=(df[y_metric].max() - df[y_metric].min()) * 0.05,
                xanchor="center",
                yanchor="middle",
                layer="above"
            )
        )
        fig.add_trace(go.Scatter(
            x=[row[x_metric]], y=[row[y_metric]],
            mode="markers",
            marker=dict(opacity=0),
            hovertemplate=f"<b>{row['Équipe']}</b><extra></extra>"
        ))

    fig.add_vline(x=x_mean, line=dict(color="rgba(61,58,42,0.5)", dash='dash'))
    fig.add_hline(y=y_mean, line=dict(color="rgba(61,58,42,0.5)", dash='dash'))

    x_axis = dict(
        showgrid=True,
        gridcolor="rgba(61,58,42,0.1)",
        gridwidth=0.5,
        griddash="dot",
        zeroline=False,
        autorange="reversed" if x_metric in colonnes_bas_mieux else True
    )
    y_axis = dict(
        showgrid=True,
        gridcolor="rgba(61,58,42,0.1)",
        gridwidth=0.5,
        griddash="dot",
        zeroline=False,
        autorange="reversed" if y_metric in colonnes_bas_mieux else True
    )

    fig.update_layout(
        template="plotly_white",
        plot_bgcolor="#f4f3ed",
        showlegend=False,
        xaxis_title=x_metric,
        yaxis_title=y_metric,
        width=1000,
        height=600,
        xaxis=x_axis,
        yaxis=y_axis,
    )

    return fig

def search_recommended_players(df, poste, thresholds):
    df_filtré = df[(df['Poste'] == poste) & (df['Minutes jouées'] >= 500)]

    df_ranked = rank_columns(df_filtré)

    df_scores = df_ranked[['Joueur + Information', 'Âge', 'Taille', 'Minutes jouées', 'Contrat expiration'   ] + list(thresholds.keys())].copy()

    for métrique, seuil in thresholds.items():
        df_scores = df_scores[df_scores[métrique] >= seuil]

    return df_scores

def performance_index(df_player, poste, match):
    df_match = df_player[df_player["Match"] == match]
    note = 6

    coefficients = {
        "Buteur": {
            # Passes
            ("Passes précises", "Passes"): (0.005, -0.05),
            ("Passes longues précises", "Passes longues"): (0.015, -0.05),
            ("Passes en profondeur précises", "Passes en profondeur"): (0.045, -0.02),
            ("Passes dans le 3ème tiers précises", "Passes dans le 3ème tiers"): (0.025, -0.04),
            ("Passes vers la surface de réparation précises", "Passes vers la surface de réparation"): (0.045, -0.025),
            ("Passes en avant précises", "Passes en avant"): (0.015, -0.04),
            ("Passes arrière précises", "Passes arrière"): (0.001, -0.09),

            # Jeu offensif
            ("Tirs cadrés", "Tirs"): (0.09, -0.02),
            ("Centres précis", "Centres"): (0.03, -0.01),
            ("Dribbles réussis", "Dribbles"): (0.06, -0.015),

            # Duels
            ("Duels gagnés", "Duels"): (0.02, -0.03),
            ("Duels offensifs gagnés", "Duels offensifs"): (0.04, -0.015),
            ("Duels aériens gagnés", "Duels aériens"): (0.035, -0.015),
            ("Duels défensifs gagnés", "Duels défensifs"): (0.01, -0.01),

            # Tacles
            ("Tacles glissés réussis", "Tacles glissés"): (0.01, -0.03),

            # Autres
            "Duels ballons gagnés": 0.02,
            "Duels ballons perdus": -0.03,
            "Récupérations": 0.02,
            "Récupérations dans le terrain adverse": 0.04,
            "Interceptions": 0.012,
            "Pertes": -0.06,
            "Pertes dans le propre terrain": -0.13,

            # Finition / Création
            "But": 1.5,
            "Passe décisive": 1.0,
            "Passes décisives avec tir": 0.12,
            "Secondes passes décisives": 0.07,
            "Courses progressives": 0.05,
            "Touches de balle dans la surface de réparation": 0.02,

            # Discipline
            "Fautes subies": 0.02,
            "Faute": -0.05,
            "Hors-jeu": -0.08,
            "Cartons rouges": -2.0,
            "Cartons jaunes": -0.7,
        },
        "Ailier": {
            # Passes
            ("Passes précises", "Passes"): (0.007, -0.055),
            ("Passes longues précises", "Passes longues"): (0.015, -0.045),
            ("Passes en profondeur précises", "Passes en profondeur"): (0.055, -0.02),
            ("Passes dans le 3ème tiers précises", "Passes dans le 3ème tiers"): (0.045, -0.02),
            ("Passes vers la surface de réparation précises", "Passes vers la surface de réparation"): (0.055, -0.02),
            ("Passes en avant précises", "Passes en avant"): (0.02, -0.035),
            ("Passes arrière précises", "Passes arrière"): (0.001, -0.08),

            # Jeu offensif
            ("Tirs cadrés", "Tirs"): (0.07, -0.015),
            ("Centres précis", "Centres"): (0.07, -0.015),
            ("Dribbles réussis", "Dribbles"): (0.09, -0.025),

            # Duels
            ("Duels gagnés", "Duels"): (0.03, -0.04),
            ("Duels offensifs gagnés", "Duels offensifs"): (0.05, -0.015),
            ("Duels aériens gagnés", "Duels aériens"): (0.02, -0.015),
            ("Duels défensifs gagnés", "Duels défensifs"): (0.01, -0.025),

            # Tacles
            ("Tacles glissés réussis", "Tacles glissés"): (0.015, -0.03),

            # Autres
            "Duels ballons gagnés": 0.035,
            "Duels ballons perdus": -0.045,
            "Récupérations": 0.03,
            "Récupérations dans le terrain adverse": 0.07,
            "Interceptions": 0.018,
            "Pertes": -0.055,
            "Pertes dans le propre terrain": -0.09,

            # Finition / Création
            "But": 1.5,
            "Passe décisive": 1.0,
            "Passes décisives avec tir": 0.13,
            "Secondes passes décisives": 0.07,
            "Courses progressives": 0.085,
            "Touches de balle dans la surface de réparation": 0.02,

            # Discipline
            "Fautes subies": 0.03,
            "Faute": -0.05,
            "Hors-jeu": -0.06,
            "Cartons rouges": -2.0,
            "Cartons jaunes": -0.7,
        },
        "Milieu offensif": {
            # Passes
            ("Passes précises", "Passes"): (0.007, -0.045),
            ("Passes longues précises", "Passes longues"): (0.017, -0.035),
            ("Passes en profondeur précises", "Passes en profondeur"): (0.06, -0.03),
            ("Passes dans le 3ème tiers précises", "Passes dans le 3ème tiers"): (0.045, -0.025),
            ("Passes vers la surface de réparation précises", "Passes vers la surface de réparation"): (0.055, -0.02),
            ("Passes en avant précises", "Passes en avant"): (0.02, -0.03),
            ("Passes arrière précises", "Passes arrière"): (0.003, -0.08),

            # Jeu offensif
            ("Tirs cadrés", "Tirs"): (0.07, -0.015),
            ("Centres précis", "Centres"): (0.06, -0.02),
            ("Dribbles réussis", "Dribbles"): (0.08, -0.015),

            # Duels
            ("Duels gagnés", "Duels"): (0.035, -0.03),
            ("Duels offensifs gagnés", "Duels offensifs"): (0.045, -0.025),
            ("Duels aériens gagnés", "Duels aériens"): (0.01, -0.015),
            ("Duels défensifs gagnés", "Duels défensifs"): (0.013, -0.035),

            # Tacles
            ("Tacles glissés réussis", "Tacles glissés"): (0.02, -0.03),

            # Autres
            "Duels ballons gagnés": 0.03,
            "Duels ballons perdus": -0.045,
            "Récupérations": 0.035,
            "Récupérations dans le terrain adverse": 0.065,
            "Interceptions": 0.025,
            "Pertes": -0.055,
            "Pertes dans le propre terrain": -0.09,

            # Finition / Création
            "But": 1.5,
            "Passe décisive": 1.0,
            "Passes décisives avec tir": 0.14,
            "Secondes passes décisives": 0.09,
            "Courses progressives": 0.09,
            "Touches de balle dans la surface de réparation": 0.02,

            # Discipline
            "Fautes subies": 0.03,
            "Faute": -0.055,
            "Hors-jeu": -0.05,
            "Cartons rouges": -2.0,
            "Cartons jaunes": -0.7,
        },
        "Milieu": {
            # Passes
            ("Passes précises", "Passes"): (0.007, -0.07),
            ("Passes longues précises", "Passes longues"): (0.025, -0.04),
            ("Passes en profondeur précises", "Passes en profondeur"): (0.045, -0.02),
            ("Passes dans le 3ème tiers précises", "Passes dans le 3ème tiers"): (0.035, -0.025),
            ("Passes vers la surface de réparation précises", "Passes vers la surface de réparation"): (0.035, -0.015),
            ("Passes en avant précises", "Passes en avant"): (0.018, -0.04),
            ("Passes arrière précises", "Passes arrière"): (0.001, -0.11),

            # Jeu offensif
            ("Tirs cadrés", "Tirs"): (0.04, -0.012),
            ("Centres précis", "Centres"): (0.018, -0.01),
            ("Dribbles réussis", "Dribbles"): (0.03, -0.02),

            # Duels
            ("Duels gagnés", "Duels"): (0.04, -0.045),
            ("Duels offensifs gagnés", "Duels offensifs"): (0.02, -0.035),
            ("Duels aériens gagnés", "Duels aériens"): (0.02, -0.02),
            ("Duels défensifs gagnés", "Duels défensifs"): (0.05, -0.07),

            # Tacles
            ("Tacles glissés réussis", "Tacles glissés"): (0.04, -0.045),

            # Autres
            "Duels ballons gagnés": 0.04,
            "Duels ballons perdus": -0.055,
            "Récupérations": 0.065,
            "Récupérations dans le terrain adverse": 0.09,
            "Interceptions": 0.06,
            "Pertes": -0.065,
            "Pertes dans le propre terrain": -0.12,

            # Finition / Création
            "But": 1.5,
            "Passe décisive": 1.0,
            "Passes décisives avec tir": 0.12,
            "Secondes passes décisives": 0.07,
            "Courses progressives": 0.07,
            "Touches de balle dans la surface de réparation": 0.012,

            # Discipline
            "Fautes subies": 0.03,
            "Faute": -0.065,
            "Hors-jeu": -0.03,
            "Cartons rouges": -2.3,
            "Cartons jaunes": -0.8,
        },
        "Latéral": {
            # Passes
            ("Passes précises", "Passes"): (0.005, -0.06),
            ("Passes longues précises", "Passes longues"): (0.018, -0.04),
            ("Passes en profondeur précises", "Passes en profondeur"): (0.045, -0.02),
            ("Passes dans le 3ème tiers précises", "Passes dans le 3ème tiers"): (0.035, -0.02),
            ("Passes vers la surface de réparation précises", "Passes vers la surface de réparation"): (0.05, -0.025),
            ("Passes en avant précises", "Passes en avant"): (0.012, -0.04),
            ("Passes arrière précises", "Passes arrière"): (0.001, -0.1),

            # Jeu offensif
            ("Tirs cadrés", "Tirs"): (0.035, -0.012),
            ("Centres précis", "Centres"): (0.07, -0.01),
            ("Dribbles réussis", "Dribbles"): (0.055, -0.015),

            # Duels
            ("Duels gagnés", "Duels"): (0.035, -0.05),
            ("Duels offensifs gagnés", "Duels offensifs"): (0.02, -0.04),
            ("Duels aériens gagnés", "Duels aériens"): (0.02, -0.03),
            ("Duels défensifs gagnés", "Duels défensifs"): (0.07, -0.08),

            # Tacles
            ("Tacles glissés réussis", "Tacles glissés"): (0.05, -0.055),

            # Autres
            "Duels ballons gagnés": 0.04,
            "Duels ballons perdus": -0.06,
            "Récupérations": 0.06,
            "Récupérations dans le terrain adverse": 0.08,
            "Interceptions": 0.05,
            "Pertes": -0.055,
            "Pertes dans le propre terrain": -0.12,

            # Finition / Création
            "But": 1.5,
            "Passe décisive": 1.0,
            "Passes décisives avec tir": 0.09,
            "Secondes passes décisives": 0.05,
            "Courses progressives": 0.065,
            "Touches de balle dans la surface de réparation": 0.01,

            # Discipline
            "Fautes subies": 0.03,
            "Faute": -0.06,
            "Hors-jeu": -0.03,
            "Cartons rouges": -2.4,
            "Cartons jaunes": -0.9,
        },
        "Défenseur central": {
            # Passes
            ("Passes précises", "Passes"): (0.005, -0.05),
            ("Passes longues précises", "Passes longues"): (0.015, -0.025),
            ("Passes en profondeur précises", "Passes en profondeur"): (0.02, -0.015),
            ("Passes dans le 3ème tiers précises", "Passes dans le 3ème tiers"): (0.015, -0.015),
            ("Passes vers la surface de réparation précises", "Passes vers la surface de réparation"): (0.015, -0.015),
            ("Passes en avant précises", "Passes en avant"): (0.008, -0.02),
            ("Passes arrière précises", "Passes arrière"): (0.001, -0.05),

            # Jeu offensif
            ("Tirs cadrés", "Tirs"): (0.02, -0.01),
            ("Centres précis", "Centres"): (0.01, -0.01),
            ("Dribbles réussis", "Dribbles"): (0.015, -0.015),

            # Duels
            ("Duels gagnés", "Duels"): (0.05, -0.05),
            ("Duels offensifs gagnés", "Duels offensifs"): (0.025, -0.01),
            ("Duels aériens gagnés", "Duels aériens"): (0.07, -0.1),
            ("Duels défensifs gagnés", "Duels défensifs"): (0.08, -0.1),

            # Tacles
            ("Tacles glissés réussis", "Tacles glissés"): (0.03, -0.06),

            # Autres
            "Duels ballons gagnés": 0.05,
            "Duels ballons perdus": -0.075,
            "Récupérations": 0.07,
            "Récupérations dans le terrain adverse": 0.08,
            "Interceptions": 0.06,
            "Pertes": -0.08,
            "Pertes dans le propre terrain": -0.1,

            # Finition / Création
            "But": 1.5,
            "Passe décisive": 1.0,
            "Passes décisives avec tir": 0.03,
            "Secondes passes décisives": 0.02,
            "Courses progressives": 0.015,
            "Touches de balle dans la surface de réparation": 0.005,

            # Discipline
            "Fautes subies": 0.03,
            "Faute": -0.05,
            "Hors-jeu": -0.02,
            "Cartons rouges": -2.5,
            "Cartons jaunes": -0.9,
        },
        "Gardien": {
            # Passes
            ("Passes précises", "Passes"): (0.005, -0.1),
            ("Passes longues précises", "Passes longues"): (0.01, -0.04),
            ("Passes en profondeur précises", "Passes en profondeur"): (0.007, -0.03),
            ("Passes dans le 3ème tiers précises", "Passes dans le 3ème tiers"): (0.002, -0.03),
            ("Passes vers la surface de réparation précises", "Passes vers la surface de réparation"): (0.003, -0.03),
            ("Passes en avant précises", "Passes en avant"): (0.003, -0.03),
            ("Passes arrière précises", "Passes arrière"): (0.001, -0.12),

            # Jeu offensif
            ("Tirs cadrés", "Tirs"): (0.01, -0.01),
            ("Centres précis", "Centres"): (0.01, -0.01),
            ("Dribbles réussis", "Dribbles"): (0.01, -0.01),

            # Duels
            ("Duels gagnés", "Duels"): (0.015, -0.05),
            ("Duels offensifs gagnés", "Duels offensifs"): (0.015, -0.05),
            ("Duels aériens gagnés", "Duels aériens"): (0.03, -0.07),
            ("Duels défensifs gagnés", "Duels défensifs"): (0.04, -0.08),

            # Tacles
            ("Tacles glissés réussis", "Tacles glissés"): (0.02, -0.04),

            # Autres
            "Duels ballons gagnés": 0.03,
            "Duels ballons perdus": -0.06,
            "Récupérations": 0.025,
            "Récupérations dans le terrain adverse": 0.01,
            "Interceptions": 0.025,
            "Pertes": -0.12,
            "Pertes dans le propre terrain": -0.2,

            # Finition / Création
            "But": 1.5,
            "Passe décisive": 1.0,
            "Passes décisives avec tir": 0.03,
            "Secondes passes décisives": 0.01,
            "Courses progressives": 0.01,
            "Touches de balle dans la surface de réparation": 0.01,

            # Discipline
            "Fautes subies": 0.01,
            "Faute": -0.07,
            "Hors-jeu": -0.01,
            "Cartons rouges": -3.0,
            "Cartons jaunes": -1.0,

            # Spécificités gardien
            "Dégagements": 0.04,
            "Sorties": 0.09,
            "Arrêts": 0.25,
            "Arrêts réflexes": 0.5,
            "Tirs contre": 0.01,

            # Sur/sous-performance
            ("xCG", "Buts concédés"): 1.0,
        }
    }

    coeffs = coefficients[poste]

    for key, coef in coeffs.items():
        if key == ("xCG", "Buts concédés"):
            xcg = df_match["xCG"].sum()
            buts = df_match["Buts concédés"].sum()
            note += (xcg - buts) * coef
        elif isinstance(key, tuple):
            col_ok, col_tot = key
            coef_success, coef_fail = coef
            ok = df_match[col_ok].sum()
            total = df_match[col_tot].sum()
            ko = total - ok
            note += ok * coef_success + ko * coef_fail
        else:
            if key in df_match.columns:
                note += df_match[key].sum() * coef

    equipes_score = match.split(" ")
    equipes = " ".join(equipes_score[:-1])
    score_str = equipes_score[-1]

    equipe_dom, _ = equipes.split(" - ")
    score_dom, score_ext = map(int, score_str.split(":"))

    if "Cannes" in equipe_dom:
        buts_cannes = score_dom
        buts_adverse = score_ext
    else:
        buts_cannes = score_ext
        buts_adverse = score_dom

    if buts_cannes > buts_adverse:
        note += 0.5
    elif buts_cannes < buts_adverse:
        note -= 0.5

    if poste in ["Défenseur central", "Latéral", "Gardien"]:
        note -= 0.25 * df_match["Buts concédés"].sum()

    return max(0, min(10, round(note, 1)))

def ajouter_pourcentages(df):
    pourcentages = {
        "% de dribbles réussis": ("Dribbles réussis", "Dribbles"),
        "% de duels défensifs gagnés": ("Duels défensifs gagnés", "Duels défensifs"),
        "% de duels aériens gagnés": ("Duels aériens gagnés", "Duels aériens"),
        "% de tirs cadrés": ("Tirs cadrés", "Tirs"),
        "% de centres précis": ("Centres précis", "Centres"),
        "% de passes longues précises": ("Passes longues précises", "Passes longues"),
        "% de passes en avant précises": ("Passes en avant précises", "Passes en avant"),
        "% de passes dans le 3ème tiers précises": ("Passes dans le 3ème tiers précises", "Passes dans le 3ème tiers"),
        "% de duels offensifs gagnés": ("Duels offensifs gagnés", "Duels offensifs"),
        "% de passes précises": ("Passes précises", "Passes")
    }

    for new_col, (num, den) in pourcentages.items():
        df[new_col] = df.apply(
            lambda row: (row[num] / row[den] * 100) if pd.notnull(row[den]) and row[den] > 0 else 0,
            axis=1
        )

    return df

def get_position_feature_weights(position, kpi_structure, kpi_weights):
    feature_weights = {}

    for kpi_name, features in kpi_structure[position].items():
        kpi_weight = kpi_weights[position].get(kpi_name, 1)
        for feature_name, feature_weight in features.items():
            total_weight = kpi_weight * feature_weight
            feature_weights[feature_name] = total_weight + feature_weights.get(feature_name, 0)
    
    # Normalisation des poids pour que la somme = 1
    total = sum(feature_weights.values())
    for key in feature_weights:
        feature_weights[key] /= total
    
    return feature_weights

def compute_similarity(df, joueur, poste):
    # 1. Filtrage selon le poste et le temps de jeu
    joueur_infos = df[df['Joueur + Information'] == joueur]

    if len(joueur_infos) > 1:
        joueur_infos = compute_weighted_stats_by_minutes(joueur_infos)

    df_filtré = df[(df['Poste'] == poste) & (df['Minutes jouées'] >= 500)]
    df_filtré = df_filtré[df_filtré['Joueur + Information'] != joueur]
    df_filtré = pd.concat([df_filtré, joueur_infos], ignore_index=True)

    # 2. Garder uniquement les colonnes d’intérêt
    feature_weights = get_position_feature_weights(poste, kpi_by_position, kpi_coefficients_by_position)
    selected_features = list(feature_weights.keys())
    df_filtré = df_filtré[['Joueur + Information', 'Âge', 'Minutes jouées', 'Contrat expiration'] + selected_features]

    # 3. Normalisation des features
    scaler = StandardScaler()
    stats_scaled = scaler.fit_transform(df_filtré[selected_features])
    df_scaled = pd.DataFrame(stats_scaled, columns=selected_features, index=df_filtré['Joueur + Information'])

    # 4. Pondération & distance cosinus
    weights = np.array([feature_weights[feat] for feat in selected_features])
    weights = weights / weights.sum()

    # On applique la pondération
    weighted_features = df_scaled * weights

    # Remplacer les NaN et inf par 0
    weighted_features = weighted_features.replace([np.inf, -np.inf], np.nan).fillna(0)

    # Récupérer le vecteur du joueur de référence
    ref_vector = weighted_features.loc[joueur].values.reshape(1, -1)

    # Calcul des distances cosinus pondérées
    similarities = cosine_similarity(weighted_features, ref_vector).flatten()

    # Création du DataFrame final
    df_filtré['Score de similarité'] = ((similarities + 1) / 2 * 100).round(1)
    df_sorted = df_filtré.sort_values(by='Score de similarité', ascending=False)

    df_sorted = df_sorted[['Joueur + Information', 'Âge', 'Minutes jouées', 'Contrat expiration', 'Score de similarité']]

    # Sécuriser la suppression des lignes correspondantes au joueur
    nom_joueur = joueur.strip().split(' - ')[0]
    df_sorted = df_sorted[
        ~df_sorted['Joueur + Information']
        .fillna('')
        .astype(str)
        .str.startswith(nom_joueur)
    ]

    return df_sorted

def create_player_data(nom_joueur, sélection_dataframe):
    file_path = f"data/Data {st.session_state['saison']}/Player stats {nom_joueur}.xlsx"

    if os.path.exists(file_path):
        df_player = pd.read_excel(file_path)
    else:
        st.warning(f"⚠️ Fichier non trouvé pour le joueur : {nom_joueur}.")
        st.stop()

    colonnes = [
        "Match",
        "Competition",
        "Date",
        "Place",
        "Minutes jouées",
        "Total actions",
        "Total actions réussies",
        "But",
        "Passe décisive",
        "Tirs",
        "Tirs cadrés",
        "xG",
        "Passes",
        "Passes précises",
        "Passes longues",
        "Passes longues précises",
        "Centres",
        "Centres précis",
        "Dribbles",
        "Dribbles réussis",
        "Duels",
        "Duels gagnés",
        "Duels aériens",
        "Duels aériens gagnés",
        "Interceptions",
        "Pertes",
        "Pertes dans le propre terrain",
        "Récupérations",
        "Récupérations dans le terrain adverse",
        "Carton jaune",
        "Carton rouge",
        "Duels défensifs",
        "Duels défensifs gagnés",
        "Duels ballons perdus",
        "Duels ballons gagnés",
        "Tacles glissés",
        "Tacles glissés réussis",
        "Dégagements",
        "Faute",
        "Cartons jaunes",
        "Cartons rouges",
        "Passes décisives avec tir",
        "Duels offensifs",
        "Duels offensifs gagnés",
        "Touches de balle dans la surface de réparation",
        "Hors-jeu",
        "Courses progressives",
        "Fautes subies",
        "Passes en profondeur",
        "Passes en profondeur précises",
        "xA",
        "Secondes passes décisives",
        "Passes dans le 3ème tiers",
        "Passes dans le 3ème tiers précises",
        "Passes vers la surface de réparation",
        "Passes vers la surface de réparation précises",
        "Passes réceptionnées",
        "Passes en avant",
        "Passes en avant précises",
        "Passes arrière",
        "Passes arrière précises",
        "Buts concédés",
        "xCG",
        "Tirs contre",
        "Arrêts",
        "Arrêts réflexes",
        "Sorties",
        "Passes au gardien de but",
        "Passes au gardien de but précises",
        "But sur coup franc",
        "But sur coup franc courtes",
        "But sur coup franc longues"
    ]

    # Renommer les colonnes
    df_player.columns = colonnes

    if sélection_dataframe == 'Joueur du championnat de France' or sélection_dataframe == 'Joueur de National 1 et National 2':
        df_player = df_player[df_player['Competition'] == 'France. National 2']

    return df_player

def plot_rating_bars_panel(df, joueur_scores, kpis):
    n = len(kpis)

    # dimensions : hauteur adaptable
    fig_h = max(1.1 * n, 3)
    fig, ax = plt.subplots(figsize=(7.2, fig_h))

    # positions Y (haut -> bas)
    y = np.arange(n)[::-1]
    bar_h = 0.55

    # largeur de référence (0→100)
    ax.barh(y, 100, height=bar_h, left=0, color="None", edgecolor="#3d3a2a")

    # boucle des KPI
    for yi, kpi in zip(y, kpis):
        # récup valeurs pour percentile + note du joueur
        values = np.asarray(df[kpi].dropna(), dtype=float)
        player_rating = float(joueur_scores[kpi])

        # couleur selon percentile
        percentile = stats.percentileofscore(values, player_rating)
        fill_color = assign_color(percentile)

        # borne dans [0,100] si c'est une échelle 0-100 (sinon supprime clamp)
        pr_clamped = max(0, min(100, percentile))

        # barre de valeur
        ax.barh(yi, pr_clamped, height=bar_h, left=0, color=fill_color, edgecolor="#3d3a2a")

        # label KPI à gauche
        ax.text(-2, yi, str(kpi), va="center", ha="right", fontsize=11, color="#3d3a2a")

        # note à droite
        ax.text(102, yi + 0.1, f"Note : " + r"$\mathbf{" + f"{player_rating:.1f}" + "}$",
                va="center", ha="left", fontsize=11, color="#3d3a2a")

        ax.text(102, yi - 0.1, f"Percentile : " + r"$\mathbf{" + f"{percentile:.1f}" + "}$",
                va="center", ha="left", fontsize=11, color="#3d3a2a")

    # axes & cadresss
    ax.set_yticks([])
    ax.set_xticks([])

    for spine in ax.spines.values():
        spine.set_visible(False)

    plt.tight_layout()

    fig.set_facecolor('#f4f3ed')
    ax.set_facecolor('#f4f3ed')

    return fig

def points_forts_faibles(df, joueur, poste):
    joueur_infos = df[df['Joueur + Information'] == joueur]

    if len(joueur_infos) > 1:
        joueur_infos = compute_weighted_stats_by_minutes(joueur_infos)

    df_filtré = df[(df['Poste'] == poste) & (df['Minutes jouées'] >= 500)]
    df_filtré = df_filtré[df_filtré['Joueur + Information'] != joueur]
    df_filtré = pd.concat([df_filtré, joueur_infos], ignore_index=True)

    df_ranked = rank_columns(df_filtré)

    joueur_data = df_ranked[df_ranked['Joueur + Information'] == joueur].iloc[0]
    points_forts = {}
    points_faibles = {}

    for col in joueur_data.index:
        if pd.api.types.is_numeric_dtype(type(joueur_data[col])):
            value = joueur_data[col]
            if value >= 80:
                points_forts[col] = value
            elif value <= 20:
                points_faibles[col] = value

    return points_forts, points_faibles

def plot_player_ranking(df, joueur, poste):
    # --- sélection du joueur ---
    joueur_infos = df[df['Joueur + Information'] == joueur]
    if len(joueur_infos) > 1:
        joueur_infos = compute_weighted_stats_by_minutes(joueur_infos)

    # --- pool de comparaison ---
    df_filtré = df[(df['Poste'] == poste) & (df['Minutes jouées'] >= 500)]
    df_filtré = df_filtré[df_filtré['Joueur + Information'] != joueur]
    df_filtré = pd.concat([df_filtré, joueur_infos], ignore_index=True)

    # --- ranking ---
    df_ranked = rank_columns(df_filtré)
    row_rank = df_ranked.loc[df_ranked['Joueur + Information'] == joueur].iloc[0]
    row_raw  = df_filtré.loc[df_filtré['Joueur + Information'] == joueur].iloc[0]

    # --- colonnes numériques ---
    exclude = {'Joueur + Information','Poste','Minutes jouées','Âge','Valeur sur le marché','Matchs joués','Taille','Poids'}
    numeric_cols = [c for c in df_ranked.columns if c not in exclude and pd.api.types.is_numeric_dtype(df_ranked[c])]

    # --- items ---
    items = []
    ordered_keys = list(métriques_par_catégorie.keys())
    if "Général" in ordered_keys:
        ordered_keys = ["Général"] + [k for k in ordered_keys if k != "Général"]

    for cat in ordered_keys:
        mets = [m for m in métriques_par_catégorie[cat] if m in numeric_cols]
        if not mets:
            continue
        if len(items) > 0:
            items.append(("spacer", None))
        items.append(("header", cat))
        for m in mets:
            items.append(("metric", m, row_raw.get(m, np.nan), row_rank.get(m, np.nan)))

    # --- layout ---
    bg, ink, mute, rail = "#f4f3ed", "#3d3a2a", "#3d3a2a", "#f4f3ed"
    bar_len   = 55
    val_gap   = 0.6
    val_strip = 6.0
    category_gap = 1.6
    line_gap = 0.75

    # positions Y
    y_seq, y = [], 0.0
    for it in items:
        if it[0] == "spacer":
            y += category_gap
            continue
        y_seq.append(y)
        y += 1.0 if it[0] == "header" else line_gap  # 🔹 plus espacé entre lignes
    y_seq = np.array(y_seq)
    y_plot = (y_seq.max()) - y_seq

    n_metrics = sum(1 for t,*_ in items if t == "metric")
    n_spacers = sum(1 for t,*_ in items if t == "spacer")
    fig_h = max(6.5, min(28, 0.37*n_metrics + 1.0*n_spacers*category_gap + 2.2))
    fig_w = 11.5

    fig = plt.figure(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor(bg)
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.4, 2.4], wspace=0.25)

    axL = fig.add_subplot(gs[0, 0])
    axR = fig.add_subplot(gs[0, 1])

    for ax in (axL, axR):
        ax.set_facecolor(bg)
        ax.set_ylim(min(y_plot)-0.5, max(y_plot)+0.5)
        ax.set_yticks([]); ax.set_xticks([])
        for s in ax.spines.values():
            s.set_visible(False)

    # --- gauche : labels
    axL.set_xlim(0, 1)
    for yi, it in zip(y_plot, [i for i in items if i[0] != "spacer"]):
        if it[0] == "header":
            axL.text(0.02, yi, it[1], ha="left", va="center",
                     fontsize=12.5, fontweight="bold", color=ink, transform=axL.transData)
        elif it[0] == "metric":
            axL.text(0.02, yi, it[1], ha="left", va="center",
                     fontsize=10.5, color=ink, transform=axL.transData)

    # --- droite : barres + valeurs
    axR.set_xlim(-(val_strip), bar_len + 3)

    bar_y, bar_vals, raw_vals = [], [], []
    for yi, it in zip(y_plot, [i for i in items if i[0] != "spacer"]):
        if it[0] == "metric":
            _, name, raw, pct = it
            bar_y.append(yi)
            bar_vals.append(0.0 if pd.isna(pct) else pct)
            raw_vals.append(raw)

    # rails + barres
    bar_height = 0.5
    axR.barh(bar_y, [bar_len]*len(bar_y), height=bar_height, color=rail, edgecolor="#3d3a2a", zorder=2)
    axR.barh(bar_y, [v*bar_len/100 for v in bar_vals], height=bar_height,
             color=[assign_color(v) for v in bar_vals], edgecolor="#3d3a2a", zorder=3)

    # valeurs gauche
    for yi, txt in zip(bar_y, raw_vals):
        axR.text(-val_gap, yi, txt, ha="right", va="center", fontsize=10.5, color=mute)

    # pourcentages alignés au bout du rail (100%)
    rail_offset = 0.4
    for yi, v in zip(bar_y, bar_vals):
        txt = "—" if np.isnan(v) else f"{int(v):d}%"
        axR.text(bar_len + rail_offset, yi, txt,
                 ha="left", va="center", fontsize=10.5, color=mute)

    plt.subplots_adjust(left=0.05, right=0.98, top=0.98, bottom=0.04)
    return fig

def calcul_ipr(df, joueur, poste):
    joueur_infos = df[df['Joueur + Information'] == joueur]

    df_filtré = df[(df['Poste'] == poste) & (df['Minutes jouées'] >= 500)].copy()

    if joueur not in df_filtré['Joueur + Information'].values:
        df_filtré = pd.concat([df_filtré, joueur_infos], ignore_index=True)

    df_filtré["influence"] = (
        df_filtré["Passes réceptionnées par 90"]
        + df_filtré["Longues passes réceptionnées par 90"]
    )

    df_filtré["IPR Viseur"] = (
        (df_filtré["Passes judicieuses par 90"]
        + df_filtré["Passes quasi décisives par 90"]
        + df_filtré["Passes dans tiers adverse par 90"]
        + df_filtré["Passes vers la surface de réparation par 90"]
        + df_filtré["Passes pénétrantes par 90"]
        + df_filtré["Passes progressives par 90"])
        / df_filtré["influence"]
    )

    df_filtré["IPR Perforateur"] = (
        (df_filtré["Courses progressives par 90"]
        + df_filtré["Accélérations par 90"])
        / df_filtré["influence"]
    )

    df_filtré["IPR Duelliste"] = df_filtré["Dribbles par 90"] / df_filtré["influence"]

    df_filtré["IPR"] = (
        df_filtré["IPR Viseur"] / 6
        + df_filtré["IPR Perforateur"] / 2
        + df_filtré["IPR Duelliste"]
    )

    df_ranked = rank_columns(df_filtré)

    return df_ranked

def get_player_metrics_by_position(df, player_name, smart_goal, analyse_par_poste, season):
    position = None
    for pos, players in smart_goal[season].items():
        if player_name in players:
            position = pos
            break

    # 2. Récupérer les métriques associées à ce poste
    poste_block = next(p for p in analyse_par_poste if p["position"] == position)

    metrics = (
        list(poste_block["animation_offensive"].items()) +
        list(poste_block["animation_défensive"].items())
    )

    selected_cols = []

    for col_name, metric in metrics:
        # Cas 1 : métrique simple
        if "/" not in metric and "-" not in metric:
            if metric in df.columns:
                df[col_name] = df[metric].round(1)
                selected_cols.append(col_name)

        # Cas 2 : métrique du type "A / B"
        if "/" in metric and "-" not in metric:
            num, den = [m.strip() for m in metric.split("/")]

            if num in df.columns and den in df.columns:
                df[col_name] = (df[num] / df[den].replace(0, np.nan) * 100).round(1).astype(str) + "%"
                selected_cols.append(col_name)

        # Cas 3 : métrique du type "A - B"
        if "-" in metric and "/" not in metric:
            part_a, part_b = [m.strip() for m in metric.split("-")]

            if part_a in df.columns and part_b in df.columns:
                df[col_name] = (df[part_a] - df[part_b]).round(1)
                selected_cols.append(col_name)

    return df[selected_cols]

def streamlit_application(all_df_dict):
    with st.sidebar:
        st.selectbox(
            "Saison",
            ["24-25", "25-26"],
            key="saison",
            label_visibility="collapsed"
        )
    
        page = option_menu(
            menu_title="",
            options=st.secrets['roles'].get(st.session_state.username, []),
            icons=["house", "bar-chart", "camera-video", "graph-up-arrow", "person", "people", "search"],
            menu_icon="cast",
            default_index=0,
            orientation="vertical",
            styles={
                "container": {"padding": "5!important", "background-color": "transparent"},
                "icon": {"font-size": "18px"},
                "nav-link": {
                    "font-size": "16px",
                    "text-align": "left",
                    "margin":"0px",
                    "--hover-color": "#f4f3ed"
                },
                "nav-link-selected": {
                    "background-color": "#AC141A",
                    "color": "#ecebe3",
                    "font-weight": "bold"
                }
            }
        )

        st.sidebar.markdown(
            """
            <div style='text-align: center; padding-top: 10px;'>
                <img src='https://i.postimg.cc/0j1RhZV5/Dragon-couleur-png.png' width='120'>
            </div>
            """,
            unsafe_allow_html=True
        )

    all_df = all_df_dict[f"all_df_{st.session_state['saison'].replace('-', '_')}"]

    if page == "Accueil":
        st.header("Accueil")

        st.write("""
            L'Association sportive de Cannes est un club de football français fondé en 1902 et basé à Cannes, dans les Alpes-Maritimes.

            Vainqueur de la Coupe de France en 1932, l'AS Cannes intègre cette année-là le championnat de France professionnel. Après de nombreuses saisons en deuxième division (1950-1987), le club connaît son apogée sportif entre 1988 et 1998 en participant au Championnat de France de football (première division française de football) et en se qualifiant à deux reprises pour la Coupe UEFA. 

            À l'été 2014, le club azuréen est exclu par la Fédération française de football des championnats nationaux en raison de problèmes financiers. Reparti du 7e échelon du football français, le club évolue actuellement dans le Championnat de France de football de National 2.

            Le club a formé Zinédine Zidane, Patrick Vieira, Johan Micoud ou encore Sébastien Frey. En juillet 2019, le bureau exécutif de la Ligue de Football Amateur a décerné au club le “Label Jeunes Élite”, plus haute distinction de formation française de jeunes. 

            Le 26 juin 2023, l'AS Cannes est officiellement rachetée par le groupe américain Friedkin.
        """)

    elif page == "Classement":
        col1, col2 = st.columns(2)

        with col1:
            championnat = st.selectbox("Sélectionnez un championnat", ['National 2', 'National 3'])

        with col2:
            if championnat == 'National 2':
                groupe = st.selectbox("Sélectionnez un groupe", ['Groupe A', 'Groupe B', 'Groupe C'])
            else:
                groupe = st.selectbox("Sélectionnez un groupe", ['Groupe A', 'Groupe B', 'Groupe C', 'Groupe D', 'Groupe E', 'Groupe F', 'Groupe G', 'Groupe H'])

        tab1, tab2 = st.tabs(["Classement", "Buteurs + passeurs"])

        with tab1:
            type_classement = st.selectbox("Sélectionnez un type de classement", ['Général', 'Domicile', 'Extérieur'])

            col1, col2 = st.columns(2)

            with col1:
                journée_début = st.number_input("Sélectionnez la journée de début", min_value=1, max_value=30, value=1)

            with col2:
                journée_fin = st.number_input("Sélectionnez la journée de fin", min_value=1, max_value=30, value=30)

            if journée_fin < journée_début:
                st.warning("⚠️ La journée de fin doit être supérieure ou égale à la journée de début.")

            else:
                division = {
                    "24-25": {
                        "National 2": {
                            "Groupe A": f"https://www.foot-national.com/data/2024-2025-classement-national2-groupe-a-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html",
                            "Groupe B": f"https://www.foot-national.com/data/2024-2025-classement-national2-groupe-b-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html",
                            "Groupe C": f"https://www.foot-national.com/data/2024-2025-classement-national2-groupe-c-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html"
                        },
                        "National 3": {
                            "Groupe A": f"https://www.foot-national.com/data/2024-2025-classement-national3-groupe-a-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html",
                            "Groupe B": f"https://www.foot-national.com/data/2024-2025-classement-national3-groupe-b-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html",
                            "Groupe C": f"https://www.foot-national.com/data/2024-2025-classement-national3-groupe-c-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html",
                            "Groupe D": f"https://www.foot-national.com/data/2024-2025-classement-national3-groupe-d-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html",
                            "Groupe E": f"https://www.foot-national.com/data/2024-2025-classement-national3-groupe-e-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html",
                            "Groupe F": f"https://www.foot-national.com/data/2024-2025-classement-national3-groupe-f-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html",
                            "Groupe G": f"https://www.foot-national.com/data/2024-2025-classement-national3-groupe-g-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html",
                            "Groupe H": f"https://www.foot-national.com/data/2024-2025-classement-national3-groupe-h-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html"
                        }
                    },
                    "25-26": {
                        "National 2": {
                            "Groupe A": f"https://www.foot-national.com/data/2025-2026-classement-national2-groupe-a-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html",
                            "Groupe B": f"https://www.foot-national.com/data/2025-2026-classement-national2-groupe-b-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html",
                            "Groupe C": f"https://www.foot-national.com/data/2025-2026-classement-national2-groupe-c-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html"
                        },
                        "National 3": {
                            "Groupe A": f"https://www.foot-national.com/data/2025-2026-classement-national3-groupe-a-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html",
                            "Groupe B": f"https://www.foot-national.com/data/2025-2026-classement-national3-groupe-b-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html",
                            "Groupe C": f"https://www.foot-national.com/data/2025-2026-classement-national3-groupe-c-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html",
                            "Groupe D": f"https://www.foot-national.com/data/2025-2026-classement-national3-groupe-d-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html",
                            "Groupe E": f"https://www.foot-national.com/data/2025-2026-classement-national3-groupe-e-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html",
                            "Groupe F": f"https://www.foot-national.com/data/2025-2026-classement-national3-groupe-f-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html",
                            "Groupe G": f"https://www.foot-national.com/data/2025-2026-classement-national3-groupe-g-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html",
                            "Groupe H": f"https://www.foot-national.com/data/2025-2026-classement-national3-groupe-h-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html"
                        }
                    }
                }

                url = division[st.session_state['saison']][championnat][groupe]
                
                response = requests.get(url)
                response.encoding = "ISO-8859-1"

                tables = pd.read_html(response.text)

                classement = tables[0]
                classement = classement.iloc[:, :-1]

                classement.columns = [col.replace('\xa0', ' ').strip() for col in classement.columns]

                classement = classement.rename(columns={'Rangs': 'Classement'})

                st.dataframe(classement, use_container_width=True, hide_index=True)
            
        with tab2:
            url = "https://www.transfermarkt.fr/championnat-national-2-groupe-c/scorerliste/wettbewerb/CN2C/saison_id/2025"

            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "fr-FR,fr;q=0.9",
                "Referer": "https://www.transfermarkt.fr/",
            }

            r = requests.get(url, headers=headers, timeout=30)
            r.raise_for_status()

            soup = BeautifulSoup(r.text, "lxml")
            table = soup.select_one("table.items")

            rows = []
            for tr in table.select("tbody > tr"):
                tds = tr.find_all("td")

                classement = int(tds[0].get_text(strip=True))
                joueur = tds[1].find("a").get_text(strip=True)
                poste = tds[4].get_text(strip=True)
                age = int(tds[7].get_text(strip=True))
                matchs = int(tds[8].get_text(strip=True))
                buts = int(tds[9].get_text(strip=True))
                passes_d = int(tds[10].get_text(strip=True))
                total = int(tds[11].get_text(strip=True))

                rows.append({
                    "Classement": classement,
                    "Joueur": joueur,
                    "Âge": age,
                    "Poste": poste,
                    "Matchs joués": matchs,
                    "Buts": buts,
                    "Passes décisives": passes_d,
                    "Total": total
                })

            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

    elif page == "Vidéo des buts":
        st.header("Vidéo des buts")

        tab1, tab2 = st.tabs(['Vidéos par équipe', 'Vidéos par journée'])

        journées = {
            "24-25": {
                "J24": [
                    'Anglet Genets Foot VS Le Puy Foot 43',
                    'Angoulême Charente FC VS Andrézieux-Bouthéon FC',
                    'AS Saint-Priest VS Jura Sud Foot',
                    'EFC Fréjus Saint-Raphaël VS AS Cannes',
                    'FC Istres VS Bergerac Périgord FC',
                    'Goal FC VS SC Toulon',
                    'Hyeres FC VS GFA Rumilly Vallieres',
                    'RCP Grasse VS Marignane Gignac FC'
                ],
                "J25": [
                    'Andrézieux-Bouthéon FC VS EFC Fréjus Saint-Raphaël',
                    'AS Cannes VS Goal FC',
                    'Bergerac Périgord FC VS RCP Grasse',
                    'GFA Rumilly Vallieres VS Angoulême Charente FC',
                    'Jura Sud Foot VS Anglet Genets Foot',
                    'Le Puy Foot 43 VS Hyeres FC',
                    'Marignane Gignac FC VS AS Saint-Priest',
                    'SC Toulon VS FC Istres'
                ],
                "J26": [
                    'Anglet Genets Foot VS Marignane Gignac FC',
                    'Angoulême Charente FC VS Le Puy Foot 43',
                    'Bergerac Périgord FC VS SC Toulon',
                    'EFC Fréjus Saint-Raphaël VS GFA Rumilly Vallieres',
                    'FC Istres VS AS Cannes',
                    'Goal FC VS Andrézieux-Bouthéon FC',
                    'Hyeres FC VS Jura Sud Foot',
                    'RCP Grasse VS AS Saint-Priest'
                ],
                "J27": [
                    "Andrézieux-Bouthéon FC VS FC Istres",
                    "AS Cannes VS Bergerac Périgord FC",
                    "AS Saint-Priest VS Anglet Genets Foot",
                    "GFA Rumilly Vallieres VS Goal FC",
                    "Jura Sud Foot VS Angoulême Charente FC",
                    "Le Puy Foot 43 VS EFC Fréjus Saint-Raphaël",
                    "Marignane Gignac FC VS Hyeres FC",
                    "SC Toulon VS RCP Grasse"
                ],
                "J28": [
                    "Angoulême Charente FC VS Marignane Gignac FC",
                    "Bergerac Périgord FC VS Andrézieux-Bouthéon FC",
                    "EFC Fréjus Saint-Raphaël VS Jura Sud Foot",
                    "FC Istres VS GFA Rumilly Vallieres",
                    "Goal FC VS Le Puy Foot 43",
                    "Hyeres FC VS AS Saint-Priest",
                    "RCP Grasse VS Anglet Genets Foot",
                    "SC Toulon VS AS Cannes"
                ],
                "J29": [
                    "Andrézieux-Bouthéon FC VS SC Toulon",
                    "Anglet Genets Foot VS Hyeres FC",
                    "AS Saint-Priest VS Angoulême Charente FC",
                    "GFA Rumilly Vallieres VS Bergerac Périgord FC",
                    "Jura Sud Foot VS Goal FC",
                    "Le Puy Foot 43 VS FC Istres",
                    "Marignane Gignac FC VS EFC Fréjus Saint-Raphaël",
                    "RCP Grasse VS AS Cannes"
                ]
            },
            "25-26": {
                "J1": [
                    'AS Saint-Priest VS Hyères FC',
                    'FC 93 VS SC Toulon',
                    'FC Rousset Sainte-Victoire VS Andrézieux-Bouthéon FC',
                    'GOAL FC VS FC Istres',
                    'Nîmes Olympique VS FC Limonest DSD',
                    'RC Grasse VS EFC Fréjus Saint-Raphaël',
                    'US Créteil Lusitanos VS GFA Rumilly Vallières',
                    'US Lusitanos Saint-Maur VS AS Cannes'
                ],
                "J2": [
                    'FC Istres VS FC Rousset Sainte-Victoire',
                    'FC 93 VS AS Saint-Priest',
                    'SC Toulon VS RC Grasse',
                    'GFA Rumilly Vallières VS Nîmes Olympique',
                    'FC Limonest DSD VS GOAL FC',
                    'Andrézieux-Bouthéon FC VS US Lusitanos Saint-Maur',
                    'EFC Fréjus Saint-Raphaël VS US Créteil Lusitanos',
                    'AS Cannes VS Hyères FC'
                ],
                "J3": [
                    'US Créteil Lusitanos VS SC Toulon',
                    'FC Rousset Sainte-Victoire VS FC Limonest DSD',
                    'GOAL FC VS GFA Rumilly Vallières',
                    'Nîmes Olympique VS EFC Fréjus Saint-Raphaël',
                    'RC Grasse VS FC 93',
                    'US Lusitanos Saint-Maur VS FC Istres',
                    'AS Saint-Priest VS AS Cannes',
                    'Hyères FC VS Andrézieux-Bouthéon FC'
                ],
                "J4": [
                    "Andrézieux-Bouthéon FC VS AS Cannes",
                    "EFC Fréjus Saint-Raphaël VS GOAL FC",
                    "FC 93 VS US Créteil Lusitanos",
                    "GFA Rumilly Vallières VS FC Rousset Sainte-Victoire",
                    "FC Limonest DSD VS US Lusitanos Saint-Maur",
                    "RC Grasse VS AS Saint-Priest",
                    "FC Istres VS Hyères FC",
                    "SC Toulon VS Nîmes Olympique"
                ],
                "J5": [
                    "FC Rousset Sainte-Victoire VS EFC Fréjus Saint-Raphaël",
                    "GOAL FC VS SC Toulon",
                    "Hyères FC VS FC Limonest DSD",
                    "Nîmes Olympique VS FC 93",
                    "US Lusitanos Saint-Maur VS GFA Rumilly Vallières",
                    "AS Saint-Priest VS Andrézieux-Bouthéon FC",
                    "US Créteil Lusitanos VS RC Grasse",
                    "AS Cannes VS FC Istres"
                ],
                "J6": [
                    "EFC Fréjus Saint-Raphaël VS US Lusitanos Saint-Maur",
                    "FC 93 VS GOAL FC",
                    "GFA Rumilly Vallières VS Hyères FC",
                    "RC Grasse VS Nîmes Olympique",
                    "FC Limonest DSD VS AS Cannes",
                    "SC Toulon VS FC Rousset Sainte-Victoire",
                    "FC Istres VS Andrézieux-Bouthéon FC",
                    "AS Saint-Priest VS US Créteil Lusitanos"
                ],
                "J7": [
                    "Andrézieux-Bouthéon FC VS FC Limonest DSD",
                    "AS Cannes VS GFA Rumilly Vallières",
                    "AS Saint-Priest VS FC Istres",
                    "FC Rousset Sainte-Victoire VS FC 93",
                    "GOAL FC VS RC Grasse",
                    "Hyères FC VS EFC Fréjus Saint-Raphaël",
                    "Nîmes Olympique VS US Créteil Lusitanos",
                    "US Lusitanos Saint-Maur VS SC Toulon"
                ],
                "J8": [
                    "EFC Fréjus Saint-Raphaël VS AS Cannes",
                    "FC 93 VS US Lusitanos Saint-Maur",
                    "GFA Rumilly Vallières VS Andrézieux-Bouthéon FC",
                    "FC Limonest DSD VS FC Istres",
                    "Nîmes Olympique VS AS Saint-Priest",
                    "RC Grasse VS FC Rousset Sainte-Victoire",
                    "SC Toulon VS Hyères FC",
                    "US Créteil Lusitanos VS GOAL FC"
                ],
                "J9": [
                    "AS Cannes VS SC Toulon",
                    "GOAL FC VS Nîmes Olympique",
                    "Hyères FC VS FC 93",
                    "US Lusitanos Saint-Maur VS RC Grasse",
                    "FC Rousset Sainte-Victoire VS US Créteil Lusitanos",
                    "AS Saint-Priest VS FC Limonest DSD",
                    "Andrézieux-Bouthéon FC VS EFC Fréjus Saint-Raphaël",
                    "FC Istres VS GFA Rumilly Vallières"
                ],
                "J10": [
                    "EFC Fréjus Saint-Raphaël VS FC Istres",
                    "GFA Rumilly Vallières VS FC Limonest DSD",
                    "GOAL FC VS AS Saint-Priest",
                    "RC Grasse VS Hyères FC",
                    "Nîmes Olympique VS FC Rousset Sainte-Victoire",
                    "SC Toulon VS Andrézieux-Bouthéon FC",
                    "FC 93 VS AS Cannes",
                    "US Créteil Lusitanos VS US Lusitanos Saint-Maur"
                ],
                "J11": [
                    "AS Cannes VS RC Grasse",
                    "Hyères FC VS US Créteil Lusitanos",
                    "FC Istres VS SC Toulon",
                    "US Lusitanos Saint-Maur VS Nîmes Olympique",
                    "FC Rousset Sainte-Victoire VS GOAL FC",
                    "AS Saint-Priest VS GFA Rumilly Vallières",
                    "FC Limonest DSD VS EFC Fréjus Saint-Raphaël",
                    "Andrézieux-Bouthéon FC VS FC 93"
                ],
                "J12": [
                    "EFC Fréjus Saint-Raphaël VS GFA Rumilly Vallières",
                    "FC Rousset Sainte-Victoire VS AS Saint-Priest",
                    "Nîmes Olympique VS Hyères FC",
                    "RC Grasse VS Andrézieux-Bouthéon FC",
                    "SC Toulon VS FC Limonest DSD",
                    "GOAL FC VS US Lusitanos Saint-Maur",
                    "FC 93 VS FC Istres",
                    "US Créteil Lusitanos VS AS Cannes"
                ],
                "J13": [
                    "AS Cannes VS Nîmes Olympique",
                    "Hyères FC VS GOAL FC",
                    "US Lusitanos Saint-Maur VS FC Rousset Sainte-Victoire",
                    "FC Istres VS RC Grasse",
                    "AS Saint-Priest VS EFC Fréjus Saint-Raphaël",
                    "Andrézieux-Bouthéon FC VS US Créteil Lusitanos",
                    "FC Limonest DSD VS FC 93",
                    "GFA Rumilly Vallières VS SC Toulon"
                ],
                "J14": [
                    "FC Rousset Sainte-Victoire VS Andrézieux-Bouthéon FC",
                    "GOAL FC VS AS Cannes",
                    "Nîmes Olympique VS Andrézieux-Bouthéon FC",
                    "RC Grasse VS FC Limonest DSD",
                    "SC Toulon VS EFC Fréjus Saint-Raphaël",
                    "US Lusitanos Saint-Maur VS AS Saint-Priest",
                    "FC 93 VS GFA Rumilly Vallières",
                    "US Créteil Lusitanos VS FC Istres"
                ],
                "J15": [
                    "Hyères FC VS US Lusitanos Saint-Maur",
                    "AS Cannes VS FC Rousset Sainte-Victoire",
                    "FC Istres VS Nîmes Olympique",
                    "SC Toulon VS AS Saint-Priest",
                    "EFC Fréjus Saint-Raphaël VS FC 93",
                    "GFA Rumilly Vallières VS RC Grasse",
                    "Andrézieux-Bouthéon FC VS GOAL FC",
                    "FC Limonest DSD VS US Créteil Lusitanos"
                ],
                "J16": [
                    "FC Rousset Sainte-Victoire VS FC Istres",
                    "Hyères FC VS AS Cannes",
                    "Nîmes Olympique VS GFA Rumilly Vallières",
                    "RC Grasse VS SC Toulon",
                    "US Lusitanos Saint-Maur VS Andrézieux-Bouthéon FC",
                    "AS Saint-Priest VS FC 93",
                    "GOAL FC VS FC Limonest DSD",
                    "US Créteil Lusitanos VS EFC Fréjus Saint-Raphaël"
                ],
                "J17": [
                    "AS Cannes VS AS Saint-Priest",
                    "FC 93 VS RC Grasse",
                    "EFC Fréjus Saint-Raphaël VS Nîmes Olympique",
                    "GFA Rumilly Vallières VS GOAL FC",
                    "FC Limonest DSD VS FC Rousset Sainte-Victoire",
                    "SC Toulon VS US Créteil Lusitanos",
                    "FC Istres VS US Lusitanos Saint-Maur",
                    "Andrézieux-Bouthéon FC VS Hyères FC"
                ]
            }
        }

        with tab1:
            col1, col2 = st.columns([3, 1])

            équipes = sorted({
                club.strip()
                for matchs in journées[st.session_state['saison']].values()
                for match in matchs
                for club in match.split("VS")
            })

            with col1:
                équipe = st.selectbox("Sélectionnez une équipe", équipes)
            with col2:
                journée = st.selectbox("Sélectionnez une journée", list(journées[st.session_state['saison']].keys()), key="sb_journee_tab1")

            match = next((m for m in journées[st.session_state['saison']][journée] if équipe in m), None)

            # Affichage si la vidéo existe
            if os.path.exists(f"data/Data {st.session_state['saison']}/{journée} - {match}.mp4"):
                st.video(f"data/Data {st.session_state['saison']}/{journée} - {match}.mp4")
            else:
                st.warning("⚠️ Vidéo non disponible pour ce match : il est possible qu'il n'y ait pas eu de but (0-0) ou que la vidéo ne soit pas encore disponible.")

        with tab2:
            col1, col2 = st.columns([1, 3])

            with col1:
                journée = st.selectbox("Sélectionnez une journée", list(journées[st.session_state['saison']].keys()), key="sb_journee_tab2")
            with col2:
                match = st.selectbox("Sélectionnez un match", journées[st.session_state['saison']][journée])

            # Affichage si la vidéo existe
            if os.path.exists(f"data/Data {st.session_state['saison']}/{journée} - {match}.mp4"):
                st.video(f"data/Data {st.session_state['saison']}/{journée} - {match}.mp4")
            else:
                st.warning("⚠️ Vidéo non disponible pour ce match : il est possible qu'il n'y ait pas eu de but (0-0) ou que la vidéo ne soit pas encore disponible.")

    elif page == "Analyse collective":
        st.header("Analyse collective")

        tab1, tab2 = st.tabs(['Statistiques globales', 'Statistiques par équipe'])

        équipes = {
            "24-25": [
                "Andrézieux",
                "Anglet Genets",
                "Angoulême",
                "Bergerac",
                "Cannes",
                "Fréjus St-Raphaël",
                "GOAL FC",
                "Grasse",
                "Hyères FC",
                "Istres",
                "Jura Sud Foot",
                "Le Puy F.43 Auvergne",
                "Marignane Gignac CB",
                "Rumilly Vallières",
                "Saint-Priest",
                "Toulon"
            ],
            "25-26": [
                "Andrézieux",
                "Cannes",
                "Fréjus St-Raphaël",
                "GOAL FC",
                "Grasse",
                "Hyères FC",
                "Istres",
                "Rumilly Vallières",
                "Saint-Priest",
                "Toulon",
                "Créteil",
                "St Maur Lusitanos",
                "Nîmes",
                "FC 93 Bobigny BG",
                "Rousset-Ste Victoire",
                "Limonest"
            ]
        }

        df_stats_moyennes = pd.DataFrame()

        for équipe in équipes[st.session_state['saison']]:
            if not os.path.exists(f"data/Data {st.session_state['saison']}/Team Stats {équipe}.xlsx"):
                continue
            df_filtré = collect_collective_data(équipe)
            df_filtré = df_filtré[df_filtré['Compétition'] == 'France. National 2']
            df_stats = df_filtré[df_filtré['Équipe'] == équipe]
            df_stats = df_stats.mean(numeric_only=True).to_frame().T.round(1)
            df_stats['Équipe'] = équipe
            df_stats['Matchs analysés'] = len(df_filtré[df_filtré['Équipe'] == équipe])
            df_stats_moyennes = pd.concat([df_stats_moyennes, df_stats], ignore_index=True)

        df_stats_moyennes = df_stats_moyennes.drop(['Championnat'], axis=1)

        cols = ['Équipe', 'Matchs analysés'] + [col for col in df_stats_moyennes.columns if col not in ['Équipe', 'Matchs analysés']]
        df_stats_moyennes = df_stats_moyennes[cols]

        colonnes_bas_mieux = {
            'Pertes', 'Pertes bas', 'Pertes Moyen', 'Pertes élevé', 'Hors-jeu',
            'Tirs contre', 'Tirs contre cadrés', 'Buts concédés', 'Fautes',
            'Cartons jaunes', 'Cartons rouges', 'PPDA'
        }
        
        with tab1:
            tab3, tab4 = st.tabs(['Statistiques joueurs', 'Statistiques équipes'])

            with tab3:
                df = all_df['Joueur du championnat de France']

                df_filtré = df[df['Équipe dans la période sélectionnée'].isin(équipes[st.session_state['saison']])]

                colonnes_à_exclure = [
                    'Minutes jouées', 'Âge', 'Taille', 'Poids', 'Valeur marchande',
                    'Matchs joués', 'xG', 'xA', 'Buts', 'Passes décisives',
                    'Cartons jaunes', 'Cartons rouges', 'Buts hors penalty',
                    'Tir', 'Buts de la tête'
                ]

                colonnes_filtrées = [
                    col for col in df_filtré.select_dtypes(include='number').columns
                    if col not in colonnes_à_exclure
                ]

                # Création des DataFrames avec classement par colonne sélectionnée
                dfs = {}

                for col in colonnes_filtrées:
                    df_temp = df_filtré[['Joueur', 'Équipe dans la période sélectionnée', 'Matchs joués', col]].copy()

                    # Classement sans supprimer les NaN
                    ranked = df_temp[col].rank(ascending=False, method='min')

                    # On place les NaN à la fin
                    df_temp['Classement'] = ranked.fillna(len(df_temp) + 1).astype(int)

                    # Ajout conditionnel de (par 90)
                    if "par 90" or "%" in col.lower():
                        display_col = col
                    else:
                        display_col = f"{col} (par 90)"

                    # Renommage des colonnes pour affichage uniquement
                    df_temp.rename(columns={
                        col: display_col,
                        'Équipe dans la période sélectionnée': 'Équipe',
                        'Matchs joués': 'Matchs analysés'
                    }, inplace=True)

                    # Réorganisation des colonnes
                    cols_order = ['Classement', 'Joueur', 'Équipe', 'Matchs analysés', display_col]
                    df_temp = df_temp[cols_order]

                    # Tri final
                    df_temp = df_temp.sort_values(by=['Classement', 'Joueur'])

                    dfs[col] = df_temp

                metric = st.selectbox("Sélectionnez une métrique", list(dfs.keys()))

                st.dataframe(dfs[metric], use_container_width=True, hide_index=True)

            with tab4:
                tab5, tab6 = st.tabs(['Classement', 'Nuage de points'])

                with tab5:
                    dfs = {}

                    base_cols = ['Équipe', 'Matchs analysés']
                    other_cols = [col for col in df_stats_moyennes.columns if col not in base_cols]

                    for col in other_cols:
                        df_temp = df_stats_moyennes[base_cols + [col]].copy()
                        ascending = True if col in colonnes_bas_mieux else False
                        df_temp['Classement'] = df_temp[col].rank(ascending=ascending, method='min').astype(int)

                        display_col = f"{col} (par 90)"
                        df_temp.rename(columns={col: display_col}, inplace=True)

                        cols_order = ['Classement'] + base_cols + [display_col]
                        df_temp = df_temp[cols_order]
                        df_temp = df_temp.sort_values(by=display_col, ascending=ascending)

                        dfs[col] = df_temp

                    metric = st.selectbox("Sélectionnez une métrique", list(dfs.keys()))

                    st.dataframe(dfs[metric], use_container_width=True, hide_index=True)

                with tab6:
                    metrics = [col for col in df_stats_moyennes.columns if col not in ['Équipe', 'Matchs analysés']]

                    col1, col2 = st.columns(2)

                    with col1:
                        x_metric = st.selectbox("Sélectionnez la métrique X", metrics)

                    with col2:
                        y_metric = st.selectbox("Sélectionnez la métrique Y", metrics)

                    fig = plot_team_metrics(df_stats_moyennes, x_metric, y_metric)
                    st.plotly_chart(fig, use_container_width=True)

        with tab2:
            team = st.selectbox("Sélectionnez une équipe", équipes[st.session_state['saison']], index=équipes[st.session_state['saison']].index("Cannes"))

            if not os.path.exists(f"data/Data {st.session_state['saison']}/Team Stats {team}.xlsx"):
                st.warning(f"⚠️ Fichier non trouvé pour {team}.")

            else:
                df_collective = collect_collective_data(team)

                tab3, tab4 = st.tabs(['Statistiques moyennes', 'Statistiques par match'])

                with tab3:
                    colonnes_a_ranker = [col for col in df_stats_moyennes.columns if col not in ['Équipe', 'Matchs analysés']]

                    df_stats_ranks = df_stats_moyennes.copy()

                    for col in colonnes_a_ranker:
                        if col in colonnes_bas_mieux:
                            # Plus c'est bas, mieux c'est
                            df_stats_ranks[col] = df_stats_moyennes[col].rank(ascending=True, method='min')
                        else:
                            # Plus c'est haut, mieux c'est
                            df_stats_ranks[col] = df_stats_moyennes[col].rank(ascending=False, method='min')

                    # Colonnes non numériques inchangées
                    df_stats_ranks['Équipe'] = df_stats_moyennes['Équipe']
                    df_stats_ranks['Matchs analysés'] = df_stats_moyennes['Matchs analysés']
                    df_stats_ranks = df_stats_ranks[cols]
                    df_stats_ranks = df_stats_ranks.astype({col: int for col in colonnes_a_ranker})

                    équipe_analysée = df_stats_moyennes[df_stats_moyennes["Équipe"] == team]
                    équipe_analysée_rank = df_stats_ranks[df_stats_ranks["Équipe"] == team]

                    tab5, tab6, tab7, tab8, tab9 = st.tabs(["Général", "Attaque", "Défense", "Passe", "Pressing"])

                    with tab5:
                        équipe_analysée_values = clean_values(équipe_analysée[indicateurs_general_moyens].values.flatten())
                        équipe_analysée_rank_values = clean_values(équipe_analysée_rank[indicateurs_general_moyens].values.flatten())

                        fig = create_plot_stats(indicateurs_general_moyens, équipe_analysée_values, team, équipe_analysée_rank_values, "Classement")
                        st.pyplot(fig, use_container_width=True)

                    with tab6:
                        équipe_analysée_values = clean_values(équipe_analysée[indicateurs_attaques].values.flatten())
                        équipe_analysée_rank_values = clean_values(équipe_analysée_rank[indicateurs_attaques].values.flatten())

                        fig = create_plot_stats(indicateurs_attaques, équipe_analysée_values, team, équipe_analysée_rank_values, "Classement")
                        st.pyplot(fig, use_container_width=True)

                    with tab7:
                        équipe_analysée_values = clean_values(équipe_analysée[indicateurs_defense_moyens].values.flatten())
                        équipe_analysée_rank_values = clean_values(équipe_analysée_rank[indicateurs_defense_moyens].values.flatten())

                        fig = create_plot_stats(indicateurs_defense_moyens, équipe_analysée_values, team, équipe_analysée_rank_values, "Classement")
                        st.pyplot(fig, use_container_width=True)

                    with tab8:
                        équipe_analysée_values = clean_values(équipe_analysée[indicateurs_passes].values.flatten())
                        équipe_analysée_rank_values = clean_values(équipe_analysée_rank[indicateurs_passes].values.flatten())

                        fig = create_plot_stats(indicateurs_passes, équipe_analysée_values, team, équipe_analysée_rank_values, "Classement")
                        st.pyplot(fig, use_container_width=True)

                    with tab9:
                        équipe_analysée_values = clean_values(équipe_analysée[indicateurs_pressing].values.flatten())
                        équipe_analysée_rank_values = clean_values(équipe_analysée_rank[indicateurs_pressing].values.flatten())

                        fig = create_plot_stats(indicateurs_pressing, équipe_analysée_values, team, équipe_analysée_rank_values, "Classement")
                        st.pyplot(fig, use_container_width=True)

                with tab4:
                    compétition = st.selectbox("Sélectionnez une compétition", df_collective["Compétition"].unique())

                    df_filtré = df_collective[df_collective["Compétition"] == compétition]

                    match = st.selectbox("Sélectionnez un match", df_filtré["Match"].unique())

                    df_filtré = df_filtré[df_filtré["Match"] == match]

                    équipe_analysée = df_filtré[df_filtré["Équipe"] == team]
                    adversaire = df_filtré[df_filtré["Équipe"] != team]

                    tab5, tab6, tab7, tab8, tab9 = st.tabs(["Général", "Attaque", "Défense", "Passe", "Pressing"])

                    with tab5:
                        équipe_analysée_values = clean_values(équipe_analysée[indicateurs_general].values.flatten())
                        adversaire_values = clean_values(adversaire[indicateurs_general].values.flatten())

                        fig = create_plot_stats(indicateurs_general, équipe_analysée_values, team, adversaire_values, adversaire['Équipe'].iloc[0])
                        st.pyplot(fig, use_container_width=True)

                    with tab6:
                        équipe_analysée_values = clean_values(équipe_analysée[indicateurs_attaques].values.flatten())
                        adversaire_values = clean_values(adversaire[indicateurs_attaques].values.flatten())

                        fig = create_plot_stats(indicateurs_attaques, équipe_analysée_values, team, adversaire_values, adversaire['Équipe'].iloc[0])
                        st.pyplot(fig, use_container_width=True)

                    with tab7:
                        équipe_analysée_values = clean_values(équipe_analysée[indicateurs_defense].values.flatten())
                        adversaire_values = clean_values(adversaire[indicateurs_defense].values.flatten())

                        fig = create_plot_stats(indicateurs_defense, équipe_analysée_values, team, adversaire_values, adversaire['Équipe'].iloc[0])
                        st.pyplot(fig, use_container_width=True)

                    with tab8:
                        équipe_analysée_values = clean_values(équipe_analysée[indicateurs_passes].values.flatten())
                        adversaire_values = clean_values(adversaire[indicateurs_passes].values.flatten())

                        fig = create_plot_stats(indicateurs_passes, équipe_analysée_values, team, adversaire_values, adversaire['Équipe'].iloc[0])
                        st.pyplot(fig, use_container_width=True)

                    with tab9:
                        équipe_analysée_values = clean_values(équipe_analysée[indicateurs_pressing].values.flatten())
                        adversaire_values = clean_values(adversaire[indicateurs_pressing].values.flatten())

                        fig = create_plot_stats(indicateurs_pressing, équipe_analysée_values, team, adversaire_values, adversaire['Équipe'].iloc[0])
                        st.pyplot(fig, use_container_width=True)

    elif page == "Analyse individuelle":
        st.header("Analyse individuelle")

        sélection_dataframe = st.selectbox("Sélectionnez la base de données que vous souhaitez analyser", all_df.keys())
        df = all_df[sélection_dataframe]

        col1, col2 = st.columns(2)

        with col1:
            if sélection_dataframe != "Joueur du top 5 européen":
                team = st.selectbox("Sélectionnez une équipe", df['Équipe dans la période sélectionnée'].unique(), index=list(df['Équipe dans la période sélectionnée'].unique()).index("Cannes"))
            else:
                team = st.selectbox("Sélectionnez une équipe", df['Équipe dans la période sélectionnée'].unique(), index=list(df['Équipe dans la période sélectionnée'].unique()).index("Real Madrid"))
            
            df_filtré = df[df['Équipe dans la période sélectionnée'] == team]

        with col2:
            joueur = st.selectbox("Sélectionnez un joueur", df_filtré['Joueur + Information'].unique())

        poste_du_joueur = df_filtré[df_filtré['Joueur + Information'] == joueur]['Poste'].iloc[0]

        if poste_du_joueur != 'Gardien':
            postes_disponibles = [k for k in kpi_by_position.keys() if k != "Gardien"]
            index_poste = postes_disponibles.index(poste_du_joueur) if poste_du_joueur in postes_disponibles else 0
            poste = st.selectbox(
                "Sélectionnez la base de comparaison (poste) pour l'analyse",
                postes_disponibles,
                index=index_poste,
                help="Vous pouvez sélectionner n'importe quel poste, même différent de celui du joueur, pour voir comment il se comporte selon d'autres critères."
            )
        else:
            poste = st.selectbox(
                "Sélectionnez la base de comparaison (poste) pour l'analyse",
                ["Gardien"],
                index=0,
                help="Le joueur est gardien, la comparaison est donc limitée à ce poste."
            )
        
        if team == "Cannes":
            tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs(["Statistiques", "Radar", "KPI", "Statistiques avancées", "Type de profil", "IPR", "Points forts/Points faibles", "Nuage de points", "Joueurs similaires", "Matchs"])
        else:
            tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(["Statistiques", "Radar", "KPI", "Statistiques avancées", "Type de profil", "IPR","Points forts/Points faibles", "Nuage de points", "Joueurs similaires"])

        with tab1:
            st.subheader('Informations')

            col1, col2, col3, col4 = st.columns(4)

            age_value = compute_weighted_stats_by_minutes(df[df['Joueur + Information'] == joueur])['Âge'].values[0]
            taille_value = compute_weighted_stats_by_minutes(df[df['Joueur + Information'] == joueur])['Taille'].values[0]
            pied_value = compute_weighted_stats_by_minutes(df[df['Joueur + Information'] == joueur])['Pied'].values[0]
            contrat_value = compute_weighted_stats_by_minutes(df[df['Joueur + Information'] == joueur])['Contrat expiration'].values[0]

            with col1:
                bordered_metric(col1, "Âge", 'Unknown' if pd.isna(age_value) or age_value == 0 or age_value == '' else int(age_value), 165)

            with col2:
                bordered_metric(col2, "Taille", 'Unknown' if pd.isna(taille_value) or taille_value == 0 or taille_value == '' else int(taille_value), 165)

            with col3:
                bordered_metric(col3, "Pied fort", 'Unknown' if pd.isna(pied_value) or pied_value == 0 or pied_value == '' else pied_value.capitalize(), 165)

            with col4:
                bordered_metric(col4, "Contrat expiration", 'Unknown' if pd.isna(contrat_value) or contrat_value == 0 or contrat_value == '' else contrat_value, 165)

            st.markdown("---")

            st.subheader('Statistiques générales')

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                bordered_metric(col1, "Matchs joués", compute_weighted_stats_by_minutes(df[df['Joueur + Information'] == joueur])['Matchs joués'].values[0], 165)

            with col2:
                bordered_metric(col2, "Minutes jouées", compute_weighted_stats_by_minutes(df[df['Joueur + Information'] == joueur])['Minutes jouées'].values[0], 165)

            with col3:
                if poste != 'Gardien':
                    bordered_metric(col3, "Buts", compute_weighted_stats_by_minutes(df[df['Joueur + Information'] == joueur])['Buts'].values[0], 165)
                else:
                    bordered_metric(col3, "Buts concédés", int(compute_weighted_stats_by_minutes(df[df['Joueur + Information'] == joueur])['Buts concédés'].values[0]), 165)

            with col4:
                if poste != 'Gardien':
                    bordered_metric(col4, "Passes décisives", compute_weighted_stats_by_minutes(df[df['Joueur + Information'] == joueur])['Passes décisives'].values[0], 165)
                else:
                    bordered_metric(col4, "xG concédés", compute_weighted_stats_by_minutes(df[df['Joueur + Information'] == joueur])['xG contre'].values[0], 165)

            if team == "Cannes":
                nom_joueur = joueur.split(" - ")[0]

                df_player = create_player_data(nom_joueur, sélection_dataframe)

                df_player_mean = df_player.mean(numeric_only=True).to_frame().T
                df_player_mean = ajouter_pourcentages(df_player_mean)

                st.markdown("---")

                st.subheader('Smart Goals (moyenne par match)')

                df_player_mean = get_player_metrics_by_position(df_player_mean, nom_joueur, smart_goal, analyse_par_poste, st.session_state['saison'])

                cols = list(df_player_mean.columns)

                for i in range(0, len(cols), 3):
                    row = st.columns(3)

                    for j, col_name in enumerate(cols[i:i + 3]):
                        value = df_player_mean[col_name].iloc[0]
                        bordered_metric(row[j], col_name, value, 225)

                    st.markdown("<div style='margin-top: 10px'></div>", unsafe_allow_html=True)

        with tab2:
            fig = create_individual_radar(df, joueur, poste)
            st.pyplot(fig, use_container_width=True)

        with tab3:
            scores_df = calcul_scores_par_kpi(df, joueur, poste)
            joueur_scores = scores_df[scores_df['Joueur + Information'] == joueur].iloc[0]
            kpis_panel = list(kpi_by_position[poste].keys()) + ["Note globale"]

            fig = plot_rating_bars_panel(scores_df, joueur_scores, kpis_panel)
            st.pyplot(fig, use_container_width=True)

            st.markdown("<div style='margin-top: 10px'></div>", unsafe_allow_html=True)
            st.warning("⚠️ Les notes sont pondérées par un coefficient reflétant le niveau du championnat, sauf pour les bases de données « Joueurs du top 5 européen » et « Joueurs français », pour lesquelles aucun ajustement n'est appliqué.")

        with tab4:
            fig = plot_player_ranking(df, joueur, poste)
            st.pyplot(fig, use_container_width=True)

        with tab5:
            scores_df = calcul_scores_par_kpi(df, joueur, poste)

            joueur_scores = scores_df[scores_df['Joueur + Information'] == joueur].iloc[0]

            st.dataframe(joueur_scores.iloc[joueur_scores.index.get_loc("Note globale")+1:].to_frame().T, use_container_width=True, hide_index=True)
        
        with tab6:
            ipr_score = calcul_ipr(df, joueur, poste)

            df_joueur = ipr_score.loc[
                ipr_score["Joueur + Information"] == joueur,
                ["IPR Viseur", "IPR Perforateur", "IPR Duelliste"]
            ]

            st.dataframe(df_joueur, use_container_width=True, hide_index=True)

            st.info(
            "L’IPR (Indice de Prise de Risque) est un indicateur qui mesure la fréquence à laquelle un joueur tente des actions à risque **à chaque ballon touché**. "
            "Il ne mesure donc pas un volume brut d’actions, mais la **propension du joueur à prendre des initiatives risquées lorsqu’il est impliqué dans le jeu**.\n\n"

            "L’IPR est normalisé par l’« influence » du joueur (ballons reçus), ce qui permet de comparer des profils ayant des volumes de jeu différents. "
            "Un IPR élevé indique un joueur qui, à chaque prise de balle, cherche régulièrement à déséquilibrer le jeu par une action ambitieuse. "
            "À l’inverse, un IPR plus faible traduit un joueur plus sécurisé, privilégiant la continuité du jeu.\n\n"

            "L’IPR Viseur mesure la part de **passes à forte intention offensive** (progression, pénétration, création) parmi les ballons joués par le joueur.\n\n"

            "L’IPR Perforateur évalue la fréquence des **prises de risque par la conduite de balle**, à travers les courses progressives et les accélérations.\n\n"

            "L’IPR Duelliste quantifie la prise de risque en **1 contre 1**, en mesurant le recours au dribble par ballon touché.\n\n"

            "Il est essentiel d’interpréter l’IPR en fonction du poste, du rôle et du style de jeu collectif, "
            "un IPR élevé n’étant ni intrinsèquement positif ni négatif, mais révélateur d’un **profil décisionnel**."
            )

        with tab7:
            points_forts_clé, points_faibles_clé = points_forts_faibles(df, joueur, poste)

            col1, col2 = st.columns(2)

            with col1:
                st.subheader('Points forts')
                if points_forts_clé:
                    for k, score in sorted(points_forts_clé.items(), key=lambda x: x[1], reverse=True):
                        phrase = points_forts.get(k)
                        if phrase:
                            st.markdown(
                                f"- {phrase}  \n"
                                f"<span style='color:#6b7280; font-size:0.9em;'>Score : {score}</span>",
                                unsafe_allow_html=True
                            )

            with col2:
                st.subheader('Points faibles')
                if points_faibles_clé:
                    for k, score in sorted(points_faibles_clé.items(), key=lambda x: x[1]):
                        phrase = points_faibles.get(k)
                        if phrase:
                            st.markdown(
                                f"- {phrase}  \n"
                                f"<span style='color:#6b7280; font-size:0.9em;'>Score : {score}</span>",
                                unsafe_allow_html=True
                            )

        with tab8:
            if poste != 'Gardien': 
                metrics_label  = st.selectbox("Sélectionnez une base de comparaison", [k for k in metrics_x_y.keys() if k != "Buts évités"])
            else:
                metrics_label = "Buts évités"

            x_metric, y_metric = metrics_x_y[metrics_label]["metrics"]
            nom_x_metric, nom_y_metric = metrics_x_y[metrics_label]["names"]
            description_1, description_2, description_3, description_4 = metrics_x_y[metrics_label]["descriptions"]

            fig = plot_player_metrics(df, joueur, poste, x_metric, y_metric, nom_x_metric, nom_y_metric, description_1, description_2, description_3, description_4)
            st.plotly_chart(fig, use_container_width=True)

        with tab9:
            nombre_joueur = st.number_input("Sélectionnez le nombre de joueurs que vous voulez voir apparaître", min_value=1, max_value=50, value=10)

            similar_players = compute_similarity(df, joueur, poste)

            similar_players.insert(0, "Classement", range(1, len(similar_players) + 1))

            st.dataframe(similar_players.head(nombre_joueur), use_container_width=True, hide_index=True)

        if team == "Cannes":
            with tab10:
                nom_joueur = joueur.split(" - ")[0]

                df_player = create_player_data(nom_joueur, sélection_dataframe)

                df_player = ajouter_pourcentages(df_player)

                match_options = df_player["Match"].dropna().unique().tolist()

                ALL_MATCHES_LABEL = "Tous les matchs"
                match_options_with_all = [ALL_MATCHES_LABEL] + match_options

                st.session_state["selected_matches"] = [
                    m for m in st.session_state.get("selected_matches", [])
                    if m in match_options_with_all
                ]

                matches = st.multiselect("Sélectionnez le(s) match(s) à analyser", options=match_options_with_all, key="selected_matches")
                
                if not matches:
                    st.info("Sélectionne au moins un match.")
                    st.stop()

                if ALL_MATCHES_LABEL in matches:
                    selected_matches = match_options
                else:
                    selected_matches = matches

                df_player = df_player[df_player["Match"].isin(selected_matches)]

                notes_par_match = []

                for match in selected_matches:
                    df_match = df_player[df_player["Match"] == match]
                    note_match = performance_index(df_match, poste, match)
                    notes_par_match.append(note_match)

                note_moyenne = (sum(notes_par_match) / len(notes_par_match)).round(1)

                st.subheader('Statistiques générales')

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    bordered_metric(col1, "Minutes jouées", df_player["Minutes jouées"].sum(), 165)

                with col2:
                    if poste != 'Gardien':
                        bordered_metric(col2, "But", df_player["But"].sum(), 165)
                    else:
                        bordered_metric(col2, "Buts concédés", df_player["Buts concédés"].sum(), 165)

                with col3:
                    if poste != 'Gardien':
                        bordered_metric(col3, "Passe décisive", df_player["Passe décisive"].sum(), 165)
                    else:
                        bordered_metric(col3, "xG concédés", df_player["xCG"].sum(), 165)

                with col4:
                    bordered_metric(col4, "Note", note_moyenne, 165, color="#ac141a")

                st.markdown("---")

                st.subheader('Smart Goals')

                df_player_mean_on_selected_matches = df_player.mean(numeric_only=True).to_frame().T

                df_player_mean_on_selected_matches = get_player_metrics_by_position(df_player_mean_on_selected_matches, nom_joueur, smart_goal, analyse_par_poste, st.session_state['saison'])

                cols = list(df_player_mean_on_selected_matches.columns)

                for i in range(0, len(cols), 3):
                    row = st.columns(3)

                    for j, col_name in enumerate(cols[i:i + 3]):
                        value = df_player_mean_on_selected_matches[col_name].iloc[0]
                        mean_value = df_player_mean[col_name].iloc[0]

                        if isinstance(value, str) and "%" in value:
                            v = float(value.replace("%", ""))
                            m = float(mean_value.replace("%", ""))
                            color = "#1aac14" if v > m else "#ac141a"
                            bordered_metric(row[j], col_name, value, 225, color)
                        else:
                            color = "#1aac14" if value > mean_value else "#ac141a"
                            bordered_metric(row[j], col_name, round(value, 1), 225, color)

                    st.markdown("<div style='margin-top: 10px'></div>", unsafe_allow_html=True)

    elif page == "Analyse comparative":
        st.header("Analyse comparative")

        sélection_dataframe = st.selectbox("Sélectionnez la base de données que vous souhaitez analyser", all_df.keys())
        df = all_df[sélection_dataframe]

        col1, col2 = st.columns(2)

        with col1:
            if sélection_dataframe != "Joueur du top 5 européen":
                team_1 = st.selectbox("Sélectionnez une équipe", df['Équipe dans la période sélectionnée'].unique(), key='team 1', index=list(df['Équipe dans la période sélectionnée'].unique()).index("Cannes"))
            else:
                team_1 = st.selectbox("Sélectionnez une équipe", df['Équipe dans la période sélectionnée'].unique(), key='team 1', index=list(df['Équipe dans la période sélectionnée'].unique()).index("Real Madrid"))

            df_filtré_1 = df[df['Équipe dans la période sélectionnée'] == team_1]
            joueur_1 = st.selectbox("Sélectionnez un joueur", df_filtré_1['Joueur + Information'].unique(), key='joueur 1')

        with col2:
            if sélection_dataframe != "Joueur du top 5 européen":
                team_2 = st.selectbox("Sélectionnez une équipe", df['Équipe dans la période sélectionnée'].unique(), key='team 2', index=list(df['Équipe dans la période sélectionnée'].unique()).index("Cannes"))
            else:
                team_2 = st.selectbox("Sélectionnez une équipe", df['Équipe dans la période sélectionnée'].unique(), key='team 2', index=list(df['Équipe dans la période sélectionnée'].unique()).index("Real Madrid"))

            df_filtré_2 = df[df['Équipe dans la période sélectionnée'] == team_2]
            joueur_2 = st.selectbox("Sélectionnez un joueur", df_filtré_2['Joueur + Information'].unique(), key='joueur 2')

        poste_1 = df_filtré_1[df_filtré_1['Joueur + Information'] == joueur_1]['Poste'].iloc[0]
        poste_2 = df_filtré_2[df_filtré_2['Joueur + Information'] == joueur_2]['Poste'].iloc[0]

        if poste_1 == 'Gardien' or poste_2 == 'Gardien':
            poste = st.selectbox(
                "Sélectionnez la base de comparaison (poste) pour l'analyse",
                ["Gardien"],
                index=0,
                help="Un des deux joueurs est gardien, la comparaison est donc limitée à ce poste."
            )
        else:
            postes_disponibles = [k for k in kpi_by_position.keys() if k != "Gardien"]
            index_poste = postes_disponibles.index(poste_1) if poste_1 in postes_disponibles else 0
            poste = st.selectbox(
                "Sélectionnez la base de comparaison (poste) pour l'analyse",
                postes_disponibles,
                index=index_poste,
                help="Vous pouvez sélectionner n'importe quel poste, même différent de celui du joueur, pour voir comment il se comporte selon d'autres critères."
            )

        type_de_comparaison = st.radio("Sélectionnez le type de comparaison", ["Radar", "KPI", "Statistiques avancées"])

        if st.button("Comparer"):
            if type_de_comparaison == "Radar":
                fig = create_comparison_radar(df, joueur_1, joueur_2, poste)
            if type_de_comparaison == "KPI":
                kpis_panel = list(kpi_by_position[poste].keys()) + ["Note globale"]
                fig = plot_kpi_comparison(df, joueur_1, joueur_2, poste, kpis_panel)
            if type_de_comparaison == "Statistiques avancées":
                fig = plot_stat_comparison(df, joueur_1, joueur_2, poste)
            st.pyplot(fig, use_container_width=True)
            
    elif page == "Scouting":
        st.header("Scouting")

        sélection_dataframe = st.selectbox("Sélectionnez la base de données que vous souhaitez analyser", all_df.keys())
        df = all_df[sélection_dataframe]

        poste = st.selectbox("Sélectionnez le poste qui vous intéresse", list(kpi_by_position.keys()))

        col1, col2 = st.columns(2)

        with col1:
            min_age, max_age = st.slider("Sélectionnez une tranche d'âge", 
                                        min_value=int(df['Âge'].min(skipna=True)), 
                                        max_value=int(df['Âge'].max(skipna=True)), 
                                        value=(int(df['Âge'].min(skipna=True)), int(df['Âge'].max(skipna=True))), 
                                        step=1)

        with col2:
            min_taille, max_taille = st.slider("Sélectionnez une tranche de taille", 
                                            min_value=int(df['Taille'].min(skipna=True)), 
                                            max_value=int(df['Taille'].max(skipna=True)), 
                                            value=(int(df['Taille'].min(skipna=True)), int(df['Taille'].max(skipna=True))), 
                                            step=1)
        
        metric_or_kpi = st.radio("Sélectionnez le type de critère pour la recommandation", ["Métrique", "KPI"])

        if metric_or_kpi == "Métrique":
            colonnes_à_exclure = [
                'Minutes jouées', 'Âge', 'Taille', 'Poids', 'Valeur marchande',
                'Matchs joués', 'xG', 'xA', 'Buts', 'Passes décisives',
                'Cartons jaunes', 'Cartons rouges', 'Buts hors penalty',
                'Tir', 'Buts de la tête'
            ]

            colonnes_filtrées = [
                col for col in df.select_dtypes(include='number').columns
                if col not in colonnes_à_exclure
            ]
            
            métriques_selectionnées = st.multiselect("Sélectionnez des métriques", colonnes_filtrées)

            thresholds = {}
            for métrique in métriques_selectionnées:
                thresholds[métrique] = st.slider(f"Sélectionnez le top % pour la métrique : {métrique}", min_value=0, max_value=100, value=50, step=5, key=métrique)

            recommended_players = search_recommended_players(df, poste, thresholds)
            recommended_players = recommended_players[((recommended_players['Âge'] >= min_age) & (recommended_players['Âge'] <= max_age)) &
                                                    ((recommended_players['Taille'] >= min_taille) & (recommended_players['Taille'] <= max_taille) | (recommended_players['Taille'] == 0))]
            recommended_players = recommended_players.sort_values(by=list(thresholds.keys()), ascending=[False] * len(list(thresholds.keys())))

            recommended_players.insert(0, "Classement", range(1, len(recommended_players) + 1))

            st.dataframe(recommended_players, use_container_width=True, hide_index=True)

        elif metric_or_kpi == "KPI":
            scores_df = calcul_scores_par_kpi(df, "", poste)

            colonnes_à_exclure = [
                'Minutes jouées', 'Âge', 'Taille'
            ]

            colonnes_filtrées = [
                col for col in scores_df.select_dtypes(include='number').columns
                if col not in colonnes_à_exclure
            ]

            kpis_sélectionnées = st.multiselect("Sélectionnez des KPIs", colonnes_filtrées)

            thresholds = {}
            for kpi in kpis_sélectionnées:
                thresholds[kpi] = st.slider(f"Sélectionnez le top % pour le KPI : {kpi}", min_value=0, max_value=100, value=50, step=5, key=kpi)

            recommended_players = search_recommended_players(scores_df, poste, thresholds)
            recommended_players = recommended_players[((recommended_players['Âge'] >= min_age) & (recommended_players['Âge'] <= max_age)) &
                                                    ((recommended_players['Taille'] >= min_taille) & (recommended_players['Taille'] <= max_taille) | (recommended_players['Taille'] == 0))]
            recommended_players = recommended_players.sort_values(by=list(thresholds.keys()), ascending=[False] * len(list(thresholds.keys())))

            recommended_players.insert(0, "Classement", range(1, len(recommended_players) + 1))

            st.dataframe(recommended_players, use_container_width=True, hide_index=True)

if __name__ == '__main__':
    st.set_page_config(
        page_title="AS Cannes",
        page_icon="https://upload.wikimedia.org/wikipedia/fr/thumb/7/72/AS_Cannes_foot_Logo_2017.svg/langfr-800px-AS_Cannes_foot_Logo_2017.svg.png"
    )

    st.title("AS Cannes")

    logo = "https://upload.wikimedia.org/wikipedia/fr/thumb/7/72/AS_Cannes_foot_Logo_2017.svg/langfr-800px-AS_Cannes_foot_Logo_2017.svg.png"

    # CSS pour placer le logo en haut à droite
    st.markdown(
        f"""
        <style>
            .logo-container {{
                position: absolute;
                top: -100px;
                right: 10px;
            }}
            .logo-container img {{
                width: 90px;
            }}
        </style>
        <div class="logo-container">
            <img src="{logo}">
        </div>
        """,
        unsafe_allow_html=True
    )

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if "username" not in st.session_state:
        st.session_state.username = None

    if not st.session_state.authenticated:
        with st.form("login_form"):
            username = st.text_input("Nom d'utilisateur")
            password = st.text_input("Mot de passe", type="password")
            submitted = st.form_submit_button("Se connecter")

            if submitted:
                if username in st.secrets['users'] and password == st.secrets['users'][username]:
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Nom d'utilisateur ou mot de passe incorrect")

    if st.session_state.authenticated:
        if "saison" not in st.session_state:
            st.session_state["saison"] = "25-26"

        all_df_dict = collect_individual_data()
        streamlit_application(all_df_dict)