import pandas as pd 
import numpy as np
import os
from mplsoccer import PyPizza
import io
from mplsoccer import Radar, FontManager, grid
import streamlit as st
import matplotlib.pyplot as plt
import plotly.express as px
import requests
import unicodedata

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

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
    query = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    return results.get('files', [])

# Télécharger un fichier depuis Google Drive et le sauvegarder dans ./data/
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

# Fonction principale : télécharge tous les fichiers du dossier Google Drive spécifié
def load_all_files_from_drive():
    folder_id = '1s_XoaozPoIQtVzY_xRnhNfCnQ3xXkTm9'
    service = authenticate_google_drive()
    files = list_files_in_folder(service, folder_id)

    if not files:
        st.warning("Aucun fichier trouvé dans le dossier Drive.")
        return

    for file in files:
        download_file(service, file['id'], file['name'])

metrics_by_position = [
    {
        "position": "Buteur",
        "metrics": {
            "Attaques réussies": "Attaques réussies par 90",
            "Buts hors pen.": "Buts hors penalty par 90",
            "xG": "xG par 90",
            "Précision tirs": "Tirs à la cible, %",
            "Conversion tirs": "Taux de conversion but/tir",
            "xA": "xA par 90",
            "Passes clés": "Passes judicieuses par 90",
            "Passes reçues": "Passes réceptionnées par 90",
            "Touches surface": "Touches de balle dans la surface de réparation sur 90",
            "Courses prog.": "Courses progressives par 90",
            "Accélérations": "Accélérations par 90",
            "Dribbles": "Dribbles par 90",
            "Dribbles réussis": "Dribbles réussis, %",
            "Duels off.": "Duels offensifs par 90",
            "Duels aér.": "Duels aériens par 90",
            "Duels aér.\ngagnés": "Duels aériens gagnés, %",
        }
    },
    {
        "position": "Ailier",
        "metrics": {
            "Attaques réussies": "Attaques réussies par 90",
            "xG": "xG par 90",
            "xA": "xA par 90",
            "Centres": "Centres par 90",
            "Centres réussis": "Сentres précises, %",
            "Passes quasi\ndéc.": "Passes quasi décisives par 90",
            "Passes clés": "Passes judicieuses par 90",
            "Passes surface": "Passes vers la surface de réparation par 90",
            "Passes\npénétrantes": "Passes pénétrantes par 90",
            "Passes tiers adv.": "Passes dans tiers adverse par 90",
            "Passes prog.": "Passes progressives par 90",
            "Courses prog.": "Courses progressives par 90",
            "Accélérations": "Accélérations par 90",
            "Dribbles": "Dribbles par 90",
            "Dribbles réussis": "Dribbles réussis, %",
            "Duels off.": "Duels offensifs par 90"
        }
    },
    {
        "position": "Milieu offensif",
        "metrics": {
            "Attaques réussies": "Attaques réussies par 90",
            "xG": "xG par 90",
            "xA": "xA par 90",
            "Passes quasi déc.": "Passes quasi décisives par 90",
            "Passes clés": "Passes judicieuses par 90",
            "Passes surface": "Passes vers la surface de réparation par 90",
            "Passes\npénétrantes": "Passes pénétrantes par 90",
            "Passes tiers adv.": "Passes dans tiers adverse par 90",
            "Passes prog.": "Passes progressives par 90",
            "Courses prog.": "Courses progressives par 90",
            "Accélérations": "Accélérations par 90",
            "Dribbles": "Dribbles par 90",
            "Dribbles réussis": "Dribbles réussis, %",
            "Duels": "Duels par 90",
            "Duels gagnés": "Duels gagnés, %",
            "Actions déf.\nréussies": "Actions défensives réussies par 90"
        }
    },
    {
        "position": "Milieu",
        "metrics": {
            "Attaques réussies": "Attaques réussies par 90",
            "xA": "xA par 90",
            "Passes avant": "Passes avant par 90",
            "Passes clés": "Passes judicieuses par 90",
            "Passes tiers adv.": "Passes dans tiers adverse par 90",
            "Passes prog.": "Passes progressives par 90",
            "Courses prog.": "Courses progressives par 90",
            "Accélérations": "Accélérations par 90",
            "Duels aér.": "Duels aériens par 90",
            "Duels aér.\ngagnés": "Duels aériens gagnés, %",
            "Duels": "Duels par 90",
            "Duels gagnés": "Duels gagnés, %",
            "Tacles glissés": "Tacles glissés par 90",
            "Interceptions": "Interceptions par 90",
            "Tirs contrés": "Tirs contrés par 90",
            "Actions déf.\nréussies": "Actions défensives réussies par 90"
        }
    },
    {
        "position": "Latéral",
        "metrics": {
            "Attaques réussies": "Attaques réussies par 90",
            "xA": "xA par 90",
            "Passes surface": "Passes vers la surface de réparation par 90",
            "Centres": "Centres par 90",
            "Centres réussis": "Сentres précises, %",
            "Passes prog.": "Passes progressives par 90",
            "Courses prog.": "Courses progressives par 90",
            "Accélérations": "Accélérations par 90",
            "Duels aér.": "Duels aériens par 90",
            "Duels aér.\ngagnés": "Duels aériens gagnés, %",
            "Duels": "Duels par 90",
            "Duels gagnés": "Duels gagnés, %",
            "Tacles glissés": "Tacles glissés par 90",
            "Interceptions": "Interceptions par 90",
            "Tirs contrés": "Tirs contrés par 90",
            "Actions déf.\nréussies": "Actions défensives réussies par 90"
        }
    },
    {
        "position": "Défenseur central",
        "metrics": {
            "Buts tête": "Buts de la tête par 90",
            "Passes avant": "Passes avant par 90",
            "Passes avant\nréussies": "Passes en avant précises, %",
            "Passes longues": "Passes en avant précises, %",
            "Passes longues\nréussies": "Longues passes précises, %",
            "Passes prog.": "Passes progressives par 90",
            "Courses prog.": "Courses progressives par 90",
            "Accélérations": "Accélérations par 90",
            "Duels aér.": "Duels aériens par 90",
            "Duels aér.\ngagnés": "Duels aériens gagnés, %",
            "Duels déf.": "Duels défensifs par 90",
            "Duels déf.\ngagnés": "Duels défensifs gagnés, %",
            "Tacles glissés": "Tacles glissés par 90",
            "Interceptions": "Interceptions par 90",
            "Tirs contrés": "Tirs contrés par 90",
            "Actions déf.\nréussies": "Actions défensives réussies par 90"
        }
    }
]

kpi_by_position = {
    "Buteur": {
        "Finition": {
            "Buts hors penalty par 90": 0.35,
            "xG par 90": 0.3,
            "Taux de conversion but/tir": 0.2,
            "Tirs à la cible, %": 0.15
        },
        "Apport offensif": {
            "Attaques réussies par 90": 0.3,
            "xA par 90": 0.4,
            "Touches de balle dans la surface de réparation sur 90": 0.3
        },
        "Qualité de passe": {
            "Passes précises, %": 0.3,
            "Longues passes précises, %": 0.2,
            "Passes en avant précises, %":0.4,
            "Passes en profondeur précises, %": 0.1
        },
        "Vision du jeu": {
            "Passes pénétrantes par 90": 0.15,
            "Passes progressives par 90": 0.15,
            "Passes dans tiers adverse par 90": 0.15,
            "Passes vers la surface de réparation par 90": 0.2,
            "Passes avant par 90": 0.05,
            "Passes judicieuses par 90": 0.3
        },
        "Percussion": {
            "Dribbles par 90": 0.1,
            "Dribbles réussis, %": 0.1,
            "Duels offensifs par 90": 0.1,
            "Courses progressives par 90": 0.35,
            "Accélérations par 90": 0.35
        },
        "Jeu aérien": {
            "Duels aériens par 90": 0.4,
            "Duels aériens gagnés, %": 0.6
        }
    },

    "Ailier": {
        "Finition": {
            "Buts hors penalty par 90": 0.35,
            "xG par 90": 0.3,
            "Taux de conversion but/tir": 0.2,
            "Tirs à la cible, %": 0.15
        },
        "Apport offensif": {
            "Centres par 90": 0.15,
            "Сentres précises, %": 0.15,
            "Attaques réussies par 90": 0.2,
            "xA par 90": 0.3,
            "Touches de balle dans la surface de réparation sur 90": 0.2
        },
        "Qualité de passe": {
            "Passes précises, %": 0.3,
            "Longues passes précises, %": 0.2,
            "Passes en avant précises, %":0.4,
            "Passes en profondeur précises, %": 0.1
        },
        "Vision du jeu": {
            "Passes pénétrantes par 90": 0.15,
            "Passes progressives par 90": 0.15,
            "Passes dans tiers adverse par 90": 0.15,
            "Passes vers la surface de réparation par 90": 0.2,
            "Passes avant par 90": 0.05,
            "Passes judicieuses par 90": 0.3
        },
        "Percussion": {
            "Dribbles par 90": 0.1,
            "Dribbles réussis, %": 0.1,
            "Duels offensifs par 90": 0.1,
            "Courses progressives par 90": 0.35,
            "Accélérations par 90": 0.35
        },
        "Jeu défensif": {
            "Duels défensifs par 90": 0.2,
            "Duels défensifs gagnés, %": 0.2,
            "Interceptions par 90": 0.15,
            "Tacles glissés par 90": 0.05,
            "Tirs contrés par 90": 0.05,
            "Actions défensives réussies par 90": 0.35
        }
    },

    "Milieu offensif": {
        "Finition": {
            "Buts hors penalty par 90": 0.35,
            "xG par 90": 0.3,
            "Taux de conversion but/tir": 0.2,
            "Tirs à la cible, %": 0.15
        },
        "Apport offensif": {
            "Attaques réussies par 90": 0.3,
            "xA par 90": 0.4,
            "Touches de balle dans la surface de réparation sur 90": 0.3
        },
        "Qualité de passe": {
            "Passes précises, %": 0.3,
            "Longues passes précises, %": 0.2,
            "Passes en avant précises, %":0.4,
            "Passes en profondeur précises, %": 0.1
        },
        "Vision du jeu": {
            "Passes pénétrantes par 90": 0.15,
            "Passes progressives par 90": 0.15,
            "Passes dans tiers adverse par 90": 0.15,
            "Passes vers la surface de réparation par 90": 0.2,
            "Passes avant par 90": 0.05,
            "Passes judicieuses par 90": 0.3
        },
        "Percussion": {
            "Dribbles par 90": 0.1,
            "Dribbles réussis, %": 0.1,
            "Duels offensifs par 90": 0.1,
            "Courses progressives par 90": 0.35,
            "Accélérations par 90": 0.35
        },
        "Jeu défensif": {
            "Duels défensifs par 90": 0.2,
            "Duels défensifs gagnés, %": 0.2,
            "Interceptions par 90": 0.15,
            "Tacles glissés par 90": 0.05,
            "Tirs contrés par 90": 0.05,
            "Actions défensives réussies par 90": 0.35
        }
    },

    "Milieu": {
        "Apport offensif": {
            "Attaques réussies par 90": 0.3,
            "xA par 90": 0.4,
            "Touches de balle dans la surface de réparation sur 90": 0.3
        },
        "Qualité de passe": {
            "Passes précises, %": 0.3,
            "Longues passes précises, %": 0.2,
            "Passes en avant précises, %":0.4,
            "Passes en profondeur précises, %": 0.1
        },
        "Vision du jeu": {
            "Passes pénétrantes par 90": 0.15,
            "Passes progressives par 90": 0.15,
            "Passes dans tiers adverse par 90": 0.15,
            "Passes vers la surface de réparation par 90": 0.2,
            "Passes avant par 90": 0.05,
            "Passes judicieuses par 90": 0.3
        },
        "Percussion": {
            "Dribbles par 90": 0.1,
            "Dribbles réussis, %": 0.1,
            "Duels offensifs par 90": 0.1,
            "Courses progressives par 90": 0.35,
            "Accélérations par 90": 0.35
        },
        "Jeu défensif": {
            "Duels défensifs par 90": 0.2,
            "Duels défensifs gagnés, %": 0.2,
            "Interceptions par 90": 0.15,
            "Tacles glissés par 90": 0.05,
            "Tirs contrés par 90": 0.05,
            "Actions défensives réussies par 90": 0.35
        },
        "Jeu aérien": {
            "Duels aériens par 90": 0.4,
            "Duels aériens gagnés, %": 0.6
        }
    },

    "Latéral": {
        "Apport offensif": {
            "Centres par 90": 0.15,
            "Сentres précises, %": 0.15,
            "Attaques réussies par 90": 0.2,
            "xA par 90": 0.3,
            "Touches de balle dans la surface de réparation sur 90": 0.2
        },
        "Qualité de passe": {
            "Passes précises, %": 0.3,
            "Longues passes précises, %": 0.2,
            "Passes en avant précises, %":0.4,
            "Passes en profondeur précises, %": 0.1
        },
        "Vision du jeu": {
            "Passes pénétrantes par 90": 0.15,
            "Passes progressives par 90": 0.15,
            "Passes dans tiers adverse par 90": 0.15,
            "Passes vers la surface de réparation par 90": 0.2,
            "Passes avant par 90": 0.05,
            "Passes judicieuses par 90": 0.3
        },
        "Percussion": {
            "Dribbles par 90": 0.1,
            "Dribbles réussis, %": 0.1,
            "Duels offensifs par 90": 0.1,
            "Courses progressives par 90": 0.35,
            "Accélérations par 90": 0.35
        },
        "Jeu défensif": {
            "Duels défensifs par 90": 0.2,
            "Duels défensifs gagnés, %": 0.2,
            "Interceptions par 90": 0.15,
            "Tacles glissés par 90": 0.05,
            "Tirs contrés par 90": 0.05,
            "Actions défensives réussies par 90": 0.35
        },
        "Jeu aérien": {
            "Duels aériens par 90": 0.4,
            "Duels aériens gagnés, %": 0.6
        }
    },

    "Défenseur central": {
        "Qualité de passe": {
            "Passes précises, %": 0.3,
            "Longues passes précises, %": 0.2,
            "Passes en avant précises, %":0.4,
            "Passes en profondeur précises, %": 0.1
        },
        "Vision du jeu": {
            "Passes pénétrantes par 90": 0.15,
            "Passes progressives par 90": 0.15,
            "Passes dans tiers adverse par 90": 0.15,
            "Passes vers la surface de réparation par 90": 0.2,
            "Passes avant par 90": 0.05,
            "Passes judicieuses par 90": 0.3
        },
        "Percussion": {
            "Dribbles par 90": 0.1,
            "Dribbles réussis, %": 0.1,
            "Duels offensifs par 90": 0.1,
            "Courses progressives par 90": 0.35,
            "Accélérations par 90": 0.35
        },
        "Jeu défensif": {
            "Duels défensifs par 90": 0.35,
            "Duels défensifs gagnés, %": 0.35,
            "Interceptions par 90": 0.2,
            "Tacles glissés par 90": 0.1
        },
        "Jeu aérien": {
            "Duels aériens par 90": 0.4,
            "Duels aériens gagnés, %": 0.6
        },
        "Protection de la surface": {
            "Tirs contrés par 90": 0.25,
            "Actions défensives réussies par 90": 0.75
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
        "Jeu aérien": 2
    },
    "Ailier": {
        "Finition": 3,
        "Apport offensif": 4,
        "Qualité de passe": 2,
        "Vision du jeu": 3,
        "Percussion": 3,
        "Jeu défensif": 1
    },
    "Milieu offensif": {
        "Finition": 2,
        "Apport offensif": 3,
        "Qualité de passe": 3,
        "Vision du jeu": 4,
        "Percussion": 2,
        "Jeu défensif": 1
    },
    "Milieu": {
        "Apport offensif": 2,
        "Qualité de passe": 3,
        "Vision du jeu": 4,
        "Percussion": 2,
        "Jeu défensif": 3,
        "Jeu aérien": 1
    },
    "Latéral": {
        "Apport offensif": 4,
        "Qualité de passe": 2,
        "Vision du jeu": 3,
        "Percussion": 2,
        "Jeu défensif": 3,
        "Jeu aérien": 1
    },
    "Défenseur central": {
        "Qualité de passe": 2,
        "Vision du jeu": 2,
        "Percussion": 1,
        "Jeu défensif": 4,
        "Jeu aérien": 4,
        "Protection de la surface": 3
    }
}

metrics_x_y = {
    "Finition": {
        "metrics": ["xG par 90", "Buts par 90"],
        "descriptions": [
            "Se procure peu d'occasions<br>mais marque beaucoup",
            "Se procure beaucoup d'occasions<br>et marque beaucoup",
            "Se procure peu d'occasions<br>et marque peu",
            "Se procure beaucoup d'occasions<br>mais marque peu"
        ]
    },
    "Progression du ballon": {
        "metrics": ["Courses progressives par 90", "Passes progressives par 90"],
        "descriptions": [
            "Progresse peu par la course<br>mais beaucoup par la passe",
            "Progresse beaucoup par la course<br>et par la passe",
            "Progresse peu par la course<br>et par la passe",
            "Progresse beaucoup par la course<br>mais peu par la passe"
        ]
    },
    "Dribble": {
        "metrics": ["Dribbles par 90", "Dribbles réussis, %"],
        "descriptions": [
            "Dribble peu<br>mais réussit beaucoup",
            "Dribble beaucoup<br>et réussit beaucoup",
            "Dribble peu<br>et réussit peu",
            "Dribble beaucoup<br>mais réussit peu"
        ]
    },
    "Qualité de centre": {
        "metrics": ["Centres par 90", "Сentres précises, %"],
        "descriptions": [
            "Centre peu<br>mais en réussit beaucoup",
            "Centre beaucoup<br>et en réussit beaucoup",
            "Centre peu<br>et en réussit peu",
            "Centre beaucoup<br>mais en réussit peu"
        ]
    },
    "Apport défensif/offensif": {
        "metrics": ["Actions défensives réussies par 90", "Attaques réussies par 90"],
        "descriptions": [
            "Apporte peu défensivement<br>mais beaucoup offensivement",
            "Apporte beaucoup défensivement<br>et offensivement",
            "Apporte peu défensivement<br>et offensivement",
            "Apporte beaucoup défensivement<br>mais peu offensivement"
        ]
    },
    "Duel": {
        "metrics": ["Duels par 90", "Duels gagnés, %"],
        "descriptions": [
            "Joue peu de duels<br>mais en remporte beaucoup",
            "Joue beaucoup de duels<br>et en remporte beaucoup",
            "Joue peu de duels<br>et en remporte peu",
            "Joue beaucoup de duels<br>mais en remporte peu"
        ]
    },
    "Duel défensif": {
        "metrics": ["Duels défensifs par 90", "Duels défensifs gagnés, %"],
        "descriptions": [
            "Joue peu de duels défensifs<br>mais en remporte beaucoup",
            "Joue beaucoup de duels défensifs<br>et en remporte beaucoup",
            "Joue peu de duels défensifs<br>et en remporte peu",
            "Joue beaucoup de duels défensifs<br>mais en remporte peu"
        ]
    },
    "Duel aérien": {
        "metrics": ["Duels aériens par 90", "Duels aériens gagnés, %"],
        "descriptions": [
            "Joue peu de duels aériens<br>mais en remporte beaucoup",
            "Joue beaucoup de duels aériens<br>et en remporte beaucoup",
            "Joue peu de duels aériens<br>et en remporte peu",
            "Joue beaucoup de duels aériens<br>mais en remporte peu"
        ]
    }
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

@st.cache_data
def collect_data():
    load_all_files_from_drive()

     # Chargement des données
    df_collective = pd.read_excel('data/AS Cannes.xlsx')

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

    # Ligue 1
    ligue1_ailier = read_with_competition('data/Ligue 1 - Ailier.xlsx')
    ligue1_buteur = read_with_competition('data/Ligue 1 - Buteur.xlsx')
    ligue1_defenseur_central = read_with_competition('data/Ligue 1 - Défenseur central.xlsx')
    ligue1_lateral = read_with_competition('data/Ligue 1 - Latéral.xlsx')
    ligue1_milieu = read_with_competition('data/Ligue 1 - Milieu.xlsx')
    ligue1_milieu_offensif = read_with_competition('data/Ligue 1 - Milieu offensif.xlsx')

    # Ligue 2
    ligue2_ailier = read_with_competition('data/Ligue 2 - Ailier.xlsx')
    ligue2_buteur = read_with_competition('data/Ligue 2 - Buteur.xlsx')
    ligue2_defenseur_central = read_with_competition('data/Ligue 2 - Défenseur central.xlsx')
    ligue2_lateral = read_with_competition('data/Ligue 2 - Latéral.xlsx')
    ligue2_milieu = read_with_competition('data/Ligue 2 - Milieu.xlsx')
    ligue2_milieu_offensif = read_with_competition('data/Ligue 2 - Milieu offensif.xlsx')

    # National 1
    nat1_ailier = read_with_competition('data/National 1 - Ailier.xlsx')
    nat1_buteur = read_with_competition('data/National 1 - Buteur.xlsx')
    nat1_defenseur_central = read_with_competition('data/National 1 - Défenseur central.xlsx')
    nat1_lateral = read_with_competition('data/National 1 - Latéral.xlsx')
    nat1_milieu = read_with_competition('data/National 1 - Milieu.xlsx')
    nat1_milieu_offensif = read_with_competition('data/National 1 - Milieu offensif.xlsx')

    # National 2
    nat2_ailier = read_with_competition('data/National 2 - Ailier.xlsx')
    nat2_buteur = read_with_competition('data/National 2 - Buteur.xlsx')
    nat2_defenseur_central = read_with_competition('data/National 2 - Défenseur central.xlsx')
    nat2_lateral = read_with_competition('data/National 2 - Latéral.xlsx')
    nat2_milieu = read_with_competition('data/National 2 - Milieu.xlsx')
    nat2_milieu_offensif = read_with_competition('data/National 2 - Milieu offensif.xlsx')

    # Concaténation de tous les DataFrames dans un giga DataFrame
    df_individual = pd.concat([
        ligue1_ailier, ligue1_buteur, ligue1_defenseur_central, ligue1_lateral, ligue1_milieu, ligue1_milieu_offensif,
        ligue2_ailier, ligue2_buteur, ligue2_defenseur_central, ligue2_lateral, ligue2_milieu, ligue2_milieu_offensif,
        nat1_ailier, nat1_buteur, nat1_defenseur_central, nat1_lateral, nat1_milieu, nat1_milieu_offensif,
        nat2_ailier, nat2_buteur, nat2_defenseur_central, nat2_lateral, nat2_milieu, nat2_milieu_offensif
    ], ignore_index=True)

    df_collective.columns = df_collective.columns.str.strip()
    df_individual.columns = df_individual.columns.str.strip()

    return df_collective, df_individual

def bordered_metric(container, label, value, color="#FFFFFF"):
    style = f"""
        <div style='
            border: 1px solid {color};
            border-radius: 6px;
            padding: 12px;
            background-color: #0e1117;
            width: 90px;
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
    if value <= 33:
        return 'red'
    elif value <= 66:
        return 'orange'
    else:
        return 'green'
    
def compute_weighted_stats_by_minutes(df_joueur):
    if df_joueur.empty:
        return pd.DataFrame()

    # Colonnes numériques à moyenner sauf la colonne des minutes
    colonnes_a_moyenner = [
        col for col in df_joueur.columns
        if df_joueur[col].dtype in ['float64', 'int64'] and col != 'Minutes jouées'
    ]

    total_minutes = df_joueur['Minutes jouées'].sum()
    resultat = {}

    for col in colonnes_a_moyenner:
        resultat[col] = (df_joueur[col] * df_joueur['Minutes jouées']).sum() / total_minutes

    # Ajouter les colonnes non numériques depuis la première ligne (identité du joueur, etc.)
    colonnes_non_numeriques = [
        col for col in df_joueur.columns
        if col not in colonnes_a_moyenner and col != 'Minutes jouées'
    ]

    for col in colonnes_non_numeriques:
        resultat[col] = df_joueur.iloc[0][col]

    # Ajouter les minutes totales
    resultat['Minutes jouées'] = total_minutes

    return pd.DataFrame([resultat])

def rank_columns(df):
    df_copy = df.copy()
    # Sélection des colonnes numériques sauf 'Minutes jouées'
    numeric_cols = df_copy.select_dtypes(include=['number']).columns
    numeric_cols = numeric_cols.drop(['Minutes jouées', 'Âge'], errors='ignore')

    # Calcul des rangs
    ranked_df = df_copy[numeric_cols].rank(pct=True, method='average') * 100
    ranked_df = ranked_df.fillna(0).astype(int)

    # Remplacement des colonnes dans le DataFrame original
    df_copy[numeric_cols] = ranked_df
    return df_copy

def create_plot_stats(indicateurs, as_cannes, adversaire, nom_adversaire):
    fig_width, fig_height = 6, 9
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), facecolor='#0e1117')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.set_facecolor('#0e1117')
    text_color = '#FFFFFF'

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
            ax.text(x_positions[1], y, "Cannes", fontsize=10, fontweight='bold', va='center', ha='center', color=text_color)
            ax.text(x_positions[2], y, nom_adversaire, fontsize=10, fontweight='bold', va='center', ha='center', color=text_color)

            ax.hlines(y - spacing / 2, 0.05, 0.95, colors='gray', linestyles='solid', linewidth=1)

        elif i - 1 < len(indicateurs):
            idx = i - 1
            label = indicateurs[idx]
            cannes_val = format_value(as_cannes[idx], label)
            adv_val = format_value(adversaire[idx], label)

            ax.text(x_positions[0], y, label, fontsize=10, va='center', color=text_color)
            ax.text(x_positions[1], y, cannes_val, fontsize=10, va='center', ha='center', color=text_color)
            ax.text(x_positions[2], y, adv_val, fontsize=10, va='center', ha='center', color=text_color)

            if i < len(indicateurs):
                ax.hlines(y - spacing / 2, 0.05, 0.95, colors='gray', linestyles='dotted', linewidth=1)

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
    df_scores = df_ranked[['Joueur + Information', 'Âge', 'Minutes jouées', 'Contrat expiration']].copy()

    # Récupération des KPI spécifiques au poste
    kpi_metrics = kpi_by_position[poste]
    kpi_coefficients = kpi_coefficients_by_position[poste]
    total_coeff = sum(kpi_coefficients.values())

    # Calcul des scores par KPI
    for kpi, metrics in kpi_metrics.items():
        df_scores[kpi] = df_ranked[list(metrics.keys())].mul(list(metrics.values()), axis=1).sum(axis=1).round(1)

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
        background_color="#FFFFFF",
        straight_line_color="#FFFFFF",
        straight_line_lw=1,
        last_circle_lw=2,
        last_circle_color="#FFFFFF",
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
        kwargs_slices=dict(edgecolor="#FFFFFF", zorder=2, linewidth=1),
        kwargs_params=dict(
            color="#FFFFFF", fontsize=11, va="center"
        ),
        kwargs_values=dict(
            color="#FFFFFF", fontsize=11, zorder=3,
            bbox=dict(
                edgecolor="#FFFFFF", facecolor="cornflowerblue",
                boxstyle="round,pad=0.2", lw=1
            )
        )
    )

    fig.set_facecolor('#0e1117')

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
    metrics_abbr = list(metrics_dict.keys())  # ex: "xG", "Buts hors pen."
    metrics_cols = [metrics_dict[m] for m in metrics_abbr]  # ex: "xG par 90", "Buts hors penalty par 90"

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
    radar.draw_circles(ax=axs['radar'], facecolor='#28252c', edgecolor='#39353f', lw=1.5)

    player_values_1 = df_ranked[df_ranked['Joueur + Information'] == joueur_1][metrics_cols].mean().values.flatten()
    player_values_2 = df_ranked[df_ranked['Joueur + Information'] == joueur_2][metrics_cols].mean().values.flatten()

    radar.draw_radar_compare(player_values_1, player_values_2, ax=axs['radar'],
                             kwargs_radar={'facecolor': '#1440AC', 'alpha': 0.6},
                             kwargs_compare={'facecolor': '#FF4B4B', 'alpha': 0.6})

    radar.draw_range_labels(ax=axs['radar'], fontsize=25, color='#FFFFFF', fontproperties=robotto_thin.prop)
    radar.draw_param_labels(ax=axs['radar'], fontsize=25, color='#FFFFFF', fontproperties=robotto_thin.prop)

    axs['title'].text(0.01, 0.60, f"{joueur_1.split(' - ')[0]}", fontsize=25, color='#1440AC',
                      fontproperties=robotto_bold.prop, ha='left', va='center')
    axs['title'].text(0.01, 0.20,
                      f"{df_ranked[df_ranked['Joueur + Information'] == joueur_1]['Équipe dans la période sélectionnée'].iloc[0]} | {df_ranked[df_ranked['Joueur + Information'] == joueur_1]['Minutes jouées'].iloc[0]} minutes jouées",
                      fontsize=20, fontproperties=robotto_thin.prop, ha='left', va='center', color='#FFFFFF')

    axs['title'].text(0.99, 0.60, f"{joueur_2.split(' - ')[0]}", fontsize=25,
                      fontproperties=robotto_bold.prop, ha='right', va='center', color='#FF4B4B')
    axs['title'].text(0.99, 0.20,
                      f"{df_ranked[df_ranked['Joueur + Information'] == joueur_2]['Équipe dans la période sélectionnée'].iloc[0]} | {df_ranked[df_ranked['Joueur + Information'] == joueur_2]['Minutes jouées'].iloc[0]} minutes jouées",
                      fontsize=20, fontproperties=robotto_thin.prop, ha='right', va='center', color='#FFFFFF')

    fig.set_facecolor('#0e1117')

    return fig

def plot_player_metrics(df, joueur, poste, x_metric, y_metric, description_1, description_2, description_3, description_4):
    joueur_infos = df[df['Joueur + Information'] == joueur]

    if len(joueur_infos) > 1:
        joueur_infos = compute_weighted_stats_by_minutes(joueur_infos)

    df_filtré = df[(df['Poste'] == poste) & (df['Minutes jouées'] >= 500) & (df[x_metric] != 0) & (df[y_metric] != 0)]
    df_filtré = df_filtré[df_filtré['Joueur + Information'] != joueur]
    df_filtré = pd.concat([df_filtré, joueur_infos], ignore_index=True)

    x_mean = df_filtré[x_metric].mean()
    y_mean = df_filtré[y_metric].mean()

    # Crée une colonne pour couleur (joueur sélectionné ou non)
    df_filtré["Catégorie"] = df_filtré["Joueur + Information"].apply(
        lambda x: "Joueur sélectionné" if x == joueur else "Autres joueurs"
    )

    fig = px.scatter(
        df_filtré,
        x=x_metric,
        y=y_metric,
        color="Catégorie",
        color_discrete_map={
            "Autres joueurs": "#FFFFFF",
            "Joueur sélectionné": "#FF4B4B"
        },
        hover_name="Joueur + Information",
        hover_data={
            "Catégorie": False,
            x_metric: False,
            y_metric: False
        },
        opacity=0.7
    )

    # Ajoute les lignes de moyenne
    fig.add_vline(x=x_mean, line=dict(color="rgba(255,255,255,0.5)", dash='dash'))
    fig.add_hline(y=y_mean, line=dict(color="rgba(255,255,255,0.5)", dash='dash'))

    # Ajoute les 4 textes descriptifs
    x_min, x_max = df_filtré[x_metric].min(), df_filtré[x_metric].max()
    y_min, y_max = df_filtré[y_metric].min(), df_filtré[y_metric].max()
    x_offset = (x_max - x_min) * 0.02
    y_offset = (y_max - y_min) * 0.02

    annotations = [
        dict(x=x_min + x_offset, y=y_max - y_offset, text=description_1, showarrow=False, font=dict(color="#FFFFFF", size=11), xanchor="left", yanchor="top"),
        dict(x=x_max - x_offset, y=y_max - y_offset, text=description_2, showarrow=False, font=dict(color="#FFFFFF", size=11), xanchor="right", yanchor="top"),
        dict(x=x_min + x_offset, y=y_min + y_offset, text=description_3, showarrow=False, font=dict(color="#FFFFFF", size=11), xanchor="left", yanchor="bottom"),
        dict(x=x_max - x_offset, y=y_min + y_offset, text=description_4, showarrow=False, font=dict(color="#FFFFFF", size=11), xanchor="right", yanchor="bottom")
    ]

    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        annotations=annotations,
        showlegend=False,
        xaxis_title=x_metric,
        yaxis_title=y_metric,
        width=1000,
        height=600,
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(255,255,255,0.1)",
            gridwidth=0.5,
            griddash="dot",
            zeroline=False
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(255,255,255,0.1)",
            gridwidth=0.5,
            griddash="dot",
            zeroline=False
        )
    )

    return fig

def search_top_players(df, poste):
    df_filtré = df[(df['Poste'] == poste) & (df['Minutes jouées'] >= 500)]

    df_ranked = rank_columns(df_filtré)

    df_scores = df_ranked[['Joueur + Information', 'Âge', 'Minutes jouées', 'Contrat expiration']].copy()

    kpi_metrics = kpi_by_position[poste]
    kpi_coefficients = kpi_coefficients_by_position[poste]
    total_coeff = sum(kpi_coefficients.values())

    for kpi, metrics in kpi_metrics.items():
        df_scores[kpi] = df_ranked[list(metrics.keys())].mul(list(metrics.values()), axis=1).sum(axis=1).round(1)

    df_scores["Note globale"] = sum(
        df_scores[kpi] * coef for kpi, coef in kpi_coefficients.items()
    ) / total_coeff
    df_scores["Note globale"] = df_scores["Note globale"].round(1)

    return df_scores

def search_recommended_players(df, poste, thresholds):
    df_filtré = df[(df['Poste'] == poste) & (df['Minutes jouées'] >= 500)]

    df_ranked = rank_columns(df_filtré)

    df_scores = df_ranked[['Joueur + Information', 'Âge', 'Minutes jouées', 'Contrat expiration'] + list(thresholds.keys())].copy()

    for métrique, seuil in thresholds.items():
        df_scores = df_scores[df_scores[métrique] >= seuil]

    return df_scores

def streamlit_application(df_collective, df_individual):
    page = st.sidebar.selectbox("Sélectionnez une page", ["Accueil", "Classement", "Vidéo des buts", "Analyse collective", "Analyse individuelle", "Analyse comparative", "Scouting"])

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
            st.warning("La journée de fin doit être supérieure ou égale à la journée de début.")

        else:
            url = f"https://www.foot-national.com/data/2024-2025-classement-national2-groupe-a-type-{unicodedata.normalize('NFKD', type_classement).encode('ASCII', 'ignore').decode('utf-8').lower()}-journees-{journée_début}-{journée_fin}.html"

            response = requests.get(url)
            response.encoding = "ISO-8859-1"

            tables = pd.read_html(response.text)

            classement = tables[0]

            classement = classement.iloc[:, :-1]

            classement.columns = [col.replace('\xa0', ' ').strip() for col in classement.columns]

            st.dataframe(classement, use_container_width=True, hide_index=True)

    elif page == "Vidéo des buts":
        st.header("Vidéo des buts")

        # Dictionnaire des journées et matchs
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
        if os.path.exists(f"data/{journée} - {match}.mp4"):
            st.video(f"data/{journée} - {match}.mp4")
        else:
            st.warning("Vidéo non disponible pour ce match : il est possible qu'il n'y ait pas eu de but (0-0) ou que la vidéo ne soit pas encore disponible.")

    elif page == "Analyse collective":
        st.header("Analyse collective")

        compétition = st.selectbox("Sélectionnez une compétition", df_collective["Compétition"].unique())

        df_filtré = df_collective[df_collective["Compétition"] == compétition]

        match = st.selectbox("Sélectionnez un match", df_filtré["Match"].unique())

        df_filtré = df_filtré[df_filtré["Match"] == match]

        as_cannes = df_filtré[df_filtré["Équipe"] == "Cannes"]
        adversaire = df_filtré[df_filtré["Équipe"] != "Cannes"]

        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Général", "Attaque", "Défense", "Passe", "Pressing"])

        indicateurs_general = [
            'Buts',
            'xG',
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

        indicateurs_passes = [
            'Rythme du match',
            'Passes',
            'Passes précises',
            'Passes avant précises',
            'Passes progressives précises',
            'Passes longues précises %',
            'Passes 3e tiers précises',
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

        with tab1:
            as_cannes_values = clean_values(as_cannes[indicateurs_general].values.flatten())
            adversaire_values = clean_values(adversaire[indicateurs_general].values.flatten())

            fig = create_plot_stats(indicateurs_general, as_cannes_values, adversaire_values, adversaire['Équipe'].iloc[0])
            st.pyplot(fig, use_container_width=True)

        with tab2:
            as_cannes_values = clean_values(as_cannes[indicateurs_attaques].values.flatten())
            adversaire_values = clean_values(adversaire[indicateurs_attaques].values.flatten())

            fig = create_plot_stats(indicateurs_attaques, as_cannes_values, adversaire_values, adversaire['Équipe'].iloc[0])
            st.pyplot(fig, use_container_width=True)

        with tab3:
            as_cannes_values = clean_values(as_cannes[indicateurs_defense].values.flatten())
            adversaire_values = clean_values(adversaire[indicateurs_defense].values.flatten())

            fig = create_plot_stats(indicateurs_defense, as_cannes_values, adversaire_values, adversaire['Équipe'].iloc[0])
            st.pyplot(fig, use_container_width=True)

        with tab4:
            as_cannes_values = clean_values(as_cannes[indicateurs_passes].values.flatten())
            adversaire_values = clean_values(adversaire[indicateurs_passes].values.flatten())

            fig = create_plot_stats(indicateurs_passes, as_cannes_values, adversaire_values, adversaire['Équipe'].iloc[0])
            st.pyplot(fig, use_container_width=True)

        with tab5:
            as_cannes_values = clean_values(as_cannes[indicateurs_pressing].values.flatten())
            adversaire_values = clean_values(adversaire[indicateurs_pressing].values.flatten())

            fig = create_plot_stats(indicateurs_pressing, as_cannes_values, adversaire_values, adversaire['Équipe'].iloc[0])
            st.pyplot(fig, use_container_width=True)

    elif page == "Analyse individuelle":
        st.header("Analyse individuelle")

        team = st.selectbox("Sélectionnez une équipe", df_individual['Équipe dans la période sélectionnée'].unique(), index=list(df_individual['Équipe dans la période sélectionnée'].unique()).index("Cannes"))
        df_filtré = df_individual[df_individual['Équipe dans la période sélectionnée'] == team]

        joueur = st.selectbox("Sélectionnez un joueur", df_filtré['Joueur + Information'].unique())

        poste = st.selectbox(
            "Sélectionnez la base de comparaison (poste) pour l'analyse",
            list(kpi_by_position.keys()),
            help="Vous pouvez sélectionner n'importe quel poste, même différent de celui du joueur, pour voir comment il se comporte selon d'autres critères."
        )
        
        if team == "Cannes":
            tab1, tab2, tab3, tab4 = st.tabs(["Radar", "Nuage de points", "KPI", "Match"])
        else:
            tab1, tab2, tab3 = st.tabs(["Radar", "Nuage de points", "KPI"])

        with tab1:
            fig = create_individual_radar(df_individual, joueur, poste)
            st.pyplot(fig, use_container_width=True)

        with tab2:
            metrics_label  = st.selectbox("Sélectionnez une base de comparaison", metrics_x_y.keys())

            x_metric, y_metric = metrics_x_y[metrics_label]["metrics"]
            description_1, description_2, description_3, description_4 = metrics_x_y[metrics_label]["descriptions"]

            fig = plot_player_metrics(df_individual, joueur, poste, x_metric, y_metric, description_1, description_2, description_3, description_4)
            st.plotly_chart(fig, use_container_width=True)

        with tab3:
            scores_df = calcul_scores_par_kpi(df_individual, joueur, poste)
            joueur_scores = scores_df[scores_df['Joueur + Information'] == joueur].iloc[0]
            kpis_poste = list(kpi_by_position[poste].keys())
            colonnes = st.columns(len(kpis_poste) + 1)

            for i, kpi in enumerate(kpis_poste):
                with colonnes[i]:
                    bordered_metric(colonnes[i], kpi, round(joueur_scores[kpi], 1))

            with colonnes[-1]:
                bordered_metric(colonnes[-1], "Note globale", round(joueur_scores["Note globale"], 1), color= "#FF4B4B")
    
    elif page == "Analyse comparative":
        st.header("Analyse comparative")

        col1, col2 = st.columns(2)

        with col1:
            team_1 = st.selectbox("Sélectionnez une équipe", df_individual['Équipe dans la période sélectionnée'].unique(), key='team 1', index=list(df_individual['Équipe dans la période sélectionnée'].unique()).index("Cannes"))
            df_filtré_1 = df_individual[df_individual['Équipe dans la période sélectionnée'] == team_1]

            joueur_1 = st.selectbox("Sélectionnez un joueur", df_filtré_1['Joueur + Information'].unique(), key='joueur 1')

        with col2:
            team_2 = st.selectbox("Sélectionnez une équipe", df_individual['Équipe dans la période sélectionnée'].unique(), key='team 2', index=list(df_individual['Équipe dans la période sélectionnée'].unique()).index("Cannes"))
            df_filtré_2 = df_individual[df_individual['Équipe dans la période sélectionnée'] == team_2]

            joueur_2 = st.selectbox("Sélectionnez un joueur", df_filtré_2['Joueur + Information'].unique(), key='joueur 2')

        poste = st.selectbox(
            "Sélectionnez la base de comparaison (poste) pour l'analyse",
            list(kpi_by_position.keys()),
            help="Vous pouvez sélectionner n'importe quel poste, même différent de celui du joueur, pour voir comment il se comporte selon d'autres critères."
        )

        if st.button("Comparer"):
            fig = create_comparison_radar(df_individual, joueur_1, joueur_2, poste)
            st.pyplot(fig, use_container_width=True)
            
    elif page == "Scouting":
        st.header("Scouting")

        poste = st.selectbox("Sélectionnez le poste qui vous intéresse", list(kpi_by_position.keys()))

        min_age, max_age = st.slider("Sélectionnez une tranche d'âge", min_value=int(df_individual['Âge'].min()), max_value=int(df_individual['Âge'].max()), value=(int(df_individual['Âge'].min()), int(df_individual['Âge'].max())), step=1)

        tab1, tab2 = st.tabs(["Classement", "Recommandation"])

        with tab1:
            nombre_joueur = st.number_input("Sélectionnez le nombre de joueurs que vous voulez voir apparaître", min_value=1, max_value=50, value=10)

            top_players = search_top_players(df_individual, poste)

            top_players = top_players[(top_players['Âge'] >= min_age) & (top_players['Âge'] <= max_age)]

            top_players = top_players.sort_values(by='Note globale', ascending=False).head(nombre_joueur)

            st.dataframe(top_players, use_container_width=True, hide_index=True)

        with tab2:
            colonnes_filtrées = [col for col in df_individual.columns if 'par 90' in col.lower() or '%' in col]
            
            métriques_selectionnées = st.multiselect("Sélectionnez des métriques", colonnes_filtrées)

            thresholds = {}
            for métrique in métriques_selectionnées:
                thresholds[métrique] = st.slider(f"Sélectionnez le top % pour la métrique : {métrique}", min_value=0, max_value=100, value=50, step=5, key=métrique)

            recommended_players = search_recommended_players(df_individual, poste, thresholds)

            recommended_players = recommended_players[(recommended_players['Âge'] >= min_age) & (recommended_players['Âge'] <= max_age)]

            recommended_players = recommended_players.sort_values(by=list(thresholds.keys()), ascending=[False] * len(list(thresholds.keys())))

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

    # Empêche l'app de se mettre en veille
    if "ping" in st.query_params:
        st.write("pong")
        st.stop()

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        with st.form("login_form"):
            password = st.text_input("Mot de passe", type="password")
            submitted = st.form_submit_button("Valider")

            if submitted:
                if password == st.secrets['password']['password']:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Mot de passe incorrect")

    if st.session_state.authenticated:
        df_collective, df_individual = collect_data()
        streamlit_application(df_collective, df_individual)