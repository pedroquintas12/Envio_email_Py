import os
import sys

from dotenv import load_dotenv

if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(__file__)

load_dotenv(os.path.join(base_dir, '.env'))


class config:
    ENV = os.getenv('ENV')
    TEMPLATE_FOLDER = os.getenv("TEMPLATE_FOLDER")
    STATIC_FOLDER = os.getenv("STATIC_FOLDER")
    UrlApiLig = os.getenv("UrlApiLig")
    UrlLocal = os.getenv("urlLocal")
    SECRET_TOKEN = os.getenv("SECRET_TOKEN")
    UrlApiProd = os.getenv("UrlApiProd")
    UrlApiTest = os.getenv("UrlApiTest")
    TOKEN_APILIG = os.getenv("TOKEN_APILIG")
    USERNAME = os.getenv("username_api")
    PASSWORD = os.getenv("password_api")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_NAME = os.getenv("DB_NAME")
    DB_LIGCONTATO_HOST = os.getenv("DB_LIGCONTATO_HOST")
    DB_LIGCONTATO_PORT = int(os.getenv("DB_LIGCONTATO_PORT", 3306))
    DB_LIGCONTATO_USER = os.getenv("DB_LIGCONTATO_USER")
    DB_LIGCONTATO_PASS = os.getenv("DB_LIGCONTATO_PASS")
    DB_LIGCONTATO_NAME = os.getenv("DB_LIGCONTATO_NAME")