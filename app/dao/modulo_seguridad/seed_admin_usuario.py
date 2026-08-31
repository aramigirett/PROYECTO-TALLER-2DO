"""
Script de línea de comandos para dar de alta el primer usuario Administrador
del Módulo Seguridad.

Un usuario SIEMPRE se vincula a exactamente una persona ya existente:
un funcionario o un médico (nunca ambos, nunca ninguno - no existe tabla
"Persona" genérica en este sistema). Por eso este script pide el id de un
funcionario O de un médico ya cargado, no crea la persona.

Se ejecuta como módulo (con -m) desde la raíz del proyecto, para que los
imports de "app" resuelvan bien:

    python -m app.dao.modulo_seguridad.seed_admin_usuario \
        --ci-ruc 1234567 --password "unaClaveSegura123" \
        --correo admin@clinica.com --id-funcionario 3

    python -m app.dao.modulo_seguridad.seed_admin_usuario \
        --ci-ruc 1234567 --password "unaClaveSegura123" \
        --correo admin@clinica.com --id-medico 1

Para ver los funcionarios/médicos disponibles:
    python -m app.dao.modulo_seguridad.seed_admin_usuario --listar
"""
import argparse
import sys

from werkzeug.security import generate_password_hash

from app.conexion.Conexion import Conexion


def listar_personas(cur):
    cur.execute("SELECT id_funcionario, nombre, apellido, cedula, correo FROM funcionario ORDER BY id_funcionario")
    funcionarios = cur.fetchall()
    cur.execute("SELECT id_medico, nombre, apellido, cedula, correo FROM medico ORDER BY id_medico")
    medicos = cur.fetchall()

    print("\nFuncionarios disponibles (id_funcionario | nombre | cédula | correo):")
    if funcionarios:
        for f in funcionarios:
            print(f"  {f[0]} | {f[1]} {f[2]} | {f[3]} | {f[4]}")
    else:
        print("  (no hay funcionarios cargados)")

    print("\nMédicos disponibles (id_medico | nombre | cédula | correo):")
    if medicos:
        for m in medicos:
            print(f"  {m[0]} | {m[1]} {m[2]} | {m[3]} | {m[4]}")
    else:
        print("  (no hay médicos cargados)")
    print()


def main():
    parser = argparse.ArgumentParser(description="Alta del primer usuario Administrador (Módulo Seguridad)")
    parser.add_argument("--ci-ruc", help="CI o RUC del usuario (login)")
    parser.add_argument("--password", help="Contraseña en texto plano (se guarda hasheada)")
    parser.add_argument("--correo", help="Correo al que se enviará el código 2FA")
    parser.add_argument("--id-funcionario", type=int, help="id_funcionario ya existente a vincular")
    parser.add_argument("--id-medico", type=int, help="id_medico ya existente a vincular")
    parser.add_argument("--listar", action="store_true", help="Lista funcionarios/médicos disponibles y termina")
    args = parser.parse_args()

    con = Conexion().getConexion()
    cur = con.cursor()

    try:
        if args.listar:
            listar_personas(cur)
            return

        faltantes = [
            nombre for nombre, valor in
            [("--ci-ruc", args.ci_ruc), ("--password", args.password), ("--correo", args.correo)]
            if not valor
        ]
        if faltantes:
            print(f"ERROR: faltan argumentos obligatorios: {', '.join(faltantes)}")
            sys.exit(1)

        if bool(args.id_funcionario) == bool(args.id_medico):
            print("ERROR: debés indicar exactamente uno de --id-funcionario o --id-medico (nunca ambos ni ninguno).")
            sys.exit(1)

        if len(args.password) < 6:
            print("ERROR: la contraseña debe tener al menos 6 caracteres.")
            sys.exit(1)

        if args.id_funcionario:
            cur.execute("SELECT 1 FROM funcionario WHERE id_funcionario = %s", (args.id_funcionario,))
            if not cur.fetchone():
                print(f"ERROR: no existe funcionario con id_funcionario={args.id_funcionario}.")
                sys.exit(1)
        else:
            cur.execute("SELECT 1 FROM medico WHERE id_medico = %s", (args.id_medico,))
            if not cur.fetchone():
                print(f"ERROR: no existe médico con id_medico={args.id_medico}.")
                sys.exit(1)

        cur.execute("SELECT id_rol FROM roles WHERE nombre_rol = 'Administrador'")
        rol = cur.fetchone()
        if not rol:
            print("ERROR: no existe el rol 'Administrador' en la tabla roles. Corré primero schema_seguridad.sql.")
            sys.exit(1)
        id_rol = rol[0]

        cur.execute("SELECT 1 FROM usuarios WHERE ci_ruc = %s", (args.ci_ruc,))
        if cur.fetchone():
            print(f"ERROR: ya existe un usuario con ci_ruc={args.ci_ruc}.")
            sys.exit(1)

        password_hash = generate_password_hash(args.password)

        cur.execute(
            """
            INSERT INTO usuarios (ci_ruc, password_hash, correo, id_rol, id_funcionario, id_medico)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id_usuario
            """,
            (args.ci_ruc, password_hash, args.correo, id_rol, args.id_funcionario, args.id_medico),
        )
        id_usuario = cur.fetchone()[0]
        con.commit()

        print(f"OK: usuario Administrador creado (id_usuario={id_usuario}, ci_ruc={args.ci_ruc}).")

    except Exception as e:
        con.rollback()
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        cur.close()
        con.close()


if __name__ == "__main__":
    main()
