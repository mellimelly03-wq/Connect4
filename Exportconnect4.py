import mysql.connector
import csv
import os

# Configuration de la connexion
config = {
    "host": "yamanote.proxy.rlwy.net",
    "port": 48344,
    "user": "root",
    "password": "DxxCDswbxSGHZMTQCSvCyhuRDejjihjJ",
    "database": "railway"
}

# Nom du dossier de sortie (change prénom/nom)
PRENOM = "MelissaZina"
NOM    = "HADDOUCHEMESROUA"
DOSSIER = f"{PRENOM}.{NOM}.bdd"

os.makedirs(DOSSIER, exist_ok=True)

tables = ["coup", "partie", "situation"]

print("Connexion à la base de données...")
conn = mysql.connector.connect(**config)
cursor = conn.cursor()

for table in tables:
    print(f"Export de la table '{table}'...")
    cursor.execute(f"SELECT * FROM {table}")
    rows = cursor.fetchall()
    colonnes = [desc[0] for desc in cursor.description]

    fichier_csv = os.path.join(DOSSIER, f"{PRENOM}.{NOM}.bdd.{table}.csv")
    with open(fichier_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(colonnes)
        writer.writerows(rows)

    print(f"  -> {fichier_csv} ({len(rows)} lignes)")

cursor.close()
conn.close()

# Création du fichier .txt
fichier_txt = os.path.join(DOSSIER, f"{PRENOM}.{NOM}.bdd.txt")
with open(fichier_txt, "w", encoding="utf-8") as f:
    f.write(f"Base de données Connect4 - {PRENOM} {NOM}\n")
    f.write("="*40 + "\n\n")
    f.write("Tables exportées : coup, partie, situation\n\n")
    f.write("Détails du modèle :\n")
    f.write("- (complète ici avec les infos de ton modèle)\n")
    f.write("- Ex: colonnes numérotées de 0 à 6, lignes de 0 à 5\n")
    f.write("- Ex: valeurs 0=vide, 1=joueur1, 2=joueur2\n")

print(f"\nFichier texte créé : {fichier_txt}")
print(f"\nTout est dans le dossier '{DOSSIER}' !")
print("N'oublie pas de remplir le fichier .txt avec les détails de ton modèle.")