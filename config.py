import os
from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

class Config:
    DB_URI = (
    f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
    SSL_CA_PATH = os.path.join(os.path.dirname(__file__), "certs", "ca.pem")

    ENGINE_OPTIONS = {
        "connect_args": {
            "ssl_ca": SSL_CA_PATH
        },
        "echo": True  # Optional: logs queries
    }
