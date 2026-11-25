from __future__ import annotations

import csv
import io
import json
from decimal import Decimal
from pathlib import Path


class ErroLeitura(ValueError):
    """Falha identificável ao abrir ou interpretar um arquivo de entrada."""


def ler_json(caminho: Path):
    try:
        with caminho.open(encoding="utf-8-sig") as arquivo:
            dados = json.load(arquivo, parse_float=Decimal)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ErroLeitura(f"não foi possível ler {caminho}: {exc}") from exc
    if not isinstance(dados, list):
        raise ErroLeitura(f"{caminho} deve conter uma lista JSON")
    for indice, registro in enumerate(dados, 1):
        if not isinstance(registro, dict):
            raise ErroLeitura(f"{caminho}, item {indice}: cada registro deve ser um objeto JSON")
    return dados


def ler_csv(caminho: Path, problemas: list[dict]) -> list[dict]:
    try:
        conteudo = caminho.read_bytes()
    except OSError as exc:
        raise ErroLeitura(f"não foi possível ler {caminho}: {exc}") from exc
    try:
        texto = conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            texto = conteudo.decode("cp1252")
        except UnicodeDecodeError as exc:
            raise ErroLeitura(f"{caminho}: codificação não reconhecida como UTF-8 ou Windows-1252") from exc
        problemas.append({
            "categoria": "corrigido",
            "arquivo": caminho.name,
            "motivo": "arquivo não é UTF-8 válido; decodificado como Windows-1252 sem alterar o original",
        })
    primeira_linha = texto.splitlines()[0] if texto.splitlines() else ""
    delimitador = ";" if primeira_linha.count(";") > primeira_linha.count(",") else ","
    leitor = csv.DictReader(io.StringIO(texto, newline=""), delimiter=delimitador)
    colunas_esperadas = {
        "tribunal.csv": {"numero_processo", "ente_devedor", "valor_face"},
        "hub.csv": {"processo", "ente", "valor_face", "apresentado_em", "prazo_pagamento"},
    }.get(caminho.name)
    colunas_lidas = set(leitor.fieldnames or [])
    if colunas_esperadas and not colunas_esperadas.issubset(colunas_lidas):
        faltantes = ", ".join(sorted(colunas_esperadas - colunas_lidas))
        raise ErroLeitura(f"{caminho}: cabeçalho incompatível; faltam as colunas {faltantes}")
    return list(leitor)


def ler_fontes(pasta: Path, problemas: list[dict]) -> dict:
    tribunal = ler_csv(pasta / "tribunal.csv", problemas)
    hub = ler_csv(pasta / "hub.csv", problemas)
    pagamentos = ler_json(pasta / "pagamentos.json")
    apresentacoes = ler_json(pasta / "apresentacoes.json")
    return {
        "tribunal": tribunal,
        "hub": hub,
        "pagamentos": pagamentos,
        "apresentacoes": apresentacoes,
    }
