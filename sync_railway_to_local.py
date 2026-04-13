import mysql.connector

print("🔄 Synchronisation Railway → Local en cours...")

# ====== CONNEXION ======
print("Connexion à la BDD distante (Railway)…")
remote = mysql.connector.connect(
    host="yamanote.proxy.rlwy.net",        # ton MYSQLHOST Railway
    user="root",
    password="DxxCDswbxSGHZMTQCSvCyhuRDejjihjJ",    # ton MYSQLPASSWORD Railway
    database="railway",
    port=48344         # ton MYSQLPORT Railway
)
cur_remote = remote.cursor(dictionary=True)
print("✅ Connexion Railway OK")

print("Connexion à la BDD locale…")
local = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="connect4",
    port=3306
)
cur_local = local.cursor(dictionary=True)
print("✅ Connexion locale OK\n")

# ====== FONCTION DE SYNCHRO ======
def sync_table(table_name, columns, key_column):
    print(f"🔹 Synchronisation de la table '{table_name}'…")

    # Récupérer toutes les lignes DISTANTES (Railway)
    cur_remote.execute(f"SELECT * FROM {table_name}")
    remote_rows = cur_remote.fetchall()
    print(f"   {len(remote_rows)} lignes trouvées dans '{table_name}' (Railway)")

    # Récupérer tous les IDs LOCAUX
    cur_local.execute(f"SELECT {key_column} FROM {table_name}")
    local_ids = set(row[key_column] for row in cur_local.fetchall())

    count = 0
    for row in remote_rows:
        if row[key_column] not in local_ids:
            placeholders = ", ".join(["%s"] * len(columns))
            col_names = ", ".join(columns)
            updates = ", ".join([f"{col}=VALUES({col})" for col in columns if col != key_column])
            sql = f"""
                INSERT INTO {table_name} ({col_names})
                VALUES ({placeholders})
                ON DUPLICATE KEY UPDATE {updates}
            """
            values = [row.get(col, 0 if 'nb_' in col else '') for col in columns]
            cur_local.execute(sql, values)   # ← on insert dans LOCAL
            count += 1
            if count % 100 == 0:
                print(f"   {count} nouvelles lignes synchronisées…")

    local.commit()   # ← on commit sur LOCAL
    print(f"✅ Table '{table_name}' synchronisée ({count} nouvelles lignes)\n")

# ====== TABLES ======
sync_table("partie",   ["id", "statut", "confiance", "nb_rows", "nb_cols", "mode", "ai_type", "starting_color", "hash_partie", "source"], "id")
sync_table("coup",     ["id", "partie_id", "numero", "colonne", "couleur"], "id")
sync_table("situation",["id", "partie_id", "coup_numero", "plateau", "hash_situation"], "id")

print("🎉 Synchronisation Railway → Local terminée !")