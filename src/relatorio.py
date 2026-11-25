from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path


def serializar(valor):
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return format(valor, ".2f")
    if isinstance(valor, dict):
        return {str(k): serializar(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [serializar(item) for item in valor]
    return valor


def escrever_json(caminho: Path, valor) -> None:
    caminho.write_text(json.dumps(serializar(valor), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
