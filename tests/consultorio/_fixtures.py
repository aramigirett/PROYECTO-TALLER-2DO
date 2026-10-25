"""Datos `ZZ` de prueba para los tests de Consultorio (consulta, ficha médica y los movimientos clínicos de las etapas siguientes).

Crea por SQL (como postgres) pacientes, médicos con su usuario (rol Medico), un funcionario con su usuario (rol Recepcion), consultorios y
citas en estado Confirmado colgadas de una agenda propia, SIN depender de datos que alguien edite a mano (ni de Oscar Gonzales ni de los
usuarios reales). `limpiar()` borra todo lo creado por ID, en el orden inverso, y la auditoría que generó.

    fx = Fixtures(cx)           # cx: conexión de tests._conexion_pruebas
    try: ...                    # usar fx.paciente(), fx.medico(), fx.cita(...) ...
    finally: fx.limpiar()
"""
import datetime
import itertools

from tests.facturacion._limpieza import borrar_auditoria

_contador = itertools.count(1)
HASH = 'scrypt:32768:8:1$zz$' + 'f' * 64   # no es una contraseña válida: estos usuarios solo se usan con sesión simulada


class Fixtures:
    def __init__(self, cx):
        self.cx, self.cu = cx, cx.cursor()
        self._borrar = []          # (tabla, columna_pk, id) en orden de creación
        self._auditoria = {}       # entidad -> {ids}
        self._n = next(_contador) * 1000 + int(datetime.datetime.now().strftime('%H%M%S')) % 1000
        self.id_ciudad = self._uno("SELECT id_ciudad FROM ciudades ORDER BY 1 LIMIT 1")
        self.id_especialidad = self._uno("SELECT id_especialidad FROM especialidades ORDER BY 1 LIMIT 1")
        self.id_cargo = self._uno("SELECT id_cargo FROM cargo ORDER BY 1 LIMIT 1")
        self.rol = {n: i for i, n in self._todos("SELECT id_rol, nombre_rol FROM roles")}
        self.estado_cita = {d: i for i, d in self._todos("SELECT id_estado_cita, descripcion FROM estado_cita")}
        self.id_dia = self._uno("SELECT id_dia FROM dias ORDER BY 1 LIMIT 1")
        self.id_turno = self._uno("SELECT id_turno FROM turnos ORDER BY 1 LIMIT 1")
        self._agenda = {}          # id_medico -> (id_agenda_cabecera, id_agenda_detalle)
        self._hora = {}

    # ---- utilidades ----
    def _uno(self, sql, p=()):
        self.cu.execute(sql, p)
        r = self.cu.fetchone()
        return r[0] if r else None

    def _todos(self, sql, p=()):
        self.cu.execute(sql, p)
        return self.cu.fetchall()

    def _insertar(self, tabla, pk, sql, p):
        self.cu.execute(sql + f" RETURNING {pk}", p)
        i = self.cu.fetchone()[0]
        self.cx.commit()
        self._borrar.append((tabla, pk, i))
        return i

    def _sufijo(self):
        return f'{self._n}{next(_contador)}'

    def auditoria_de(self, entidad, i):
        self._auditoria.setdefault(entidad, set()).add(i)

    # ---- personas y lugares ----
    def paciente(self, activo=True, nombre='ZZ PACIENTE'):
        s = self._sufijo()
        return self._insertar('paciente', 'id_paciente',
                              "INSERT INTO paciente(nombre, apellido, cedula_entidad, id_ciudad, activo) VALUES (%s,'PRUEBA',%s,%s,%s)",
                              (f'{nombre} {s[-4:]}', f'ZZ{s}', self.id_ciudad, activo))

    def medico(self, activo=True, con_usuario=True, nombre='ZZ MEDICO'):
        """Devuelve (id_medico, id_usuario|None). El usuario tiene rol Medico y está activo."""
        s = self._sufijo()
        id_medico = self._insertar('medico', 'id_medico',
                                   "INSERT INTO medico(nombre, apellido, cedula, id_especialidad, id_ciudad, activo) VALUES (%s,'PRUEBA',%s,%s,%s,%s)",
                                   (f'{nombre} {s[-4:]}', f'ZZM{s}', self.id_especialidad, self.id_ciudad, activo))
        id_usuario = None
        if con_usuario:
            id_usuario = self._insertar('usuarios', 'id_usuario',
                                        "INSERT INTO usuarios(password_hash, id_rol, id_medico, activo) VALUES (%s,%s,%s,true)",
                                        (HASH, self.rol['Medico'], id_medico))
        return id_medico, id_usuario

    def recepcion(self):
        """Devuelve (id_funcionario, id_usuario) de un funcionario ZZ con usuario de rol Recepcion."""
        s = self._sufijo()
        id_f = self._insertar('funcionario', 'id_funcionario',
                              "INSERT INTO funcionario(nombre, apellido, cedula, id_cargo, activo) VALUES (%s,'PRUEBA',%s,%s,true)",
                              (f'ZZ RECEPCION {s[-4:]}', f'ZZF{s}', self.id_cargo))
        id_u = self._insertar('usuarios', 'id_usuario',
                              "INSERT INTO usuarios(password_hash, id_rol, id_funcionario, activo) VALUES (%s,%s,%s,true)",
                              (HASH, self.rol['Recepcion'], id_f))
        return id_f, id_u

    def consultorio(self, activo=True):
        s = self._sufijo()
        return self._insertar('consultorio', 'codigo',
                              "INSERT INTO consultorio(nombre_consultorio, direccion, correo, activo) VALUES (%s,'ZZ DIRECCION',%s,%s)",
                              (f'ZZ CONSULTORIO {s[-4:]}', f'zz{s}@test.invalid', activo))

    def tipo_diagnostico(self, activo=True):
        """Un tipo de diagnóstico ZZ (referencial). Devuelve su id."""
        s = self._sufijo()
        return self._insertar('tipo_diagnostico', 'id_tipo_diagnostico',
                              "INSERT INTO tipo_diagnostico(descripcion_diagnostico, tipo_diagnostico, activo) VALUES (%s,'ZZ',%s)",
                              (f'ZZ TIPO DX {s[-6:]}', activo))

    def sintoma(self, activo=True):
        """Un síntoma ZZ (referencial). Devuelve su id."""
        s = self._sufijo()
        return self._insertar('sintoma', 'id_sintoma', "INSERT INTO sintoma(descripcion_sintoma, activo) VALUES (%s,%s)", (f'ZZ SINTOMA {s[-6:]}', activo))

    def tipo_tratamiento(self, activo=True):
        """Un tipo de tratamiento ZZ (referencial). Devuelve su id."""
        s = self._sufijo()
        return self._insertar('tipos_tratamiento', 'id_tipo_tratamiento',
                              "INSERT INTO tipos_tratamiento(descripcion, precio, iva, activo) VALUES (%s,1000,10,%s)", (f'ZZ TIPO TRAT {s[-6:]}', activo))

    def tipo_procedimiento(self, activo=True):
        """Un tipo de procedimiento médico ZZ (referencial). Devuelve su id."""
        s = self._sufijo()
        return self._insertar('tipo_procedimiento_medico', 'id_tipo_procedimiento',
                              "INSERT INTO tipo_procedimiento_medico(descripcion, activo) VALUES (%s,%s)", (f'ZZ PROCEDIMIENTO {s[-6:]}', activo))

    def insumo(self, activo=True):
        """Un tipo de insumo ZZ (referencial). Devuelve su id."""
        s = self._sufijo()
        return self._insertar('insumos', 'id_insumo', "INSERT INTO insumos(descripcion, activo) VALUES (%s,%s)", (f'ZZ INSUMO {s[-6:]}', activo))

    def medicamento(self, activo=True):
        """Un medicamento ZZ (referencial). Devuelve su id."""
        s = self._sufijo()
        return self._insertar('medicamentos', 'id_medicamento', "INSERT INTO medicamentos(nombre_comercial, activo) VALUES (%s,%s)", (f'ZZ MEDICAMENTO {s[-6:]}', activo))

    def tipo_estudio(self, activo=True):
        """Un tipo de estudio ZZ (referencial). Devuelve su id."""
        s = self._sufijo()
        return self._insertar('tipo_estudio', 'id_tipo_estudio', "INSERT INTO tipo_estudio(descripcion, activo) VALUES (%s,%s)", (f'ZZ ESTUDIO {s[-6:]}', activo))

    def tipo_analisis(self, activo=True):
        """Un tipo de análisis ZZ (referencial). Devuelve su id."""
        s = self._sufijo()
        return self._insertar('tipo_analisis', 'id_tipo_analisis', "INSERT INTO tipo_analisis(descripcion, activo) VALUES (%s,%s)", (f'ZZ ANALISIS {s[-6:]}', activo))

    def estado_dental(self, aplica_a='SUPERFICIE', activo=True):
        """Un estado dental ZZ. Devuelve su id."""
        s = self._sufijo()
        return self._insertar('estado_dental', 'id_estado_dental',
                              "INSERT INTO estado_dental(descripcion, color, simbolo, activo, aplica_a) VALUES (%s,'#123456','Z',%s,%s)",
                              (f'ZZ ESTADO {s[-6:]}', activo, aplica_a))

    def desactivar(self, tabla, pk, i):
        self.cu.execute(f"UPDATE {tabla} SET activo = false WHERE {pk} = %s", (i,))
        self.cx.commit()

    # ---- citas ----
    def _agenda_de(self, id_medico, id_consultorio, id_funcionario):
        if (id_medico, id_consultorio) not in self._agenda:
            fecha = datetime.date.today() + datetime.timedelta(days=30 + len(self._agenda))
            dispo = self._insertar('disponibilidad_horaria', 'id_disponibilidad',
                                   "INSERT INTO disponibilidad_horaria(id_medico, id_dia, id_turno, dispo_hora_inicio, dispo_hora_fin, dispo_cupos, dispo_fecha) "
                                   "VALUES (%s,%s,%s,'08:00','18:00',50,%s)", (id_medico, self.id_dia, self.id_turno, fecha))
            cab = self._insertar('agenda_cabecera', 'id_agenda_cabecera',
                                 "INSERT INTO agenda_cabecera(id_medico, id_especialidad, fecha_agenda, estado, id_funcionario, observaciones, id_consultorio) "
                                 "VALUES (%s,%s,%s,'Activo',%s,'ZZ',%s)", (id_medico, self.id_especialidad, fecha, id_funcionario, id_consultorio))
            det = self._insertar('agenda_detalle', 'id_agenda_detalle',
                                 "INSERT INTO agenda_detalle(id_agenda_cabecera, id_disponibilidad_horaria, id_dia, id_turno, hora_inicio, hora_fin, "
                                 "cupos_disponibles, cupos_maximos) VALUES (%s,%s,%s,%s,'08:00','18:00',50,50)",
                                 (cab, dispo, self.id_dia, self.id_turno))
            self._agenda[(id_medico, id_consultorio)] = (cab, det, fecha)
        return self._agenda[(id_medico, id_consultorio)]

    def cita(self, id_medico, id_paciente, id_consultorio, id_funcionario, estado='Confirmado'):
        """Una cita (cita_detalle) del médico en su agenda ZZ. Devuelve id_cita_detalle."""
        cab_agenda, det_agenda, fecha = self._agenda_de(id_medico, id_consultorio, id_funcionario)
        n = self._hora.get(id_medico, 0)
        self._hora[id_medico] = n + 1
        hora = datetime.time(8 + (n // 2) % 10, 30 * (n % 2))
        cab = self._insertar('cita_cabecera', 'id_cita_cabecera',
                             "INSERT INTO cita_cabecera(id_paciente, id_agenda_cabecera, observaciones, estado, id_funcionario) VALUES (%s,%s,'ZZ','Activo',%s)",
                             (id_paciente, cab_agenda, id_funcionario))
        i = self._insertar('cita_detalle', 'id_cita_detalle',
                           "INSERT INTO cita_detalle(id_cita_cabecera, id_agenda_detalle, fecha_cita, hora_cita, motivo_consulta, id_estado_cita) "
                           "VALUES (%s,%s,%s,%s,'ZZ',%s)", (cab, det_agenda, fecha, hora, self.estado_cita[estado]))
        if estado in ('Reservado', 'Confirmado', 'Realizado'):   # igual que Agendamiento: la cita vigente ocupa un cupo
            self.cu.execute("UPDATE agenda_detalle SET cupos_disponibles = cupos_disponibles - 1 WHERE id_agenda_detalle = %s", (det_agenda,))
            self.cx.commit()
        return i

    def estado_de_cita(self, id_cita):
        return self._uno("SELECT ec.descripcion FROM cita_detalle cd JOIN estado_cita ec USING (id_estado_cita) WHERE cd.id_cita_detalle = %s", (id_cita,))

    # ---- lo que cuelga de una consulta ----
    def registrar_consulta(self, id_cita, id_funcionario, estado='programada'):
        """Crea la consulta por SQL (sin pasar por la API) y pasa la cita a Realizado. Devuelve id_consulta_cab."""
        self.cu.execute("""SELECT cc.id_paciente, ac.id_medico, ac.id_consultorio, cd.fecha_cita, cd.hora_cita
                           FROM cita_detalle cd JOIN cita_cabecera cc USING (id_cita_cabecera)
                           JOIN agenda_cabecera ac ON ac.id_agenda_cabecera = cc.id_agenda_cabecera WHERE cd.id_cita_detalle = %s""", (id_cita,))
        pac, med, cons, fecha, hora = self.cu.fetchone()
        i = self._insertar('consultas_cab', 'id_consulta_cab',
                           "INSERT INTO consultas_cab(id_cita, id_paciente, id_medico, id_consultorio, id_funcionario, fecha_cita, hora_cita, estado) "
                           "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (id_cita, pac, med, cons, id_funcionario, fecha, hora, estado))
        self.cu.execute("UPDATE cita_detalle SET id_estado_cita = %s WHERE id_cita_detalle = %s", (self.estado_cita['Realizado'], id_cita))
        self.cx.commit()
        self.auditoria_de('consultas_cab', i)
        return i

    def dato_clinico(self, tipo, id_consulta):
        """Inserta un registro VIGENTE de ese tipo colgado de la consulta. Devuelve (tabla, pk, id)."""
        self.cu.execute("SELECT id_paciente, id_medico FROM consultas_cab WHERE id_consulta_cab = %s", (id_consulta,))
        pac, med = self.cu.fetchone()
        s = self._sufijo()
        tipo_dx = self._uno("SELECT id_tipo_diagnostico FROM tipo_diagnostico WHERE activo ORDER BY 1 LIMIT 1")
        tipo_trat = self._uno("SELECT id_tipo_tratamiento FROM tipos_tratamiento WHERE activo ORDER BY 1 LIMIT 1")
        tipo_est = self._uno("SELECT id_tipo_estudio FROM tipo_estudio WHERE activo ORDER BY 1 LIMIT 1")
        tipo_ana = self._uno("SELECT id_tipo_analisis FROM tipo_analisis WHERE activo ORDER BY 1 LIMIT 1")
        med_receta = self.medicamento() if tipo == 'receta' else None
        modelos = {
            'ficha': ('ficha_medica_consulta', 'id_ficha_medica',
                      "INSERT INTO ficha_medica_consulta(id_consulta_cab, temperatura) VALUES (%s, 36.5)", (id_consulta,)),
            # un diagnóstico vigente exige al menos un síntoma (trigger diferido): se inserta todo antes de confirmar
            'diagnostico': ('diagnosticos', 'id_diagnostico',
                            "WITH dx AS (INSERT INTO diagnosticos(codigo, id_consulta_cab, id_paciente, id_medico, id_tipo_diagnostico, descripcion_diagnostico, fecha_diagnostico) "
                            "VALUES (%s,%s,%s,%s,%s,'ZZ',CURRENT_DATE) RETURNING id_diagnostico), "
                            "sx AS (INSERT INTO diagnostico_sintoma(id_diagnostico, id_sintoma) SELECT id_diagnostico, %s FROM dx) "
                            "SELECT id_diagnostico FROM dx", (f'ZD{s[-8:]}', id_consulta, pac, med, tipo_dx, self._uno("SELECT id_sintoma FROM sintoma WHERE activo ORDER BY 1 LIMIT 1"))),
            'odontograma': ('odontograma', 'id_odontograma',
                            "INSERT INTO odontograma(id_paciente, id_medico, id_consulta_cab, fecha_registro) VALUES (%s,%s,%s,NOW())", (pac, med, id_consulta)),
            'tratamiento': ('tratamientos', 'id_tratamiento',
                            "INSERT INTO tratamientos(codigo, id_consulta_cab, id_paciente, id_medico, id_tipo_tratamiento, descripcion_tratamiento, fecha_tratamiento, estado) "
                            "VALUES (%s,%s,%s,%s,%s,'ZZ',CURRENT_DATE,'pendiente')", (f'ZT{s[-8:]}', id_consulta, pac, med, tipo_trat)),
            # una receta vigente exige al menos un medicamento (trigger diferido): se inserta todo antes de confirmar
            'receta': ('recetas', 'id_receta',
                       "WITH rc AS (INSERT INTO recetas(id_consulta_cab, indicaciones_generales, fecha_receta) VALUES (%s,'ZZ',CURRENT_DATE) RETURNING id_receta), "
                       "rm AS (INSERT INTO receta_medicamento(id_receta, id_medicamento, dosis, frecuencia, duracion) SELECT id_receta, %s, 'ZZ', 'ZZ', 'ZZ' FROM rc) "
                       "SELECT id_receta FROM rc", (id_consulta, med_receta)),
            'orden_estudio': ('orden_estudios', 'id_orden_estudio',
                              "INSERT INTO orden_estudios(id_consulta_cab, id_tipo_estudio, motivo_orden, fecha_orden, estado) VALUES (%s,%s,'ZZ',CURRENT_DATE,'pendiente')",
                              (id_consulta, tipo_est)),
            'orden_analisis': ('orden_analisis', 'id_orden_analisis',
                               "INSERT INTO orden_analisis(id_consulta_cab, id_tipo_analisis, motivo_orden, fecha_orden, estado) VALUES (%s,%s,'ZZ',CURRENT_DATE,'pendiente')",
                               (id_consulta, tipo_ana)),
            'justificativo': ('justificativo_medico', 'id_justificativo',
                              "INSERT INTO justificativo_medico(id_consulta_cab, dias_reposo, fecha_justificativo, estado) VALUES (%s,1,CURRENT_DATE,'activo')", (id_consulta,)),
        }
        tabla, pk, sql, p = modelos[tipo]
        if tipo in ('diagnostico', 'receta'):   # la consulta WITH ya devuelve el id: _insertar le agregaría RETURNING
            self.cu.execute(sql, p)
            i = self.cu.fetchone()[0]
            self.cx.commit()
            self._borrar.append((tabla, pk, i))
            return tabla, pk, i
        return tabla, pk, self._insertar(tabla, pk, sql, p)

    def dejar_sin_vigencia(self, tabla, pk, i):
        """Hace que el registro deje de estar vigente (baja lógica según la tabla)."""
        if tabla in ('tratamientos', 'orden_estudios', 'orden_analisis'):
            self.cu.execute(f"UPDATE {tabla} SET estado = 'cancelado' WHERE {pk} = %s", (i,))
        elif tabla == 'justificativo_medico':
            self.cu.execute(f"UPDATE {tabla} SET estado = 'anulado' WHERE {pk} = %s", (i,))
        elif tabla == 'odontograma':
            self.cu.execute(f"UPDATE {tabla} SET activo = false WHERE {pk} = %s", (i,))
        else:
            self.cu.execute(f"UPDATE {tabla} SET activo = false WHERE {pk} = %s", (i,))
        self.cx.commit()

    # ---- limpieza ----
    def limpiar(self):
        self.cx.rollback()
        # los usuarios ZZ aparecen en la auditoría que generaron: se borra antes (solo en esta conexión se salta el trigger de inmutabilidad)
        usuarios = [i for t, _, i in self._borrar if t == 'usuarios']
        if usuarios:
            self.cu.execute("SET session_replication_role = replica")
            self.cu.execute("DELETE FROM auditoria_cambios WHERE id_usuario = ANY(%s)", (usuarios,))
            self.cu.execute("RESET session_replication_role")
        for tabla, pk, i in reversed(self._borrar):
            if tabla == 'consultas_cab':
                for hija, col in (('ficha_medica_consulta', 'id_consulta_cab'), ('odontograma', 'id_consulta_cab'),
                                  ('recetas', 'id_consulta_cab'), ('orden_estudios', 'id_consulta_cab'), ('orden_analisis', 'id_consulta_cab'),
                                  ('justificativo_medico', 'id_consulta_cab'), ('tratamientos', 'id_consulta_cab'), ('diagnosticos', 'id_consulta_cab')):
                    if col is None:
                        continue
                    if hija == 'odontograma':
                        self.cu.execute("DELETE FROM odontograma_detalle WHERE id_odontograma IN (SELECT id_odontograma FROM odontograma WHERE id_consulta_cab = %s)", (i,))
                    if hija == 'diagnosticos':
                        self.cu.execute("DELETE FROM diagnostico_sintoma WHERE id_diagnostico IN (SELECT id_diagnostico FROM diagnosticos WHERE id_consulta_cab = %s)", (i,))
                    if hija == 'tratamientos':
                        sub = "SELECT id_sesion FROM sesiones_tratamiento WHERE id_consulta_cab = %s OR id_tratamiento IN (SELECT id_tratamiento FROM tratamientos WHERE id_consulta_cab = %s)"
                        self.cu.execute(f"DELETE FROM sesion_insumos WHERE id_sesion IN ({sub})", (i, i))
                        self.cu.execute(f"DELETE FROM sesion_procedimientos WHERE id_sesion IN ({sub})", (i, i))
                        self.cu.execute("DELETE FROM sesiones_tratamiento WHERE id_consulta_cab = %s OR id_tratamiento IN (SELECT id_tratamiento FROM tratamientos WHERE id_consulta_cab = %s)", (i, i))
                    if hija == 'recetas':
                        self.cu.execute("DELETE FROM receta_medicamento WHERE id_receta IN (SELECT id_receta FROM recetas WHERE id_consulta_cab = %s)", (i,))
                    self.cu.execute(f"DELETE FROM {hija} WHERE {col} = %s", (i,))
            if tabla == 'tipo_procedimiento_medico':
                self.cu.execute("DELETE FROM sesion_procedimientos WHERE id_tipo_procedimiento = %s", (i,))
            if tabla == 'insumos':
                self.cu.execute("DELETE FROM sesion_insumos WHERE id_insumo = %s", (i,))
            if tabla == 'recetas':
                self.cu.execute("DELETE FROM receta_medicamento WHERE id_receta = %s", (i,))
            if tabla == 'medicamentos':
                self.cu.execute("DELETE FROM receta_medicamento WHERE id_medicamento = %s", (i,))
            if tabla == 'tipo_estudio':
                self.cu.execute("DELETE FROM orden_estudios WHERE id_tipo_estudio = %s", (i,))
            if tabla == 'tipo_analisis':
                self.cu.execute("DELETE FROM orden_analisis WHERE id_tipo_analisis = %s", (i,))
            self.cu.execute(f"DELETE FROM {tabla} WHERE {pk} = %s", (i,))
        # consultas registradas por la API (no pasaron por registrar_consulta): se borran por las citas ZZ
        for entidad, ids in self._auditoria.items():
            borrar_auditoria(self.cu, entidad, ids)
        self.cx.commit()

    def borrar_consultas_de_citas(self, ids_cita):
        """Para las consultas creadas por la API sobre citas ZZ: las registra para su limpieza (con su auditoría)."""
        self.cx.rollback()   # por si la prueba cortó a mitad de una transacción
        for (i,) in self._todos("SELECT id_consulta_cab FROM consultas_cab WHERE id_cita = ANY(%s)", (list(ids_cita),)):
            if ('consultas_cab', 'id_consulta_cab', i) not in self._borrar:
                self._borrar.append(('consultas_cab', 'id_consulta_cab', i))
            self.auditoria_de('consultas_cab', i)
