import unittest
from datetime import date
from decimal import Decimal

from src.normalizacao import calcular_prazo, interpretar_data, normalizar_processo, parsear_valor


class NormalizacaoTest(unittest.TestCase):
    def test_valores_brasileiros_com_decimal(self):
        self.assertEqual(parsear_valor("45.000,00"), Decimal("45000.00"))
        self.assertEqual(parsear_valor("2.500,50"), Decimal("2500.50"))

    def test_valores_invalidos_ou_ausentes(self):
        for valor in (None, "", "2,500.50"):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                parsear_valor(valor)

    def test_negativo_preservado_para_validacao_de_tipo(self):
        self.assertEqual(parsear_valor("-200.00"), Decimal("-200.00"))

    def test_data_iso_brasileira_e_timestamp_preservam_data_local(self):
        self.assertEqual(interpretar_data("2025-04-02").data_local, date(2025, 4, 2))
        self.assertEqual(interpretar_data("10/04/2025").data_local, date(2025, 4, 10))
        data = interpretar_data("2025-04-02T23:30:00-03:00")
        self.assertEqual(data.data_local, date(2025, 4, 2))
        self.assertEqual(data.fuso_original, "-0300")
        with self.assertRaises(ValueError):
            interpretar_data("2025-04-02T23:30:00")
        with self.assertRaises(ValueError):
            interpretar_data("31/02/2025")

    def test_cnj_formatado_e_sem_mascara_compartilham_chave(self):
        self.assertEqual(normalizar_processo("0023456-21.2020.8.26.0053"), "00234562120208260053")
        self.assertEqual(normalizar_processo("00234562120208260053"), "00234562120208260053")
        with self.assertRaises(ValueError):
            normalizar_processo("")

    def test_prazo_corte_2_de_abril_e_dia_seguinte(self):
        self.assertEqual(calcular_prazo(date(2025, 4, 2)), date(2026, 12, 31))
        self.assertEqual(calcular_prazo(date(2025, 4, 3)), date(2027, 12, 31))

    def test_data_bissexta(self):
        self.assertEqual(calcular_prazo(date(2024, 2, 29)), date(2025, 12, 31))


if __name__ == "__main__":
    unittest.main()
