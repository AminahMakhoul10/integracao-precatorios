from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from .normalizacao import interpretar_data, normalizar_processo, parsear_valor, validar_formato_cnj


def processar_pagamentos(eventos: list[dict], processos: set[str], problemas: list[dict]):
    historico: list[dict] = []
    por_evento: dict[str, list[dict]] = defaultdict(list)
    versoes_invalidas: dict[str, list[dict]] = defaultdict(list)
    processos_pendentes: set[str] = set()
    for numero, original in enumerate(eventos, 1):
        evento = dict(original)
        event_id = evento.get("evento_id")
        if not event_id:
            problemas.append({"categoria": "rejeitado", "arquivo": "pagamentos.json", "registro": numero, "motivo": "evento_id ausente"})
            try:
                processos_pendentes.add(normalizar_processo(str(evento.get("processo", ""))))
            except ValueError:
                pass
            continue
        try:
            atualizado = datetime.fromisoformat(str(evento["atualizado_em"]).replace("Z", "+00:00"))
            if atualizado.tzinfo is None:
                raise ValueError("atualizado_em sem fuso")
            processo = normalizar_processo(str(evento.get("processo", "")))
            if not validar_formato_cnj(str(evento.get("processo", ""))):
                problemas.append({"categoria": "corrigido", "arquivo": "pagamentos.json", "registro": numero, "evento_id": event_id, "motivo": "formatação do processo normalizada para chave de 20 dígitos; valor original preservado"})
            tipo = evento.get("tipo")
            if tipo not in ("pagamento", "estorno"):
                raise ValueError(f"tipo desconhecido: {tipo}")
            valor = parsear_valor(evento.get("valor"))
            if valor <= 0:
                raise ValueError("valor deve ser positivo; evento negativo não será reinterpretado como estorno")
            data_pagamento = interpretar_data(str(evento.get("data_pagamento", "")))
            convertido = {
                "evento_id": str(event_id),
                "processo_chave": processo,
                "processo_original": evento.get("processo"),
                "tipo": tipo,
                "valor": valor,
                "data_pagamento_original": data_pagamento.original,
                "data_pagamento": data_pagamento.data_local,
                "atualizado_em_original": evento["atualizado_em"],
                "atualizado_em": atualizado,
                "registro_origem": numero,
                "registro_original": evento,
            }
            historico.append(convertido)
            por_evento[str(event_id)].append(convertido)
        except (ValueError, KeyError, TypeError) as exc:
            problemas.append({"categoria": "rejeitado", "arquivo": "pagamentos.json", "registro": numero, "evento_id": event_id, "registro_original": evento, "motivo": str(exc)})
            processo_invalido = None
            try:
                processo_invalido = normalizar_processo(str(evento.get("processo", "")))
            except (ValueError, KeyError, TypeError):
                pass
            try:
                atualizado_invalido = datetime.fromisoformat(str(evento["atualizado_em"]).replace("Z", "+00:00"))
                if atualizado_invalido.tzinfo is None:
                    atualizado_invalido = None
            except (ValueError, KeyError, TypeError):
                atualizado_invalido = None
            if event_id:
                versoes_invalidas[str(event_id)].append({
                    "atualizado_em": atualizado_invalido,
                    "registro": numero,
                    "processo_chave": processo_invalido,
                })

    efetivos = []
    for event_id in sorted(por_evento.keys() | versoes_invalidas.keys()):
        versoes = por_evento.get(event_id, [])
        if not versoes:
            processos_pendentes.update(
                v["processo_chave"] for v in versoes_invalidas[event_id] if v["processo_chave"]
            )
            continue
        if len(versoes) > 1:
            problemas.append({
                "categoria": "duplicado",
                "arquivo": "pagamentos.json",
                "evento_id": event_id,
                "registros": [v["registro_origem"] for v in versoes],
                "motivo": "histórico preservado; será selecionada a versão válida mais recente",
            })
        mais_recente = max(v["atualizado_em"] for v in versoes)
        candidatas = [v for v in versoes if v["atualizado_em"] == mais_recente]
        assinaturas = {(v["processo_chave"], v["tipo"], v["valor"], v["data_pagamento"]) for v in candidatas}
        if len(assinaturas) > 1:
            processos_pendentes.update(v["processo_chave"] for v in candidatas)
            problemas.append({"categoria": "pendencia", "arquivo": "pagamentos.json", "evento_id": event_id, "motivo": "versões conflitantes têm o mesmo atualizado_em; nenhuma versão efetiva escolhida"})
            continue
        efetivo = candidatas[-1]
        invalidas_mais_novas = [
            item for item in versoes_invalidas.get(event_id, [])
            if item["atualizado_em"] is None or item["atualizado_em"] >= mais_recente
        ]
        if invalidas_mais_novas:
            processos_pendentes.add(efetivo["processo_chave"])
            processos_pendentes.update(
                item["processo_chave"] for item in invalidas_mais_novas if item["processo_chave"]
            )
            problemas.append({
                "categoria": "pendencia",
                "arquivo": "pagamentos.json",
                "evento_id": event_id,
                "registros_invalidos": [item["registro"] for item in invalidas_mais_novas],
                "motivo": "há versão inválida tão nova ou mais nova que a última versão válida; nenhuma versão efetiva escolhida",
            })
            continue
        if len(versoes) > 1:
            if len(assinaturas) == 1 and len(candidatas) > 1:
                problemas.append({"categoria": "duplicado", "arquivo": "pagamentos.json", "evento_id": event_id, "motivo": "duplicata idêntica; contabilizada uma única vez"})
            elif efetivo is not versoes[0]:
                problemas.append({"categoria": "corrigido", "arquivo": "pagamentos.json", "evento_id": event_id, "registros": [v["registro_origem"] for v in versoes], "registro_efetivo": efetivo["registro_origem"], "motivo": "versão mais recente selecionada e versões anteriores mantidas no histórico"})
        if efetivo["processo_chave"] not in processos:
            problemas.append({"categoria": "rejeitado", "arquivo": "pagamentos.json", "registro": efetivo["registro_origem"], "evento_id": event_id, "motivo": "processo não encontrado em nenhuma fonte cadastral"})
            continue
        efetivos.append(efetivo)

    totais: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for pagamento in efetivos:
        if pagamento["tipo"] == "estorno":
            processos_pendentes.add(pagamento["processo_chave"])
            problemas.append({
                "categoria": "pendencia",
                "arquivo": "pagamentos.json",
                "registro": pagamento["registro_origem"],
                "evento_id": pagamento["evento_id"],
                "processo_chave": pagamento["processo_chave"],
                "motivo": "estorno preservado, mas não aplicado ao total; relação com pagamento e regra de compensação não documentadas",
            })
            continue
        totais[pagamento["processo_chave"]] += pagamento["valor"]
    return historico, efetivos, totais, processos_pendentes
