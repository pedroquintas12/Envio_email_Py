from threading import Thread
from app import create_app

app = create_app()

# Inicia o Flask e o agendamento
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, threaded=True)