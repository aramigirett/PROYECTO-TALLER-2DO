import os

# run.py arranca en modo debug: se declara antes de importar la app para que esta lo sepa
# (permite arrancar sin SECRET_KEY solo en este modo; ver app/__init__.py).
os.environ.setdefault('FLASK_DEBUG', '1')

from app import app

if __name__== "__main__":
    app.run(debug=True)
