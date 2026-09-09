import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from descargar_inpc import SeriePlan, argumentos, descargar_series, planificar_series, seleccionar_series

CONFIG = {"inegi": {}, "periodo": {}, "nacional": {"nacional": {"idEstructura": "1", "indices": {"indice_general": "10", "pan": {"serie": "11", "nivel_clasificacion": "sub_subgrupo", "ruta": ["1. Alimentos", "1.1 Alimentos"]}}}}}

class SeleccionSeriesTests(unittest.TestCase):
    def setUp(self):
        self.plan = planificar_series(CONFIG)

    def test_legado_asigna_indice_general(self):
        item = next(x for x in self.plan if x.indice == "indice_general")
        self.assertEqual(item.nivel_clasificacion, "indice_general")

    def test_catalogo_enriquecido_preserva_metadata(self):
        item = next(x for x in self.plan if x.indice == "pan")
        self.assertEqual(item.ruta[-1], "1.1 Alimentos")

    def test_filtra_por_ruta_y_nivel(self):
        resultado = seleccionar_series(self.plan, nivel=[], ubicacion=[], indice=[], clasificacion=[], desagregacion=[], nivel_clasificacion=["sub_subgrupo"], ruta=["1. Alimentos"])
        self.assertEqual([x.indice for x in resultado], ["pan"])

    def test_rechaza_valor_desconocido(self):
        with self.assertRaisesRegex(ValueError, "nivel no disponible"):
            seleccionar_series(self.plan, nivel=["ciudades"], ubicacion=[], indice=[], clasificacion=[], desagregacion=[], nivel_clasificacion=[], ruta=[])


class DescargaSeriesTests(unittest.TestCase):
    def setUp(self):
        self.plan = [SeriePlan("nacional", "nacional", "indice_general", "10", "1", "objeto_gasto", ("indice_general",), "indice_general", "indice_general")]
        self.config = {"inegi": {"endpoint": "https://ejemplo.test"}}

    def _crear_cache(self, tmp_dir: Path) -> Path:
        destino = tmp_dir / "nacional" / "nacional_indice_general.xls"
        destino.parent.mkdir()
        destino.write_bytes(b"XLS previo")
        return destino

    @patch("sys.argv", ["descargar_inpc.py"])
    def test_cache_esta_desactivada_por_defecto(self):
        self.assertFalse(argumentos().use_cache)

    @patch("descargar_inpc.construir_body", return_value={})
    @patch("descargar_inpc.requests.Session")
    def test_por_defecto_actualiza_un_xls_existente(self, session_cls, _construir_body):
        respuesta = session_cls.return_value.__enter__.return_value.post.return_value
        respuesta.content = bytes.fromhex("d0cf11e0") + b"XLS actualizado"

        with tempfile.TemporaryDirectory() as directorio:
            destino = self._crear_cache(Path(directorio))
            descargadas, reutilizadas, errores = descargar_series(self.config, Path(directorio), self.plan)
            self.assertEqual((descargadas, reutilizadas, errores), (1, 0, 0))
            self.assertEqual(destino.read_bytes(), bytes.fromhex("d0cf11e0") + b"XLS actualizado")

        session_cls.return_value.__enter__.return_value.post.assert_called_once()

    @patch("descargar_inpc.requests.Session")
    def test_use_cache_reutiliza_un_xls_existente(self, session_cls):
        with tempfile.TemporaryDirectory() as directorio:
            self._crear_cache(Path(directorio))
            descargadas, reutilizadas, errores = descargar_series(self.config, Path(directorio), self.plan, use_cache=True)

        self.assertEqual((descargadas, reutilizadas, errores), (0, 1, 0))
