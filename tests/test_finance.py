from decimal import Decimal
import pandas as pd
import pytest
from vitaliza_case.finance import money_to_cents,brt_timestamps,aggregate_payments,rounded_cents,DUPLICATE_KEY

def row(pid='p1',uid='u_demo',when='2026-09-05 10:00:00',value='39.90',method='app_store',status='aprovado',attempt=1):
    return dict(pagamento_id=pid,user_id=uid,data_hora=when,valor=value,metodo=method,status=status,tentativa=attempt)

@pytest.mark.parametrize('value,cents',[
    ('34.90',3490),(39.9,3990),('R$ 34,90',3490),(' R$ 1.234,56 ',123456),
    ('1,234.56',123456),('-299.90',-29990),('R$ -39,90',-3990),('0',0)
])
def test_money_formats(value,cents):assert money_to_cents(value)==cents

@pytest.mark.parametrize('bad',[None,'','abc','12x34','1.001','NaN'])
def test_invalid_money_fails(bad):
    with pytest.raises(ValueError):money_to_cents(bad)

def test_utc_boundary_is_brasilia_month():
    dates=brt_timestamps(pd.Series(['2026-10-01T01:30:00Z','2026-09-01T01:30:00Z','2026-09-30 22:30:00']))
    assert dates.dt.strftime('%Y-%m').tolist()==['2026-09','2026-08','2026-09']
    assert dates.iloc[0]==dates.iloc[2]

def test_invalid_date_fails():
    with pytest.raises(ValueError):brt_timestamps(pd.Series(['não é data']))

def test_functional_duplicate_different_payment_ids():
    raw=pd.DataFrame([row('p1'),row('p2')]);r=aggregate_payments(raw)
    assert raw.pagamento_id.is_unique
    assert len(r.duplicates)==1 and len(r.unique)==1
    assert r.monthly.valor_aprovado_mes.sum()==39.9
    assert r.monthly.registros_pagamento_brutos_mes.sum()==2
    assert r.monthly.registros_pagamento_duplicados_mes.sum()==1

def test_dedup_after_timezone_and_money_normalization():
    raw=pd.DataFrame([row('p1',when='2026-09-05T13:00:00Z',value='39.90'),row('p2',when='2026-09-05 10:00:00',value='R$ 39,90')])
    r=aggregate_payments(raw);assert len(r.unique)==1

def test_distinct_approvals_same_user_and_month_are_preserved():
    r=aggregate_payments(pd.DataFrame([row('p1',when='2026-09-01 10:00:00'),row('p2',when='2026-09-29 10:00:00')]))
    assert len(r.unique)==2 and len(r.duplicates)==0
    assert rounded_cents(r.monthly.valor_aprovado_mes.sum())==7980

def test_approved_retry_after_refusal_is_preserved():
    raw=pd.DataFrame([row('p1',status='recusado'),row('p2',when='2026-09-06 10:00:00',attempt=2)])
    r=aggregate_payments(raw)
    assert r.monthly.cobrancas_aprovadas_mes.sum()==1
    assert r.monthly.cobrancas_recusadas_mes.sum()==1
    assert r.monthly.valor_aprovado_mes.sum()==39.9

def test_distinct_attempts_are_not_blindly_removed():
    r=aggregate_payments(pd.DataFrame([row('p1',attempt=1),row('p2',attempt=2)]))
    assert len(r.unique)==2

def test_adjustments_keep_negative_sign_and_not_taxed_as_approval():
    raw=pd.DataFrame([row('p1'),row('p2',when='2026-09-06 10:00:00',value='-39.90',status='estornado')])
    r=aggregate_payments(raw)
    assert r.monthly.valor_ajustes_mes.sum()==-39.9
    assert r.monthly.valor_aprovado_mes.sum()==39.9
    assert r.monthly.taxas_sobre_aprovados_mes.sum()==5.985

@pytest.mark.parametrize('method,bp',[('app_store',1500),('google_play',1500),('cartao',350),('pix_automatico',99)])
def test_exact_fee_micro_units(method,bp):
    r=aggregate_payments(pd.DataFrame([row(method=method)]))
    assert r.unique.taxa_microreais.sum()==3990*bp
    assert r.unique.liquido_microreais.sum()==3990*10000-3990*bp

def test_missing_fee_method_fails():
    with pytest.raises(ValueError):aggregate_payments(pd.DataFrame([row(method='metodo_desconhecido')]))

def test_unknown_status_fails():
    with pytest.raises(ValueError):aggregate_payments(pd.DataFrame([row(status='indefinido')]))

def test_missing_required_column_fails():
    with pytest.raises(ValueError):aggregate_payments(pd.DataFrame([row()]).drop(columns='user_id'))

def test_invalid_attempt_fails():
    with pytest.raises(ValueError):aggregate_payments(pd.DataFrame([row(attempt=0)]))

def test_monthly_grain_and_accounting_identities():
    r=aggregate_payments(pd.DataFrame([row('p1'),row('p2'),row('p3',uid='u_other',status='recusado')]))
    m=r.monthly
    assert not m.duplicated(['user_id','mes_referencia']).any()
    assert (m.registros_pagamento_brutos_mes==m.tentativas_pagamento_mes+m.registros_pagamento_duplicados_mes).all()
    assert len(r.unique)+len(r.duplicates)==len(r.normalized)
    assert not r.unique.duplicated(DUPLICATE_KEY).any()

def test_cutoff_is_applied_in_brasilia():
    r=aggregate_payments(pd.DataFrame([row('p1',when='2026-10-01T01:30:00Z'),row('p2',when='2026-10-01T04:00:00Z')]))
    assert len(r.unique)==1 and r.unique.iloc[0].pagamento_id=='p1'

def test_half_up_only_at_display():
    assert rounded_cents(Decimal('33.915'))==3392
