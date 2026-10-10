import time

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from app.dao.modulo_seguridad.UsuarioDao import UsuarioDao, BLOQUEO_MINUTOS, MAX_INTENTOS_FALLIDOS
from app.dao.modulo_seguridad.TokenDao import (
    TokenDao, RECUPERACION_MINUTOS, RECUPERACION_COOLDOWN_SEGUNDOS
)
from app.dao.modulo_seguridad.AuditoriaDao import AuditoriaDao
from app.Services.email_service import enviar_codigo_2fa, alertar_intento_fallido, alertar_bloqueo, enviar_codigo_recuperacion
from app.rutas.modulo_seguridad.password_policy import validar_password_compleja

seguridadmod = Blueprint('seguridad', __name__, template_folder='templates')

MENSAJE_CUENTA_BLOQUEADA = (
    f'Cuenta bloqueada por intentos fallidos. Contactá al administrador '
    f'o esperá {BLOQUEO_MINUTOS} minutos para volver a intentar.'
)


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

        if usuario and usuario['bloqueado']:
            if usuario['bloqueo_vencido']:
                # Desbloqueo por tiempo: pasaron BLOQUEO_MINUTOS desde el bloqueo
                usuariodao.liberar_bloqueo_vencido(usuario['id_usuario'])
                AuditoriaDao().registrar(usuario['id_usuario'], ci_ruc, 'DESBLOQUEADO', ip, 'DESBLOQUEO_TIEMPO')
            else:
                AuditoriaDao().registrar(usuario['id_usuario'], ci_ruc, 'CUENTA_BLOQUEADA', ip, 'LOGIN')
                flash(MENSAJE_CUENTA_BLOQUEADA, 'danger')
                return render_template('login.html')

        if usuario and usuariodao.validar_password(usuario['password_hash'], password):
            if not usuario['correo']:
                # El correo sale de la persona vinculada: si se lo borraron no hay a dónde enviar el 2FA
                flash('Tu cuenta no tiene un correo registrado. Contactá al administrador.', 'danger')
                return render_template('login.html')
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

            # Mensaje genérico mientras no se bloquea, para no revelar si el CI/RUC existe
            bloqueo = usuariodao.registrar_fallo(id_usuario) if usuario else None
            if bloqueo and bloqueo['bloqueado']:
                AuditoriaDao().registrar(id_usuario, ci_ruc, 'CUENTA_BLOQUEADA', ip, 'BLOQUEO')
                # Al usuario y a los administradores (menos él mismo, si lo es)
                alertar_bloqueo(usuario['correo'], usuariodao.getCorreosAdministradores(id_usuario),
                                ci_ruc, ip, BLOQUEO_MINUTOS)
                flash(MENSAJE_CUENTA_BLOQUEADA, 'danger')
            else:
                if bloqueo:
                    alertar_intento_fallido(usuario['correo'], ci_ruc, ip,
                                            bloqueo['intentos'], MAX_INTENTOS_FALLIDOS)
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

            UsuarioDao().reiniciar_intentos(usuario['id_usuario'])
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


# ---------------------------------------------------------------------------
# Recuperación de contraseña: /recuperar -> /recuperar/codigo -> /recuperar/nueva
# Mismo mensaje exista o no el CI/RUC (no se revela qué cuentas existen). La
# sesión solo guarda el CI/RUC tipeado hasta que el código se valida.
# ---------------------------------------------------------------------------
MENSAJE_RECUPERACION = (
    'Si el CI/RUC corresponde a una cuenta activa, enviamos un código de '
    'recuperación al correo registrado.'
)
MENSAJE_CODIGO_INVALIDO = 'Código inválido o vencido. Volvé a solicitar uno si hace falta.'
SESION_RECUPERACION_SEGUNDOS = RECUPERACION_MINUTOS * 60


@seguridadmod.route('/recuperar', methods=['GET', 'POST'])
def recuperar():
    if session.get('id_usuario'):
        return redirect(url_for('vista.vistaIndex'))

    if request.method == 'POST':
        ci_ruc = request.form.get('ci_ruc', '').strip()[:20]
        ip = request.remote_addr
        if not ci_ruc:
            flash('Ingresá tu CI o RUC.', 'danger')
            return render_template('recuperar.html', paso=1)

        usuario = UsuarioDao().get_by_ci_ruc(ci_ruc)
        AuditoriaDao().registrar(usuario['id_usuario'] if usuario else None,
                                 ci_ruc, 'SOLICITADO', ip, 'RECUPERACION')

        tokendao = TokenDao()
        if usuario and usuario['correo'] and not tokendao.hay_codigo_reciente(
                usuario['id_usuario'], 'RECUPERACION', RECUPERACION_COOLDOWN_SEGUNDOS):
            codigo = tokendao.generar_codigo_recuperacion(usuario['id_usuario'])
            if codigo:
                enviar_codigo_recuperacion(usuario['correo'], codigo, RECUPERACION_MINUTOS)

        session.clear()
        session['recuperar_ci'] = ci_ruc
        flash(MENSAJE_RECUPERACION, 'info')
        return redirect(url_for('seguridad.recuperar_codigo'))

    return render_template('recuperar.html', paso=1)


@seguridadmod.route('/recuperar/codigo', methods=['GET', 'POST'])
def recuperar_codigo():
    ci_ruc = session.get('recuperar_ci')
    if not ci_ruc:
        return redirect(url_for('seguridad.recuperar'))

    if request.method == 'POST':
        codigo = request.form.get('codigo', '').strip()
        ip = request.remote_addr
        usuario = UsuarioDao().get_by_ci_ruc(ci_ruc)

        resultado = 'INVALIDO'
        if usuario and codigo.isdigit() and len(codigo) == 6:
            resultado = TokenDao().validar_codigo_recuperacion(usuario['id_usuario'], codigo)

        if resultado == 'OK':
            AuditoriaDao().registrar(usuario['id_usuario'], ci_ruc, 'CODIGO_VERIFICADO', ip, 'RECUPERACION')
            session.pop('recuperar_ci', None)
            session['recuperar_ok'] = {'id_usuario': usuario['id_usuario'], 'ts': time.time()}
            return redirect(url_for('seguridad.recuperar_nueva'))

        AuditoriaDao().registrar(usuario['id_usuario'] if usuario else None,
                                 ci_ruc, 'CODIGO_INVALIDO', ip, 'RECUPERACION')
        flash(MENSAJE_CODIGO_INVALIDO, 'danger')

    return render_template('recuperar.html', paso=2)


@seguridadmod.route('/recuperar/nueva', methods=['GET', 'POST'])
def recuperar_nueva():
    ok = session.get('recuperar_ok')
    if not ok or time.time() - ok.get('ts', 0) > SESION_RECUPERACION_SEGUNDOS:
        session.pop('recuperar_ok', None)
        return redirect(url_for('seguridad.recuperar'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirmar = request.form.get('confirmar', '')
        ip = request.remote_addr

        error = validar_password_compleja(password)
        if not error and password != confirmar:
            error = 'Las contraseñas no coinciden.'
        if error:
            flash(error, 'danger')
            return render_template('recuperar.html', paso=3)

        usuariodao = UsuarioDao()
        id_usuario = ok['id_usuario']
        usuario = usuariodao.get_by_id(id_usuario)
        if not usuario or not usuariodao.restablecer_password(id_usuario, password):
            flash('No se pudo cambiar la contraseña. Intentá nuevamente.', 'danger')
            return render_template('recuperar.html', paso=3)

        TokenDao().invalidar_codigos_recuperacion(id_usuario)
        AuditoriaDao().registrar(id_usuario, usuario['ci_ruc'], 'EXITOSO', ip, 'RECUPERACION')
        session.clear()
        flash('Contraseña actualizada. Ya podés iniciar sesión.', 'success')
        return redirect(url_for('seguridad.login'))

    return render_template('recuperar.html', paso=3)
