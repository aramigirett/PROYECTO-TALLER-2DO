-- ============================================
-- MODULO SEGURIDAD - CUS "Mantener Roles y Permisos"
-- Relación Rol 1 --- N Permisos: cada permiso pertenece a un único rol.
-- La FK vive en permisos y apunta a roles (nunca al revés: "Roles puede
-- tener Permisos, pero Permisos no puede tener Roles").
-- ============================================

CREATE TABLE permisos (
    id_permiso SERIAL PRIMARY KEY,
    nombre_permiso VARCHAR(100) NOT NULL,
    descripcion VARCHAR(255) NULL,
    id_rol INTEGER NOT NULL REFERENCES roles(id_rol),
    CONSTRAINT uq_permiso_rol_nombre UNIQUE (id_rol, nombre_permiso)
);
