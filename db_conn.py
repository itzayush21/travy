import mysql.connector
from mysql.connector import errorcode
import os
from dotenv import load_dotenv

# MySQL config (change if hosted)
load_dotenv()

config = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT")),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}

# SQL statements
TABLES = {}

TABLES['users'] = """
CREATE TABLE IF NOT EXISTS users (
    id INT PRIMARY KEY,
    email VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

TABLES['user_profiles'] = """
CREATE TABLE IF NOT EXISTS user_profiles (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    blood_group VARCHAR(5),
    health_conditions TEXT,
    allergies TEXT,
    food_preferences TEXT,
    travel_preferences TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

TABLES['emergency_contacts'] = """
CREATE TABLE IF NOT EXISTS emergency_contacts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    name VARCHAR(100),
    relation VARCHAR(50),
    phone VARCHAR(20),
    email VARCHAR(100),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

TABLES['language_preferences'] = """
CREATE TABLE IF NOT EXISTS language_preferences (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    preferred_language VARCHAR(30),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

def create_database(cursor):
    try:
        cursor.execute("CREATE DATABASE IF NOT EXISTS defaultdb")
        print("✅ Database 'travy' ensured.")
    except mysql.connector.Error as err:
        print(f"❌ Failed creating database: {err}")
        exit(1)

def connect_and_create_tables():
    try:
        # Step 1: Connect to MySQL
        cnx = mysql.connector.connect(**config)
        cursor = cnx.cursor()
        create_database(cursor)

        # Step 2: Reconnect using new DB
        cnx.database = 'travy'
        for name, ddl in TABLES.items():
            try:
                print(f"🛠️ Creating table `{name}`...", end='')
                cursor.execute(ddl)
                print(" done.")
            except mysql.connector.Error as err:
                if err.errno == errorcode.ER_TABLE_EXISTS_ERROR:
                    print(" already exists.")
                else:
                    print(f"❌ Error: {err.msg}")
        cursor.close()
        cnx.close()
        print("✅ All tables created.")
    except mysql.connector.Error as err:
        print(f"❌ Connection error: {err}")

if __name__ == '__main__':
    connect_and_create_tables()
