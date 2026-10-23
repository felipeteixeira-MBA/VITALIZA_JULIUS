"""Normalização, deduplicação funcional e agregação financeira auditável.

Taxas são calculadas em microreais inteiros: centavos × pontos-base.
Não se arredonda cada taxa por registro, pois o enunciado não define essa política.
Líquido aqui significa somente aprovado deduplicado menos taxas do enunciado.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import json,re
import numpy as np
import pandas as pd

DEFAULT_FEES = {"app_store": 1500, "google_play": 1500, "cartao": 350, "pix_automatico": 99}
DUPLICATE_KEY = ["user_id", "data_hora_brt", "valor_centavos", "metodo", "status", "tentativa"]
STATUSES = {"aprovado", "recusado", "estornado", "chargeback"}

def money_to_cents(value) -> int:
    if value is None or pd.isna(value):
        raise ValueError("Valor monetário ausente")
    s = str(value).strip().replace("R$", "").replace("\u00a0", "").replace(" ", "")
    if not re.fullmatch(r"[+-]?\d+(?:[.,]\d+)*", s):
        raise ValueError("Formato monetário inválido")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        d = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError("Valor monetário inválido") from exc
    if not d.is_finite() or d != d.quantize(Decimal("0.01")):
        raise ValueError("Valor deve ser finito, com precisão de centavos")
    return int(d * 100)

def brt_timestamps(values: pd.Series) -> pd.Series:
    """Offsets explícitos são respeitados; timestamps naive são assumidos Brasília."""
    s = values.astype("string").str.strip()
    aware = s.str.contains(r"Z$|[+-]\d\d:\d\d$", na=False)
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns, America/Sao_Paulo]")
    out.loc[aware] = pd.to_datetime(s[aware], format="mixed", utc=True, errors="coerce").dt.tz_convert("America/Sao_Paulo")
    local = pd.to_datetime(s[~aware], format="mixed", errors="coerce")
    out.loc[~aware] = local.dt.tz_localize("America/Sao_Paulo")
    if out.isna().any():
        raise ValueError(f"Datas de pagamento inválidas: {int(out.isna().sum())}")
    return out

@dataclass
class PaymentResult:
    normalized: pd.DataFrame
    unique: pd.DataFrame
    duplicates: pd.DataFrame
    monthly: pd.DataFrame

def aggregate_payments(raw: pd.DataFrame, fees: dict | None = None,
                       start_month: str = "2024-07-01", cutoff: str = "2026-09-30") -> PaymentResult:
    fees = DEFAULT_FEES if fees is None else fees
    required = {"pagamento_id", "user_id", "data_hora", "valor", "metodo", "status", "tentativa"}
    if missing := required - set(raw.columns):
        raise ValueError(f"Colunas ausentes: {sorted(missing)}")
    p = raw.copy()
    for c in ["pagamento_id", "user_id", "metodo", "status"]:
        p[c] = p[c].astype("string").str.strip()
        if p[c].isna().any() or p[c].eq("").any():
            raise ValueError(f"Chave/categoria ausente: {c}")
    p["status"] = p.status.str.lower(); p["metodo"] = p.metodo.str.lower()
    if not set(p.status) <= STATUSES:
        raise ValueError("Status desconhecido; revisar contrato de dados")
    if not set(p.metodo) <= set(fees):
        raise ValueError("Método sem taxa configurada")
    attempts = pd.to_numeric(p.tentativa, errors="coerce")
    if attempts.isna().any() or attempts.lt(1).any() or attempts.mod(1).ne(0).any():
        raise ValueError("Número de tentativa inválido")
    p["tentativa"] = attempts.astype("int64")
    p["valor_centavos"] = p.valor.map(money_to_cents).astype("int64")
    p["data_hora_brt"] = brt_timestamps(p.data_hora)
    p["mes_referencia"] = p.data_hora_brt.dt.strftime("%Y-%m")
    p = p.sort_values(["data_hora_brt", "pagamento_id"], kind="stable")
    p["duplicado_negocio"] = p.duplicated(DUPLICATE_KEY, keep="first")
    lower = pd.Timestamp(start_month, tz="America/Sao_Paulo")
    upper = pd.Timestamp(cutoff, tz="America/Sao_Paulo") + pd.Timedelta(days=1)
    p = p[p.data_hora_brt.ge(lower) & p.data_hora_brt.lt(upper)].copy()
    # payment_id is deliberately not part of the functional key.
    unique = p[~p.duplicado_negocio].copy()
    duplicates = p[p.duplicado_negocio].copy()
    if unique.duplicated(DUPLICATE_KEY).any():
        raise AssertionError("Deduplicação funcional falhou")
    if unique.loc[unique.status.eq("aprovado"), "valor_centavos"].lt(0).any():
        raise ValueError("Aprovação com valor negativo: revisar sua semântica")
    unique["taxa_bp"] = unique.metodo.map(fees).astype("int64")
    for status in STATUSES:
        unique["n_" + status] = unique.status.eq(status).astype("int64")
    unique["aprovado_centavos"] = unique.valor_centavos.where(unique.status.eq("aprovado"), 0)
    unique["ajustes_centavos"] = unique.valor_centavos.where(unique.status.isin(["estornado", "chargeback"]), 0)
    unique["taxa_microreais"] = unique.aprovado_centavos * unique.taxa_bp
    unique["liquido_microreais"] = unique.aprovado_centavos * 10000 - unique.taxa_microreais
    keys = ["user_id", "mes_referencia"]
    monthly = unique.groupby(keys).agg(
        tentativas_pagamento_mes=("pagamento_id", "size"),
        cobrancas_aprovadas_mes=("n_aprovado", "sum"),
        cobrancas_recusadas_mes=("n_recusado", "sum"),
        estornos_mes=("n_estornado", "sum"), chargebacks_mes=("n_chargeback", "sum"),
        aprovado_centavos=("aprovado_centavos", "sum"), ajustes_centavos=("ajustes_centavos", "sum"),
        taxa_microreais=("taxa_microreais", "sum"), liquido_microreais=("liquido_microreais", "sum")
    ).reset_index()
    raw_counts = p.groupby(keys).size().rename("registros_pagamento_brutos_mes").reset_index()
    raw_approved = p.assign(v=p.valor_centavos.where(p.status.eq("aprovado"), 0)).groupby(keys).v.sum().rename("aprovado_bruto_centavos").reset_index()
    duplicate_counts = duplicates.groupby(keys).size().rename("registros_pagamento_duplicados_mes").reset_index()
    duplicate_values = duplicates.assign(v=duplicates.valor_centavos.where(duplicates.status.eq("aprovado"), 0)).groupby(keys).v.sum().rename("aprovado_duplicado_centavos").reset_index()
    # Outer union protects groups composed solely of a duplicate in general inputs.
    monthly = raw_counts.merge(monthly, on=keys, how="left", validate="one_to_one")
    for frame in [raw_approved, duplicate_counts, duplicate_values]:
        monthly = monthly.merge(frame, on=keys, how="left", validate="one_to_one")
    for c in monthly.columns.difference(keys):
        monthly[c] = monthly[c].fillna(0).astype("int64")
    assert (monthly.registros_pagamento_brutos_mes == monthly.tentativas_pagamento_mes + monthly.registros_pagamento_duplicados_mes).all()
    assert (monthly.aprovado_bruto_centavos == monthly.aprovado_centavos + monthly.aprovado_duplicado_centavos).all()
    assert (monthly.tentativas_pagamento_mes == monthly.cobrancas_aprovadas_mes + monthly.cobrancas_recusadas_mes + monthly.estornos_mes + monthly.chargebacks_mes).all()
    converters = {
        "aprovado_centavos": ("valor_aprovado_mes", 100),
        "ajustes_centavos": ("valor_ajustes_mes", 100),
        "aprovado_bruto_centavos": ("valor_aprovado_bruto_registros_mes", 100),
        "aprovado_duplicado_centavos": ("valor_aprovado_duplicado_mes", 100),
        "taxa_microreais": ("taxas_sobre_aprovados_mes", 1000000),
        "liquido_microreais": ("valor_aprovado_liquido_taxas_mes", 1000000)
    }
    for old, (new, divisor) in converters.items():
        monthly[new] = monthly.pop(old) / divisor
    return PaymentResult(p, unique, duplicates, monthly)

def monthly_financial_report(result: PaymentResult) -> pd.DataFrame:
    cols = result.monthly.select_dtypes("number").columns
    return result.monthly.groupby("mes_referencia")[list(cols)].sum().reset_index()

def rounded_cents(amount) -> int:
    return int((Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) * 100)

def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
