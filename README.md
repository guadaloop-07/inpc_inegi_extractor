# INPC INEGI Extractor

Extractor independiente y minimalista del Índice Nacional de Precios al
Consumidor (INPC) publicado por el INEGI. Descarga series mensuales nacionales,
por entidad federativa y por ciudad, y las consolida en un único archivo CSV.

La configuración incluida contiene el índice general y ocho divisiones por
objeto del gasto para el nivel nacional, las 32 entidades y las 55 ciudades
del catálogo: 1,246 series en total.

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

Esto actualiza los XLS desde INEGI y genera `data/inpc_integrado.csv`, para que
el CSV incluya los últimos periodos publicados.

También se pueden indicar rutas distintas:

```bash
python descargar_inpc.py \
  --config inpc_config.yaml \
  --tmp-dir tmp \
  --output data/inpc_integrado.csv
```

Para reutilizar los XLS ya descargados, por ejemplo al reanudar una ejecución
interrumpida:

```bash
python descargar_inpc.py --use-cache
```


## Modos de funcionamiento

El programa construye primero un plan de series, lo valida y solo entonces inicia descargas. Sin filtros selecciona todo el catálogo; `--todo` expresa explícitamente el mismo comportamiento y no puede combinarse con filtros.

```bash
# Catálogo completo
python descargar_inpc.py
python descargar_inpc.py --todo

# Toda la desagregación, sólo nivel nacional
python descargar_inpc.py --nivel nacional

# Inspección sin peticiones a INEGI
python descargar_inpc.py --listar-series --nivel nacional

# Una selección puntual; cada filtro puede repetirse
python descargar_inpc.py --nivel estados --ubicacion sonora --indice alimentos
python descargar_inpc.py --nivel nacional --indice alimentos --indice transporte

# Series de un nivel o prefijo de ruta oficial
python descargar_inpc.py --listar-series --nivel-clasificacion sub_subgrupo
python descargar_inpc.py --listar-series --ruta "1. Alimentos, bebidas y tabaco"
```

Los filtros disponibles son `--nivel`, `--ubicacion`, `--indice`, `--clasificacion`, `--desagregacion`, `--nivel-clasificacion` y `--ruta`. Un valor desconocido o una combinación sin series disponibles termina con error antes de descargar.

### Descarga, reanudación y consolidación

Los XLS se guardan en `<tmp-dir>/<nivel>/<ubicacion>_<indice>.xls`; el valor predeterminado de `--tmp-dir` es `tmp/`. Por omisión se descargan de nuevo para que el CSV no quede desactualizado. Use `--use-cache` para reutilizar un archivo válido existente. El CSV se consolida solo con el plan seleccionado.

```bash
# Una serie pequeña, con resultados fuera del repositorio
python descargar_inpc.py --nivel nacional --indice pan_tortillas_cereales \
  --tmp-dir /tmp/inpc-prueba --output /tmp/inpc-prueba/inpc.csv

# Reanudar usando los XLS locales
python descargar_inpc.py --nivel nacional --indice pan_tortillas_cereales --use-cache
```

## Catálogo y diccionario de datos

El YAML admite el formato legado, donde `indices` mapea un nombre lógico directamente a un ID de serie, y un formato enriquecido para subseries con metadatos oficiales.

```yaml
pan_tortillas_cereales:
  serie: "583769"
  estructura: "112001300040"
  clasificacion: objeto_gasto
  desagregacion: alimentos
  nivel_clasificacion: sub_subgrupo
```

| Campo | Significado |
| --- | --- |
| `nombre` | Denominación oficial publicada por INEGI. |
| `ruta` | Secuencia de denominaciones oficiales desde el índice general hasta la serie. |
| `serie` / `idSerie` | Identificador opaco de la serie de tiempo de INEGI. No codifica el nivel jerárquico. |
| `estructura` | `idEstructura` de INEGI usado para solicitar la serie; una subserie puede usar una estructura distinta de su categoría padre. |
| `clasificacion` | Clasificador oficial: por ahora `objeto_gasto`. |
| `desagregacion` | Rama funcional dentro de la clasificación, por ejemplo `alimentos`. |
| `nivel_clasificacion` | Nivel oficial de la serie dentro del clasificador; alimenta el CSV. |

Para **Objeto del gasto**, INEGI organiza la desagregación como: `indice_general`, `grupo`, `subgrupo`, `sub_subgrupo`, `conjunto_generico` y `generico`. Los ocho rubros históricos del proyecto son `grupo`; las series más específicas no se infieren por los dígitos de su ID, sino por la metadata oficial del árbol de INEGI.

## Salida CSV

Cada ejecución produce un único CSV con una fila por período y serie. El orden de columnas es fijo:

```text
nivel_geografico,ubicacion,nivel_clasificacion,indice,anio,mes,valor
```

| Columna | Tipo | Descripción |
| --- | --- | --- |
| `nivel_geografico` | texto | Cobertura solicitada: `nacional`, `estados` o `ciudades`. |
| `ubicacion` | texto | Clave de la ubicación del catálogo, como `nacional` o `sonora`. |
| `nivel_clasificacion` | texto | Nivel de desagregación oficial de INEGI. |
| `indice` | texto | Nombre lógico estable de la serie en el catálogo. |
| `anio` | entero | Año del período mensual. |
| `mes` | entero | Mes del período, de 1 a 12. |
| `valor` | número | Valor del índice publicado por INEGI; no es una tasa de variación. |

Ejemplo:

```text
nacional,nacional,sub_subgrupo,pan_tortillas_cereales,2018,1,97.902300635729
```

Los directorios `data/`, `tmp/` y `.venv/` son locales y no se incluyen en Git.
