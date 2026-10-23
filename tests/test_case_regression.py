from pathlib import Path
import pandas as pd
import pytest
from vitaliza_case.finance import aggregate_payments,monthly_financial_report,rounded_cents,load_config

ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.integration
def test_real_case_september_reproduces_reference():
    path=ROOT/'data/raw/pagamentos.csv'
    if not path.exists():pytest.skip('Base privada não disponível; não buscar automaticamente.')
    cfg=load_config(ROOT/'config/case.json');expected=cfg['reference_september_2026']
    result=aggregate_payments(pd.read_csv(path,dtype={'valor':'string'}),cfg['fee_basis_points'],cfg['start_month'],cfg['cutoff'])
    sep=monthly_financial_report(result).set_index('mes_referencia').loc['2026-09']
    assert rounded_cents(sep.valor_aprovado_bruto_registros_mes)==expected['approved_before_dedup_cents']
    assert int(sep.registros_pagamento_duplicados_mes)==expected['duplicate_approved_rows']
    assert rounded_cents(sep.valor_aprovado_duplicado_mes)==expected['duplicate_approved_cents']
    assert rounded_cents(sep.valor_aprovado_mes)==expected['approved_dedup_cents']
    assert rounded_cents(sep.valor_aprovado_liquido_taxas_mes)==expected['net_of_fees_rounded_cents']
    assert len(result.duplicates)==1941

@pytest.mark.integration
def test_panel_v2_roundtrip_if_built():
    path=ROOT/'data/processed/vitaliza_tidy_panel_v2.csv'
    if not path.exists():pytest.skip('Execute vitaliza panel para construir o painel.')
    cols=['user_id','mes_referencia','valor_aprovado_mes','valor_aprovado_bruto_registros_mes','valor_aprovado_duplicado_mes','taxas_sobre_aprovados_mes','valor_aprovado_liquido_taxas_mes']
    p=pd.read_csv(path,usecols=cols)
    assert not p.duplicated(['user_id','mes_referencia']).any()
    assert len(p)==946907 and p.user_id.nunique()==64829
    sep=p[p.mes_referencia.eq('2026-09')]
    assert rounded_cents(sep.valor_aprovado_mes.sum())==49257170
    assert rounded_cents(sep.valor_aprovado_liquido_taxas_mes.sum())==43644235
