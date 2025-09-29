import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# ⚠️ Requiere: pip install selenium webdriver-manager

from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


def enviar_whatsapp(numero, mensaje):
    """
    Envía un mensaje de WhatsApp usando WhatsApp Web con Selenium.
    - numero: en formato internacional (ej: +595981111111)
    - mensaje: texto del mensaje
    """

    try:
        # Configuración de Chrome
        chrome_options = Options()
        chrome_options.add_argument("--user-data-dir=selenium")  # Guarda sesión (QR solo 1 vez)
        chrome_options.add_argument("--profile-directory=Default")
        chrome_options.add_experimental_option("detach", True)   # No cerrar ventana al terminar

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )

        # Abrir WhatsApp Web
        driver.get("https://web.whatsapp.com/")
        print("📲 Escanea el código QR si es la primera vez...")
        time.sleep(15)  # Tiempo para escanear QR (ajustar según tu PC)

        # Ir al chat con el número
        url = f"https://web.whatsapp.com/send?phone={numero}&text={mensaje}"
        driver.get(url)
        time.sleep(10)

        # Presionar ENTER para enviar
        input_box = driver.find_element(By.XPATH, "//div[@title='Escribe un mensaje']")
        input_box.send_keys(Keys.ENTER)

        print(f"✅ Mensaje enviado a {numero}: {mensaje}")
        return True

    except Exception as e:
        print(f"❌ Error al enviar WhatsApp: {e}")
        return False