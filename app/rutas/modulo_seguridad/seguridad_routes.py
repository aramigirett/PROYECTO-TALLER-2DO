from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from app.dao.modulo_seguridad.UsuarioDao import UsuarioDao
from app.dao.modulo_seguridad.TokenDao import TokenDao
from app.dao.modulo_seguridad.AuditoriaDao import AuditoriaDao
from app.Services.email_service import enviar_codigo_2fa

seguridadmod = Blueprint('seguridad', __name__, template_folder='templates')


@seguridadmod.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('id_usuario'):
        return redirect(url_for('vista.vistaIndex'))

    if request.method == 'POST':
        ci_ruc = request.form.get('ci_ruc', '').strip()
        password = request.form.get('password', '')
        ip = request.remote_addr

        usuariodao = UsuarioDao()
        usuario = usuariodao.get_by_ci_ruc(ci_ruc)

        if usuario and usuariodao.validar_password(usuario['password_hash'], password):
            codigo = TokenDao().generar_codigo(usuario['id_usuario'])
            if codigo and enviar_codigo_2fa(usuario['correo'], codigo):
                session.clear()
                session['pendiente_2fa'] = usuario['id_usuario']
                return redirect(url_for('seguridad.verificar_2fa'))
            else:
                flash('No se pudo enviar el código de verificación. Intente nuevamente.', 'danger')
        else:
            id_usuario = usuario['id_usuario'] if usuario else None
            AuditoriaDao().registrar(id_usuario, ci_ruc, 'CREDENCIALES_INVALIDAS', ip, 'LOGIN')
            flash('CI/RUC o contraseña incorrectos.', 'danger')

    return render_template('login.html')


@seguridadmod.route('/verificar-2fa', methods=['GET', 'POST'])
def verificar_2fa():
    id_usuario = session.get('pendiente_2fa')
    if not id_usuario:
        return redirect(url_for('seguridad.login'))

    if request.method == 'POST':
        codigo = request.form.get('codigo', '').strip()
        ip = request.remote_addr

        resultado = TokenDao().validar_codigo(id_usuario, codigo)
        usuario = UsuarioDao().get_by_id(id_usuario)
        ci_ruc = usuario['ci_ruc'] if usuario else ''

        if resultado == 'OK' and usuario:
            session.pop('pendiente_2fa', None)
            session['id_usuario'] = usuario['id_usuario']
            session['id_rol'] = usuario['id_rol']
            session['nombre_rol'] = usuario['nombre_rol']
            session['ci_ruc'] = usuario['ci_ruc']
            session['nombre_completo'] = usuario['nombre_completo']

            AuditoriaDao().registrar(usuario['id_usuario'], ci_ruc, 'EXITOSO', ip, 'LOGIN')
            flash('Inicio de sesión exitoso.', 'success')
            return redirect(url_for('vista.vistaIndex'))

        AuditoriaDao().registrar(id_usuario, ci_ruc, resultado, ip, 'VERIFICACION_2FA')
        if resultado == 'EXPIRADO':
            flash('El código expiró. Iniciá sesión nuevamente para recibir uno nuevo.', 'danger')
        else:
            flash('Código inválido. Intentá nuevamente.', 'danger')

    return render_template('verificar_2fa.html')


@seguridadmod.route('/logout')
def logout():
    id_usuario = session.get('id_usuario')
    ci_ruc = session.get('ci_ruc', '')

    if id_usuario:
        AuditoriaDao().registrar(id_usuario, ci_ruc, 'EXITOSO', request.remote_addr, 'LOGOUT')

    session.clear()
    flash('Sesión cerrada correctamente.', 'success')
    return redirect(url_for('seguridad.login'))
