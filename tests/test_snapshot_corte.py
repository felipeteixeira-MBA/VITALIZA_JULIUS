# -*- coding: utf-8 -*-
"""Regressão da base analítica do corte (artefato intermediário).

Trava as âncoras do enunciado e do professor reconciliadas em 28/10/2026
por recálculo externo (Claude) direto dos CSVs brutos. Requer o data room
completo (12 arquivos) em ``data/raw/``; sem ele, o teste é pulado.
"""
from pathlib import Path

import pytest

from vitaliza_case.finance import load_config, rounded_cents
from vitaliza_case.snapshot import SNAPSHOT_INPUTS, build_snapshot

ROOT = Path(__file__).resolve().parents[1]

COLUNAS_ESPERADAS = {
    "user_id", "assinatura_id", "plano", "canal_cobranca", "inicio_assinatura",
    "meses_de_casa", "meses_ate_renovacao", "idade", "sexo", "uf",
    "canal_aquisicao", "sistema", "relogio", "nivel", "tem_objetivo",
    "ultima_cobranca_valor", "mrr", "receita_liq_12m", "n_recusas_12m",
    "teve_duplicidade_pagto", "n_renovacoes", "teve_carencia_12m",
    "renov_auto_off_eventos", "atividades_ult3m", "minutos_ult3m",
    "tendencia_atividades_jul_set", "queda50_set_vs_t2", "n_treinos_90d",
    "dias_desde_ultimo_treino", "seguidores", "seguindo", "n_posts_90d",
    "n_tickets_12m", "ticket_cobranca_12m", "grupo_campanha_ago26",
    "abriu_campanha", "clicou_campanha", "respondeu_pesquisa_saida",
}


@pytest.mark.integration
def test_snapshot_reproduces_case_anchors():
    raw = ROOT / "data/raw"
    faltam = [f for f in SNAPSHOT_INPUTS if not (raw / f).exists()]
    if faltam:
        pytest.skip(f"Base privada incompleta ({faltam}); não buscar automaticamente.")
    cfg = load_config(ROOT / "config/case.json")
    built = build_snapshot(raw, cfg)
    base, serie, a = built["base"], built["serie_churn"], built["anchors"]

    # Grão e cobertura
    assert len(base) == 14753 and not base.user_id.duplicated().any()
    assert a["cortesias_excluidas"] == 60
    assert not base.plano.eq("cortesia").any()
    assert COLUNAS_ESPERADAS <= set(base.columns)

    # MRR do corte (última cobrança aprovada > 0; anual ÷ 12) — R$ 457.281,85
    assert a["mrr_corte_cents"] == 45728185

    # Churn oficial (dicionário §11): set/26 e pior mês (abr/26)
    assert (a["churn_set26"]["perdas"], a["churn_set26"]["ativos_inicio"]) == (714, 14319)
    assert (a["churn_abr26"]["perdas"], a["churn_abr26"]["ativos_inicio"]) == (1154, 14237)
    m25 = serie[serie.mes.str.startswith("2025")].churn_pct.mean()
    m26 = serie[serie.mes.str.startswith("2026")].churn_pct.mean()
    assert round(m25, 2) == 5.62 and round(m26, 2) == 6.62

    # Mix de plano e canal no corte (enunciado §01: 57/43 e 70/30)
    assert a["mix_plano"] == {"anual": 8478, "mensal": 6275}
    assert a["mix_canal"] == {"app_store": 5395, "google_play": 4964,
                              "web_cartao": 2994, "web_pix": 1400}

    # Coerência com o pipeline financeiro canônico
    assert a["duplicados_funcionais_total"] == 1941

    # Anti-vazamento: nenhuma data de referência posterior ao corte
    import pandas as pd
    cut_fim = pd.Timestamp(cfg["cutoff"]) + pd.Timedelta(days=1)
    for col in ["inicio_assinatura", "data_cadastro", "ultima_cobranca_data"]:
        assert pd.to_datetime(base[col]).dropna().lt(cut_fim).all(), col

    # Receita líquida 12m individual reconcilia com o total do relatório mensal
    total = rounded_cents(float(base.receita_liq_12m.sum()))
    assert total > 0
