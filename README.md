# INPC INEGI Extractor

Extractor independiente y minimalista del Índice Nacional de Precios al
Consumidor (INPC) publicado por el INEGI. Descarga series mensuales nacionales,
por entidad federativa y por ciudad, y las consolida en un único archivo CSV.

La configuración incluida contiene el índice general y ocho divisiones por
objeto del gasto para el nivel nacional, las 32 entidades y las 55 ciudades
del catálogo: 792 series en total.

## Requisitos

- Python 3.12 o posterior.
- Acceso a `www.inegi.org.mx`.

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Uso

Con los valores predeterminados:

```bash
python descargar_inpc.py
```

Esto conserva los XLS en `tmp/` y genera `data/inpc_integrado.csv`. Las
descargas existentes se reutilizan para poder reanudar una ejecución
interrumpida.

También se pueden indicar rutas distintas:

```bash
python descargar_inpc.py \
  --config inpc_config.yaml \
  --tmp-dir tmp \
  --output data/inpc_integrado.csv
```

Para volver a descargar archivos existentes:

```bash
python descargar_inpc.py --force
```

## Salida

El CSV contiene estas columnas:

```text
nivel_geografico,ubicacion,indice,anio,mes,valor
```

Los directorios `data/`, `tmp/` y `.venv/` son locales y no se incluyen en Git.
