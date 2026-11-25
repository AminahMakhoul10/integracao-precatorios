from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

CNJ_FORMATADO = re.compile(r"^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$")


def normalizar_processo(valor: str) -> str:
    digitos = re.sub(r"\D", "", valor or "")
    if len(digitos) != 20:
        raise ValueError("processo deve conter os 20 dígitos CNJ")
    return digitos


def validar_formato_cnj(valor: str) -> bool:
    return bool(CNJ_FORMATADO.fullmatch(valor or ""))


def parsear_valor(valor: object) -> Decimal:
    if valor is None or isinstance(valor, bool):
        raise ValueError("valor ausente ou inválido")
    if isinstance(valor, Decimal):
        numero = valor
    elif isinstance(valor, (int, float)):
        numero = Decimal(str(valor))
    else:
        texto = str(valor).strip()
        if not texto:
            raise ValueError("valor ausente")
        if "," in texto:
            if not re.fullmatch(r"-?(?:\d{1,3}(?:\.\d{3})+|\d+),\d{1,2}", texto):
                raise ValueError(f"formato monetário ambíguo: {texto}")
            texto = texto.replace(".", "").replace(",", ".")
        try:
            numero = Decimal(texto)
        except InvalidOperation as exc:
            raise ValueError(f"valor monetário inválido: {texto}") from exc
    if not numero.is_finite() or numero.as_tuple().exponent < -2:
        raise ValueError("valor deve ser finito e ter no máximo duas casas decimais")
    return numero.quantize(Decimal("0.01"))


@dataclass(frozen=True)
class DataInterpretada:
    original: str
    data_local: date
    timestamp: bool
    fuso_original: str | None


def interpretar_data(valor: str) -> DataInterpretada:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError("data ausente")
    texto = valor.strip()
    try:
        if re.fullmatch(r"\d{2}/\d{2}/\d{4}", texto):
            data = datetime.strptime(texto, "%d/%m/%Y").date()
            return DataInterpretada(texto, data, False, None)
        if "T" not in texto:
            return DataInterpretada(texto, date.fromisoformat(texto), False, None)
        momento = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"data inválida: {texto}") from exc
    if momento.tzinfo is None:
        raise ValueError("timestamp precisa informar fuso horário")
    return DataInterpretada(texto, momento.date(), True, momento.strftime("%z"))


def calcular_prazo(data_apresentacao: date) -> date:
    """Aplica a regra literal do enunciado a uma data civil já definida."""
    ano_vencimento = data_apresentacao.year + (1 if (data_apresentacao.month, data_apresentacao.day) <= (4, 2) else 2)
    return date(ano_vencimento, 12, 31)


def chave_nome(valor: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", valor or "")
    return " ".join("".join(c for c in sem_acento if not unicodedata.combining(c)).casefold().split())
