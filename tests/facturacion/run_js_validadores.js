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
var tels = ['', '12', '0981 123456', '+5-95-1 1'];
for (var t = 0; t < tels.length; t++) out.push('telOpc\t' + tels[t] + '\t' + V.telefonoOpcional(tels[t]));
var cors = ['', 'A@B.com', 'malo'];
for (var m = 0; m < cors.length; m++) out.push('corOpc\t' + cors[m] + '\t' + V.correoOpcional(cors[m]));
var montos = ['0', '1500', '-1', '-5', 'abc', '', '1.5', '15.5', '999999999999', '1000000000000'];
for (var q = 0; q < montos.length; q++) out.push('monto\t' + montos[q] + '\t' + V.monto(montos[q]));
out.push('ubicacion\tPLANTA\t' + V.ubicacion('PLANTA') + '|' + V.ubicacion('') );
// salida en UTF-8 sin BOM vía ADODB
var so = new ActiveXObject('ADODB.Stream'); so.Type = 2; so.Charset = 'utf-8'; so.Open();
so.WriteText(out.join('\n')); so.SaveToFile(WScript.Arguments(2), 2); so.Close();
