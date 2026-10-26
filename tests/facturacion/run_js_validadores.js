// Ejecuta app/static/js/facturacion-validadores.js con JScript (WSH) y imprime resultados "entrada<TAB>mensaje".
if (!String.prototype.trim) { String.prototype.trim = function () { return this.replace(/^\s+|\s+$/g, ''); }; }
var window = this;
var st = new ActiveXObject('ADODB.Stream');
st.Type = 2; st.Charset = 'utf-8'; st.Open();
st.LoadFromFile(WScript.Arguments(0));
var codigo = st.ReadText(); st.Close();
eval(codigo);
var V = window.FacturacionValidadores;
var casos = WScript.Arguments(1).split('|');
var out = [];
for (var i = 0; i < casos.length; i++) {
  var c = casos[i];
  out.push('ciRuc\t' + c + '\t' + V.ciRuc(c));
}
var bases = ['44444401', '80012345', '80000001', '80069563', '1234567', '800123450', '99999999'];
for (var j = 0; j < bases.length; j++) out.push('dv\t' + bases[j] + '\t' + V.calcularDvRuc(bases[j]));
var nombres = ["O'brien & hijos s.a.", 'a<b', '', 'x'];
for (var k = 0; k < nombres.length; k++) {
  out.push('nombre\t' + nombres[k] + '\t' + V.nombre(nombres[k], 'nombre', true));
  out.push('apellido\t' + nombres[k] + '\t' + V.nombre(nombres[k], 'apellido', false));
}
var tels = ['', '12', '0981 123456', '+5-95-1 1', '021 555123', '+595981123456'];
for (var t = 0; t < tels.length; t++) out.push('telOpc\t' + tels[t] + '\t' + V.telefonoOpcional(tels[t]));
var cors = ['', 'A@B.com', 'malo'];
for (var m = 0; m < cors.length; m++) out.push('corOpc\t' + cors[m] + '\t' + V.correoOpcional(cors[m]));
var montos = ['0', '1500', '-1', '-5', 'abc', '', '1.5', '15.5', '999999999999', '1000000000000'];
for (var q = 0; q < montos.length; q++) out.push('monto\t' + montos[q] + '\t' + V.monto(montos[q]));
var cants = ['1', '5', '0', '-1', 'abc', '', '1.5', ' 7 ', '2147483647', '2147483648'];
for (var w = 0; w < cants.length; w++) out.push('cantPos\t' + cants[w] + '\t' + V.cantidadPositiva(cants[w]));
var largo = ''; for (var z = 0; z < 201; z++) largo += 'a';
var obs = ['', '   ', 'Entrega por la tarde', largo, largo.substring(0, 200), 'con   espacios  internos', 'raro\u0001'];
for (var o = 0; o < obs.length; o++) out.push('observacion\t' + obs[o] + '\t' + V.observacion(obs[o]));
var mp = ['1', '1500', '0', '-1', 'abc', '', '1.5', ' 7 ', '999999999999', '1000000000000'];
for (var a1 = 0; a1 < mp.length; a1++) out.push('montoPos\t' + mp[a1] + '\t' + V.montoPositivo(mp[a1]));
var cods = ['', '   ', 'abc123', 'REF-2026/01', 'a b.c_d', 'con%raro', '-empieza', 'x', '123456789012345678901234567890', '1234567890123456789012345678901'];
for (var a2 = 0; a2 < cods.length; a2++) out.push('codigo\t' + cods[a2] + '\t' + V.codigo(cods[a2], 'referencia', 30, true) + '|' + V.codigo(cods[a2], 'referencia', 30, false));
var uds = ['1234', '0000', '123', '12345', 'abcd', '', ' 1234 ', '12 4'];
for (var a3 = 0; a3 < uds.length; a3++) out.push('ultDig\t' + uds[a3] + '\t' + V.ultimosDigitos(uds[a3]));
var ncs = ['1020304050', '12345', '1234', '123-456-78', '-12345', 'abc12345', '12 345', '', '   ', '12345678901234567890123456789', '123456789012345678901234567890', '1234567890123456789012345678901'];
for (var a4 = 0; a4 < ncs.length; a4++) out.push('nroCuenta\t' + ncs[a4] + '\t' + V.numeroCuenta(ncs[a4]));
var largo101 = ''; for (var z2 = 0; z2 < 101; z2++) largo101 += 'a';
var prs = ['', '   ', 'Caja x 20 comprimidos', 'FRASCO 100 ML (SUSPENSION)', 'tubo 5 g', 'a<b', largo101, largo101.substring(0, 100), '10%  sol.'];
for (var a5 = 0; a5 < prs.length; a5++) out.push('presentacion\t' + prs[a5] + '\t' + V.presentacion(prs[a5]));
var meds = ['', 'ibuprofeno 400 mg', 'AMOXICILINA/CLAVULANICO 875/125 MG', 'amoxicilina/clavulánico 875/125 mg', 'a<b', '(x)', 'x'];
for (var a6 = 0; a6 < meds.length; a6++) out.push('descMed\t' + meds[a6] + '\t' + V.descripcion(meds[a6], { max: 200, ampliada: true, etiqueta: 'nombre comercial', articulo: 'El' }));
out.push('ubicacion\tPLANTA\t' + V.ubicacion('PLANTA') + '|' + V.ubicacion('') );
// Agendamiento (espejo de app/rutas/modulo_agendamiento/utils.py)
var dias = ['lunes', 'MARTES', 'Miércoles', 'sábado', 'domingo', 'LUNES ', 'viernes ', 'enero', '', '   ', 'lun', 'jueves1'];
for (var d1 = 0; d1 < dias.length; d1++) out.push('dia\t' + dias[d1] + '\t' + V.dia(dias[d1]));
var tpy = ['0984818035', '0984 818 035', '0984-818-035', '  0984 818 035  ', '09848180', '098481803512', '0884818035', '595984818035', '+595984818035', '984818035',
           '021 339 8423', '0213398423', '021 600 600', '021600600', '0361 12345', '03611234567', '0112345678', '0912345678', '', '   ', 'abc', '09a4818035', '0984 818 03(5)', '021 339 842'];
for (var d2 = 0; d2 < tpy.length; d2++) {
  out.push('tel	' + tpy[d2] + '	' + V.telefono(tpy[d2]));
  out.push('telNorm	' + tpy[d2] + '	' + (V.normalizarTelefono(tpy[d2]) || ''));
  out.push('telFmt	' + tpy[d2] + '	' + V.formatearTelefono(tpy[d2]));
  out.push('telWa	' + tpy[d2] + '	' + (V.aWhatsapp(tpy[d2]) || ''));
}
var hrs = ['08:00', '8:30', '23:59', '24:00', '12:60', '08:00:30', '08:00:61', '', '  ', 'abc', '8', '08:5'];
for (var d3 = 0; d3 < hrs.length; d3++) out.push('hora\t' + hrs[d3] + '\t' + V.hora(hrs[d3], 'hora de inicio'));
var cps = ['1', '50', '1000', '1001', '0', '-1', '1.5', 'abc', '', ' 7 ', '01'];
for (var d4 = 0; d4 < cps.length; d4++) out.push('cupos\t' + cps[d4] + '\t' + V.cupos(cps[d4]));
var hh = ['08:00|09:00', '09:00|08:00', '08:00|08:00', '08:00|08:01'];
for (var d5 = 0; d5 < hh.length; d5++) { var pa = hh[d5].split('|'); out.push('horario\t' + hh[d5] + '\t' + V.horario(pa[0], pa[1])); }
var fns = ['1990-05-05', '1900-01-01', '1899-12-31', '2999-01-01', '2026-02-30', '1990-13-01', 'abc', '', '  ', '90-05-05', '2000-02-29', '1999-02-29'];
for (var d6 = 0; d6 < fns.length; d6++) out.push('fechaNac	' + fns[d6] + '	' + V.fechaNacimiento(fns[d6]));
// salida en UTF-8 sin BOM vía ADODB
var so = new ActiveXObject('ADODB.Stream'); so.Type = 2; so.Charset = 'utf-8'; so.Open();
so.WriteText(out.join('\n')); so.SaveToFile(WScript.Arguments(2), 2); so.Close();
