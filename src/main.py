from __future__ import annotations

import argparse
from pathlib import Path

from .leitura import ErroLeitura, ler_fontes
from .normalizacao import normalizar_processo
from .pagamentos import processar_pagamentos
from .precatorios import conciliar_precatorios
from .relatorio import escrever_json


def executar(pasta_dados: Path, pasta_saida: Path) -> None:
    problemas: list[dict] = []
    fontes = ler_fontes(pasta_dados, problemas)
    chaves_precatorios = set()
    for nome in ("tribunal", "hub", "apresentacoes"):
        campo = "numero_processo" if nome == "tribunal" else "processo"
        for registro in fontes[nome]:
            try:
                chaves_precatorios.add(normalizar_processo(str(registro.get(campo, ""))))
            except ValueError:
                pass
    historico, pagamentos, totais, processos_pendentes = processar_pagamentos(fontes["pagamentos"], chaves_precatorios, problemas)
    precatorios = conciliar_precatorios(fontes, problemas, totais, processos_pendentes)
    pasta_saida.mkdir(parents=True, exist_ok=True)
    escrever_json(pasta_saida / "precatorios.json", precatorios)
    escrever_json(pasta_saida / "pagamentos.json", pagamentos)
    escrever_json(pasta_saida / "historico_pagamentos.json", historico)
    escrever_json(pasta_saida / "relatorio.json", problemas)
    print(f"Precatórios: {len(precatorios)}; pagamentos efetivos: {len(pagamentos)}; versões no histórico: {len(historico)}; ocorrências: {len(problemas)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Concilia e normaliza os arquivos do case.")
    parser.add_argument("--input", type=Path, default=Path("dados"), help="pasta com arquivos originais")
    parser.add_argument("--output", type=Path, default=Path("saida"), help="pasta de saída")
    argumentos = parser.parse_args()
    try:
        executar(argumentos.input, argumentos.output)
    except ErroLeitura as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
