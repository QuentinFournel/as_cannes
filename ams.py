import pandas as pd 
import numpy as np
import os
from mplsoccer import PyPizza
import io
from mplsoccer import Radar, FontManager, grid
import streamlit as st
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
import requests
import unicodedata
from streamlit_option_menu import option_menu
import math
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics.pairwise import cosine_distances
import seaborn as sns
from scipy import stats

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
        '1MS5J8AdY785pxf7LEZdG38bkciijlZm_': 'Data 24-25',
        '1PQgcChI1Lb9rAGgpHCsGnaBQtuFo6FJ8': 'Data 25-26',
    }

    service = authenticate_google_drive()

    for folder_id, local_dir in folder_targets.items():
        files = list_files_in_folder(service, folder_id)

        if not files:
            st.warning(f"⚠️ Aucun fichier trouvé dans le dossier Drive ({folder_id}).")
            continue

        st.info(f"📂 Téléchargement de {len(files)} fichier(s) depuis {folder_id} vers '{local_dir}'...")

        # Téléchargement fichier par fichier dans le dossier correspondant
        for file in files:
            download_file(service, file['id'], file['name'], output_folder=local_dir)

        st.success(f"✅ Terminé pour '{local_dir}'.")

league_rating = {
    "Ligue 1": 1,
    "Ligue 2": 0.875008125,
    "National 1": 0.807142174,
    "National 2": 0.746953201,
    "National 3": 0.669607688
}

smart_goal = {
    "J. Aymes": [
        ["Tirs contre", "Arrêts", "Arrêts réflexes"],
        ["Passes", "Passes précises", "% de passes précises"],
        ["Duels aériens", "Duels aériens gagnés", "% de duels aériens gagnés"],
    ],
    "F. Vanni": [
        ["Tirs contre", "Arrêts", "Arrêts réflexes"],
        ["Passes", "Passes précises", "% de passes précises"],
        ["Duels aériens", "Duels aériens gagnés", "% de duels aériens gagnés"],
    ],
    "M. Fischer": [
        ["Duels défensifs", "Duels défensifs gagnés", "% de duels défensifs gagnés"],
        ["Duels aériens", "Duels aériens gagnés", "% de duels aériens gagnés"],
        ["Centres", "Centres précis", "% de centres précis"]
    ],
    "L. Vinci": [
        ["Duels défensifs", "Duels défensifs gagnés", "% de duels défensifs gagnés"],
        ["Duels aériens", "Duels aériens gagnés", "% de duels aériens gagnés"],
        ["Passes en avant", "Passes en avant précises", "% de passes en avant précises"]
    ],
    "G. Pineau": [
        ["Duels défensifs", "Duels défensifs gagnés", "% de duels défensifs gagnés"],
        ["Duels aériens", "Duels aériens gagnés", "% de duels aériens gagnés"],
        ["Passes longues", "Passes longues précises", "% de passes longues précises"]
    ],
    "H. Abderrahmane": [
        ["Duels défensifs", "Duels défensifs gagnés", "% de duels défensifs gagnés"],
        ["Duels aériens", "Duels aériens gagnés", "% de duels aériens gagnés"],
        ["Passes longues", "Passes longues précises", "% de passes longues précises"]
    ],
    "J. Smith": [
        ["Duels défensifs", "Duels défensifs gagnés", "% de duels défensifs gagnés"],
        ["Duels aériens", "Duels aériens gagnés", "% de duels aériens gagnés"],
        ["Passes longues", "Passes longues précises", "% de passes longues précises"]
    ],
    "C. N'Doye": [
        ["Passes en avant", "Passes en avant précises", "% de passes en avant précises"],
        ["Récupérations"]
    ],
    "H. Hafidi": [
        ["Passes en avant", "Passes en avant précises", "% de passes en avant précises"],
        ["Récupérations", "Touches de balle dans la surface de réparation"]
    ],
    "A. N'Diaye": [
        ["Tirs", "Tirs cadrés", "% de tirs cadrés"],
        ["Touches de balle dans la surface de réparation"]
    ],
    "C. Gonçalves": [
        ["Passes longues", "Passes longues précises", "% de passes longues précises"],
        ["Récupérations", "Touches de balle dans la surface de réparation"]
    ],
    "T. Trinker": [
        ["Dribbles", "Dribbles réussis", "% de dribbles réussis"],
        ["Passes dans le 3ème tiers", "Passes dans le 3ème tiers précises", "% de passes dans le 3ème tiers précises"],
        ["Touches de balle dans la surface de réparation"]
    ],
    "M. Blanc": [
        ["Passes dans le 3ème tiers", "Passes dans le 3ème tiers précises", "% de passes dans le 3ème tiers précises"],
        ["Touches de balle dans la surface de réparation"]
    ],
    "Alexis Gonçalves": [
        ["Dribbles", "Dribbles réussis", "% de dribbles réussis"],
        ["Centres", "Centres précis", "% de centres précis"],
        ["Tirs", "Tirs cadrés", "% de tirs cadrés"]
    ],
    "C. Abbas": [
        ["Dribbles", "Dribbles réussis", "% de dribbles réussis"],
        ["Centres", "Centres précis", "% de centres précis"],
        ["Tirs", "Tirs cadrés", "% de tirs cadrés"]
    ],
    "D. Mai": [
        ["Dribbles", "Dribbles réussis", "% de dribbles réussis"],
        ["Centres", "Centres précis", "% de centres précis"],
        ["Tirs", "Tirs cadrés", "% de tirs cadrés"]
    ],
    "M. Lopes": [
        ["Dribbles", "Dribbles réussis", "% de dribbles réussis"],
        ["Centres", "Centres précis", "% de centres précis"],
        ["Tirs", "Tirs cadrés", "% de tirs cadrés"]
    ],
    "J. Mambu": [
        ["Dribbles", "Dribbles réussis", "% de dribbles réussis"],
        ["Centres", "Centres précis", "% de centres précis"],
        ["Tirs", "Tirs cadrés", "% de tirs cadrés"]
    ],
    "J. Domingues": [
        ["Duels offensifs", "Duels offensifs gagnés", "% de duels offensifs gagnés"],
        ["Touches de balle dans la surface de réparation"]
    ],
    "D. Segbe-Azankpo": [
        ["Duels offensifs", "Duels offensifs gagnés", "% de duels offensifs gagnés"],
        ["Touches de balle dans la surface de réparation"]
    ],
    "M. Mamadou Kamissoko": []
}

metrics_by_position = [
    {
        "position": "Buteur",
        "metrics": {
            "Attaques\nréussies": "Attaques réussies par 90",
            "Buts\nhors penalty": "Buts hors penalty par 90",
            "Buts - xG": "Buts - xG",
            "xG\n/ Tirs": "xG / Tirs",
            "Tirs cadrés\n/ Tirs": "Tirs à la cible, %",
            "Touches\ndans la surface": "Touches de balle dans la surface de réparation sur 90",
            "Ballons\nreçus": "Passes réceptionnées par 90",
            "Précision\npasses": "Passes précises, %",
            "xA\n/ Passes": "xA / Passes",
            "Passes clés \n/ Passes": "Passes clés / Passes",
            "Passes avant tir\n/ Passes": "Passes avant tir / Passes",
            "Courses\nprogressives": "Courses progressives par 90",
            "Accélérations": "Accélérations par 90",
            "Duels\noffensifs": "Duels offensifs par 90",
            "Duels\noffensifs gagnés (%)": "Duels de marquage, %",
            "Duels\naériens": "Duels aériens par 90",
            "Duels\naériens gagnés (%)": "Duels aériens gagnés, %"
        }
    },
    {
        "position": "Ailier",
        "metrics": {
            "Attaques\nréussies": "Attaques réussies par 90",
            "Buts - xG": "Buts - xG",
            "Ballons\nreçus": "Passes réceptionnées par 90",
            "Précision\npasses": "Passes précises, %",
            "xA\n/ Passes": "xA / Passes",
            "Passes clés\n/ Passes": "Passes clés / Passes",
            "Passes judicieuses\n/ Passes": "Passes judicieuses / Passes",
            "Passes surface\n/ Passes": "Passes vers la surface / Passes",
            "Passes tiers adv.\n/ Passes": "Passes dans le tiers adverse / Passes",
            "Passes avant tir\n/ Passes": "Passes avant tir / Passes",
            "Passes progressives\n/ Passes": "Passes progressives / Passes",
            "Centres": "Centres par 90",
            "Centres\nréussis (%)": "Сentres précises, %",
            "Courses\nprogressives": "Courses progressives par 90",
            "Accélérations": "Accélérations par 90",
            "Dribbles": "Dribbles par 90",
            "Dribbles\nréussis (%)": "Dribbles réussis, %"
        }
    },
    {
        "position": "Milieu offensif",
        "metrics": {
            "Attaques\nréussies": "Attaques réussies par 90",
            "Ballons\nreçus": "Passes réceptionnées par 90",
            "Précision\npasses": "Passes précises, %",
            "xA\n/ Passes": "xA / Passes",
            "Passes clés\n/ Passes": "Passes clés / Passes",
            "Passes judicieuses\n/ Passes": "Passes judicieuses / Passes",
            "Passes surface\n/ Passes": "Passes vers la surface / Passes",
            "Passes tiers adv.\n/ Passes": "Passes dans le tiers adverse / Passes",
            "Passes avant tir\n/ Passes": "Passes avant tir / Passes",
            "Passes progressives\n/ Passes": "Passes progressives / Passes",
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
            "xA\n/ Passes": "xA / Passes",
            "Passes avant\n/ Passes": "Passes avant / Passes",
            "Passes clés\n/ Passes": "Passes clés / Passes",
            "Passes progressives\n/ Passes": "Passes progressives / Passes",
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
            "xA\n/ Passes": "xA / Passes",
            "Passes avant\n/ Passes": "Passes avant / Passes",
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
            "Passes avant\n/ Passes": "Passes avant / Passes",
            "Passes\navant réussies (%)": "Passes en avant précises, %",
            "Passes longues\n/ Passes": "Passes longues / Passes",
            "Passes\nlongues réussies (%)": "Longues passes précises, %",
            "Passes progressives\n/ Passes": "Passes progressives / Passes",
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
            "Passes courtes\n/ Passes": "Passes courtes / Passes",
            "Passes\ncourtes réussies (%)": "Passes courtes / moyennes précises, %",
            "Passes longues\n/ Passes": "Passes longues / Passes",
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
            "Attaques réussies par 90": 0.5,
            "Touches de balle dans la surface de réparation sur 90": 0.3,
            "Duels offensifs par 90": 0.1,
            "Duels de marquage, %": 0.1
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
            "xA / Passes": 0.25,
            "Passes clés / Passes": 0.2,
            "Passes avant tir / Passes": 0.15,
            "Passes judicieuses / Passes": 0.15,
            "Passes dans la zone dangereuse / Passes": 0.1,
            "Passes vers la surface / Passes": 0.05,
            "Passes dans le tiers adverse / Passes": 0.04,
            "Passes progressives / Passes": 0.03,
            "Passes en profondeur / Passes": 0.03
        },
        "Percussion": {
            "Courses progressives par 90": 0.3,
            "Accélérations par 90": 0.3,
            "Dribbles par 90": 0.2,
            "Dribbles réussis, %": 0.2
        },
        "Jeu aérien": {
            "Duels aériens par 90": 0.5,
            "Duels aériens gagnés, %": 0.5
        }
    },

    "Ailier": {
        "Finition": {
            "Buts - xG": 0.75,
            "Tirs à la cible, %": 0.15,
            "Taux de conversion but/tir": 0.1
        },
        "Apport offensif": {
            "Attaques réussies par 90": 0.4,
            "Centres par 90": 0.3,
            "Touches de balle dans la surface de réparation sur 90": 0.2,
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
            "xA / Passes": 0.25,
            "Passes clés / Passes": 0.2,
            "Passes avant tir / Passes": 0.15,
            "Passes judicieuses / Passes": 0.15,
            "Passes dans la zone dangereuse / Passes": 0.1,
            "Passes vers la surface / Passes": 0.05,
            "Passes dans le tiers adverse / Passes": 0.04,
            "Passes progressives / Passes": 0.03,
            "Passes en profondeur / Passes": 0.03
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
            "Duels défensifs par 90": 0.15,
            "Duels défensifs gagnés, %": 0.15,
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
            "Attaques réussies par 90": 0.5,
            "Touches de balle dans la surface de réparation sur 90": 0.3,
            "Duels offensifs par 90": 0.1,
            "Duels de marquage, %": 0.1
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
            "xA / Passes": 0.25,
            "Passes clés / Passes": 0.2,
            "Passes avant tir / Passes": 0.15,
            "Passes judicieuses / Passes": 0.15,
            "Passes dans la zone dangereuse / Passes": 0.1,
            "Passes vers la surface / Passes": 0.05,
            "Passes dans le tiers adverse / Passes": 0.04,
            "Passes progressives / Passes": 0.03,
            "Passes en profondeur / Passes": 0.03
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
            "Duels défensifs par 90": 0.15,
            "Duels défensifs gagnés, %": 0.15,
            "Tacles glissés PAdj": 0.05,
            "Tirs contrés par 90": 0.05
        }
    },

    "Milieu": {
        "Apport offensif": {
            "Attaques réussies par 90": 0.5,
            "Touches de balle dans la surface de réparation sur 90": 0.3,
            "Duels offensifs par 90": 0.1,
            "Duels de marquage, %": 0.1
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
            "xA / Passes": 0.25,
            "Passes clés / Passes": 0.2,
            "Passes avant tir / Passes": 0.15,
            "Passes judicieuses / Passes": 0.15,
            "Passes dans la zone dangereuse / Passes": 0.1,
            "Passes vers la surface / Passes": 0.05,
            "Passes dans le tiers adverse / Passes": 0.04,
            "Passes progressives / Passes": 0.03,
            "Passes en profondeur / Passes": 0.03
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
            "Duels défensifs par 90": 0.15,
            "Duels défensifs gagnés, %": 0.15,
            "Tacles glissés PAdj": 0.05,
            "Tirs contrés par 90": 0.05
        },
        "Jeu aérien": {
            "Duels aériens par 90": 0.5,
            "Duels aériens gagnés, %": 0.5
        }
    },

    "Latéral": {
        "Apport offensif": {
            "Attaques réussies par 90": 0.4,
            "Centres par 90": 0.3,
            "Touches de balle dans la surface de réparation sur 90": 0.2,
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
            "xA / Passes": 0.25,
            "Passes clés / Passes": 0.2,
            "Passes avant tir / Passes": 0.15,
            "Passes judicieuses / Passes": 0.15,
            "Passes dans la zone dangereuse / Passes": 0.1,
            "Passes vers la surface / Passes": 0.05,
            "Passes dans le tiers adverse / Passes": 0.04,
            "Passes progressives / Passes": 0.03,
            "Passes en profondeur / Passes": 0.03
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
            "Duels défensifs par 90": 0.15,
            "Duels défensifs gagnés, %": 0.15,
            "Tacles glissés PAdj": 0.05,
            "Tirs contrés par 90": 0.05
        },
        "Jeu aérien": {
            "Duels aériens par 90": 0.5,
            "Duels aériens gagnés, %": 0.5
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
            "xA / Passes": 0.25,
            "Passes clés / Passes": 0.2,
            "Passes avant tir / Passes": 0.15,
            "Passes judicieuses / Passes": 0.15,
            "Passes dans la zone dangereuse / Passes": 0.1,
            "Passes vers la surface / Passes": 0.05,
            "Passes dans le tiers adverse / Passes": 0.04,
            "Passes progressives / Passes": 0.03,
            "Passes en profondeur / Passes": 0.03
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
            "Duels défensifs par 90": 0.15,
            "Duels défensifs gagnés, %": 0.15,
            "Tacles glissés PAdj": 0.05,
            "Tirs contrés par 90": 0.05
        },
        "Jeu aérien": {
            "Duels aériens par 90": 0.5,
            "Duels aériens gagnés, %": 0.5
        }
    },

    "Gardien": {
        "Participe au jeu": {
            "Passes réceptionnées par 90": 1
        },
        "Jeu court": {
            "Passes courtes / Passes": 0.5,
            "Passes courtes / moyennes précises, %": 0.5,
        },
        "Jeu long": {
            "Passes longues / Passes": 0.5,
            "Longues passes précises, %": 0.5
        },
        "Sortie": {
            "Sorties par 90": 1
        },
        "Présence aérienne": {
            "Duels aériens par 90": 0.5,
            "Duels aériens gagnés, %": 0.5
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
        "metrics": ["Passes judicieuses / Passes", "Passes intelligentes précises, %"],
        "names": ["Passes judicieuses / Passes", "Passes judicieuses réussies, %"],
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
        new_columns = {
            'Buts - xG': df['Buts par 90'] - df['xG par 90'],
            'xG / Tirs': df['xG par 90'] / df['Tirs par 90'],
            'xA / Passes': df['xA par 90'] / df['Passes par 90'],
            'Passes courtes / Passes': df['Passes courtes / moyennes par 90'] / df['Passes par 90'],
            'Passes avant / Passes': df['Passes avant par 90'] / df['Passes par 90'],
            'Passes longues / Passes': df['Passes longues par 90'] / df['Passes par 90'],
            'Passes clés / Passes': df['Passes quasi décisives par 90'] / df['Passes par 90'],
            'Passes judicieuses / Passes': df['Passes judicieuses par 90'] / df['Passes par 90'],
            'Passes vers la surface / Passes': df['Passes vers la surface de réparation par 90'] / df['Passes par 90'],
            'Passes en profondeur / Passes': df['Passes pénétrantes par 90'] / df['Passes par 90'],
            'Passes dans le tiers adverse / Passes': df['Passes dans tiers adverse par 90'] / df['Passes par 90'],
            'Passes avant tir / Passes': df['Passes décisives avec tir par 90'] / df['Passes par 90'],
            'Passes progressives / Passes': df['Passes progressives par 90'] / df['Passes par 90'],
            'Passes dans la zone dangereuse / Passes': df['Réalisations en profondeur par 90'] / df['Passes par 90'],
        }

        df = pd.concat([df, pd.DataFrame(new_columns)], axis=1)

        all_df[name] = df
    return all_df

@st.cache_data
def collect_individual_data():
    load_all_files_from_drive()

    # Ligue 1
    ligue1_ailier = read_with_competition(f"data/Data {st.session_state['saison']}/Ligue 1 - Ailier.xlsx")
    ligue1_buteur = read_with_competition(f"data/Data {st.session_state['saison']}/Ligue 1 - Buteur.xlsx")
    ligue1_defenseur_central = read_with_competition(f"data/Data {st.session_state['saison']}/Ligue 1 - Défenseur central.xlsx")
    ligue1_lateral = read_with_competition(f"data/Data {st.session_state['saison']}/Ligue 1 - Latéral.xlsx")
    ligue1_milieu = read_with_competition(f"data/Data {st.session_state['saison']}/Ligue 1 - Milieu.xlsx")
    ligue1_milieu_offensif = read_with_competition(f"data/Data {st.session_state['saison']}/Ligue 1 - Milieu offensif.xlsx")
    ligue1_gardien = read_with_competition(f"data/Data {st.session_state['saison']}/Ligue 1 - Gardien.xlsx")

    # Ligue 2
    ligue2_ailier = read_with_competition(f"data/Data {st.session_state['saison']}/Ligue 2 - Ailier.xlsx")
    ligue2_buteur = read_with_competition(f"data/Data {st.session_state['saison']}/Ligue 2 - Buteur.xlsx")
    ligue2_defenseur_central = read_with_competition(f"data/Data {st.session_state['saison']}/Ligue 2 - Défenseur central.xlsx")
    ligue2_lateral = read_with_competition(f"data/Data {st.session_state['saison']}/Ligue 2 - Latéral.xlsx")
    ligue2_milieu = read_with_competition(f"data/Data {st.session_state['saison']}/Ligue 2 - Milieu.xlsx")
    ligue2_milieu_offensif = read_with_competition(f"data/Data {st.session_state['saison']}/Ligue 2 - Milieu offensif.xlsx")
    ligue2_gardien = read_with_competition(f"data/Data {st.session_state['saison']}/Ligue 2 - Gardien.xlsx")

    # National 1
    nat1_ailier = read_with_competition(f"data/Data {st.session_state['saison']}/National 1 - Ailier.xlsx")
    nat1_buteur = read_with_competition(f"data/Data {st.session_state['saison']}/National 1 - Buteur.xlsx")
    nat1_defenseur_central = read_with_competition(f"data/Data {st.session_state['saison']}/National 1 - Défenseur central.xlsx")
    nat1_lateral = read_with_competition(f"data/Data {st.session_state['saison']}/National 1 - Latéral.xlsx")
    nat1_milieu = read_with_competition(f"data/Data {st.session_state['saison']}/National 1 - Milieu.xlsx")
    nat1_milieu_offensif = read_with_competition(f"data/Data {st.session_state['saison']}/National 1 - Milieu offensif.xlsx")
    nat1_gardien = read_with_competition(f"data/Data {st.session_state['saison']}/National 1 - Gardien.xlsx")

    # National 2
    nat2_ailier = read_with_competition(f"data/Data {st.session_state['saison']}/National 2 - Ailier.xlsx")
    nat2_buteur = read_with_competition(f"data/Data {st.session_state['saison']}/National 2 - Buteur.xlsx")
    nat2_defenseur_central = read_with_competition(f"data/Data {st.session_state['saison']}/National 2 - Défenseur central.xlsx")
    nat2_lateral = read_with_competition(f"data/Data {st.session_state['saison']}/National 2 - Latéral.xlsx")
    nat2_milieu = read_with_competition(f"data/Data {st.session_state['saison']}/National 2 - Milieu.xlsx")
    nat2_milieu_offensif = read_with_competition(f"data/Data {st.session_state['saison']}/National 2 - Milieu offensif.xlsx")
    nat2_gardien = read_with_competition(f"data/Data {st.session_state['saison']}/National 2 - Gardien.xlsx")

    # Français
    français_ailier = read_with_competition(f"data/Data {st.session_state['saison']}/Français - Ailier.xlsx")
    français_buteur = read_with_competition(f"data/Data {st.session_state['saison']}/Français - Buteur.xlsx")
    français_defenseur_central = read_with_competition(f"data/Data {st.session_state['saison']}/Français - Défenseur central.xlsx")
    français_lateral = read_with_competition(f"data/Data {st.session_state['saison']}/Français - Latéral.xlsx")
    français_milieu = read_with_competition(f"data/Data {st.session_state['saison']}/Français - Milieu.xlsx")
    français_milieu_offensif = read_with_competition(f"data/Data {st.session_state['saison']}/Français - Milieu offensif.xlsx")
    français_gardien = read_with_competition(f"data/Data {st.session_state['saison']}/Français - Gardien.xlsx")

    # Top 5 Européen
    top5europe_ailier = read_with_competition(f"data/Data {st.session_state['saison']}/Top 5 Européen - Ailier.xlsx")
    top5europe_buteur = read_with_competition(f"data/Data {st.session_state['saison']}/Top 5 Européen - Buteur.xlsx")
    top5europe_defenseur_central = read_with_competition(f"data/Data {st.session_state['saison']}/Top 5 Européen - Défenseur central.xlsx")
    top5europe_lateral = read_with_competition(f"data/Data {st.session_state['saison']}/Top 5 Européen - Latéral.xlsx")
    top5europe_milieu = read_with_competition(f"data/Data {st.session_state['saison']}/Top 5 Européen - Milieu.xlsx")
    top5europe_milieu_offensif = read_with_competition(f"data/Data {st.session_state['saison']}/Top 5 Européen - Milieu offensif.xlsx")
    top5europe_gardien = read_with_competition(f"data/Data {st.session_state['saison']}/Top 5 Européen - Gardien.xlsx")

    # Concaténation de tous les DataFrames dans un giga DataFrame
    df_championnat_de_france = pd.concat([
        ligue1_ailier, ligue1_buteur, ligue1_defenseur_central, ligue1_lateral, ligue1_milieu, ligue1_milieu_offensif, ligue1_gardien,
        ligue2_ailier, ligue2_buteur, ligue2_defenseur_central, ligue2_lateral, ligue2_milieu, ligue2_milieu_offensif, ligue2_gardien,
        nat1_ailier, nat1_buteur, nat1_defenseur_central, nat1_lateral, nat1_milieu, nat1_milieu_offensif, nat1_gardien,
        nat2_ailier, nat2_buteur, nat2_defenseur_central, nat2_lateral, nat2_milieu, nat2_milieu_offensif, nat2_gardien
    ], ignore_index=True)

    df_français = pd.concat([
        français_ailier, français_buteur, français_defenseur_central, français_lateral, français_milieu, français_milieu_offensif, français_gardien
    ])

    df_top5européen = pd.concat([
        top5europe_ailier, top5europe_buteur, top5europe_defenseur_central, top5europe_lateral, top5europe_milieu, top5europe_milieu_offensif, top5europe_gardien
    ])

    df_championnat_de_france.columns = df_championnat_de_france.columns.str.strip()
    df_français.columns = df_français.columns.str.strip()
    df_top5européen.columns = df_top5européen.columns.str.strip()

    df_championnat_de_france['Contrat expiration'] = pd.to_datetime(df_championnat_de_france['Contrat expiration'], errors='coerce').dt.date
    df_français['Contrat expiration'] = pd.to_datetime(df_français['Contrat expiration'], errors='coerce').dt.date
    df_top5européen['Contrat expiration'] = pd.to_datetime(df_top5européen['Contrat expiration'], errors='coerce').dt.date

    all_df = {
        'Joueur du championnat de France': df_championnat_de_france,
        'Joueur français': df_français,
        'Joueur du top 5 européen': df_top5européen
    }

    all_df = add_new_columns(all_df)

    return all_df

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
        coeffs = df_scores["Joueur + Information"].str.extract(r'\((.*?)\)')[0].apply(lambda x: league_rating.get(x, 1))

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
        "Toulon": "https://upload.wikimedia.org/wikipedia/fr/thumb/d/d6/Logo_SC_Toulon.svg/langfr-800px-Logo_SC_Toulon.svg.png"
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

def search_top_players(df, poste):
    df_filtré = df[(df['Poste'] == poste) & (df['Minutes jouées'] >= 500)]

    df_ranked = rank_columns(df_filtré)

    df_scores = df_ranked[['Joueur + Information', 'Âge', 'Taille', 'Minutes jouées', 'Contrat expiration']].copy()

    kpi_metrics = kpi_by_position[poste]
    kpi_coefficients = kpi_coefficients_by_position[poste]
    total_coeff = sum(kpi_coefficients.values())

    for kpi, metrics in kpi_metrics.items():
        # Extraire la ligue et remplacer les valeurs absentes par 1
        coeffs = df_scores["Joueur + Information"].str.extract(r'\((.*?)\)')[0].apply(lambda x: league_rating.get(x, 1))

        # Appliquer le calcul du score avec la pondération
        df_scores[kpi] = (
            df_ranked[list(metrics.keys())].mul(list(metrics.values()), axis=1).sum(axis=1)
            * (1 - 0.5 + 0.5 * coeffs)
        ).round(1)

    df_scores["Note globale"] = sum(
        df_scores[kpi] * coef for kpi, coef in kpi_coefficients.items()
    ) / total_coeff

    df_scores["Note globale"] = df_scores["Note globale"].round(1)

    return df_scores

def search_recommended_players(df, poste, thresholds):
    df_filtré = df[(df['Poste'] == poste) & (df['Minutes jouées'] >= 500)]

    df_ranked = rank_columns(df_filtré)

    df_scores = df_ranked[['Joueur + Information', 'Âge', 'Taille', 'Minutes jouées', 'Contrat expiration'] + list(thresholds.keys())].copy()

    for métrique, seuil in thresholds.items():
        df_scores = df_scores[df_scores[métrique] >= seuil]

    return df_scores

def creation_moyenne_anglaise(résultats, type_classement, journée_début, journée_fin):
    # Filtrer les journées
    résultats_filtrés = résultats[(résultats["Journée"] >= journée_début) & (résultats["Journée"] <= journée_fin)].copy()

    # Initialiser un dictionnaire pour stocker les stats
    stats = {}

    for _, row in résultats_filtrés.iterrows():
        eq_dom = row["Équipe à domicile"]
        eq_ext = row["Équipe à l'extérieur"]
        score = row["Score"]
        buts_dom, buts_ext = map(int, score.split(" - "))

        if type_classement == "Général":
            équipes_concernées = [(eq_dom, buts_dom, buts_ext, True), (eq_ext, buts_ext, buts_dom, False)]
        elif type_classement == "Domicile":
            équipes_concernées = [(eq_dom, buts_dom, buts_ext, True)]
        elif type_classement == "Extérieur":
            équipes_concernées = [(eq_ext, buts_ext, buts_dom, False)]
        else:
            raise ValueError("Type de classement non reconnu")

        for équipe, bp, bc, is_home in équipes_concernées:
            if équipe not in stats:
                stats[équipe] = {"Moyenne anglaise": 0}

            # Détermination du résultat
            if bp > bc:
                stats[équipe]["Moyenne anglaise"] += 0 if is_home else 2
            elif bp == bc:
                stats[équipe]["Moyenne anglaise"] += -2 if is_home else 0
            else:
                stats[équipe]["Moyenne anglaise"] += -3 if is_home else -1

    # Conversion en DataFrame
    df_ranking = pd.DataFrame.from_dict(stats, orient='index')
    df_ranking.index.name = "Equipes"

    # Tri simplement par valeur, car c'est une Series ou DataFrame d'une colonne
    df_ranking = df_ranking.sort_values("Moyenne anglaise", ascending=False).reset_index()

    return df_ranking

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

    if sélection_dataframe == 'Joueur du championnat de France':
        df_player = df_player[df_player['Competition'] == 'France. National 2']

    return df_player

def plot_rating_distribution(values, player_rating, kpi):
    # Créer la figure et les axes
    fig, ax = plt.subplots(figsize=(5, 3))

    # Courbe KDE (estimation de densité)
    sns.kdeplot(values, fill=False, color="black", linewidth=1.5, ax=ax)

    # Créer des points pour la zone ombrée
    x = np.linspace(0, 100, 1000)
    kde = stats.gaussian_kde(values)
    y = kde(x)

    # Remplir la zone jusqu’à la note du joueur
    ax.fill_between(x, 0, y, where=(x <= player_rating), color='#ac141a')

    # Calcul du percentile
    percentile = stats.percentileofscore(values, player_rating)

    # Titre de l'axe
    ax.set_title(f"{kpi}", fontsize=15, fontweight='bold', loc='center')

    # Texte centré dans la figure (et pas dans l'axe) – dans la marge blanche
    fig.text(0.5, 0.8, f"Rating : {player_rating} | Percentile : {int(percentile)}",
             fontsize=11, ha='center', va='bottom')

    # Supprimer les bordures noires autour
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Nettoyage des axes
    ax.set_xticks(np.arange(0, 101, 20))
    ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, max(y) * 1.25)

    fig.tight_layout()

    fig.set_facecolor('#f4f3ed')
    ax.set_facecolor('#f4f3ed')

    return fig

def streamlit_application(all_df):
    with st.sidebar:
        saison = st.selectbox(
            "Saison",
            ["24-25", "25-26"],
            index=0
        )
        st.session_state["saison"] = saison
    
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
        type_classement = st.selectbox("Sélectionnez un type de classement", ['Général', 'Domicile', 'Extérieur'])

        col1, col2 = st.columns(2)

        with col1:
            journée_début = st.number_input("Sélectionnez la journée de début", min_value=1, max_value=30, value=1)

        with col2:
            journée_fin = st.number_input("Sélectionnez la journée de fin", min_value=1, max_value=30, value=30)

        if journée_fin < journée_début:
            st.warning("⚠️ La journée de fin doit être supérieure ou égale à la journée de début.")

        else:
            url = f"https://www.foot-national.com/data/2024-2025-classement-national2-groupe-a-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html"

            response = requests.get(url)
            response.encoding = "ISO-8859-1"

            tables = pd.read_html(response.text)

            classement = tables[0]
            classement = classement.iloc[:, :-1]

            classement.columns = [col.replace('\xa0', ' ').strip() for col in classement.columns]

            df_résultats = pd.read_excel(f"data/Data {st.session_state['saison']}/résultats.xlsx")
            df_résultats.columns = df_résultats.columns.str.strip()

            moyenne_anglaise = creation_moyenne_anglaise(df_résultats, type_classement, journée_début, journée_fin)
            classement = classement.merge(moyenne_anglaise, on="Equipes", how="left")

            classement = classement.rename(columns={'Rangs': 'Classement'})

            st.dataframe(classement, use_container_width=True, hide_index=True)

    elif page == "Vidéo des buts":
        st.header("Vidéo des buts")

        journées = {
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
        }

        col1, col2 = st.columns([1, 3])

        with col1:
            journée = st.selectbox("Sélectionnez une journée", list(journées.keys()))
        with col2:
            match = st.selectbox("Sélectionnez un match", journées[journée])

        # Affichage si la vidéo existe
        if os.path.exists(f"data/Data {st.session_state['saison']}/{journée} - {match}.mp4"):
            st.video(f"data/Data {st.session_state['saison']}/{journée} - {match}.mp4")
        else:
            st.warning("⚠️ Vidéo non disponible pour ce match : il est possible qu'il n'y ait pas eu de but (0-0) ou que la vidéo ne soit pas encore disponible.")

    elif page == "Analyse collective":
        st.header("Analyse collective")

        tab1, tab2 = st.tabs(['Statistiques globales', 'Statistiques par équipe'])

        équipes = [
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
        ]

        df_stats_moyennes = pd.DataFrame()

        for équipe in équipes:
            df_filtré = collect_collective_data(équipe)
            df_filtré = df_filtré[df_filtré['Compétition'] == 'France. National 2']
            df_stats = df_filtré[df_filtré['Équipe'] == équipe]
            df_stats = df_stats.mean(numeric_only=True).to_frame().T.round(2)
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

                df_filtré = df[df['Équipe dans la période sélectionnée'].isin(équipes)]

                colonnes_à_exclure = [
                    'Minutes jouées', 'Âge', 'Taille', 'Poids', 'Valeur marchande',
                    'Matchs joués', 'xG', 'xA', 'Buts', 'Passes décisives',
                    'Cartons jaunes', 'Cartons rouges', 'Buts hors penaltyButs hors penalty',
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
            team = st.selectbox("Sélectionnez une équipe", équipes, index=équipes.index("Cannes"))

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
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Statistique", "Radar", "Nuage de points", "KPI", "Joueur similaire", "Match"])
        else:
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["Statistique", "Radar", "Nuage de points", "KPI", "Joueur similaire"])

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

                colonnes_smart = smart_goal.get(nom_joueur, [])

                for groupe in colonnes_smart:
                    cols = st.columns(len(groupe))

                    for i, col_name in enumerate(groupe):
                        val = df_player_mean[col_name].values[0]
                        val = round(val, 2)
                        
                        if len(groupe) == 3:
                            bordered_metric(cols[i], col_name, val, 225)
                        elif len(groupe) == 2:
                            bordered_metric(cols[i], col_name, val, 345)
                        elif len(groupe) == 1:
                            bordered_metric(cols[i], col_name, val, 705)

                    st.markdown("<div style='margin-top: 10px'></div>", unsafe_allow_html=True)
                
        with tab2:
            fig = create_individual_radar(df, joueur, poste)
            st.pyplot(fig, use_container_width=True)

        with tab3:
            if poste != 'Gardien': 
                metrics_label  = st.selectbox("Sélectionnez une base de comparaison", [k for k in metrics_x_y.keys() if k != "Buts évités"])
            else:
                metrics_label = "Buts évités"

            x_metric, y_metric = metrics_x_y[metrics_label]["metrics"]
            nom_x_metric, nom_y_metric = metrics_x_y[metrics_label]["names"]
            description_1, description_2, description_3, description_4 = metrics_x_y[metrics_label]["descriptions"]

            fig = plot_player_metrics(df, joueur, poste, x_metric, y_metric, nom_x_metric, nom_y_metric, description_1, description_2, description_3, description_4)
            st.plotly_chart(fig, use_container_width=True)

        with tab4:
            scores_df = calcul_scores_par_kpi(df, joueur, poste)
            joueur_scores = scores_df[scores_df['Joueur + Information'] == joueur].iloc[0]
            kpis_poste = list(kpi_by_position[poste].keys())

            col1, col2 = st.columns(2)

            with col1:
                fig1 = plot_rating_distribution(scores_df[kpis_poste[0]], joueur_scores[kpis_poste[0]], kpis_poste[0])
                st.pyplot(fig1)

                fig3 = plot_rating_distribution(scores_df[kpis_poste[2]], joueur_scores[kpis_poste[2]], kpis_poste[2])
                st.pyplot(fig3)

                fig5 = plot_rating_distribution(scores_df[kpis_poste[4]], joueur_scores[kpis_poste[4]], kpis_poste[4])
                st.pyplot(fig5)

            with col2:
                fig2 = plot_rating_distribution(scores_df[kpis_poste[1]], joueur_scores[kpis_poste[1]], kpis_poste[1])
                st.pyplot(fig2)

                fig4 = plot_rating_distribution(scores_df[kpis_poste[3]], joueur_scores[kpis_poste[3]], kpis_poste[3])
                st.pyplot(fig4)

                fig6 = plot_rating_distribution(scores_df[kpis_poste[5]], joueur_scores[kpis_poste[5]], kpis_poste[5])
                st.pyplot(fig6)

            # Créer 3 colonnes pour centrer la fig 7
            _, col_center, _ = st.columns([1, 2, 1])

            with col_center:
                fig7 = plot_rating_distribution(scores_df['Note globale'], joueur_scores['Note globale'], 'Note globale')
                st.pyplot(fig7)

            st.markdown("<div style='margin-top: 10px'></div>", unsafe_allow_html=True)

            st.warning("⚠️ Les notes sont pondérées par un coefficient reflétant le niveau du championnat, sauf pour les bases de données « Joueurs du top 5 européen » et « Joueurs français », pour lesquelles aucun ajustement n'est appliqué.")

        with tab5:
            nombre_joueur = st.number_input("Sélectionnez le nombre de joueurs que vous voulez voir apparaître", min_value=1, max_value=50, value=10)

            similar_players = compute_similarity(df, joueur, poste)

            similar_players.insert(0, "Classement", range(1, len(similar_players) + 1))

            st.dataframe(similar_players.head(nombre_joueur), use_container_width=True, hide_index=True)

        if team == "Cannes":
            with tab6:
                nom_joueur = joueur.split(" - ")[0]

                df_player = create_player_data(nom_joueur, sélection_dataframe)

                df_player = ajouter_pourcentages(df_player)

                match = st.selectbox("Sélectionnez le match à analyser", df_player["Match"].unique())
                df_player = df_player[df_player["Match"] == match]

                note = performance_index(df_player, poste, match)

                st.subheader('Statistiques générales')

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    bordered_metric(col1, "Minutes jouées", df_player["Minutes jouées"].values[0], 165)

                with col2:
                    if poste != 'Gardien':
                        bordered_metric(col2, "But", df_player["But"].values[0], 165)
                    else:
                        bordered_metric(col2, "Buts concédés", df_player["Buts concédés"].values[0], 165)

                with col3:
                    if poste != 'Gardien':
                        bordered_metric(col3, "Passe décisive", df_player["Passe décisive"].values[0], 165)
                    else:
                        bordered_metric(col3, "xG concédés", df_player["xCG"].values[0], 165)

                with col4:
                    bordered_metric(col4, "Note", note, 165, color="#ac141a")

                st.markdown("---")

                st.subheader('Smart Goals')

                colonnes_smart = smart_goal.get(nom_joueur, [])

                for groupe in colonnes_smart:
                    cols = st.columns(len(groupe))

                    for i, col_name in enumerate(groupe):
                        val = df_player[col_name].values[0]
                        val = int(val)

                        mean_val = df_player_mean[col_name].values[0]
                        color = "#1aac14" if val > mean_val else "#ac141a"

                        if len(groupe) == 3:
                            bordered_metric(cols[i], col_name, val, 225, color)
                        elif len(groupe) == 2:
                            bordered_metric(cols[i], col_name, val, 345, color)
                        elif len(groupe) == 1:
                            bordered_metric(cols[i], col_name, val, 705, color)

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

        if st.button("Comparer"):
            fig = create_comparison_radar(df, joueur_1, joueur_2, poste)
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

        tab1, tab2 = st.tabs(["Classement", "Recommandation"])

        with tab1:
            nombre_joueur = st.number_input("Sélectionnez le nombre de joueurs que vous voulez voir apparaître", min_value=1, max_value=50, value=10)

            top_players = search_top_players(df, poste)
            top_players = top_players[((top_players['Âge'] >= min_age) & (top_players['Âge'] <= max_age)) & 
                                    ((top_players['Taille'] >= min_taille) & (top_players['Taille'] <= max_taille) | (top_players['Taille'] == 0))]
            top_players = top_players.sort_values(by='Note globale', ascending=False).head(nombre_joueur)

            top_players.insert(0, "Classement", range(1, len(top_players) + 1))

            st.dataframe(top_players, use_container_width=True, hide_index=True)

            st.warning("⚠️ Les notes sont pondérées par un coefficient reflétant le niveau du championnat, sauf pour les bases de données « Joueurs du top 5 européen » et « Joueurs français », pour lesquelles aucun ajustement n'est appliqué.")

        with tab2:
            metric_or_kpi = st.radio("Sélectionnez le type de critère pour la recommandation", ["Métrique", "KPI"])

            if metric_or_kpi == "Métrique":
                colonnes_à_exclure = [
                    'Minutes jouées', 'Âge', 'Taille', 'Poids', 'Valeur marchande',
                    'Matchs joués', 'xG', 'xA', 'Buts', 'Passes décisives',
                    'Cartons jaunes', 'Cartons rouges', 'Buts hors penaltyButs hors penalty',
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

                kpis_sélectionnées = st.multiselect("Sélectionnez des métriques", colonnes_filtrées)

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
        all_df = collect_individual_data()
        streamlit_application(all_df)