import json
import unittest
from pathlib import Path

from src.main import executar


class IntegracaoTest(unittest.TestCase):
    def test_fontes_reais_geram_saida_sem_alterar_entradas(self):
        raiz = Path(__file__).resolve().parents[1]
        saida = raiz / "saida"
        hashes_antes = {p.name: p.read_bytes() for p in (raiz / "dados").iterdir()}
        executar(raiz / "dados", saida)
        hashes_depois = {p.name: p.read_bytes() for p in (raiz / "dados").iterdir()}
        self.assertEqual(hashes_antes, hashes_depois)
        saidas_primeira_execucao = {p.name: p.read_bytes() for p in saida.iterdir()}
        executar(raiz / "dados", saida)
        saidas_segunda_execucao = {p.name: p.read_bytes() for p in saida.iterdir()}
        self.assertEqual(saidas_primeira_execucao, saidas_segunda_execucao)
        for nome in ("precatorios.json", "pagamentos.json", "historico_pagamentos.json", "relatorio.json"):
            self.assertTrue((saida / nome).is_file())
            json.loads((saida / nome).read_text(encoding="utf-8"))
        pagamentos = json.loads((saida / "pagamentos.json").read_text(encoding="utf-8"))
        historico = json.loads((saida / "historico_pagamentos.json").read_text(encoding="utf-8"))
        self.assertEqual(len(historico), 10)
        self.assertEqual(len(pagamentos), 8)
        relatorio = json.loads((saida / "relatorio.json").read_text(encoding="utf-8"))
        self.assertTrue(any(p["categoria"] == "pendencia" and "valor_face divergente" in p["motivo"] for p in relatorio))
        ausencia = next(p for p in relatorio if "ausente em tribunal.csv" in p["motivo"])
        self.assertEqual(ausencia["linhas"]["tribunal.csv"], None)
        self.assertEqual(ausencia["linhas"]["hub.csv"], 6)
        self.assertTrue(any(p["categoria"] == "rejeitado" and p.get("evento_id") == "ev-004" for p in relatorio))
        self.assertTrue(any(p["categoria"] == "corrigido" and "Windows-1252" in p["motivo"] for p in relatorio))
        precatorios = json.loads((saida / "precatorios.json").read_text(encoding="utf-8"))
        primeiro = next(p for p in precatorios if p["processo_chave"] == "00123451020198260053")
        self.assertEqual(primeiro["prazo_calculado"], "2026-12-31")
        self.assertEqual(primeiro["origem_linhas"]["tribunal.csv"], 2)
        self.assertEqual(primeiro["origem_linhas"]["hub.csv"], 2)
        self.assertEqual(primeiro["ente_devedor_comparacao"], "equivalentes_apos_normalizacao")
        self.assertEqual(primeiro["ente_devedor_por_fonte"]["tribunal"], "Município de São Paulo")
        self.assertEqual(primeiro["ente_devedor_por_fonte"]["hub"], "MUNICIPIO DE SAO PAULO")
        timestamp = next(p for p in precatorios if p["processo_chave"] == "00456784320215020011")
        self.assertEqual(timestamp["ente_devedor_comparacao"], "divergentes")
        self.assertEqual(timestamp["ente_devedor_por_fonte"]["tribunal"], "União")
        self.assertEqual(timestamp["ente_devedor_por_fonte"]["hub"], "Município de Santos")
        self.assertIsNone(timestamp["prazo_calculado"])
        self.assertEqual(timestamp["apresentado_em_data_local"], "2025-04-02")
        estorno = next(p for p in precatorios if p["processo_chave"] == "00345673220188260405")
        self.assertTrue(estorno["pagamentos_pendentes"])
        self.assertIsNone(estorno["total_pago_liquido"])
        evento_invalido = next(p for p in precatorios if p["processo_chave"] == "00234562120208260053")
        self.assertTrue(evento_invalido["pagamentos_pendentes"])
        self.assertIsNone(evento_invalido["total_pago_liquido"])


if __name__ == "__main__":
    unittest.main()
