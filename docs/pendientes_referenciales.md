# Pendientes de referenciales

> Orden de trabajo de los referenciales pendientes.
> Movido tal cual desde `CLAUDE.md` (sin cambios de contenido) al reorganizarlo. La guía compacta es `CLAUDE.md`.

## Pendientes de referenciales (en este orden)
1. **Facturación — migrar Caja, Depósito y Cliente a `facturacion-listado.js`** (hoy cada una tiene su propia copia de
   `pedir`, `escapar`, el badge, los botones y los flujos de SweetAlert2) y **unificar el parámetro de Caja de
   `?inactivas` a `?inactivos`** (el del estándar, que ya usan Depósito, Cliente y los otros 6). Verificado en el
   código: ninguna otra pantalla usa `?inactivas`, solo la propia vista y API de Caja; aun así, al unificar, hacer que
   la API de Caja acepte los dos nombres durante la transición y quitar `inactivas` cuando se confirme que nada lo usa
   (el DAO de Caja también usa `incluir_inactivas`; renombrar a `incluir_inactivos`). Esas 3 vistas ya se probaron
   a mano en el navegador: volver a probarlas después de migrarlas.
   *(El punto 4 del estándar —Estado, "Mostrar inactivos", Reactivar— ya está aplicado a Forma de Cobro, Marca de
   Tarjeta, Entidad Emisora, Entidad Adherida, Tipo Ítems e Ítems: ver "Módulo Facturación".)*
2. ✅ **HECHO — Consultorio**: los 8 referenciales cumplen el estándar completo (etapa 1: 6 con baja lógica; etapa 2: Tipo Diagnóstico y Síntomas, que pasaron
   de borrado físico a lógico).
3. **Agendamiento — al migrar a Tabler, pasar de borrado físico a lógico y aplicar el estándar completo** a los
   7 referenciales: agregar `activo`, convertir sus `UNIQUE` en índices únicos parciales (y actualizar las
   `estaEnUso()`/JOIN que los consultan, ver regla 4 de las "Reglas generales aprendidas"), vista Tabler,
   puntos 4 y 6. Ojo con `consultorio`: lo referencian `caja` (FK física), agenda, consultas, tratamientos y avisos;
   hoy "consultorio activo" = "consultorio existente" y las cajas lo usan así.
4. ✅ **HECHO — `precio NUMERIC(12,0)` e `iva` en `tipos_tratamiento`** (rama `consultorio`; ver "Tipo Tratamiento:
   precio" más arriba). Queda para la Venta de Tratamiento: guardar el precio y el IVA vigentes en la venta (hoy los
   tratamientos no copian el precio ni el IVA del tipo; si cambian, cambian para todos).
5. **Facturación — nuevo referencial "Mantener Timbrado"** (*pendiente de definir en el análisis*): no programarlo
   hasta tener el CUS (campos, validaciones y reglas de uso). Cuando se programe, cumple el estándar completo.
6. **Facturación — movimientos**: ✅ Registrar Apertura y Cierre de Caja y ✅ Registrar Pedido Cliente y ✅ Registrar Ventas (etapas 1 y 2) y ✅ Registrar Cobranzas y ✅ Registrar Nota de Remisión y ✅ Registrar Notas de Crédito y Débito y ✅ Mantener Cuenta Bancaria + ✅ Registrar Arqueo de Caja (ver
   "Movimientos de Facturación");
   el resto de los movimientos (sin empezar) se programa después de los puntos anteriores.

