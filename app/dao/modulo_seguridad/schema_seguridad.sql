-- ============================================
-- MODULO SEGURIDAD - CUS "Mantener Acceso"
-- Login (CI/RUC + contraseña) + 2FA por correo
-- ============================================

-- ROLES
CREATE TABLE roles (
    id_rol SERIAL PRIMARY KEY,
    nombre_rol VARCHAR(20) NOT NULL UNIQUE
        CHECK (nombre_rol IN ('Administrador', 'Medico', 'Recepcion', 'Cajero')),
    activo BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO roles (nombre_rol) VALUES
    ('Administrador'),
    ('Medico'),
    ('Recepcion'),
    ('Cajero');

-- USUARIOS
-- Un usuario se vincula SIEMPRE a exactamente una persona: funcionario O medico,
-- nunca ambos ni ninguno (no existe tabla "Persona" genérica en este sistema).
CREATE TABLE usuarios (
    id_usuario SERIAL PRIMARY KEY,
    ci_ruc VARCHAR(20) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    correo VARCHAR(150) NOT NULL,
    id_rol INTEGER NOT NULL REFERENCES roles(id_rol),
    id_funcionario INTEGER NULL REFERENCES funcionario(id_funcionario),
    id_medico INTEGER NULL REFERENCES medico(id_medico),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_usuario_persona_xor CHECK (
        (id_funcionario IS NOT NULL AND id_medico IS NULL) OR
        (id_funcionario IS NULL AND id_medico IS NOT NULL)
    )
);

-- TOKEN_2FA
CREATE TABLE token_2fa (
    id_token SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    codigo VARCHAR(6) NOT NULL,
    fecha_generacion TIMESTAMP NOT NULL DEFAULT NOW(),
    fecha_expiracion TIMESTAMP NOT NULL,
    usado BOOLEAN NOT NULL DEFAULT FALSE
);

-- AUDITORIA_ACCESO
-- id_usuario queda NULL cuando el CI/RUC ingresado no corresponde a ningún usuario.
CREATE TABLE auditoria_acceso (
    id_auditoria SERIAL PRIMARY KEY,
    id_usuario INTEGER NULL REFERENCES usuarios(id_usuario),
    ci_ruc_ingresado VARCHAR(20) NOT NULL,
    fecha_hora TIMESTAMP NOT NULL DEFAULT NOW(),
    resultado VARCHAR(30) NOT NULL,
    ip VARCHAR(45) NULL,
    accion VARCHAR(30) NOT NULL
);
