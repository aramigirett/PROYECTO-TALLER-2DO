# Plan: Mantener Cuenta Bancaria + Registrar Arqueo de Caja

Revisé la base y no modifiqué nada. `arqueo_caja`, `arqueo_caja_det` y `recaudacion_depositar` existen y están vacías. `cuenta_bancaria` no existe.

## Diferencias entre el prompt y la base
- **`cuenta_bancaria` no existe** (la creo). **`recaudacion_depositar` no tiene la FK a la cuenta**: le agrego `id_cuenta_bancaria` (INT NULL, FK RESTRICT) y un CHECK que exige cuenta cuando el estado es DEPOSITADA. Las dos cosas hay que sumarlas al DER.
- Estados reales en la base: arqueo `REGISTRADO/ANULADO`, recaudación `PENDIENTE/DEPOSITADA/ANULADA`.
- `arqueo_caja_det` tiene una fila por **forma de cobro**: no hay fila para el fondo inicial ni para el reintegro. Van dentro del efectivo (sistema = fondo + efectivo cobrado − reintegros).
- Ya existen: único `REGISTRADO` por apertura (se puede volver a arquear una apertura con arqueo anulado) y un único `recaudacion` vigente por arqueo.
- `arqueo_caja_det` exige `monto_sistema >= 0` y `recaudacion_depositar` exige `monto_efectivo >= 0`.

## Parte A — Cuenta Bancaria
1. `schema_cuenta_bancaria.sql` (idempotente): tabla `cuenta_bancaria` (FK a banco RESTRICT, `tipo_cuenta` CORRIENTE / CAJA DE AHORRO, `numero_cuenta`, `titular` en mayúsculas, `activo`), único parcial `(id_entidad_emisora, numero_cuenta) WHERE activo`, la FK en `recaudacion_depositar` y los 2 datos iniciales (titular = razón social de la empresa).
2. Estándar completo: vista Tabler, Estado, "Mostrar inactivos", Reactivar (valida banco activo y duplicado), baja bloqueada si está en uso (`FOR UPDATE`), `auditoria_cambios`, validadores en espejo (número de cuenta y titular).
3. Ventana `cuentabancaria` en "Referenciales Facturación"; el Cajero solo ve.
4. Conexiones: `EntidadEmisoraDao.esta_en_uso` suma las cuentas activas; `CuentaBancariaDao.esta_en_uso` consulta las recaudaciones.

## Parte B — Arqueo de Caja
1. **SQL** `schema_arqueo.sql` (idempotente):
   - `sp_registrar_arqueo(...)` (procedimiento): en una transacción inserta el arqueo, el detalle (**el monto del sistema lo calcula la base**: `v_resumen_caja`; en efectivo suma el fondo inicial y resta los reintegros) y la recaudación PENDIENTE (efectivo contado − fondo + cheques contados). Valida y tiene `EXCEPTION`.
   - Trigger `trg_validar_arqueo` (BEFORE INSERT): la apertura debe estar CERRADA.
   - Vista `v_arqueos_diferencias`: por apertura, cajero, fecha, total sistema, total contado y diferencia.
   - Todo con comentarios y `COMMENT ON`.
2. **Permisos:** ventana `arqueo` con `ver`, `nuevo`, `anular` y `estado` (marcar depositada), fila en `menu` y seed.
3. **Código:** `ArqueoDao`, API y rutas, vista Tabler y PDF del arqueo (ORIGINAL y DUPLICADO, mismo patrón que los demás).
4. **Pantalla:**
   - listado de arqueos con filtros y badge cuadra / sobrante / faltante;
   - Nuevo Arqueo: elegir una apertura cerrada sin arqueo, grilla sistema / contado / diferencia en vivo, observación obligatoria si hay diferencia;
   - sección Recaudaciones con estado y "Marcar depositada" (cuenta activa, boleta y fecha);
   - Ver y PDF.
5. **Conexiones:** el listado de aperturas muestra si tienen arqueo (y un endpoint con las cerradas sin arqueo alimenta la pantalla); anular un arqueo solo si su recaudación sigue PENDIENTE (la anula también).
6. **Tests:** `smoke_cuenta_bancaria.py`, `smoke_arqueo.py` y la regresión completa. Al final, `resumen_arqueo.md` y `CLAUDE.md`, sin commitear.

## Supuestos técnicos
- La grilla lista las formas con movimiento en la apertura más las de tipo EFECTIVO; el fondo y los reintegros se asignan a la primera forma EFECTIVO.
- Hay que contar todas las formas con movimiento (monto contado ≥ 0, entero).
- La observación es obligatoria si **alguna** forma tiene diferencia (aunque se compensen entre sí).
- Solo se puede arquear una apertura CERRADA; si el arqueo se anula, se puede volver a arquear.
- Marcar depositada pide cuenta activa, boleta y fecha (no futura); una recaudación DEPOSITADA no se revierte.

## Preguntas de negocio
1. **¿Quién puede usar el Arqueo?** Recomendación: el Cajero con `ver`, `nuevo`, `anular` y `estado` (como los demás movimientos), sin impedir que arquee su propia caja: queda auditado quién lo hizo. Alternativa: solo el Administrador.
2. **Si el efectivo contado es menor al fondo inicial**, ¿qué se hace? Recomendación: se permite (el faltante queda registrado y exige observación), el efectivo a depositar es 0 y, si no hay nada que depositar (efectivo 0 y sin cheques), no se genera recaudación.
