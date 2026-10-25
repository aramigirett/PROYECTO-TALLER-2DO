"""Datos de prueba para probar Registrar Consulta con el médico de prueba Oscar Gonzales (CI 2222222).

Deja, para el próximo día hábil (lunes a viernes), una agenda del médico con su disponibilidad y TRES citas en estado "Confirmado"
sin consulta (09:00, 09:30 y 10:00) para el primer paciente activo. Todo lo que crea lleva la marca "[PRUEBA-OSCAR]" en sus
observaciones / motivo, para poder reconocerlo y limpiarlo.

    python scripts/datos_prueba_oscar.py                # SIMULA: muestra qué haría y deshace (no cambia nada)
    python scripts/datos_prueba_oscar.py --ejecutar     # crea lo que falte (idempotente: completa hasta 3 citas sin consulta)
    python scripts/datos_prueba_oscar.py --limpiar --ejecutar   # borra las citas de prueba SIN consulta y lo que quede vacío

Idempotente: correrlo de nuevo no duplica la agenda, el detalle ni la disponibilidad; solo repone las citas que ya se usaron
(las que tienen consulta no se tocan nunca). Usa la conexión de la aplicación (odontoclinic_app), no la de postgres.
"""
import argparse
import datetime
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.conexion.Conexion import Conexion

MARCA = '[PRUEBA-OSCAR]'
CEDULA_MEDICO = '2222222'
CITAS_OBJETIVO = 3
HORAS = [datetime.time(9, 0), datetime.time(9, 30), datetime.time(10, 0), datetime.time(10, 30), datetime.time(11, 0)]
DIA_POR_WEEKDAY = {0: 'LUNES', 1: 'MARTES', 2: 'MIERCOLES', 3: 'JUEVES', 4: 'VIERNES'}


def proximo_dia_habil(hoy):
    d = hoy
    while d.weekday() > 4:
        d += datetime.timedelta(days=1)
    return d


def uno(cur, sql, params=()):
    cur.execute(sql, params)
    r = cur.fetchone()
    return r[0] if r else None


def limpiar(cur):
    cur.execute("""SELECT cd.id_cita_detalle, cd.id_agenda_detalle, cd.id_cita_cabecera
                   FROM cita_detalle cd
                   WHERE cd.motivo_consulta LIKE %s
                     AND NOT EXISTS (SELECT 1 FROM consultas_cab c WHERE c.id_cita = cd.id_cita_detalle)""", (MARCA + '%',))
    citas = cur.fetchall()
    for id_cd, id_ad, id_cc in citas:
        cur.execute("DELETE FROM cita_detalle WHERE id_cita_detalle = %s", (id_cd,))
        cur.execute("""UPDATE agenda_detalle SET cupos_disponibles = LEAST(cupos_maximos, cupos_disponibles + 1),
                       estado_detalle = CASE WHEN estado_detalle = 'Agotado' THEN 'Disponible' ELSE estado_detalle END
                       WHERE id_agenda_detalle = %s""", (id_ad,))
    cur.execute("""DELETE FROM cita_cabecera cc WHERE cc.observaciones LIKE %s
                   AND NOT EXISTS (SELECT 1 FROM cita_detalle d WHERE d.id_cita_cabecera = cc.id_cita_cabecera)""", (MARCA + '%',))
    cur.execute("""DELETE FROM agenda_detalle ad USING agenda_cabecera ac
                   WHERE ad.id_agenda_cabecera = ac.id_agenda_cabecera AND ac.observaciones LIKE %s
                   AND NOT EXISTS (SELECT 1 FROM cita_detalle d WHERE d.id_agenda_detalle = ad.id_agenda_detalle)""", (MARCA + '%',))
    cur.execute("""DELETE FROM agenda_cabecera ac WHERE ac.observaciones LIKE %s
                   AND NOT EXISTS (SELECT 1 FROM agenda_detalle ad WHERE ad.id_agenda_cabecera = ac.id_agenda_cabecera)
                   AND NOT EXISTS (SELECT 1 FROM cita_cabecera cc WHERE cc.id_agenda_cabecera = ac.id_agenda_cabecera)""", (MARCA + '%',))
    print(f'Citas de prueba sin consulta borradas: {len(citas)} (las que ya tienen consulta no se tocan).')


def crear(cur):
    # ---- el médico y su usuario ----
    cur.execute("SELECT id_medico, nombre, apellido, id_especialidad, activo FROM medico WHERE cedula = %s", (CEDULA_MEDICO,))
    med = cur.fetchone()
    if not med:
        sys.exit(f'No existe un médico con CI {CEDULA_MEDICO}. Cargalo primero en Agendamiento > Médicos.')
    id_medico, nombre, apellido, id_especialidad, activo = med
    if not activo:
        sys.exit(f'El médico {nombre} {apellido} está inactivo.')
    cur.execute("""SELECT u.id_usuario, r.nombre_rol, u.activo FROM usuarios u JOIN roles r USING (id_rol) WHERE u.id_medico = %s""", (id_medico,))
    usr = cur.fetchone()
    print(f'Médico: {nombre} {apellido} (id {id_medico}, CI {CEDULA_MEDICO}); usuario: {usr if usr else "SIN USUARIO VINCULADO"}')

    # ---- datos de apoyo ----
    consultorio = uno(cur, "SELECT codigo FROM consultorio WHERE activo ORDER BY codigo LIMIT 1")
    funcionario = uno(cur, """SELECT f.id_funcionario FROM funcionario f JOIN usuarios u ON u.id_funcionario = f.id_funcionario
                              JOIN roles r ON r.id_rol = u.id_rol
                              WHERE f.activo AND u.activo AND r.nombre_rol = 'Recepcion' ORDER BY 1 LIMIT 1""") \
        or uno(cur, "SELECT id_funcionario FROM funcionario WHERE activo ORDER BY 1 LIMIT 1")
    paciente = uno(cur, "SELECT id_paciente FROM paciente WHERE activo ORDER BY 1 LIMIT 1")
    if not (consultorio and funcionario and paciente):
        sys.exit('Faltan datos base: un consultorio, un funcionario y un paciente activos.')
    estado_confirmado = uno(cur, "SELECT id_estado_cita FROM estado_cita WHERE descripcion = 'Confirmado'")
    fecha = proximo_dia_habil(datetime.date.today())
    id_dia = uno(cur, "SELECT id_dia FROM dias WHERE UPPER(descripcion) = %s", (DIA_POR_WEEKDAY[fecha.weekday()],))
    id_turno = uno(cur, "SELECT id_turno FROM turnos WHERE UPPER(descripcion) LIKE 'MA%%ANA' ORDER BY id_turno LIMIT 1")
    if not (id_dia and id_turno):
        sys.exit('No se encontró el día o el turno mañana en los referenciales.')
    print(f'Fecha de la agenda: {fecha} ({DIA_POR_WEEKDAY[fecha.weekday()]}); consultorio {consultorio}; funcionario {funcionario}; paciente {paciente}')

    # ---- disponibilidad horaria ----
    dispo = uno(cur, """SELECT id_disponibilidad FROM disponibilidad_horaria
                        WHERE id_medico = %s AND dispo_fecha = %s AND id_dia = %s AND id_turno = %s ORDER BY 1 LIMIT 1""",
                (id_medico, fecha, id_dia, id_turno))
    if dispo:
        print(f'Disponibilidad horaria existente: {dispo}')
    else:
        dispo = uno(cur, """INSERT INTO disponibilidad_horaria(id_medico, id_dia, id_turno, dispo_hora_inicio, dispo_hora_fin, dispo_cupos, dispo_fecha)
                            VALUES (%s,%s,%s,'08:00','12:00',5,%s) RETURNING id_disponibilidad""", (id_medico, id_dia, id_turno, fecha))
        print(f'Disponibilidad horaria creada: {dispo}')

    # ---- agenda (cabecera) ----
    agenda = uno(cur, "SELECT id_agenda_cabecera FROM agenda_cabecera WHERE id_medico = %s AND fecha_agenda = %s AND estado <> 'Inactivo'",
                 (id_medico, fecha))
    if agenda:
        print(f'Agenda existente de ese día: {agenda}')
    else:
        agenda = uno(cur, """INSERT INTO agenda_cabecera(id_medico, id_especialidad, fecha_agenda, estado, id_funcionario, observaciones, id_consultorio)
                             VALUES (%s,%s,%s,'Activo',%s,%s,%s) RETURNING id_agenda_cabecera""",
                     (id_medico, id_especialidad, fecha, funcionario, MARCA + ' agenda de prueba', consultorio))
        print(f'Agenda creada: {agenda}')

    # ---- agenda (detalle) ----
    detalle = uno(cur, """SELECT id_agenda_detalle FROM agenda_detalle
                          WHERE id_agenda_cabecera = %s AND id_disponibilidad_horaria = %s AND estado_detalle <> 'Cancelado'""", (agenda, dispo))
    if detalle:
        print(f'Detalle de agenda existente: {detalle}')
    else:
        detalle = uno(cur, """INSERT INTO agenda_detalle(id_agenda_cabecera, id_disponibilidad_horaria, id_dia, id_turno, hora_inicio, hora_fin,
                                                         cupos_disponibles, cupos_maximos, estado_detalle)
                              VALUES (%s,%s,%s,%s,'08:00','12:00',5,5,'Disponible') RETURNING id_agenda_detalle""",
                      (agenda, dispo, id_dia, id_turno))
        print(f'Detalle de agenda creado: {detalle}')

    # ---- citas confirmadas sin consulta ----
    cur.execute("""SELECT cd.hora_cita FROM cita_detalle cd
                   WHERE cd.motivo_consulta LIKE %s AND cd.id_agenda_detalle = %s""", (MARCA + '%', detalle))
    horas_usadas = {r[0] for r in cur.fetchall()}
    sin_consulta = uno(cur, """SELECT COUNT(*) FROM cita_detalle cd JOIN estado_cita ec ON ec.id_estado_cita = cd.id_estado_cita
                               WHERE cd.motivo_consulta LIKE %s AND cd.id_agenda_detalle = %s AND ec.descripcion = 'Confirmado'
                               AND NOT EXISTS (SELECT 1 FROM consultas_cab c WHERE c.id_cita = cd.id_cita_detalle AND c.activo)""",
                       (MARCA + '%', detalle))
    faltan = max(0, CITAS_OBJETIVO - sin_consulta)
    print(f'Citas de prueba Confirmado sin consulta: {sin_consulta}; se crean {faltan}.')
    cab = uno(cur, "SELECT id_cita_cabecera FROM cita_cabecera WHERE observaciones LIKE %s AND id_agenda_cabecera = %s AND estado = 'Activo' LIMIT 1",
              (MARCA + '%', agenda))
    for hora in [h for h in HORAS if h not in horas_usadas][:faltan]:
        cupos = uno(cur, "SELECT cupos_disponibles FROM agenda_detalle WHERE id_agenda_detalle = %s FOR UPDATE", (detalle,))
        if cupos < 1:
            print('Sin cupos en el detalle de agenda: no se crean más citas.')
            break
        if not cab:
            cab = uno(cur, """INSERT INTO cita_cabecera(id_paciente, id_agenda_cabecera, observaciones, estado, id_funcionario)
                              VALUES (%s,%s,%s,'Activo',%s) RETURNING id_cita_cabecera""", (paciente, agenda, MARCA + ' citas de prueba', funcionario))
        n = len(horas_usadas) + 1
        cita = uno(cur, """INSERT INTO cita_detalle(id_cita_cabecera, id_agenda_detalle, fecha_cita, hora_cita, motivo_consulta, id_estado_cita)
                           VALUES (%s,%s,%s,%s,%s,%s) RETURNING id_cita_detalle""",
                   (cab, detalle, fecha, hora, f'{MARCA} cita {n}', estado_confirmado))
        horas_usadas.add(hora)
        cur.execute("""UPDATE agenda_detalle SET cupos_disponibles = cupos_disponibles - 1,
                       estado_detalle = CASE WHEN cupos_disponibles - 1 = 0 THEN 'Agotado' ELSE estado_detalle END
                       WHERE id_agenda_detalle = %s""", (detalle,))
        print(f'  cita {cita}: {fecha} {hora}, Confirmado')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ejecutar', action='store_true', help='confirma los cambios (sin esto solo simula y deshace)')
    ap.add_argument('--limpiar', action='store_true', help='borra las citas de prueba sin consulta y lo que quede vacío')
    args = ap.parse_args()
    sys.stdout.reconfigure(errors='replace')

    con = Conexion().getConexion()
    cur = con.cursor()
    try:
        (limpiar if args.limpiar else crear)(cur)
        if args.ejecutar:
            con.commit()
            print('\nHECHO: cambios confirmados.')
        else:
            con.rollback()
            print('\nSIMULACIÓN: no se cambió nada. Agregá --ejecutar para confirmar.')
    except SystemExit:
        con.rollback()
        raise
    except Exception:
        con.rollback()
        raise
    finally:
        cur.close()
        con.close()


if __name__ == '__main__':
    main()
