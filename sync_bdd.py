import mysql.connector

print("🔄 Synchronisation en cours...")

# ====== CONNEXION ======
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

print("Connexion à la BDD distante (Railway)…")
remote = mysql.connector.connect(
    host="yamanote.proxy.rlwy.net",
    user="root",
    password="tzAmyMicMRHrbNQGrhUnTOjqpYYGYnaf",
    database="railway",
    port=48344
)
cur_remote = remote.cursor(dictionary=True)
print("✅ Connexion distante OK\n")

# ====== FONCTION DE SYNCHRO ======
def sync_table(table_name, columns, key_column):
    print(f"🔹 Synchronisation de la table '{table_name}'…")
    
    # Récupérer toutes les lignes locales
    cur_local.execute(f"SELECT * FROM {table_name}")
    local_rows = cur_local.fetchall()
    print(f"{len(local_rows)} lignes trouvées dans '{table_name}' (local)")
    
    # Récupérer tous les IDs distants
    cur_remote.execute(f"SELECT {key_column} FROM {table_name}")
    remote_ids = set(row[key_column] for row in cur_remote.fetchall())
    
    count = 0
    for row in local_rows:
        # On insert seulement si l'ID n'existe pas encore
        if row[key_column] not in remote_ids:
            placeholders = ", ".join(["%s"] * len(columns))
            col_names = ", ".join(columns)
            updates = ", ".join([f"{col}=VALUES({col})" for col in columns if col != key_column])
            sql = f"""
                INSERT INTO {table_name} ({col_names})
                VALUES ({placeholders})
                ON DUPLICATE KEY UPDATE {updates}
            """
            values = [row.get(col, 0 if 'nb_' in col else '') for col in columns]
            cur_remote.execute(sql, values)
            count += 1
            if count % 100 == 0:
                print(f"{count} nouvelles lignes synchronisées…")
    
    remote.commit()
    print(f"✅ Table '{table_name}' synchronisée ({count} nouvelles lignes)\n")


# ====== TABLES ======
sync_table("partie", ["id", "statut", "confiance", "nb_rows", "nb_cols"], "id")
sync_table("coup", ["id", "partie_id", "numero", "colonne"], "id")
sync_table("situation", ["id", "partie_id", "coup_numero", "plateau", "hash_situation"], "id")

print("🎉 Synchronisation complète terminée !")