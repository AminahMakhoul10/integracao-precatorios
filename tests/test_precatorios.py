import unittest
from decimal import Decimal

from src.precatorios import conciliar_precatorios


PROCESSO = "0012345-10.2019.8.26.0053"


def fontes_com_nomes(nome_tribunal, nome_hub):
    return {
        "tribunal": [{
            "numero_processo": PROCESSO,
            "ente_devedor": nome_tribunal,
            "valor_face": "45.000,00",
        }],
        "hub": [{
            "processo": PROCESSO,
            "ente": nome_hub,
            "valor_face": "45000.00",
        }],
        "apresentacoes": [],
    }


class ConciliacaoNomesTest(unittest.TestCase):
    def test_caixa_acentos_e_espacos_sao_equivalentes_e_originais_sao_preservados(self):
        tribunal = "Município de São Paulo"
        hub = "  MUNICIPIO   DE SAO PAULO  "
        problemas = []

        resultado = conciliar_precatorios(
            fontes_com_nomes(tribunal, hub), problemas, {}, set()
        )[0]

        self.assertEqual(resultado["ente_devedor_comparacao"], "equivalentes_apos_normalizacao")
        self.assertEqual(resultado["ente_devedor_por_fonte"], {"tribunal": tribunal, "hub": hub})
        self.assertFalse(any("ente_devedor divergente" in p["motivo"] for p in problemas))
        self.assertTrue(any(p["categoria"] == "informativo" for p in problemas))

    def test_nomes_realmente_diferentes_continuam_pendentes(self):
        problemas = []

        resultado = conciliar_precatorios(
            fontes_com_nomes("União", "Município de Santos"), problemas, {}, set()
        )[0]

        self.assertEqual(resultado["ente_devedor_comparacao"], "divergentes")
        self.assertEqual(
            resultado["ente_devedor_por_fonte"],
            {"tribunal": "União", "hub": "Município de Santos"},
        )
        divergencia = next(p for p in problemas if "ente_devedor divergente" in p["motivo"])
        self.assertIn("União", divergencia["motivo"])
        self.assertIn("Município de Santos", divergencia["motivo"])


if __name__ == "__main__":
    unittest.main()
