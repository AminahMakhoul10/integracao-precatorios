from __future__ import annotations

from datetime import date
from decimal import Decimal

from .normalizacao import calcular_prazo, chave_nome, interpretar_data, normalizar_processo, parsear_valor


def _chave(valor, arquivo, linha, problemas):
    try:
        return normalizar_processo(str(valor or ""))
    except ValueError as exc:
        problemas.append({"categoria": "rejeitado", "arquivo": arquivo, "registro": linha, "motivo": str(exc), "valor_original": valor})
        return None


def conciliar_precatorios(fontes: dict, problemas: list[dict], totais: dict[str, Decimal], processos_pendentes: set[str]):
    por_fonte = {"tribunal.csv": {}, "hub.csv": {}, "apresentacoes.json": {}}
    for arquivo, registros, campo_processo in (
        ("tribunal.csv", fontes["tribunal"], "numero_processo"),
        ("hub.csv", fontes["hub"], "processo"),
        ("apresentacoes.json", fontes["apresentacoes"], "processo"),
    ):
        for linha, row in enumerate(registros, 2 if arquivo.endswith(".csv") else 1):
            chave = _chave(row.get(campo_processo), arquivo, linha, problemas)
            if not chave:
                continue
            if chave in por_fonte[arquivo]:
                problemas.append({"categoria": "pendencia", "arquivo": arquivo, "registro": linha, "processo_chave": chave, "motivo": "processo repetido na mesma fonte; registros mantidos para revisão"})
                continue
            por_fonte[arquivo][chave] = (row, linha)

    base = []
    for chave in sorted(set().union(*(set(fonte) for fonte in por_fonte.values()))):
        t = por_fonte["tribunal.csv"].get(chave)
        h = por_fonte["hub.csv"].get(chave)
        a = por_fonte["apresentacoes.json"].get(chave)
        tribunal = t[0] if t else None
        hub = h[0] if h else None
        apresentacao = a[0] if a else None
        valores = {}
        for label, registro, campo, arquivo, linha in (
            ("tribunal", tribunal, "valor_face", "tribunal.csv", t[1] if t else None),
            ("hub", hub, "valor_face", "hub.csv", h[1] if h else None),
        ):
            if registro is None:
                valores[label] = None
                continue
            try:
                valores[label] = parsear_valor(registro.get(campo))
            except ValueError as exc:
                valores[label] = None
                problemas.append({"categoria": "rejeitado", "arquivo": arquivo, "registro": linha, "processo_chave": chave, "motivo": str(exc)})
        if tribunal is None or hub is None:
            faltante = "hub.csv" if hub is None else "tribunal.csv"
            problemas.append({
                "categoria": "pendencia",
                "processo_chave": chave,
                "linhas": {"tribunal.csv": t[1] if t else None, "hub.csv": h[1] if h else None},
                "motivo": f"processo ausente em {faltante}; não inferir exclusão sem conhecer se o arquivo é completo",
            })
        elif valores["tribunal"] != valores["hub"]:
            problemas.append({
                "categoria": "pendencia",
                "processo_chave": chave,
                "linhas": {"tribunal.csv": t[1], "hub.csv": h[1]},
                "motivo": f"valor_face divergente: tribunal={valores['tribunal']}, hub={valores['hub']}; nenhuma fonte escolhida",
            })
        nomes = {
            "tribunal": tribunal.get("ente_devedor") if tribunal else None,
            "hub": hub.get("ente") if hub else None,
        }
        comparacao_ente = "fonte_ausente"
        if tribunal and hub:
            nome_tribunal = nomes["tribunal"]
            nome_hub = nomes["hub"]
            if not str(nome_tribunal or "").strip() or not str(nome_hub or "").strip():
                comparacao_ente = "nome_ausente"
                problemas.append({
                    "categoria": "pendencia",
                    "processo_chave": chave,
                    "linhas": {"tribunal.csv": t[1], "hub.csv": h[1]},
                    "motivo": "nome do ente devedor ausente em uma das fontes",
                })
            elif chave_nome(nome_tribunal) == chave_nome(nome_hub):
                comparacao_ente = "equivalentes_apos_normalizacao"
                if nome_tribunal != nome_hub:
                    problemas.append({
                        "categoria": "informativo",
                        "processo_chave": chave,
                        "linhas": {"tribunal.csv": t[1], "hub.csv": h[1]},
                        "nomes_originais": nomes,
                        "motivo": "nomes equivalentes após normalizar caixa, acentos e espaços; grafias originais preservadas",
                    })
            else:
                comparacao_ente = "divergentes"
                problemas.append({
                    "categoria": "pendencia",
                    "processo_chave": chave,
                    "linhas": {"tribunal.csv": t[1], "hub.csv": h[1]},
                    "motivo": f"ente_devedor divergente: tribunal={nome_tribunal!r}, hub={nome_hub!r}; nenhuma fonte escolhida",
                })

        data_original = apresentacao.get("apresentado_em") if apresentacao else (hub.get("apresentado_em") if hub else None)
        data_resultado = None
        prazo = None
        prazo_status = "sem data de apresentação"
        if data_original:
            try:
                data_resultado = interpretar_data(str(data_original))
                if data_resultado.timestamp:
                    prazo_status = "pendente: timestamp/fuso precisa ser interpretado conforme regra jurídica local"
                    problemas.append({"categoria": "pendencia", "processo_chave": chave, "motivo": f"apresentado_em é timestamp {data_original!r}; fuso legal do corte de 2 de abril não definido"})
                else:
                    prazo = calcular_prazo(data_resultado.data_local)
                    prazo_status = "calculado pela regra do enunciado"
            except ValueError as exc:
                prazo_status = f"data inválida: {exc}"
                problemas.append({"categoria": "rejeitado", "processo_chave": chave, "motivo": prazo_status})
        prazo_hub = None
        if hub and hub.get("prazo_pagamento"):
            try:
                prazo_hub = date.fromisoformat(hub["prazo_pagamento"])
                if prazo is not None and prazo_hub != prazo:
                    problemas.append({"categoria": "pendencia", "arquivo": "hub.csv", "registro": h[1], "processo_chave": chave, "motivo": f"prazo divergente: hub={prazo_hub}, calculado={prazo}"})
            except ValueError:
                problemas.append({"categoria": "rejeitado", "arquivo": "hub.csv", "registro": h[1], "processo_chave": chave, "motivo": "prazo_pagamento fora do formato ISO"})
        elif prazo is not None:
            problemas.append({"categoria": "pendencia", "processo_chave": chave, "motivo": "prazo calculado não pode ser comparado: hub sem prazo"})

        if apresentacao and hub and hub.get("apresentado_em") and str(hub["apresentado_em"]) != str(apresentacao.get("apresentado_em")):
            problemas.append({"categoria": "pendencia", "processo_chave": chave, "motivo": f"data de apresentação diverge: apresentações.json={apresentacao.get('apresentado_em')!r}, hub={hub.get('apresentado_em')!r}"})
        base.append({
            "processo_chave": chave,
            "processo_tribunal": tribunal.get("numero_processo") if tribunal else None,
            "processo_hub": hub.get("processo") if hub else None,
            "origem_linhas": {
                "tribunal.csv": t[1] if t else None,
                "hub.csv": h[1] if h else None,
                "apresentacoes.json": a[1] if a else None,
            },
            "ente_devedor_por_fonte": nomes,
            "ente_devedor_comparacao": comparacao_ente,
            "valor_face_por_fonte": valores,
            "apresentado_em_original": str(data_original) if data_original else None,
            "apresentado_em_data_local": data_resultado.data_local.isoformat() if data_resultado else None,
            "apresentado_em_fuso_original": data_resultado.fuso_original if data_resultado else None,
            "prazo_calculado": prazo.isoformat() if prazo else None,
            "prazo_hub": prazo_hub.isoformat() if prazo_hub else None,
            "status_prazo": prazo_status,
            "total_pagamentos_validos": totais.get(chave, Decimal("0.00")),
            "total_pago_liquido": None if chave in processos_pendentes else totais.get(chave, Decimal("0.00")),
            "pagamentos_pendentes": chave in processos_pendentes,
        })
    return base
