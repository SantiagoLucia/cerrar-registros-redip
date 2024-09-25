from playwright.sync_api import sync_playwright
from time import sleep
import configparser
import oracledb as db
from tqdm import tqdm

# Configuración
config = configparser.ConfigParser()
config.read("config.ini")

# Constantes
LOGIN_URL = "https://cas.gdeba.gba.gob.ar/acceso/login/?service=https://redip.gdeba.gba.gob.ar/redip-web/j_spring_cas_security_check"
VIEWPORT = {"width": 1280, "height": 720}
SELECTORS = {
    "usuario": "input[placeholder='Usuario/Cuil/Cuit']",
    "contraseña": "input[placeholder='Contraseña']",
    "acceder": "button[role='button'][name='Acceder']",
    "bandbox": ".z-bandbox-inp.z-bandbox-readonly",
    "aceptar": "div[title='Aceptar'] div[class='z-toolbarbutton-cnt']",
    "buscar": "input[placeholder='Buscar...']",
    "ver_registros": "//span[contains(text(),'Ver Registros')][1]",
    "procesando": "Procesando..."
}

def obtener_lista_dni(nombre_delegacion: str, max_cantidad: int) -> list[str]:
    query = f"""select * from (
    select regexp_substr(d.motivo, '[^: ]+[0-9]$') as dni
    from rce_ged.jbpm4_task t
    inner join rce_ged.jbpm4_variable v
    on t.execution_ = v.execution_
    inner join rce_ged.rce_registro r
    on t.execution_id_ = r.id_flujo_jbpm
    inner join gedo_ged.gedo_documento d
    on d.workfloworigen = v.string_value_
    inner join rce_ged.sys_circunscripcion c 
    on r.fk_id_circunscripcion = c.id_circunscripcion
    where
    t.name_ = 'Esperar Firma Digital' and
    v.key_ = 'idFlujoFirma' and
    r.numero is null and
    r.fecha_inutilizacion is null and 
    r.fecha_anulacion is null and
    r.fecha_inmovilizacion is null and
    d.numero is not null and
    c.nombre = '{nombre_delegacion}' and
    rownum <= {max_cantidad} )
    where dni is not null"""

    with db.connect(
        user=config["APP"]["user"],
        password=config["APP"]["password"],
        host=config["APP"]["host"],
        port=int(config["APP"]["port"]),
        service_name=config["APP"]["service_name"],
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchall()
            lista_dni = [x[0] for x in result]

    return lista_dni

def iniciar_sesion(page):
    page.goto(LOGIN_URL)
    page.locator(SELECTORS["usuario"]).fill(config["APP"]["usuario"])
    page.locator(SELECTORS["contraseña"]).fill(config["APP"]["pass"])
    page.locator(SELECTORS["acceder"]).click()
    page.locator(SELECTORS["bandbox"]).click()
    page.locator(
        "body > div:nth-child(6) > div:nth-child(1) > div:nth-child(1) > div:nth-child(3) > table:nth-child(2) > tbody:nth-child(1) > tr:nth-child(1) > td:nth-child(1) > table:nth-child(1) > tbody:nth-child(1) > tr:nth-child(5) > td:nth-child(1) > div:nth-child(1) > div:nth-child(3) > table:nth-child(1) > tbody:nth-child(2) > tr:nth-child(1) > td:nth-child(1) > div:nth-child(1)"
    ).click()
    page.locator(SELECTORS["aceptar"]).click()

def procesar_dni(page, dni):
    page.locator(SELECTORS["buscar"]).fill(str(dni))
    page.locator(
        "//body[1]/div[1]/div[2]/div[1]/div[1]/div[1]/div[1]/div[1]/div[1]/div[1]/div[1]/div[1]/table[1]/tbody[1]/tr[1]/td[1]/table[1]/tbody[1]/tr[1]/td[5]/span[1]/table[1]/tbody[1]/tr[2]/td[2]/img[1]"
    ).click()
    esperar_procesamiento(page)

    for locator in page.locator(SELECTORS["ver_registros"]).all():
        locator.click()
        esperar_procesamiento(page)
        page.locator(
            "body > div:nth-child(5) > div:nth-child(2) > div:nth-child(1) > div:nth-child(1) > div:nth-child(1) > div:nth-child(1)"
        ).click()
        sleep(1)

def esperar_procesamiento(page):
    while True:
        procesando = page.get_by_text(SELECTORS["procesando"])
        sleep(1)
        if not procesando.is_visible():
            break

def main():
    delegacion = input("Ingrese el nombre de la delegación: ")
    lista_dni = obtener_lista_dni(delegacion, 200)

    if len(lista_dni) == 0:
        print("No hay registros en espera de firma digital.")
        return

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config["APP"].getboolean("headless"))
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()

        iniciar_sesion(page)

        for dni in tqdm(lista_dni, desc=delegacion, total=len(lista_dni)):
            procesar_dni(page, dni)

        context.close()
        browser.close()

if __name__ == "__main__":
    main()