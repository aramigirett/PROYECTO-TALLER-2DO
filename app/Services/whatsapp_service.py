from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import urllib.parse
from datetime import datetime
from flask import current_app as app
from app.dao.referenciales_agendamiento.avisosRecordatorios.AvisosRecordatorioDao import AvisoRecordatorioDao

class WhatsAppService:
    """Servicio para enviar mensajes por WhatsApp Web"""
    
    def __init__(self):
        self.driver = None
        self.conectado = False
        
    def inicializar_navegador(self):
        """Inicializa el navegador con WhatsApp Web"""
        if self.driver is not None:
            return True
        
        try:
            import os
        
            options = webdriver.ChromeOptions()
        
            # Usar SIEMPRE la misma carpeta de sesión (persistente)
            user_data_dir = os.path.join(os.getcwd(), 'whatsapp_session_persistente')
        
            options.add_argument(f'--user-data-dir={user_data_dir}')
            options.add_argument('--profile-directory=Default')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--start-maximized')
        
            print(f"Usando sesion persistente: {user_data_dir}")
        
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options
            )
            self.driver.get('https://web.whatsapp.com')
            print("Esperando inicio de sesion en WhatsApp Web...")
            return True
        except Exception as e:
            print(f"Error al inicializar navegador: {e}")
            return False
    
    def esperar_carga(self, timeout=240):
        """Espera a que WhatsApp Web esté listo"""
        try:
            print("   Esperando que cargue WhatsApp Web...")
            
            # Espera inicial para que la página cargue
            time.sleep(5)
            
            tiempo_inicio = time.time()
            tiempo_limite = tiempo_inicio + timeout
            
            while time.time() < tiempo_limite:
                try:
                    # Busca cualquier indicador de que WhatsApp cargó
                    # 1. Campo de búsqueda (ya logueado)
                    campos = self.driver.find_elements(By.XPATH, '//div[@contenteditable="true"]')
                    if len(campos) > 0:
                        print("   WhatsApp Web conectado correctamente")
                        self.conectado = True
                        time.sleep(2)
                        return True
                    
                    # 2. Canvas del QR (necesita escaneo)
                    canvas = self.driver.find_elements(By.TAG_NAME, 'canvas')
                    if len(canvas) > 0:
                        print("   Codigo QR detectado - Escanea con tu telefono")
                        # Sigue esperando...
                    
                    time.sleep(2)
                    
                except Exception as e:
                    # Continúa intentando
                    time.sleep(2)
            
            # Si llegó aquí, se acabó el tiempo
            print("   Tiempo de espera agotado")
            self.conectado = False
            return False
            
        except Exception as e:
            print(f"   Error al esperar carga: {str(e)}")
            self.conectado = False
            return False
    
    def enviar_mensaje(self, numero, mensaje):
        """
        Envía un mensaje por WhatsApp
        Args:
            numero (str): Número con código de país sin signos (ej: 595981234567)
            mensaje (str): Texto del mensaje
        Returns:
            bool: True si se envió correctamente
        """
        try:
            # Limpia el número (elimina espacios, guiones, etc)
            numero_limpio = ''.join(filter(str.isdigit, str(numero)))
            
            mensaje_codificado = urllib.parse.quote(mensaje)
            url = f'https://web.whatsapp.com/send?phone={numero_limpio}&text={mensaje_codificado}'
            
            print(f"   Abriendo chat con {numero_limpio}...")
            self.driver.get(url)
            time.sleep(6)
            
            print("   Buscando boton de enviar...")
            
            # Intenta múltiples selectores
            selectores = [
                '//button[@aria-label="Enviar"]',
                '//button[@aria-label="Send"]',
                '//span[@data-icon="send"]',
                '//button[@data-tab="11"]',
                '//button[contains(@class, "send")]',
                '//div[@role="button"][@aria-label="Enviar"]',
                '//div[@role="button"][@aria-label="Send"]'
            ]
            
            boton_encontrado = False
            for i, selector in enumerate(selectores):
                try:
                    boton_enviar = WebDriverWait(self.driver, 8).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    boton_enviar.click()
                    print(f"   Mensaje enviado (metodo {i+1})")
                    boton_encontrado = True
                    break
                except:
                    continue
            
            if not boton_encontrado:
                print("   Intentando metodo alternativo (Enter)...")
                try:
                    input_box = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"][@data-tab="10"]'))
                    )
                    input_box.click()
                    time.sleep(1)
                    input_box.send_keys(Keys.ENTER)
                    print("   Mensaje enviado con Enter")
                    boton_encontrado = True
                except Exception as e:
                    print(f"   Metodo alternativo fallo: {str(e)}")
                    
                    try:
                        print("   Ultimo intento...")
                        boton = self.driver.find_element(By.XPATH, '//button[.//span[@data-icon="send"]]')
                        boton.click()
                        print("   Mensaje enviado (ultimo intento)")
                        boton_encontrado = True
                    except:
                        print("   No se pudo enviar el mensaje")
            
            # ✅ Mantener la ventana abierta
            if boton_encontrado:
                print("   ✅ Mensaje enviado. La ventana permanecerá abierta.")
            
            time.sleep(2)
            return boton_encontrado
            
        except Exception as e:
            print(f"   Error al enviar a {numero}: {str(e)}")
            return False
    
    def cerrar(self):
        """Cierra el navegador"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.conectado = False


class AvisoRecordatorioService:
    """Servicio principal para enviar recordatorios desde la BD"""
    
    def __init__(self):
        self.dao = AvisoRecordatorioDao()
        self.whatsapp = WhatsAppService()
    
    def formatear_mensaje(self, aviso):
        """
        Formatea el mensaje del recordatorio
        Args:
            aviso (dict): Datos del aviso con información del paciente
        Returns:
            str: Mensaje formateado para WhatsApp
        """
        # ✅ Verificar si el mensaje existe Y no está vacío
        mensaje_personalizado = aviso.get('mensaje', '')
        if mensaje_personalizado and mensaje_personalizado.strip():
            return mensaje_personalizado
        
        # Si no hay mensaje o está vacío, generar automático
        paciente = aviso.get('paciente', 'Estimado/a paciente')
        funcionario = aviso.get('funcionario', 'Nuestro equipo')  # ✅ CAMBIO
        fecha = aviso.get('fecha_cita', 'N/A')
        hora = aviso.get('hora_cita', 'N/A')
        medico = aviso.get('medico')
        consultorio = aviso.get('nombre_consultorio', 'nuestras instalaciones')
        
        # ✅ Construir la línea del médico solo si existe
        if medico:
            linea_medico = f"👨‍⚕️ *Médico:* {medico}"
        else:
            linea_medico = "👨‍⚕️ *Médico:* Por asignar"
        
        mensaje = f"""Buenos días/tardes, {paciente}

Le saluda {funcionario} del {consultorio}.

Le recordamos que tiene una cita médica programada con los siguientes detalles:

📅 *Fecha:* {fecha}
🕐 *Hora:* {hora}
{linea_medico}
🏥 *Consultorio:* {consultorio}

Por favor, le solicitamos confirmar su asistencia respondiendo a este mensaje.

En caso de necesitar reprogramar su cita, le pedimos que nos avise con la mayor anticipación posible.

Quedamos atentos a su confirmación.

Gracias."""
        
        return mensaje
    
    def obtener_telefono_paciente(self, id_paciente):
        """
        Obtiene el teléfono del paciente desde la BD
        """
        from app.conexion.Conexion import Conexion
        
        sql = "SELECT telefono FROM paciente WHERE id_paciente = %s;"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_paciente,))
            row = cur.fetchone()
            if row and row[0]:
                return row[0]
            return None
        except Exception as e:
            print(f"Error al obtener telefono: {e}")
            return None
        finally:
            cur.close()
            con.close()
    
    def procesar_avisos_pendientes(self):
        """Procesa y envía todos los avisos pendientes de WhatsApp"""
        print(f"\n{'='*60}")
        print(f"Procesando avisos - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        try:
            avisos = self.dao.getAvisos()
            
            avisos_whatsapp = [
                a for a in avisos 
                if a.get('forma_envio') == 'WhatsApp' 
                and a.get('estado_envio') == 'Pendiente'
            ]
            
            if not avisos_whatsapp:
                print("No hay avisos de WhatsApp pendientes")
                return
            
            print(f"{len(avisos_whatsapp)} avisos para procesar\n")
            
            if not self.whatsapp.inicializar_navegador():
                print("No se pudo inicializar el navegador")
                return
            
            if not self.whatsapp.esperar_carga():
                print("No se pudo conectar a WhatsApp Web")
                self.whatsapp.cerrar()
                return
            
            exitosos = 0
            fallidos = 0
            
            for aviso in avisos_whatsapp:
                id_aviso = aviso['id_aviso']
                paciente = aviso.get('paciente', 'Paciente')
                
                print(f"{'='*60}")
                print(f"Procesando aviso #{id_aviso} - {paciente}")
                print(f"{'='*60}")
                
                aviso_completo = self.dao.getAvisoById(id_aviso)
                if not aviso_completo:
                    print(f"   ❌ No se encontró el aviso\n")
                    continue
                
                id_paciente = aviso_completo.get('id_paciente')
                telefono = self.obtener_telefono_paciente(id_paciente)
                
                if not telefono:
                    print(f"   ❌ Paciente sin teléfono registrado\n")
                    self._marcar_error(id_aviso)
                    fallidos += 1
                    continue
                
                # ✅ PASO 1: Generar el mensaje automático
                print(f"   📝 Generando mensaje automático...")
                mensaje_generado = self.formatear_mensaje(aviso_completo)
                
                print(f"   ✅ Mensaje generado ({len(mensaje_generado)} caracteres)")
                print(f"   Primeros 150 caracteres:")
                print(f"   {mensaje_generado[:150]}...")
                print()
                
                # ✅ PASO 2: Enviar por WhatsApp
                print(f"   📤 Enviando a: {telefono}")
                
                if self.whatsapp.enviar_mensaje(telefono, mensaje_generado):
                    print(f"   ✅ Mensaje enviado por WhatsApp exitosamente")
                    
                    # ✅ PASO 3: GUARDAR EL MENSAJE GENERADO EN LA BD
                    print(f"   💾 Guardando mensaje en la base de datos...")
                    
                    datos_para_actualizar = {
                        'id_paciente': aviso_completo['id_paciente'],
                        'id_funcionario': aviso_completo['id_funcionario'],  # ✅ CAMBIO
                        'id_medico': aviso_completo.get('id_medico'),
                        'codigo': aviso_completo.get('codigo'),
                        'fecha_cita': aviso_completo['fecha_cita'],
                        'hora_cita': aviso_completo['hora_cita'],
                        'forma_envio': aviso_completo['forma_envio'],
                        'mensaje': mensaje_generado,
                        'estado_envio': 'Enviado',
                        'estado_confirmacion': aviso_completo.get('estado_confirmacion', 'Pendiente')
                    }
                    
                    resultado = self.dao.updateAviso(id_aviso, datos_para_actualizar)
                    
                    if resultado:
                        print(f"   ✅ Mensaje guardado en BD correctamente")
                        exitosos += 1
                    else:
                        print(f"   ⚠️ Mensaje enviado pero hubo error al guardar en BD")
                        exitosos += 1
                    
                else:
                    print(f"   ❌ Error al enviar mensaje por WhatsApp")
                    self._marcar_error(id_aviso)
                    fallidos += 1
                
                print()
                time.sleep(3)
            
            print(f"\n{'='*60}")
            print(f"RESUMEN FINAL:")
            print(f"   ✅ Exitosos: {exitosos}")
            print(f"   ❌ Fallidos: {fallidos}")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"❌ Error general al procesar avisos: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _marcar_error(self, id_aviso):
        """Marca un aviso como error"""
        try:
            aviso = self.dao.getAvisoById(id_aviso)
            if aviso:
                aviso['estado_envio'] = 'Error'
                self.dao.updateAviso(id_aviso, aviso)
        except Exception as e:
            print(f"Error al marcar como error: {e}")
    
    def ejecutar_una_vez(self):
        """Ejecuta el envío una sola vez"""
        try:
            self.procesar_avisos_pendientes()
        finally:
            input("\nPresiona Enter para cerrar el navegador...")
            self.whatsapp.cerrar()
    
    def mantener_activo(self):
        """Mantiene el servicio activo"""
        print("Servicio de WhatsApp iniciado")
        print("Ejecuta este script cada vez que quieras enviar avisos pendientes\n")
        
        self.procesar_avisos_pendientes()
        
        print("\nProceso completado")
        print("El navegador permanecera abierto para mantener la sesion")
        print("Presiona Ctrl+C para cerrar\n")
        
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("\nCerrando servicio...")
            self.whatsapp.cerrar()


if __name__ == "__main__":
    servicio = AvisoRecordatorioService()
    servicio.ejecutar_una_vez()