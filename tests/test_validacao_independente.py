# -*- coding: utf-8 -*-
"""Validação independente complementar — números NÃO cobertos por
test_case_regression.py, verificados em 22/10/2026 por recálculo externo
(Claude) direto do CSV bruto. Documentação em docs/decisoes.md.
"""
from pathlib import Path

import pandas as pd
import pytest

from vitaliza_case.finance import (
    aggregate_payments,
    load_config,
    monthly_financial_report,
    rounded_cents,
)

ROOT = Path(__file__).resolve().parents[1]

# Bruto aprovado deduplicado por mês de 2026, em centavos (Brasília)
MENSAL_2026_CENTS = {
    "2026-01": 50981830,
    "2026-02": 44447720,
    "2026-03": 49481550,
    "2026-04": 44031940,
    "2026-05": 42706050,
    "2026-06": 39632030,
    "2026-07": 42406220,
    "2026-08": 46091150,
    "2026-09": 49257170,
}


@pytest.mark.integration
def test_independent_cross_check_payments():
    path = ROOT / "data/raw/pagamentos.csv"
    if not path.exists():
        pytest.skip("Base privada não disponível; não buscar automaticamente.")
    cfg = load_config(ROOT / "config/case.json")
    result = aggregate_payments(
        pd.read_csv(path, dtype={"valor": "string"}),
        cfg["fee_basis_points"],
        cfg["start_month"],
        cfg["cutoff"],
    )
    monthly = monthly_financial_report(result).set_index("mes_referencia")

    # Duplicidade estrutural na base inteira (jul/24–set/26): valor removido
    assert rounded_cents(monthly.valor_aprovado_duplicado_mes.sum()) == 11829590

    # Acumulado jan–set/2026
    y26 = monthly[monthly.index.str.startswith("2026")]
    assert rounded_cents(y26.valor_aprovado_mes.sum()) == 409035660
    assert rounded_cents(y26.valor_aprovado_liquido_taxas_mes.sum()) == 362931133

    # Mês a mês de 2026 (bruto aprovado deduplicado)
    for mes, esperado in MENSAL_2026_CENTS.items():
        assert rounded_cents(monthly.loc[mes, "valor_aprovado_mes"]) == esperado, mes
