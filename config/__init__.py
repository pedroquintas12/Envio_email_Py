import os
import sys

from dotenv import load_dotenv

if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(__file__)

load_dotenv(os.path.join(base_dir, 'config.env'))


class config:
    ENV = os.getenv('ENV')
    TEMPLATE_FOLDER = os.getenv("TEMPLATE_FOLDER")
    STATIC_FOLDER = os.getenv("STATIC_FOLDER")
    UrlApiLig = os.getenv("UrlApiLig")
    UrlLocal = os.getenv("urlLocal")
    SECRET_TOKEN = os.getenv("SECRET_TOKEN")
    UrlApiProd = os.getenv("UrlApiProd")
    UrlApiTest = os.getenv("UrlApiTest")