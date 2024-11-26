-- Crear tabla de estados para las citas
CREATE TABLE estado_citas (
    id_estado_cita SERIAL PRIMARY KEY,
    descripcion VARCHAR(60) UNIQUE NOT NULL
);

-- Crear tabla de días (si no la tienes ya definida)
CREATE TABLE dias (
    id_dia SERIAL PRIMARY KEY,
    descripcion VARCHAR(15) UNIQUE NOT NULL
);

-- Crear tabla de personas (base para médicos y pacientes)
CREATE TABLE personas (
    id_persona SERIAL PRIMARY KEY,
    nombres VARCHAR(70) NOT NULL,
    apellidos VARCHAR(70) NOT NULL,
    ci TEXT UNIQUE NOT NULL,
    telefono VARCHAR(20),
    correo VARCHAR(100),
    fechanac DATE,
    creacion_fecha DATE NOT NULL,
    creacion_hora TIME NOT NULL,
    creacion_usuario INTEGER NOT NULL,
    modificacion_fecha DATE,
    modificacion_hora TIME,
    modificacion_usuario INTEGER
);

-- Crear tabla de médicos
CREATE TABLE medicos (
    id_medico INTEGER PRIMARY KEY,
    id_persona INTEGER NOT NULL REFERENCES personas(id_persona) ON DELETE CASCADE,
    especialidad VARCHAR(100) NOT NULL
);

-- Crear tabla de pacientes
CREATE TABLE pacientes (
    id_paciente INTEGER PRIMARY KEY,
    id_persona INTEGER NOT NULL REFERENCES personas(id_persona) ON DELETE CASCADE,
    numero_historial VARCHAR(50) UNIQUE
);

-- Crear tabla de disponibilidad de médicos (hora de inicio y fin)
CREATE TABLE dias_horarios_medicos (
    id_dia_horario SERIAL PRIMARY KEY,
    id_medico INTEGER NOT NULL REFERENCES medicos(id_medico) ON DELETE CASCADE,
    id_dia INT NOT NULL REFERENCES dias(id_dia),
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    UNIQUE (id_medico, id_dia, hora_inicio, hora_fin)
);

-- Crear tabla de citas con hora de inicio y hora de fin
CREATE TABLE citas (
    id_cita SERIAL PRIMARY KEY,
    id_medico INTEGER NOT NULL REFERENCES medicos(id_medico) ON DELETE CASCADE,
    id_paciente INTEGER NOT NULL REFERENCES pacientes(id_paciente) ON DELETE CASCADE,
    fecha DATE NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    id_estado_cita INTEGER NOT NULL REFERENCES estado_citas(id_estado_cita),
    observaciones TEXT,
    UNIQUE (id_medico, fecha, hora_inicio, hora_fin)
);

-- Crear tabla de avisos para recordatorios
CREATE TABLE avisos (
    id_aviso SERIAL PRIMARY KEY,
    id_cita INTEGER NOT NULL REFERENCES citas(id_cita) ON DELETE CASCADE,
    mensaje TEXT NOT NULL,
    fecha_envio TIMESTAMP DEFAULT NOW()
);