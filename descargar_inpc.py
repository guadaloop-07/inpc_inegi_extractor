#!/usr/bin/env python3
"""Descarga y consolida series mensuales del INPC publicadas por el INEGI."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
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

@dataclass(frozen=True)
class SeriePlan:
    nivel: str
    ubicacion: str
    indice: str
    serie: str
    estructura: str
    clasificacion: str
    ruta: tuple[str, ...]
    desagregacion: str
    nivel_clasificacion: str


def planificar_series(config: Mapping[str, Any]) -> list[SeriePlan]:
    """Expande el catálogo legado o enriquecido a series seleccionables."""
    plan = []
    catalogo = config.get("catalogo", config)
    for nivel in NIVELES:
        for ubicacion, datos in catalogo.get(nivel, {}).items():
            for indice, valor in datos["indices"].items():
                meta = valor if isinstance(valor, Mapping) else {}
                serie = meta.get("serie", meta.get("idSerie", valor))
                if serie is None:
                    raise ValueError("La serie %r no declara un identificador" % indice)
                plan.append(SeriePlan(nivel, ubicacion, indice, str(serie), str(meta.get("estructura", datos["idEstructura"])), str(meta.get("clasificacion", datos.get("clasificacion", "objeto_gasto"))), tuple(meta.get("ruta", [indice])), str(meta.get("desagregacion", indice)), str(meta.get("nivel_clasificacion", "indice_general" if indice == "indice_general" else "grupo"))))
    if not plan:
        raise ValueError("El catálogo no contiene series")
    return plan


def seleccionar_series(plan: list[SeriePlan], **filtros: list[str]) -> list[SeriePlan]:
    """Valida filtros antes de iniciar las descargas."""
    seleccion = plan
    for filtro in ("nivel", "ubicacion", "indice", "clasificacion", "desagregacion", "nivel_clasificacion"):
        pedidos = filtros[filtro]
        if not pedidos:
            continue
        disponibles = {getattr(item, filtro).casefold() for item in plan}
        desconocidos = [valor for valor in pedidos if valor.casefold() not in disponibles]
        if desconocidos:
            raise ValueError("%s no disponible: %s" % (filtro, ", ".join(desconocidos)))
        permitidos = {valor.casefold() for valor in pedidos}
        seleccion = [item for item in seleccion if getattr(item, filtro).casefold() in permitidos]
    for ruta in filtros["ruta"]:
        seleccion = [item for item in seleccion if any(" > ".join(item.ruta[posicion:]).casefold().startswith(ruta.casefold()) for posicion in range(len(item.ruta)))]
    if filtros["ruta"] and not seleccion:
        raise ValueError("ruta no disponible para la selección solicitada")
    if not seleccion:
        raise ValueError("Los filtros no producen ninguna combinación disponible")
    return seleccion



def configurar_plan(config: dict[str, Any], plan: list[SeriePlan]) -> dict[str, Any]:
    seleccionada = {clave: valor for clave, valor in config.items() if clave != "catalogo"}
    for nivel in NIVELES:
        seleccionada[nivel] = {}
    for item in plan:
        destino = seleccionada[item.nivel].setdefault(item.ubicacion, {"idEstructura": item.estructura, "indices": {}})
        destino["indices"][item.indice] = item.serie
    return seleccionada
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


def descargar_series(config: dict[str, Any], tmp_dir: Path, plan: list[SeriePlan], *, use_cache: bool = False) -> tuple[int, int, int]:
    """Descarga el plan y reutiliza XLS previos únicamente bajo petición."""
    descargadas = reutilizadas = errores = 0
    with requests.Session() as session:
        session.headers.update({"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mozilla/5.0"})
        for item in plan:
            destino = tmp_dir / item.nivel / f"{item.ubicacion}_{item.indice}.xls"
            destino.parent.mkdir(parents=True, exist_ok=True)
            if destino.exists() and destino.stat().st_size > 0 and use_cache:
                reutilizadas += 1
                continue
            try:
                respuesta = session.post(config["inegi"]["endpoint"], data=construir_body(config, item.estructura, item.serie), timeout=60)
                respuesta.raise_for_status()
                if not respuesta.content.startswith(bytes.fromhex("d0cf11e0")):
                    raise RuntimeError("la respuesta no parece un archivo XLS válido")
                temporal = destino.with_suffix(".xls.part")
                temporal.write_bytes(respuesta.content)
                temporal.replace(destino)
                descargadas += 1
            except Exception as error:
                errores += 1
                LOG.error("Error en %s: %s", destino.name, error)
    return descargadas, reutilizadas, errores




def procesar_archivo(path: Path, nivel: str, ubicacion: str, nivel_clasificacion: str, indice: str) -> pd.DataFrame:
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
    resultado.insert(0, "nivel_clasificacion", nivel_clasificacion)
    resultado.insert(0, "ubicacion", ubicacion)
    resultado.insert(0, "nivel_geografico", nivel)
    return resultado




def argumentos() -> argparse.Namespace:
    base = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=base / "inpc_config.yaml")
    parser.add_argument("--tmp-dir", type=Path, default=base / "tmp")
    parser.add_argument("--output", type=Path, default=base / "data" / "inpc_integrado.csv")
    parser.add_argument("--use-cache", action="store_true", help="reutiliza los XLS existentes; útil para reanudar una ejecución")
    parser.add_argument("--force", action="store_false", dest="use_cache", help=argparse.SUPPRESS)
    parser.add_argument("--nivel", action="append", default=[], help="nivel geográfico (repetible)")
    parser.add_argument("--ubicacion", action="append", default=[], help="ubicación (repetible)")
    parser.add_argument("--indice", action="append", default=[], help="índice lógico (repetible)")
    parser.add_argument("--clasificacion", action="append", default=[], help="clasificación (repetible)")
    parser.add_argument("--desagregacion", action="append", default=[], help="desagregación (repetible)")
    parser.add_argument("--nivel-clasificacion", action="append", default=[], help="nivel oficial INEGI (repetible)")
    parser.add_argument("--ruta", action="append", default=[], help="prefijo de ruta oficial (repetible)")
    parser.add_argument("--listar-series", action="store_true", help="muestra el plan sin descargar")
    parser.add_argument("--todo", action="store_true", help="descarga todo el catálogo disponible")
    args = parser.parse_args()
    if args.todo and any((args.nivel, args.ubicacion, args.indice, args.clasificacion, args.desagregacion, args.nivel_clasificacion, args.ruta)):
        parser.error("--todo no se puede combinar con filtros restrictivos")
    return args
def consolidar_archivos(tmp_dir: Path, output: Path, plan: list[SeriePlan]) -> int:
    """Consolida exclusivamente los XLS del plan seleccionado."""
    tablas = []
    for item in plan:
        archivo = tmp_dir / item.nivel / f"{item.ubicacion}_{item.indice}.xls"
        if archivo.exists():
            try:
                tablas.append(procesar_archivo(archivo, item.nivel, item.ubicacion, item.nivel_clasificacion, item.indice))
            except Exception as error:
                LOG.error("No se pudo procesar %s: %s", archivo.name, error)
    if not tablas:
        raise RuntimeError("No hay archivos XLS válidos para consolidar")
    resultado = pd.concat(tablas, ignore_index=True).sort_values(["nivel_geografico", "ubicacion", "nivel_clasificacion", "indice", "anio", "mes"])
    output.parent.mkdir(parents=True, exist_ok=True)
    resultado.to_csv(output, index=False)
    return len(resultado)




def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = argumentos()
    config = cargar_config(args.config)
    try:
        plan = seleccionar_series(planificar_series(config), nivel=args.nivel, ubicacion=args.ubicacion, indice=args.indice, clasificacion=args.clasificacion, desagregacion=args.desagregacion, nivel_clasificacion=args.nivel_clasificacion, ruta=args.ruta)
    except ValueError as error:
        LOG.error("Selección inválida: %s", error)
        return 2
    LOG.info("Plan de descarga: %s series", len(plan))
    if args.listar_series:
        for item in plan:
            print("\t".join((item.nivel, item.ubicacion, item.indice, item.clasificacion, item.desagregacion, item.serie)))
        return 0

    descargadas, reutilizadas, errores = descargar_series(config, args.tmp_dir, plan, use_cache=args.use_cache)
    registros = consolidar_archivos(args.tmp_dir, args.output, plan)
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
