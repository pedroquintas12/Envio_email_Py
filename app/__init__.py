from app.schedule import run_scheduler
from threading import Thread
from app.routes import main_bp
from flask import Flask
from flask_cors import CORS
from config import config

def create_app():

    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}})

    app.register_blueprint(main_bp)

    Thread(target=run_scheduler).start()

    return app