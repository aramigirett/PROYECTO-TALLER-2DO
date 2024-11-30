-- Crear tabla persona
CREATE TABLE persona (
    id_persona SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    cedula VARCHAR(15) UNIQUE,
    fecha_nacimiento DATE,
    telefono VARCHAR(15),
    direccion TEXT,
    genero CHAR(1) CHECK (genero IN ('M', 'F'))
);

-- Crear tabla paciente (extiende a persona)
CREATE TABLE paciente (
    id_paciente SERIAL PRIMARY KEY,
    id_persona INTEGER UNIQUE NOT NULL,
    FOREIGN KEY (id_persona) REFERENCES persona (id_persona)
);

-- Crear tabla medico (extiende a persona)
CREATE TABLE medico (
    id_medico SERIAL PRIMARY KEY,
    id_persona INTEGER UNIQUE NOT NULL,
    especialidad VARCHAR(100),
    correo VARCHAR(100),
    FOREIGN KEY (id_persona) REFERENCES persona (id_persona)
);

-- Crear tabla dias
CREATE TABLE dias (
    id_dia SERIAL PRIMARY KEY,
    descripcion VARCHAR(15) UNIQUE NOT NULL,
    CONSTRAINT chk_dias CHECK (descripcion IN ('LUNES', 'MARTES', 'MIERCOLES', 'JUEVES', 'VIERNES', 'SABADO', 'DOMINGO'))
);

-- Crear tabla horario
CREATE TABLE horario (
    id_horario SERIAL PRIMARY KEY,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    CONSTRAINT chk_horario CHECK (hora_inicio < hora_fin)
);

-- Crear tabla medico_disponibilidad (relaciona medico con dias y horarios disponibles)
CREATE TABLE medico_disponibilidad (
    id_medico INTEGER NOT NULL,
    id_dia INTEGER NOT NULL,
    id_horario INTEGER NOT NULL,
    PRIMARY KEY (id_medico, id_dia, id_horario),
    FOREIGN KEY (id_medico) REFERENCES medico (id_medico),
    FOREIGN KEY (id_dia) REFERENCES dias (id_dia),
    FOREIGN KEY (id_horario) REFERENCES horario (id_horario)
);

-- Crear tabla estado_cita
CREATE TABLE estado_cita (
    id_estado_cita SERIAL PRIMARY KEY,
    descripcion VARCHAR(50) NOT NULL UNIQUE
);

-- Crear tabla cita
CREATE TABLE cita (
    id_cita SERIAL PRIMARY KEY,
    id_paciente INTEGER NOT NULL,
    id_medico INTEGER NOT NULL,
    fecha DATE NOT NULL,
    id_horario INTEGER NOT NULL,
    id_estado_cita INTEGER DEFAULT 1, -- Estado inicial: programado
    observaciones TEXT,
    FOREIGN KEY (id_paciente) REFERENCES paciente (id_paciente),
    FOREIGN KEY (id_medico) REFERENCES medico (id_medico),
    FOREIGN KEY (id_horario) REFERENCES horario (id_horario),
    FOREIGN KEY (id_estado_cita) REFERENCES estado_cita (id_estado_cita)
);

-- Crear tabla agenda_cita (relaciona la disponibilidad del medico con la agenda)
CREATE TABLE agenda_cita (
    id_agenda SERIAL PRIMARY KEY,
    id_medico INTEGER NOT NULL,
    fecha_disponible DATE NOT NULL,
    id_horario INTEGER NOT NULL,
    estado_cita INTEGER DEFAULT 1, -- Estado inicial: disponible
    FOREIGN KEY (id_medico) REFERENCES medico (id_medico),
    FOREIGN KEY (id_horario) REFERENCES horario (id_horario),
    FOREIGN KEY (estado_cita) REFERENCES estado_cita (id_estado_cita)
);

-- Insertar datos iniciales

-- Insertar estados de cita
INSERT INTO estado_cita (descripcion) VALUES 
('Programado'), ('Cancelado'), ('Finalizado'), ('Disponible');

-- Insertar días de la semana
INSERT INTO dias (descripcion) VALUES 
('LUNES'), ('MARTES'), ('MIERCOLES'), ('JUEVES'), ('VIERNES'), ('SABADO'), ('DOMINGO');

-- Insertar horarios
INSERT INTO horario (hora_inicio, hora_fin) VALUES 
('08:00', '10:00'),
('10:00', '12:00'),
('12:00', '14:00'),
('14:00', '16:00'),
('16:00', '18:00');
