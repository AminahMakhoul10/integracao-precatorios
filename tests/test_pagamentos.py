import unittest
from decimal import Decimal

from src.pagamentos import processar_pagamentos


def evento(eid, valor, atualizado, tipo="pagamento"):
    return {"evento_id": eid, "processo": "0012345-10.2019.8.26.0053", "valor": valor,
            "data_pagamento": "2025-02-10", "tipo": tipo, "atualizado_em": atualizado}


class PagamentosTest(unittest.TestCase):
    processo = {"00123451020198260053"}

    def test_duplicata_identica_so_conta_uma_vez_e_preserva_historico(self):
        row = evento("ev-1", Decimal("10.00"), "2025-02-10T10:00:00-03:00")
        historico, efetivos, totais, pendentes = processar_pagamentos([row, row], self.processo, [])
        self.assertEqual(len(historico), 2)
        self.assertEqual(len(efetivos), 1)
        self.assertEqual(totais["00123451020198260053"], Decimal("10.00"))
        self.assertEqual(pendentes, set())

    def test_versao_atualizada_prevalece_mantendo_versoes(self):
        eventos = [evento("ev-1", Decimal("10.00"), "2025-02-10T10:00:00-03:00"),
                   evento("ev-1", Decimal("15.00"), "2025-02-11T10:00:00-03:00")]
        historico, efetivos, totais, pendentes = processar_pagamentos(eventos, self.processo, [])
        self.assertEqual(len(historico), 2)
        self.assertEqual(efetivos[0]["valor"], Decimal("15.00"))
        self.assertEqual(totais["00123451020198260053"], Decimal("15.00"))
        self.assertEqual(pendentes, set())

    def test_estorno_fica_pendente_sem_regra_confirmada(self):
        eventos = [evento("ev-p", Decimal("50.00"), "2025-02-10T10:00:00-03:00"),
                   evento("ev-e", Decimal("20.00"), "2025-02-11T10:00:00-03:00", "estorno")]
        problemas = []
        _, efetivos, totais, pendentes = processar_pagamentos(eventos, self.processo, problemas)
        self.assertEqual(totais["00123451020198260053"], Decimal("50.00"))
        self.assertEqual(pendentes, self.processo)
        self.assertEqual(len(efetivos), 2)
        self.assertTrue(any("não aplicado ao total" in p["motivo"] for p in problemas))

    def test_evento_de_processo_inexistente_e_rejeitado_com_evidencia(self):
        problemas = []
        _, efetivos, _, _ = processar_pagamentos([evento("ev-1", 10, "2025-02-10T10:00:00Z")], set(), problemas)
        self.assertEqual(efetivos, [])
        self.assertTrue(any("não encontrado" in p["motivo"] for p in problemas))

    def test_versoes_conflitantes_no_mesmo_instante_ficam_pendentes(self):
        rows = [evento("ev-1", 10, "2025-02-10T10:00:00Z"),
                evento("ev-1", 20, "2025-02-10T10:00:00Z")]
        problemas = []
        _, efetivos, _, pendentes = processar_pagamentos(rows, self.processo, problemas)
        self.assertEqual(efetivos, [])
        self.assertEqual(pendentes, self.processo)
        self.assertTrue(any(p["categoria"] == "pendencia" for p in problemas))

    def test_empate_conflitante_marca_os_dois_processos_pendentes(self):
        processo_2 = "00234562120208260053"
        rows = [evento("ev-1", 10, "2025-02-10T10:00:00Z"),
                evento("ev-1", 20, "2025-02-10T10:00:00Z")]
        rows[1]["processo"] = "0023456-21.2020.8.26.0053"
        _, efetivos, _, pendentes = processar_pagamentos(rows, self.processo | {processo_2}, [])
        self.assertEqual(efetivos, [])
        self.assertEqual(pendentes, self.processo | {processo_2})

    def test_versao_invalida_mais_nova_bloqueia_uso_de_versao_antiga(self):
        antiga = evento("ev-1", 10, "2025-02-10T10:00:00Z")
        nova_invalida = evento("ev-1", None, "2025-02-11T10:00:00Z")
        problemas = []
        _, efetivos, totais, pendentes = processar_pagamentos([antiga, nova_invalida], self.processo, problemas)
        self.assertEqual(efetivos, [])
        self.assertNotIn("00123451020198260053", totais)
        self.assertEqual(pendentes, self.processo)
        self.assertTrue(any("nenhuma versão efetiva escolhida" in p["motivo"] for p in problemas))


if __name__ == "__main__":
    unittest.main()
