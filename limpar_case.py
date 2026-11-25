#!/usr/bin/env python3
"""Normalize supplied tribunal extracts without modifying their originals."""
from __future__ import annotations
import argparse, csv, json, re
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

CNJ = re.compile(r"^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$")

def parse_money(value):
    if value is None or value == "": raise ValueError("valor ausente")
    if isinstance(value, bool): raise ValueError("valor booleano inválido")
    if isinstance(value, (int, float, Decimal)): amount = Decimal(str(value))
    else:
        raw = str(value).strip()
        if "," in raw:
            if not re.fullmatch(r"-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2}", raw):
                raise ValueError(f"formato monetário ambíguo: {raw}")
            raw = raw.replace(".", "").replace(",", ".")
        amount = Decimal(raw)
    if not amount.is_finite() or amount.as_tuple().exponent < -2: raise ValueError("valor não finito ou com mais de 2 casas")
    return amount.quantize(Decimal("0.01"))

def parse_date(value):
    if not isinstance(value, str) or not value: raise ValueError("data ausente")
    if "T" not in value: return date.fromisoformat(value)
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None: raise ValueError("timestamp sem fuso")
    return dt.astimezone(timezone.utc).date()

def parse_payment_date(value):
    if isinstance(value, str) and re.fullmatch(r"\d{2}/\d{2}/\d{4}", value):
        return date.strptime(value, "%d/%m/%Y") if hasattr(date, "strptime") else datetime.strptime(value, "%d/%m/%Y").date()
    return date.fromisoformat(value)

def process_key(value):
    digits = re.sub(r"\D", "", value or "")
    return digits if len(digits) == 20 else None

def read_hub(path, issues):
    rows = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for line,row in enumerate(csv.DictReader(f),2):
            k=process_key(row.get("processo",""))
            if not k:
                issues.append({"kind":"rejected","source":"hub.csv","line":line,"reason":"número CNJ ausente/inválido"}); continue
            try: amount=parse_money(row["valor_face"]); presented=parse_date(row["apresentado_em"]); due=date.fromisoformat(row["prazo_pagamento"])
            except (ValueError,KeyError,InvalidOperation) as e:
                issues.append({"kind":"rejected","source":"hub.csv","line":line,"process_key":k,"reason":str(e)}); continue
            if k in rows:
                issues.append({"kind":"review","source":"hub.csv","line":line,"process_key":k,"reason":"duplicata de processo"}); continue
            rows[k]={"process_key":k,"processo":row["processo"],"ente_devedor":row["ente"],"valor_face":amount,"apresentado_em":presented,"prazo_hub":due,"source":"hub.csv","line":line}
    return rows

def read_court(path, issues):
    rows={}
    # The delivered sample contains legacy single-byte Portuguese text despite
    # the UTF-8 claim. Fall back only when UTF-8 decoding fails and report it.
    try:
        raw=path.read_bytes()
        try: content=raw.decode("utf-8-sig"); encoding="utf-8"
        except UnicodeDecodeError:
            content=raw.decode("cp1252"); encoding="cp1252"
            issues.append({"kind":"corrected","source":"tribunal.csv","reason":"bytes inválidos em UTF-8; decodificado como Windows-1252 para preservar acentos"})
    except OSError as e:
        raise ValueError(f"não foi possível ler {path}: {e}") from e
    import io
    with io.StringIO(content,newline="") as f:
        for line,row in enumerate(csv.DictReader(f,delimiter=";"),2):
            k=process_key(row.get("numero_processo",""))
            if not k:
                issues.append({"kind":"rejected","source":"tribunal.csv","line":line,"reason":"número CNJ ausente/inválido"}); continue
            try: amount=parse_money(row["valor_face"])
            except (ValueError,KeyError,InvalidOperation) as e:
                issues.append({"kind":"rejected","source":"tribunal.csv","line":line,"process_key":k,"reason":str(e)}); continue
            item={"process_key":k,"processo":row["numero_processo"],"ente_devedor":row["ente_devedor"],"valor_face":amount,"apresentado_em":None,"prazo_hub":None,"source":"tribunal.csv","line":line}
            if k in rows and rows[k]!=item:
                issues.append({"kind":"review","source":"tribunal.csv","line":line,"process_key":k,"reason":"duplicata conflitante"}); continue
            rows[k]=item
    return rows

def clean(data_dir):
    issues=[]; hub=read_hub(data_dir/"hub.csv",issues); court=read_court(data_dir/"tribunal.csv",issues); merged={}
    for k in sorted(hub.keys()|court.keys()):
        h,c=hub.get(k),court.get(k)
        if h and c:
            if h["valor_face"]!=c["valor_face"]: issues.append({"kind":"review","process_key":k,"reason":f"valor_face diverge: hub={h['valor_face']}, tribunal={c['valor_face']}"})
            if h["ente_devedor"].casefold()!=c["ente_devedor"].casefold(): issues.append({"kind":"review","process_key":k,"reason":f"ente_devedor diverge: hub={h['ente_devedor']}, tribunal={c['ente_devedor']}"})
            merged[k]={**c,"apresentado_em":h["apresentado_em"],"prazo_hub":h["prazo_hub"],"fonte_hub":h["line"]}
        else:
            src=h or c; merged[k]=src.copy()
            issues.append({"kind":"review","process_key":k,"reason":f"presente apenas em {src['source']}"})
    with (data_dir/"pagamentos.json").open(encoding="utf-8-sig") as f: events=json.load(f)
    candidates=defaultdict(list)
    for idx,e in enumerate(events,1):
        eid=e.get("evento_id")
        if not eid:
            issues.append({"kind":"rejected","source":"pagamentos.json","record":idx,"reason":"evento_id ausente"}); continue
        try:
            updated=datetime.fromisoformat(e["atualizado_em"].replace("Z","+00:00"))
            if updated.tzinfo is None: raise ValueError("atualizado_em sem fuso")
            candidates[eid].append((updated,idx,e))
        except (ValueError,KeyError,TypeError) as err:
            issues.append({"kind":"rejected","source":"pagamentos.json","record":idx,"event_id":eid,"reason":str(err)})
    selected={}
    for eid,versions in candidates.items():
        versions.sort(key=lambda x:(x[0],x[1])); selected[eid]=versions[-1]
        if len(versions)>1:
            issues.append({"kind":"corrected","source":"pagamentos.json","event_id":eid,"records":[v[1] for v in versions],"selected_record":versions[-1][1],"reason":"mantida versão com maior atualizado_em"})
    payments=[]
    for eid,(updated,idx,e) in sorted(selected.items()):
        try:
            k=process_key(e.get("processo",""))
            if not k or not CNJ.fullmatch(e.get("processo","")): raise ValueError("processo fora do formato CNJ documentado")
            if k not in merged: raise ValueError("processo não consta nas listas")
            typ=e.get("tipo")
            if typ not in ("pagamento","estorno"): raise ValueError(f"tipo inválido: {typ}")
            amount=parse_money(e.get("valor"))
            if amount<=0: raise ValueError("valor deve ser positivo; sinal não define semântica de estorno")
            paid=parse_payment_date(e["data_pagamento"])
            if "/" in e["data_pagamento"]:
                issues.append({"kind":"corrected","source":"pagamentos.json","record":idx,"event_id":eid,"reason":"data DD/MM/AAAA convertida para ISO"})
            payments.append({"evento_id":eid,"process_key":k,"processo":merged[k]["processo"],"tipo":typ,"valor":amount,"data_pagamento":paid,"atualizado_em":updated})
        except (ValueError,KeyError,TypeError,InvalidOperation) as err:
            issues.append({"kind":"rejected","source":"pagamentos.json","record":idx,"event_id":eid,"reason":str(err)})
    totals=defaultdict(lambda:Decimal("0.00"))
    for p in payments: totals[p["process_key"]]+=p["valor"] if p["tipo"]=="pagamento" else -p["valor"]
    for p in merged.values(): p["total_pago_liquido"]=totals[p["process_key"]]
    return list(merged.values()),payments,issues

def jsonable(o):
    if isinstance(o,(date,datetime)): return o.isoformat()
    if isinstance(o,Decimal): return str(o)
    if isinstance(o,dict): return {k:jsonable(v) for k,v in o.items()}
    if isinstance(o,list): return [jsonable(v) for v in o]
    return o

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",type=Path,default=Path("dados")); ap.add_argument("--output",type=Path,default=Path("saida")); a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=True); prec,pay,issues=clean(a.input)
    for name,obj in (("precatorios.json",prec),("pagamentos.json",pay),("relatorio.json",issues)):
        (a.output/name).write_text(json.dumps(jsonable(obj),ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Precatórios: {len(prec)}; pagamentos válidos: {len(pay)}; ocorrências: {len(issues)}")
if __name__=="__main__": main()
