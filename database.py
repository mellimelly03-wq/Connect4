import mysql.connector
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # Sur Railway, dotenv n'est pas installé, les variables sont déjà là

def get_connection():
    return mysql.connector.connect(
        host=os.environ.get('MYSQLHOST', 'localhost'),
        user=os.environ.get('MYSQLUSER', 'root'),
        password=os.environ.get('MYSQLPASSWORD', ''),
        database=os.environ.get('MYSQLDATABASE', 'connect4'),
        port=int(os.environ.get('MYSQLPORT', 3306))
    )