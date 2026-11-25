import unittest
from pathlib import Path
from unittest.mock import patch

from src.leitura import ErroLeitura, ler_csv, ler_json


class LeituraArquivosTest(unittest.TestCase):
    def setUp(self):
        self.dados = Path(__file__).resolve().parents[1] / "dados"

    def test_csv_hub_com_virgula_e_utf8(self):
        problemas = []
        linhas = ler_csv(self.dados / "hub.csv", problemas)

        self.assertEqual(len(linhas), 5)
        self.assertEqual(linhas[0]["processo"], "0012345-10.2019.8.26.0053")
        self.assertEqual(linhas[0]["ente"], "MUNICIPIO DE SAO PAULO")
        self.assertEqual(problemas, [])

    def test_csv_tribunal_com_ponto_e_virgula_e_fallback_windows1252(self):
        problemas = []
        linhas = ler_csv(self.dados / "tribunal.csv", problemas)

        self.assertEqual(len(linhas), 5)
        self.assertEqual(linhas[0]["valor_face"], "45.000,00")
        self.assertEqual(linhas[0]["ente_devedor"], "Município de São Paulo")
        self.assertEqual(problemas[0]["categoria"], "corrigido")
        self.assertIn("Windows-1252", problemas[0]["motivo"])

    def test_erro_de_leitura_informa_arquivo(self):
        caminho = self.dados / "hub.csv"
        with patch.object(Path, "read_bytes", side_effect=PermissionError("acesso negado")):
            with self.assertRaisesRegex(ErroLeitura, "hub.csv.*acesso negado"):
                ler_csv(caminho, [])

    def test_json_top_level_precisa_ser_lista_de_objetos(self):
        caminho = self.dados / "pagamentos.json"
        self.assertEqual(len(ler_json(caminho)), 13)
        with patch.object(Path, "open", side_effect=FileNotFoundError("não encontrado")):
            with self.assertRaisesRegex(ErroLeitura, "pagamentos.json.*não encontrado"):
                ler_json(caminho)


if __name__ == "__main__":
    unittest.main()
