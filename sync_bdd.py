import mysql.connector

# ====== CONNEXION ======
print("🔄 Synchronisation en cours...")

# Connexion locale
print("Connexion à la BDD locale…")
local = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="connect4",
    port=3306
)
cur_local = local.cursor(dictionary=True)
print("✅ Connexion locale OK")

# Connexion distante (Railway)
print("Connexion à la BDD distante (Railway)…")
remote = mysql.connector.connect(
    host="yamanote.proxy.rlwy.net",
    user="root",
    password="DxxCDswbxSGHZMTQCSvCyhuRDejjihjJ",
    database="railway",
    port=48344
)
cur_remote = remote.cursor()
print("✅ Connexion distante OK\n")

# ====== TABLE PARTIE ======
print("🔹 Synchronisation de la table 'partie'…")
cur_local.execute("SELECT * FROM partie")
parties = cur_local.fetchall()
print(f"{len(parties)} lignes trouvées dans 'partie'")

for i, row in enumerate(parties, 1):
    cur_remote.execute("""
        INSERT INTO partie (id, statut, confiance, nb_rows, nb_cols)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            statut=VALUES(statut),
            confiance=VALUES(confiance),
            nb_rows=VALUES(nb_rows),
            nb_cols=VALUES(nb_cols)
    """, (
        row["id"],
        row.get("statut", ""),         
        row.get("confiance", 0),
        row.get("nb_rows", 0),
        row.get("nb_cols", 0)
    ))
    if i % 100 == 0:
        print(f"{i} lignes synchronisées…")

remote.commit()
print("✅ Table 'partie' synchronisée\n")

# ====== TABLE COUP ======
print("🔹 Synchronisation de la table 'coup'…")
cur_local.execute("SELECT * FROM coup")
coups = cur_local.fetchall()
print(f"{len(coups)} lignes trouvées dans 'coup'")

for i, row in enumerate(coups, 1):
    cur_remote.execute("""
        INSERT INTO coup (id, partie_id, numero, colonne)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            colonne=VALUES(colonne)
    """, (
        row["id"],
        row["partie_id"],
        row["numero"],      # <-- ici c'est bien 'numero'
        row["colonne"]
    ))
    if i % 100 == 0:
        print(f"{i} lignes synchronisées…")

remote.commit()
print("✅ Table 'coup' synchronisée\n")

# ====== TABLE SITUATION ======
print("🔹 Synchronisation de la table 'situation'…")
cur_local.execute("SELECT * FROM situation")
situations = cur_local.fetchall()
print(f"{len(situations)} lignes trouvées dans 'situation'")

for i, row in enumerate(situations, 1):
    cur_remote.execute("""
        INSERT INTO situation (id, partie_id, coup_numero, plateau)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            plateau=VALUES(plateau)
    """, (
        row["id"],
        row["partie_id"],
        row["coup_numero"],  # <-- le nom correct
        row["plateau"]
    ))
    if i % 100 == 0:
        print(f"{i} lignes synchronisées…")

remote.commit()
print("✅ Table 'situation' synchronisée\n")

print("🎉 Synchronisation complète terminée !")