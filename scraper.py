# En Google Colab: %pip -q install "numpy==2.2.6" "numba==0.61.2" "llvmlite==0.44.0" "pandas==2.2.3" "requests==2.32.4" "ydata-profiling>=4.16,<5" beautifulsoup4 openpyxl pyarrow

import os, re, json, time, warnings, base64, zlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import requests
from bs4 import BeautifulSoup
import pandas as pd
from IPython.display import display

CARPETA = Path('resultados_scraping')
CARPETA.mkdir(exist_ok=True)
AUTORES = ['Lisbeth Salvador - 2025-0736', 'Keury Eliezer Rijo Perez - 2025-2137', 'Sandi Dotel - 2025-0844', 'Carlos Valdez - 2026-1167', 'Starlin Michael Castro Arias - 20251334']
EJECUTAR_SCRAPERS_EN_VIVO = True
LIMITE_POR_PORTAL = 200
COLUMNAS_ES = {'source':'fuente','name':'nombre','price':'precio','location':'ubicación','seller':'vendedor','size':'tamaño','bedrooms':'habitaciones','bathrooms':'baños','parking':'parqueos','url':'url','listing_id':'id_anuncio','currency':'moneda','price_numeric':'precio_numerico'}

class CorotosScraper:


    def __init__(self):


        self.url = "https://www.corotos.com.do/c/inmuebles-en-venta"


        self.headers = {
            "User-Agent": "Mozilla/5.0"
        }


        self.propiedades = []


        self.ids_vistos = set()


        self.tiempos_solicitudes = []


    def extraer_propiedad(self, anuncio):


        listing_id = anuncio.get("data-listing-id")


        nombre = anuncio.select_one("h3.search-card__title")


        moneda = anuncio.select_one(".item__currency")
        monto = anuncio.select_one(".item__price-amount")


        especificaciones = [
            dato.get_text(" ", strip=True)
            for dato in anuncio.select("span.search-card__spec")
        ]


        tamano = next(
            (dato for dato in especificaciones if "m²" in dato),
            None
        )

        habitaciones = next(
            (dato for dato in especificaciones if "hab" in dato.lower()),
            None
        )

        banos = next(
            (dato for dato in especificaciones if "baño" in dato.lower()),
            None
        )


        ubicacion = anuncio.select_one(".search-card__location")
        vendedor = anuncio.select_one(".search-card__seller-name")


        propiedad = {
            "source": "Corotos",
            "name": nombre.get_text(" ", strip=True) if nombre else None,
            "price": (
                f"{moneda.get_text(strip=True) if moneda else ''} "
                f"{monto.get_text(strip=True) if monto else ''}"
            ).strip() or None,
            "location": ubicacion.get_text(" ", strip=True) if ubicacion else None,
            "seller": vendedor.get_text(" ", strip=True) if vendedor else None,
            "size": tamano,
            "bedrooms": habitaciones,
            "bathrooms": banos,
            "parking": None
        }


        return listing_id, propiedad


    def extraer_pagina(self, numero_pagina, limite=200):


        inicio = time.time()


        if numero_pagina == 1:
            url_pagina = self.url
        else:
            url_pagina = f"{self.url}?page={numero_pagina}"


        respuesta = requests.get(
            url_pagina,
            headers=self.headers,
            timeout=30
        )


        respuesta.raise_for_status()


        soup = BeautifulSoup(respuesta.text, "html.parser")


        anuncios = soup.select("article.search-card")


        propiedades_nuevas = 0


        for anuncio in anuncios:


            if len(self.propiedades) >= limite:
                break


            listing_id, propiedad = self.extraer_propiedad(anuncio)


            if listing_id and listing_id not in self.ids_vistos:


                self.ids_vistos.add(listing_id)


                self.propiedades.append(propiedad)


                propiedades_nuevas += 1


        duracion = round(time.time() - inicio, 2)


        self.tiempos_solicitudes.append({
            "pagina": numero_pagina,
            "duracion": duracion,
            "estado": respuesta.status_code
        })


        print(
            "Página:", numero_pagina,
            "Propiedades nuevas:", propiedades_nuevas,
            "Tiempo:", duracion, "segundos"
        )


        return propiedades_nuevas


    def ejecutar_scraper(self, limite=200):


        print("Iniciando extracción de Corotos...\n")


        numero_pagina = 1


        while len(self.propiedades) < limite:


            nuevas = self.extraer_pagina(numero_pagina, limite)


            if nuevas == 0:
                print("No se encontraron propiedades nuevas.")
                break


            numero_pagina += 1


            if len(self.propiedades) < limite:
                time.sleep(1)


        df = pd.DataFrame(
            self.propiedades,
            columns=[
                "source",
                "name",
                "price",
                "location",
                "seller",
                "size",
                "bedrooms",
                "bathrooms",
                "parking"
            ]
        )


        print("\nExtracción finalizada.")
        print("Total de propiedades:", len(df))
        print("Total de IDs únicos:", len(self.ids_vistos))


        return df

"""## Scraper: SuperCasas

"""

class SuperCasasScraper:
    def __init__(self):
        self.url_principal = "https://www.supercasas.com/buscar/"
        self.urls_respaldo = [
            "https://www.supercasas.com/apartamentos/",
            "https://www.supercasas.com/casas/",
            "https://www.supercasas.com/villas/",
            "https://www.supercasas.com/oficinas/",
        ]
        self.urls = [self.url_principal] + self.urls_respaldo
        self.url_actual = self.urls[0]
        self.parametro_pagina = "PagingPageSkip"
        self.primera_pagina = 0
        self.max_paginas = 50
        self.quitar_repetidos = True
        self.dominio = "https://www.supercasas.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0"
        }
        self.selector_anuncio = "#bigsearch-results-inner-results li[data-id]"
        self.propiedades = []
        self.ids_vistos = set()
        self.claves_vistas = set()
        self.tiempos_solicitudes = []
    def construir_url(self, numero_pagina):
        valor = numero_pagina - 1 + self.primera_pagina
        union = "&" if "?" in self.url_actual else "?"
        return f"{self.url_actual}{union}{self.parametro_pagina}={valor}"
    def limpiar(self, texto):
        if not texto:
            return None
        return " ".join(texto.split())
    def formatear(self, valor, singular, plural):
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            return valor
        if numero == int(numero):
            numero = int(numero)
        palabra = singular if numero == 1 else plural
        return f"{numero} {palabra}"
    def leer_caracteristicas(self, anuncio):
        caracteristicas = {}
        for etiqueta in anuncio.select("section label"):
            texto = etiqueta.get_text(" ", strip=True)
            if ":" in texto:
                nombre, valor = texto.split(":", 1)
                caracteristicas[nombre.strip()] = valor.strip()
        return caracteristicas
    def leer_precio_venta(self, anuncio):
        for linea in anuncio.select("div.title2"):
            texto = linea.get_text(" ", strip=True)
            if texto.lower().startswith("venta"):
                return texto.split(":", 1)[1].strip()
        return None
    def extraer_propiedad(self, anuncio):
        listing_id = anuncio.get("data-id")
        tipo = anuncio.select_one("div.type")
        sector = anuncio.select_one("div.title1")
        tipo = tipo.get_text(" ", strip=True) if tipo else None
        sector = sector.get_text(" ", strip=True) if sector else None
        partes = [parte for parte in (tipo, sector) if parte]
        nombre = self.limpiar(" - ".join(partes)) if partes else None
        sector = self.limpiar(sector)
        datos = self.leer_caracteristicas(anuncio)
        tamano = datos.get("Construcción") or datos.get("Terreno")
        if tamano:
            tamano = re.sub(r"mt2|m2", "m²", tamano, flags=re.IGNORECASE)
        habitaciones = self.formatear(datos.get("Habitaciones"), "hab", "habs") if "Habitaciones" in datos else None
        banos = self.formatear(datos.get("Baños"), "baño", "baños") if "Baños" in datos else None
        parqueos = self.formatear(datos.get("Parqueos"), "parqueo", "parqueos") if "Parqueos" in datos else None
        propiedad = {
            "source": "SuperCasas",
            "name": nombre,
            "price": self.leer_precio_venta(anuncio),
            "location": sector,
            "seller": None,
            "size": tamano,
            "bedrooms": habitaciones,
            "bathrooms": banos,
            "parking": parqueos
        }
        return listing_id, propiedad
    def obtener_vendedor(self, enlace):
        inicio = time.time()
        url_detalle = self.dominio + enlace
        try:
            respuesta = requests.get(
                url_detalle,
                headers=self.headers,
                timeout=30
            )
            respuesta.raise_for_status()
            estado = respuesta.status_code
            soup = BeautifulSoup(respuesta.text, "html.parser")
            nombre = soup.select_one("#detail-right h3")
            vendedor = self.limpiar(nombre.get_text()) if nombre else None
        except requests.RequestException:
            estado = "error"
            vendedor = None
        self.tiempos_solicitudes.append({
            "pagina": "detalle " + enlace.strip("/").split("/")[-1],
            "duracion": round(time.time() - inicio, 2),
            "estado": estado
        })
        time.sleep(0.5)
        return vendedor
    def extraer_pagina(self, numero_pagina, limite=200):
        inicio = time.time()
        url_pagina = self.construir_url(numero_pagina)
        respuesta = requests.get(
            url_pagina,
            headers=self.headers,
            timeout=30
        )
        respuesta.raise_for_status()
        duracion = round(time.time() - inicio, 2)
        soup = BeautifulSoup(respuesta.text, "html.parser")
        anuncios = soup.select(self.selector_anuncio)
        propiedades_nuevas = 0
        repetidas = 0
        for anuncio in anuncios:
            if len(self.propiedades) >= limite:
                break
            listing_id, propiedad = self.extraer_propiedad(anuncio)
            if not listing_id or not propiedad["price"]:
                continue
            if listing_id in self.ids_vistos:
                repetidas += 1
                continue
            self.ids_vistos.add(listing_id)
            clave = (
                propiedad["name"], propiedad["price"], propiedad["size"],
                propiedad["bedrooms"], propiedad["bathrooms"], propiedad["parking"]
            )
            if self.quitar_repetidos and clave in self.claves_vistas:
                repetidas += 1
                continue
            self.claves_vistas.add(clave)
            enlace = anuncio.select_one("a[href]")
            if enlace:
                propiedad["seller"] = self.obtener_vendedor(enlace["href"])
            self.propiedades.append(propiedad)
            propiedades_nuevas += 1
        self.tiempos_solicitudes.append({
            "pagina": numero_pagina,
            "duracion": duracion,
            "estado": respuesta.status_code
        })
        print(
            "Página:", numero_pagina,
            "| Anuncios:", len(anuncios),
            "| Nuevas:", propiedades_nuevas,
            "| Repetidas:", repetidas,
            "| Tiempo:", duracion, "segundos"
        )
        return propiedades_nuevas
    def ejecutar_scraper(self, limite=200):
        print("Iniciando extracción de SuperCasas...")
        for numero_busqueda, url_base in enumerate(self.urls, start=1):
            if len(self.propiedades) >= limite:
                break
            self.url_actual = url_base
            numero_pagina = 1
            paginas_sin_nuevas = 0
            if numero_busqueda == 1:
                print(f"\nBúsqueda principal: {url_base}")
            else:
                print(f"\nFaltan propiedades ({len(self.propiedades)} de {limite}). "
                      f"Probando apartado de respaldo: {url_base}")
            while len(self.propiedades) < limite and numero_pagina <= self.max_paginas:
                nuevas = self.extraer_pagina(numero_pagina, limite)
                if nuevas == 0:
                    paginas_sin_nuevas += 1
                else:
                    paginas_sin_nuevas = 0
                if paginas_sin_nuevas >= 2:
                    print("Esta búsqueda ya no tiene más propiedades nuevas.")
                    break
                numero_pagina += 1
                if len(self.propiedades) < limite:
                    time.sleep(1)
        df = pd.DataFrame(
            self.propiedades,
            columns=[
                "source",
                "name",
                "price",
                "location",
                "seller",
                "size",
                "bedrooms",
                "bathrooms",
                "parking"
            ]
        )
        print("\nExtracción finalizada.")
        print("Total de propiedades:", len(df))
        if len(df) < limite:
            print(f"OJO: se pidieron {limite} y solo se consiguieron {len(df)}.")
            print("Ya se consultaron la búsqueda principal y todos los apartados de respaldo.")
        return df

class PlusvalScraper:

    def __init__(self):


        self.url = "https://plusval.com.do/buscar?action=1&range_price_tag=0+-+2%2C000%2C000&coin=2&min_price=0.00&max_price=2000000.00&source=home&page=1"


        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
            "Accept-Language": "es-DO,es;q=0.9,en;q=0.8"
        }


        self.propiedades = []
        self.ids_vistos = set()
        self.tiempos_solicitudes = []


    def construir_url(self, numero_pagina):

        partes = urlparse(self.url)
        parametros = parse_qs(partes.query)
        parametros["page"] = [str(numero_pagina)]

        nueva_consulta = urlencode(parametros, doseq=True)
        return urlunparse((
            partes.scheme, partes.netloc, partes.path,
            partes.params, nueva_consulta, partes.fragment
        ))


    def obtener_texto_tarjeta(self, enlace):


        contenedor = enlace
        mejor_texto = enlace.get_text(" ", strip=True)

        for nivel in range(1, 6):
            if contenedor.parent:
                contenedor = contenedor.parent
                texto = contenedor.get_text(" ", strip=True)


                if len(texto) > len(mejor_texto):
                    mejor_texto = texto

                if len(texto) > 80 and re.search(r"US\$|RD\$", texto):
                    return texto, contenedor

        return mejor_texto, contenedor


    def extraer_propiedad(self, enlace):

        texto, tarjeta = self.obtener_texto_tarjeta(enlace)
        url_propiedad = enlace.get("href", "")


        coincidencia_id = re.search(r"(\d+)(?:/?$)", url_propiedad)
        listing_id = coincidencia_id.group(1) if coincidencia_id else url_propiedad


        precio_match = re.search(r"(US\$|RD\$)\s*[\d,.]+", texto, re.IGNORECASE)
        precio = precio_match.group(0).strip() if precio_match else None


        habitaciones = re.search(r"Habitaciones?\s*([\d.]+)", texto, re.IGNORECASE)
        banos = re.search(r"Baños?\s*([\d.]+)", texto, re.IGNORECASE)
        parqueos = re.search(r"Parqueos?\s*([\d.]+)", texto, re.IGNORECASE)
        construccion = re.search(r"Construcción\s*([\d,.]+)\s*M²", texto, re.IGNORECASE)


        nombre_match = re.search(
            r"DESTACADA\s*(.*?)\s*(?=US\\$|RD\\$)",
            texto,
            re.IGNORECASE
        )

        nombre = nombre_match.group(1).strip() if nombre_match else None


        if not nombre or len(nombre) < 8:
            nombre = url_propiedad.rstrip("/").split("/")[-1]
            nombre = re.sub(r"-\d+$", "", nombre).replace("-", " ").title()

        ubicacion = None
        if "DESTACADA" in texto:
            ubicacion = texto.split("DESTACADA")[0].strip()


        propiedad = {
            "source": "Plusval",
            "name": nombre,
            "price": precio,
            "location": ubicacion or None,
            "seller": None,
            "size": construccion.group(1) + " M²" if construccion else None,
            "bedrooms": habitaciones.group(1) if habitaciones else None,
            "bathrooms": banos.group(1) if banos else None,
            "parking": parqueos.group(1) if parqueos else None,
            "url": (
                "https://plusval.com.do" + url_propiedad
                if url_propiedad.startswith("/") else url_propiedad
            ),
            "listing_id": listing_id
        }

        return listing_id, propiedad


    def extraer_pagina(self, numero_pagina, limite=200):

        inicio = time.time()
        url_pagina = self.construir_url(numero_pagina)

        respuesta = requests.get(
            url_pagina,
            headers=self.headers,
            timeout=30
        )
        respuesta.raise_for_status()

        soup = BeautifulSoup(respuesta.text, "html.parser")


        enlaces = soup.select('a[href*="/propiedad/"]')

        propiedades_nuevas = 0

        for enlace in enlaces:

            if len(self.propiedades) >= limite:
                break

            listing_id, propiedad = self.extraer_propiedad(enlace)

            if listing_id and listing_id not in self.ids_vistos:
                self.ids_vistos.add(listing_id)
                self.propiedades.append(propiedad)
                propiedades_nuevas += 1

        duracion = round(time.time() - inicio, 2)

        self.tiempos_solicitudes.append({
            "pagina": numero_pagina,
            "duracion": duracion,
            "estado": respuesta.status_code,
            "anuncios_encontrados": len(enlaces)
        })

        print(
            "Página:", numero_pagina,
            "| Propiedades nuevas:", propiedades_nuevas,
            "| Tiempo:", duracion, "segundos"
        )

        return propiedades_nuevas


    def ejecutar_scraper(self, limite=200):

        print("Iniciando extracción de Plusval...\n")
        numero_pagina = 1

        while len(self.propiedades) < limite:

            nuevas = self.extraer_pagina(numero_pagina, limite)


            if nuevas == 0:
                print("No se encontraron propiedades nuevas. Proceso detenido.")
                break

            numero_pagina += 1

            if len(self.propiedades) < limite:
                time.sleep(1)


        columnas = [
            "source", "name", "price", "location", "seller",
            "size", "bedrooms", "bathrooms", "parking", "url", "listing_id"
        ]

        df = pd.DataFrame(self.propiedades, columns=columnas)

        print("\nExtracción finalizada.")
        print("Total de propiedades:", len(df))
        print("Total de IDs únicos:", len(self.ids_vistos))

        return df

def ejecutar_portal(clase, nombre, limite=200):
    inicio = time.perf_counter()
    try:
        instancia = clase()
        datos = instancia.ejecutar_scraper(limite=limite)
        registros = instancia.tiempos_solicitudes
        return datos, registros, None, round(time.perf_counter() - inicio, 3)
    except Exception as error:
        return pd.DataFrame(), [], str(error), round(time.perf_counter() - inicio, 3)

resultados_portales = {}
tiempos_solicitudes = []
errores = {}
duraciones_portales = {}

if EJECUTAR_SCRAPERS_EN_VIVO:
    for nombre, clase in [('Corotos', CorotosScraper), ('SuperCasas', SuperCasasScraper), ('Plusval', PlusvalScraper)]:
        tabla, tiempos, error, duracion = ejecutar_portal(clase, nombre, LIMITE_POR_PORTAL)
        resultados_portales[nombre] = tabla
        duraciones_portales[nombre] = duracion
        if error:
            errores[nombre] = error
        for registro in tiempos:
            tiempos_solicitudes.append({'fuente': nombre, **registro})
        tabla.rename(columns=COLUMNAS_ES).to_csv(CARPETA / f'{nombre.lower()}_extraido.csv', index=False, encoding='utf-8-sig')
    if not any(len(tabla) for tabla in resultados_portales.values()):
        raise RuntimeError('No se extrajeron propiedades. Revisa las URL, selectores y errores de cada portal.')
    datos = pd.concat([tabla for tabla in resultados_portales.values() if len(tabla)], ignore_index=True)
    origen_datos = 'extraccion_en_vivo'
else:
    datos = pd.read_csv(pd.io.common.BytesIO(zlib.decompress(base64.b64decode('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'))))
    origen_datos = 'excel_original_incorporado'

print('Origen:', origen_datos)
print('Registros recibidos:', len(datos))
display(datos.head())

columnas = ['source','name','price','location','seller','size','bedrooms','bathrooms','parking']
aliases = {'fuente':'source','fuente de info':'source','número de habitaciones':'bedrooms','número de baños':'bathrooms','número de parqueos':'parking','nombre':'name','precio':'price','ubicación':'location','ubicacion':'location','vendedor':'seller','tamaño':'size','tamano':'size','habitaciones':'bedrooms','baños':'bathrooms','banos':'bathrooms','parqueos':'parking'}
datos.columns = [aliases.get(str(c).strip().lower(),str(c).strip().lower()) for c in datos.columns]
for columna in columnas:
    if columna not in datos.columns:
        datos[columna] = pd.NA

def extraer_precio(valor):
    if pd.isna(valor): return None
    texto = str(valor).replace(' ','')
    encontrado = re.search(r'[\d][\d.,]*', texto)
    if not encontrado: return None
    numero = encontrado.group().strip('.,')
    if ',' in numero and '.' in numero:
        numero = numero.replace(',','') if numero.rfind('.') > numero.rfind(',') else numero.replace('.','').replace(',','.')
    elif numero.count(',') > 0:
        numero = numero.replace(',','') if len(numero.split(',')[-1]) == 3 else numero.replace(',','.')
    elif numero.count('.') > 1 or ('.' in numero and len(numero.split('.')[-1]) == 3):
        numero = numero.replace('.','')
    try: return float(numero)
    except ValueError: return None

datos['currency'] = datos['price'].astype(str).apply(lambda s: 'USD' if 'US$' in s or 'USD' in s.upper() else ('DOP' if 'RD$' in s or 'DOP' in s.upper() else 'Sin especificar'))
datos['price_numeric'] = datos['price'].apply(extraer_precio)
for columna in ['bedrooms','bathrooms','parking']:
    datos[columna] = pd.to_numeric(datos[columna],errors='coerce')
datos['source'] = datos['source'].astype('string').str.strip()
datos['name'] = datos['name'].astype('string').str.strip()
repetidas = int(datos.duplicated(subset=columnas).sum())
limpios = datos.drop_duplicates(subset=columnas).reset_index(drop=True)
print('Filas originales:',len(datos),'| Duplicadas:',repetidas,'| Filas únicas:',len(limpios))
limpios = limpios.rename(columns=COLUMNAS_ES)
columnas_es = [COLUMNAS_ES[c] for c in columnas]
display(limpios.groupby('fuente',dropna=False).size().rename('cantidad').reset_index())
display(limpios[columnas_es].isna().sum().rename('faltantes').to_frame())

inicio_reportes = time.perf_counter()
limpios.to_csv(CARPETA/'Propiedades_Consolidadas.csv',index=False,encoding='utf-8-sig')
limpios.to_excel(CARPETA/'Propiedades_Consolidadas.xlsx',index=False)
limpios.to_parquet(CARPETA/'Propiedades_Consolidadas.parquet',index=False)
limpios.to_json(CARPETA/'Propiedades_Consolidadas.json',orient='records',force_ascii=False,indent=2)
limpios.to_html(CARPETA/'Propiedades_Consolidadas.html',index=False)
print('Archivos de datos exportados.')

import subprocess, sys, textwrap
script_perfil = textwrap.dedent("""
import sys
import pandas as pd
from ydata_profiling import ProfileReport
archivo_entrada, archivo_salida = sys.argv[1:3]
df = pd.read_csv(archivo_entrada)
reporte = ProfileReport(df, title='Reporte de propiedades', minimal=True, explorative=False)
reporte.to_file(archivo_salida)
""")
script_path = CARPETA / '_crear_perfil.py'
script_path.write_text(script_perfil, encoding='utf-8')
proceso = subprocess.run([sys.executable, str(script_path), str(CARPETA/'Propiedades_Consolidadas.csv'), str(CARPETA/'Reporte_Profiling.html')], capture_output=True, text=True, timeout=900)
profiling_estado = 'generado' if proceso.returncode == 0 and (CARPETA/'Reporte_Profiling.html').exists() else 'error'
if profiling_estado != 'generado':
    (CARPETA/'Error_Profiling.txt').write_text(proceso.stdout + '\n' + proceso.stderr, encoding='utf-8')
    print('No se generó ydata-profiling. Revisa Error_Profiling.txt')
else:
    print('Reporte de ydata-profiling generado correctamente.')

precios = limpios.dropna(subset=['precio_numerico'])
maximo = precios.loc[precios['precio_numerico'].idxmax()].to_dict() if len(precios) else None
minimo = precios.loc[precios['precio_numerico'].idxmin()].to_dict() if len(precios) else None

def json_compatible(obj):
    if isinstance(obj,dict):return {str(k):json_compatible(v) for k,v in obj.items()}
    if isinstance(obj,list):return [json_compatible(v) for v in obj]
    if pd.isna(obj):return None
    if hasattr(obj,'item'):return obj.item()
    return obj

estado = {
    'fecha_hora_utc':datetime.now(timezone.utc).isoformat(),
    'autores':AUTORES,
    'origen_datos':origen_datos,
    'scraping_en_vivo_ejecutado':EJECUTAR_SCRAPERS_EN_VIVO,
    'cantidad_recibida':int(len(datos)),
    'cantidad_sin_duplicados':int(len(limpios)),
    'duplicados':repetidas,
    'cantidad_por_fuente':limpios.groupby('fuente',dropna=False).size().to_dict(),
    'duraciones_portales_segundos':duraciones_portales,
    'solicitudes_registradas':tiempos_solicitudes,
    'errores_scraping':errores,
    'duracion_generacion_reportes_segundos':round(time.perf_counter()-inicio_reportes,3),
    'reporte_profiling':profiling_estado,
    'precio_mayor':maximo,
    'precio_menor':minimo,
    'nota_precios':'No se convierten USD y DOP entre sí. Comparar extremos solo si comparten moneda.'
}
with open(CARPETA/'Estado_Scraping.json','w',encoding='utf-8') as archivo:
    json.dump(json_compatible(estado),archivo,ensure_ascii=False,indent=2)
print('Reporte:',profiling_estado)
print('JSON de estado guardado.')

import shutil
archivo_zip = shutil.make_archive('Proyecto_Resultados','zip',CARPETA)
print('Archivo de resultados:',archivo_zip)
try:
    from google.colab import files
    files.download(archivo_zip)
except ImportError:
    pass