import mysql.connector
import os

def get_connection():
    # En local (WAMP), on garde les valeurs par défaut
    # Sur Railway, les variables d'environnement sont injectées automatiquement
    return mysql.connector.connect(
        host=os.environ.get('MYSQLHOST', 'localhost'),
        user=os.environ.get('MYSQLUSER', 'root'),
        password=os.environ.get('MYSQLPASSWORD', ''),
        database=os.environ.get('MYSQLDATABASE', 'connect4'),
        port=int(os.environ.get('MYSQLPORT', 3306))
    )