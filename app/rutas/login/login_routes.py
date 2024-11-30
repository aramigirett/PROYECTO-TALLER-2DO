
from flask import Flask, render_template, request, redirect, url_for, flash
from flask import Blueprint 

loginmod = Blueprint('login', __name__, template_folder='templates')

app = Flask(__name__)
app.secret_key = 'clave_secreta'

# Usuario y contraseña predefinidos
USUARIO_CORRECTO = "ARAMI GIRETT"
CONTRASENA_CORRECTA = "1"

@loginmod.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Validar usuario y contraseña
        if username == USUARIO_CORRECTO and password == CONTRASENA_CORRECTA:
            flash('Inicio de sesión exitoso.')
            return redirect(url_for('vista.html'))
        else:
            flash('Usuario o contraseña incorrectos.')
            return redirect(url_for('login'))

    return render_template('login-index.html')

@loginmod.route('/vista')
def vistaIndex():
    return render_template('vista-index.html')

# Registrar el Blueprint en la aplicación
app.register_blueprint(loginmod)

if __name__ == '__main__':
    app.run(debug=True)