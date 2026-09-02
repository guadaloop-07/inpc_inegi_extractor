#!/usr/bin/env python3
"""Exporta el catálogo oficial nacional por objeto del gasto a TSV."""
import argparse
import re
import requests

URL = "https://www.inegi.org.mx/app/indicesdeprecios/servicios/ArbolAjaxInteraccion.asmx/EstructuraInicial"
PATRON = re.compile(r"ShowMoreInformation\(\x27(\d+)\x27,\x27(\d+)\x27,\x27([^\x27]+)\x27")
PREFIJO = "112001300040001"

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", default="catalogo_objeto_gasto.tsv")
args = parser.parse_args()
respuesta = requests.post(URL, json={"idEstructura": "112001300040", "esquemaBD": 0, "paramFuente": "pf", "notas": []}, timeout=60)
respuesta.raise_for_status()
series = [(a, b, c) for a, b, c in PATRON.findall(respuesta.json()["d"]) if b.startswith(PREFIJO)]
with open(args.output, "w", encoding="utf-8") as salida:
    salida.write("id_serie\tclave_jerarquia\tnombre_oficial\n")
    for serie, clave, nombre in series:
        salida.write(f"{serie}\t{clave}\t{nombre}\n")
print(f"{len(series)} series escritas en {args.output}")
