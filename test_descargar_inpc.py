import unittest

from descargar_inpc import planificar_series, seleccionar_series

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
