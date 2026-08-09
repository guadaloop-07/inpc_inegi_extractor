#!/usr/bin/env python3
"""Descarga y consolida series mensuales del INPC publicadas por el INEGI."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yaml


MESES = {
    "Ene": 1,
    "Feb": 2,
    "Mar": 3,
    "Abr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Ago": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dic": 12,
}

NIVELES = ("nacional", "estados", "ciudades")
LOG = logging.getLogger("inpc")


def cargar_config(path: Path) -> dict[str, Any]:
    """Carga y valida la estructura mínima de la configuración YAML."""
    with path.open(encoding="utf-8") as archivo:
        config = yaml.safe_load(archivo)

    for seccion in ("inegi", "periodo"):
        if seccion not in config:
            raise ValueError(f"Falta la sección '{seccion}' en {path}")
    return config


def construir_body(config: dict[str, Any], estructura: str, serie: str) -> dict[str, Any]:
    """Construye los campos enviados al formulario de exportación del INEGI."""
    inegi = config["inegi"]
    periodo = config["periodo"]
    return {
        "INPtipoExporta": inegi["tipo_exporta"],
        "idEstructura": estructura,
        "_formato": inegi["formato"],
        "_anioI": periodo["anio_inicio"],
        "_anioF": periodo["anio_fin"],
        "_meta": inegi["meta"],
        "_tipo": inegi["tipo"],
        "_info": inegi["info"],
        "_orient": inegi["orientacion"],
        "esquema": inegi["esquema"],
        "st": inegi["st"],
        "inp": inegi["inp"],
        "cuadro": estructura,
        "_series": f"e|{serie},",
        "cvEstructura": estructura,
    }


def descargar_series(
    config: dict[str, Any], tmp_dir: Path, *, force: bool = False
) -> tuple[int, int, int]:
    """Descarga todas las series; reutiliza archivos existentes salvo con force."""
    endpoint = config["inegi"]["endpoint"]
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
    }
    descargadas = reutilizadas = errores = 0

    with requests.Session() as session:
        session.headers.update(headers)
        for nivel in NIVELES:
            carpeta = tmp_dir / nivel
            carpeta.mkdir(parents=True, exist_ok=True)
            for ubicacion, datos in config.get(nivel, {}).items():
                estructura = str(datos["idEstructura"])
                for indice, serie in datos["indices"].items():
                    destino = carpeta / f"{ubicacion}_{indice}.xls"
                    if destino.exists() and destino.stat().st_size > 0 and not force:
                        reutilizadas += 1
                        continue

                    LOG.info("Descargando %s / %s / %s", nivel, ubicacion, indice)
                    temporal = destino.with_suffix(".xls.part")
                    try:
                        respuesta = session.post(
                            endpoint,
                            data=construir_body(config, estructura, str(serie)),
                            timeout=60,
                        )
                        respuesta.raise_for_status()
                        if b"<html" in respuesta.content[:200].lower():
                            raise RuntimeError("el servidor respondió HTML en lugar de XLS")
                        if not respuesta.content.startswith(bytes.fromhex("d0cf11e0")):
                            raise RuntimeError("la respuesta no parece un archivo XLS válido")
                        temporal.write_bytes(respuesta.content)
                        temporal.replace(destino)
                        descargadas += 1
                    except Exception as error:
                        temporal.unlink(missing_ok=True)
                        errores += 1
                        LOG.error("Error en %s: %s", destino.name, error)

    return descargadas, reutilizadas, errores


def procesar_archivo(path: Path, nivel: str, ubicacion: str, indice: str) -> pd.DataFrame:
    """Convierte un XLS del INEGI al formato tabular común."""
    df = pd.read_excel(path, skiprows=16, header=None, usecols=[0, 1])
    df.columns = ["periodo", "valor"]
    df["periodo"] = df["periodo"].astype("string").str.strip()
    partes = df["periodo"].str.extract(r"^(Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Oct|Nov|Dic)\s+(\d{4})$")
    validas = partes.notna().all(axis=1)
    df = df.loc[validas].copy()
    partes = partes.loc[validas]
    df["anio"] = partes[1].astype(int)
    df["mes"] = partes[0].map(MESES).astype(int)
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["valor"])

    resultado = df[["anio", "mes", "valor"]].copy()
    resultado.insert(0, "indice", indice)
    resultado.insert(0, "ubicacion", ubicacion)
    resultado.insert(0, "nivel_geografico", nivel)
    return resultado


def consolidar_archivos(config: dict[str, Any], tmp_dir: Path, output: Path) -> int:
    """Consolida los XLS descargados en un CSV ordenado."""
    tablas: list[pd.DataFrame] = []
    for nivel in NIVELES:
        for ubicacion, datos in config.get(nivel, {}).items():
            for indice in datos["indices"]:
                archivo = tmp_dir / nivel / f"{ubicacion}_{indice}.xls"
                if not archivo.exists():
                    continue
                try:
                    tablas.append(procesar_archivo(archivo, nivel, ubicacion, indice))
                except Exception as error:
                    LOG.error("No se pudo procesar %s: %s", archivo.name, error)

    if not tablas:
        raise RuntimeError("No hay archivos XLS válidos para consolidar")

    resultado = pd.concat(tablas, ignore_index=True)
    resultado = resultado.sort_values(
        ["nivel_geografico", "ubicacion", "indice", "anio", "mes"]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    resultado.to_csv(output, index=False)
    return len(resultado)


def argumentos() -> argparse.Namespace:
    base = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=base / "inpc_config.yaml")
    parser.add_argument("--tmp-dir", type=Path, default=base / "tmp")
    parser.add_argument("--output", type=Path, default=base / "data" / "inpc_integrado.csv")
    parser.add_argument("--force", action="store_true", help="vuelve a descargar los XLS existentes")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = argumentos()
    config = cargar_config(args.config)
    descargadas, reutilizadas, errores = descargar_series(
        config, args.tmp_dir, force=args.force
    )
    registros = consolidar_archivos(config, args.tmp_dir, args.output)
    LOG.info(
        "Finalizado: %s descargas, %s reutilizadas, %s errores, %s registros en %s",
        descargadas,
        reutilizadas,
        errores,
        registros,
        args.output,
    )
    return 1 if errores else 0


if __name__ == "__main__":
    raise SystemExit(main())
