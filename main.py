from playwright.sync_api import sync_playwright
from time import sleep
import configparser
import oracledb as db
from tqdm import tqdm

config = configparser.ConfigParser()
config.read("config.ini")


def obtener_lista_dni(nombre_delegacion: str, max_cantidad: int) -> list[str]:
    query = f"""select p.numero_documento
    from rce_ged.jbpm4_task t
    inner join rce_ged.jbpm4_variable v
    on t.execution_ = v.execution_
    inner join rce_ged.rce_registro r
    on t.execution_id_ = r.id_flujo_jbpm
    inner join rce_ged.rce_registro_persona pr
    on r.id_registro = pr.fk_registro
    inner join rce_ged.rce_persona p
    on pr.fk_persona = p.id_persona
    inner join gedo_ged.gedo_documento d
    on d.workfloworigen = v.string_value_
    inner join rce_ged.sys_circunscripcion c 
    on r.fk_id_circunscripcion = c.id_circunscripcion   
    where
    t.name_ = 'Esperar Firma Digital' and
    v.key_ = 'idFlujoFirma' and
    d.numero is not null and
    p.numero_documento is not null and
    c.nombre = '{nombre_delegacion}' and
    rownum <= {max_cantidad}"""

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


def main():
    delegacion = input("Ingrese el nombre de la delegación: ")
    lista_dni = obtener_lista_dni(delegacion, 200)

    if len(lista_dni) == 0:
        print("No hay registros en espera de firma digital.")
        return

    with sync_playwright() as pw:
        # create browser instance
        browser = pw.chromium.launch(headless=config["APP"].getboolean("headless"))
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            # record_video_dir="videos/",
            # record_video_size={"width": 1280, "height": 720},
        )
        page = context.new_page()

        page.goto(
            "https://cas.gdeba.gba.gob.ar/acceso/login/?service=https://redip.gdeba.gba.gob.ar/redip-web/j_spring_cas_security_check"
        )
        page.get_by_placeholder("Usuario/Cuil/Cuit").fill(config["APP"]["usuario"])
        page.get_by_placeholder("Contraseña").fill(config["APP"]["pass"])
        page.get_by_role("button", name="Acceder").click()
        page.locator(".z-bandbox-inp.z-bandbox-readonly").click()
        page.locator(
            "body > div:nth-child(6) > div:nth-child(1) > div:nth-child(1) > div:nth-child(3) > table:nth-child(2) > tbody:nth-child(1) > tr:nth-child(1) > td:nth-child(1) > table:nth-child(1) > tbody:nth-child(1) > tr:nth-child(5) > td:nth-child(1) > div:nth-child(1) > div:nth-child(3) > table:nth-child(1) > tbody:nth-child(2) > tr:nth-child(1) > td:nth-child(1) > div:nth-child(1)"
        ).click()
        page.locator("div[title='Aceptar'] div[class='z-toolbarbutton-cnt']").click()

        for dni in tqdm(
            iterable=lista_dni,
            desc=delegacion,
            total=len(lista_dni),
        ):
            page.locator("//input[@placeholder='Buscar...']").fill(str(dni))
            page.locator(
                "//body[1]/div[1]/div[2]/div[1]/div[1]/div[1]/div[1]/div[1]/div[1]/div[1]/div[1]/div[1]/table[1]/tbody[1]/tr[1]/td[1]/table[1]/tbody[1]/tr[1]/td[5]/span[1]/table[1]/tbody[1]/tr[2]/td[2]/img[1]"
            ).click()

            sleep(1)

            while True:
                procesando = page.get_by_text("Procesando...")
                sleep(1)
                if not procesando.is_visible():
                    break

            for locator in page.locator(
                "//span[contains(text(),'Ver Registros')][1]"
            ).all():
                locator.click()

                while True:
                    procesando = page.get_by_text("Procesando...")
                    sleep(1)
                    if not procesando.is_visible():
                        break

                page.locator(
                    "body > div:nth-child(5) > div:nth-child(2) > div:nth-child(1) > div:nth-child(1) > div:nth-child(1) > div:nth-child(1)"
                ).click()
                sleep(1)

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
