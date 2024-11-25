SELECT
	e.id_empleado,
	, CONCAT(p.nombres,' ',p.apellidos) empleado
	, p.ci
FROM empleados e LEFT JOIN personas p ON e.id_empleado = p.id_persona;


SELECT
	sd.id_sucursal
	, s.descripcion nombre_sucursal
	, sd.id_deposito
	, d.descripcion nombre_deposito
	, sd.observaciones
	, sd.estado
FROM
	sucursal_depositos sd
LEFT JOIN depositos d
	ON sd.id_deposito = d.id_deposito
LEFT JOIN sucursales s
	ON sd.id_sucursal = s.id_sucursal
WHERE
	sd.id_sucursal = 1