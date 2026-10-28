# -*- coding: utf-8 -*-
"""Base analítica do corte — o "artefato intermediário" do case.

Uma linha por assinante pagante ativo em 30/09/2026 (14.753 × 61), integrando
os 12 arquivos do data room pelo ``user_id``. É o insumo dos objetivos 3 a 8
(segmentação, previsão, decisão, ROI, mensagem). Nenhuma variável usa
informação posterior ao corte.

Regras herdadas do pipeline canônico:
  - pagamentos passam por :func:`vitaliza_case.finance.aggregate_payments`
    (normalização monetária, fuso Brasília, deduplicação funcional, taxas);
  - timestamps de eventos usam :func:`vitaliza_case.finance.brt_timestamps`;
  - cortesias ficam fora da base pagante;
  - série de churn pela regra oficial do dicionário §11: perda é assinatura
    ativa no início do mês cujo fim cai no mês (começou-e-terminou no mesmo
    mês fica fora do numerador).

Validação: 15 âncoras do enunciado/professor reconciliadas em 28/10/2026
(ver ``tests/test_snapshot_corte.py`` e docs/decisoes.md).
"""
from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .finance import aggregate_payments, brt_timestamps, rounded_cents

SNAPSHOT_INPUTS = [
    "usuarios.csv", "assinaturas.csv", "eventos_assinatura.csv",
    "pagamentos.csv", "uso_mensal.csv", "atividades.parquet",
    "onboarding.csv", "amizades.csv", "feed_posts.csv",
    "tickets_suporte.csv", "campanha_ago26.csv", "pesquisa_saida.csv",
]


def monthly_churn_series(ass_pag: pd.DataFrame, start: str, cutoff: str) -> pd.DataFrame:
    """Churn mensal oficial: ativos no início do mês e perdas da base inicial."""
    meses = pd.period_range("2025-01", pd.Timestamp(cutoff), freq="M")
    rows = []
    for m in meses:
        ini, fim = m.start_time, m.end_time.normalize()
        ativos = ((ass_pag.inicio < ini)
                  & (ass_pag.data_fim.isna() | (ass_pag.data_fim >= ini))).sum()
        perdas = ((ass_pag.inicio < ini) & ass_pag.data_fim.between(ini, fim)).sum()
        rows.append({"mes": str(m), "ativos_inicio": int(ativos),
                     "perdas": int(perdas),
                     "churn_pct": round(100 * perdas / ativos, 2)})
    return pd.DataFrame(rows)


def build_snapshot(raw_dir: Path, config: dict) -> dict:
    """Constrói a base e devolve ``{"base", "serie_churn", "anchors"}``."""
    raw_dir = Path(raw_dir)
    cut = pd.Timestamp(config["cutoff"])
    cut_fim = cut + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    j12_ini = (cut + pd.Timedelta(days=1) - pd.DateOffset(months=12)).normalize()
    j90_ini = cut - pd.Timedelta(days=89)
    fees_frac = {k: v / 10000 for k, v in config["fee_basis_points"].items()}
    anchors: dict = {}

    # ---------------------------------------------------------- assinaturas
    ass = pd.read_csv(raw_dir / "assinaturas.csv", parse_dates=["inicio", "data_fim"])
    ass_pag = ass[ass.plano_atual != "cortesia"].copy()
    anchors["cortesias_excluidas"] = int((ass.plano_atual == "cortesia").sum())
    ativos = ass_pag[(ass_pag.inicio <= cut)
                     & (ass_pag.data_fim.isna() | (ass_pag.data_fim > cut))].copy()
    if ativos.user_id.duplicated().any():
        raise AssertionError("Usuário com mais de uma assinatura ativa no corte")
    anchors["pagantes_ativos_corte"] = int(len(ativos))

    serie = monthly_churn_series(ass_pag, config["start_month"], config["cutoff"])
    anchors["churn_set26"] = serie.loc[serie.mes.eq("2026-09")].iloc[0].to_dict()
    anchors["churn_abr26"] = serie.loc[serie.mes.eq("2026-04")].iloc[0].to_dict()

    # ---------------------------------------------------------- pagamentos (pipeline canônico)
    result = aggregate_payments(
        pd.read_csv(raw_dir / "pagamentos.csv", dtype={"valor": "string"}),
        config["fee_basis_points"], config["start_month"], config["cutoff"])
    uq = result.unique.copy()
    uq["dt"] = uq.data_hora_brt.dt.tz_localize(None)
    apr = uq[uq.status.eq("aprovado")].copy()
    apr["valor_reais"] = apr.valor_centavos / 100
    apr["liquido_reais"] = apr.liquido_microreais / 1_000_000

    ult = (apr[apr.valor_centavos > 0].sort_values(["dt", "pagamento_id"])
           .groupby("user_id").tail(1).set_index("user_id"))
    rec_12m = apr[apr.dt >= j12_ini].groupby("user_id").liquido_reais.sum().round(2)
    n_aprov = apr.groupby("user_id").size()
    n_recusas_12m = uq[uq.status.eq("recusado") & (uq.dt >= j12_ini)].groupby("user_id").size()
    teve_dup = set(result.duplicates.user_id)

    # ---------------------------------------------------------- eventos
    ev = pd.read_csv(raw_dir / "eventos_assinatura.csv")
    ev["dt"] = brt_timestamps(ev.data_hora).dt.tz_localize(None)
    ev = ev[ev.dt <= cut_fim]
    n_renov = ev[ev.evento.eq("renovacao")].groupby("user_id").size()
    carencia = set(ev[(ev.evento.eq("periodo_carencia")) & (ev.dt >= j12_ini)].user_id)
    sw = ev[ev.evento.isin(["renovacao_automatica_desligada", "renovacao_automatica_religada"])]
    renov_off = (sw.sort_values("dt").groupby("user_id").evento.last()
                 .eq("renovacao_automatica_desligada"))

    # ---------------------------------------------------------- cadastro e onboarding
    usu = pd.read_csv(raw_dir / "usuarios.csv",
                      parse_dates=["data_cadastro", "data_nascimento"]).set_index("user_id")
    usu["idade"] = ((cut - usu.data_nascimento).dt.days / 365.25).round(0)
    usu["relogio"] = usu.relogio_conectado.fillna("nenhum").ne("nenhum")
    onb = (pd.read_csv(raw_dir / "onboarding.csv").sort_values("respondido_em")
           .groupby("user_id").tail(1).set_index("user_id"))
    onb["tem_objetivo"] = onb.objetivo_texto.notna() & onb.objetivo_texto.astype(str).str.strip().ne("")

    # ---------------------------------------------------------- uso mensal (jul–set/26)
    uso = pd.read_csv(raw_dir / "uso_mensal.csv")
    u3 = uso[uso.mes.between("2026-07", "2026-09")]
    agg3 = u3.groupby("user_id").agg(
        atividades_ult3m=("atividades", "sum"), ar_livre_ult3m=("atividades_ar_livre", "sum"),
        video_ult3m=("atividades_video", "sum"), minutos_ult3m=("minutos", "sum"),
        dias_ativos_ult3m=("dias_ativos", "sum"), sessoes_ult3m=("sessoes_app", "sum"))
    piv = u3.pivot_table(index="user_id", columns="mes", values="atividades", aggfunc="sum")
    agg3["tendencia_atividades_jul_set"] = piv.get("2026-09", 0) - piv.get("2026-07", 0)
    u_prev = uso[uso.mes.between("2026-04", "2026-06")].groupby("user_id").atividades.mean()
    agg3["queda50_set_vs_t2"] = (piv.get("2026-09").reindex(agg3.index).fillna(0)
                                 < 0.5 * u_prev.reindex(agg3.index).fillna(0))

    # ---------------------------------------------------------- atividades (janela 90d)
    atv = pd.read_parquet(raw_dir / "atividades.parquet")
    atv["dt"] = pd.to_datetime(atv.inicio)
    a90 = atv[atv.dt.between(j90_ini, cut_fim)]
    f90 = a90.groupby("user_id").agg(n_treinos_90d=("atividade_id", "size"),
                                     minutos_90d=("duracao_min", "sum"),
                                     n_outdoor_90d=("gps_ok", "sum"))
    f90["n_treinos_companhia_90d"] = (a90[a90.treino_com.fillna("") != ""]
                                      .groupby("user_id").size())
    dias_ult_treino = (cut_fim - atv[atv.dt <= cut_fim].groupby("user_id").dt.max()).dt.days

    # ---------------------------------------------------------- rede, posts, suporte
    ami = pd.read_csv(raw_dir / "amizades.csv", parse_dates=["desde"])
    ami = ami[ami.desde <= cut]
    posts = pd.read_csv(raw_dir / "feed_posts.csv", parse_dates=["data_hora"])
    p90 = posts[posts.data_hora.between(j90_ini, cut_fim)]
    tic = pd.read_csv(raw_dir / "tickets_suporte.csv", parse_dates=["aberto_em"])
    t12 = tic[tic.aberto_em.between(j12_ini, cut_fim)]

    # ---------------------------------------------------------- campanha e pesquisa
    camp = pd.read_csv(raw_dir / "campanha_ago26.csv").set_index("user_id")
    camp["abriu_campanha"] = camp.abriu_push.fillna(False) | camp.abriu_email.fillna(False)
    pes = (pd.read_csv(raw_dir / "pesquisa_saida.csv").sort_values("respondido_em")
           .groupby("user_id").tail(1).set_index("user_id"))

    # ---------------------------------------------------------- montagem
    b = ativos.set_index("user_id").rename(columns={
        "plano_atual": "plano", "inicio": "inicio_assinatura",
        "renovacao_automatica": "renov_auto_snapshot"})
    b["meses_de_casa"] = ((cut - b.inicio_assinatura).dt.days / 30.44).round(1)
    b["meses_ate_renovacao"] = np.where(
        b.plano.eq("anual"),
        (12 - (((cut - b.inicio_assinatura).dt.days / 30.44) % 12)).round(1), 1.0)
    b = b.join(usu[["data_cadastro", "idade", "sexo", "uf", "canal_aquisicao",
                    "sistema", "relogio"]])
    b["dias_desde_cadastro"] = (cut - b.data_cadastro.dt.normalize()).dt.days
    b["dias_cadastro_ate_assinar"] = (b.inicio_assinatura - b.data_cadastro.dt.normalize()).dt.days
    b = b.join(onb[["nivel", "dias_por_semana", "tem_objetivo"]])
    b = b.join(ult[["valor_reais", "metodo", "dt"]].rename(columns={
        "valor_reais": "ultima_cobranca_valor", "metodo": "ultimo_metodo",
        "dt": "ultima_cobranca_data"}))
    b["mrr"] = np.where(b.plano.eq("anual"), b.ultima_cobranca_valor / 12,
                        b.ultima_cobranca_valor)
    anchors["mrr_corte_cents"] = rounded_cents(float(b.mrr.sum()))
    b["receita_liq_12m"] = rec_12m
    b["n_cobrancas_aprovadas_total"] = n_aprov
    b["n_recusas_12m"] = n_recusas_12m
    b["teve_duplicidade_pagto"] = b.index.isin(teve_dup)
    b["n_renovacoes"] = n_renov
    b["teve_carencia_12m"] = b.index.isin(carencia)
    b["renov_auto_off_eventos"] = renov_off.reindex(b.index).fillna(False)
    b = b.join(agg3)
    b["share_ar_livre_ult3m"] = (b.ar_livre_ult3m / b.atividades_ult3m.replace(0, np.nan)).round(3)
    b["share_video_ult3m"] = (b.video_ult3m / b.atividades_ult3m.replace(0, np.nan)).round(3)
    b = b.join(f90)
    b["dias_desde_ultimo_treino"] = dias_ult_treino
    b["seguidores"] = ami.groupby("seguido_id").size()
    b["seguindo"] = ami.groupby("seguidor_id").size()
    b["n_posts_90d"] = p90.groupby("user_id").size()
    b["curtidas_90d"] = p90.groupby("user_id").curtidas.sum()
    b["n_tickets_12m"] = t12.groupby("user_id").size()
    b["ticket_cobranca_12m"] = b.index.isin(
        set(t12[t12.categoria_atendente.eq("cobranca")].user_id))
    b["ticket_cancelamento_12m"] = b.index.isin(
        set(t12[t12.categoria_atendente.str.contains("cancel", na=False)].user_id))
    b = b.join(camp[["grupo", "abriu_campanha", "clicou"]].rename(columns={
        "grupo": "grupo_campanha_ago26", "clicou": "clicou_campanha"}))
    b["respondeu_pesquisa_saida"] = b.index.isin(pes.index)
    b = b.join(pes[["motivo_principal"]].rename(
        columns={"motivo_principal": "motivo_pesquisa_saida"}))

    zeros = ["atividades_ult3m", "ar_livre_ult3m", "video_ult3m", "minutos_ult3m",
             "dias_ativos_ult3m", "sessoes_ult3m", "tendencia_atividades_jul_set",
             "n_treinos_90d", "minutos_90d", "n_outdoor_90d", "n_treinos_companhia_90d",
             "seguidores", "seguindo", "n_posts_90d", "curtidas_90d", "n_tickets_12m",
             "n_recusas_12m", "n_renovacoes", "n_cobrancas_aprovadas_total",
             "receita_liq_12m"]
    b[zeros] = b[zeros].fillna(0)
    b["queda50_set_vs_t2"] = b.queda50_set_vs_t2.fillna(False).astype(bool)

    anchors["mix_plano"] = b.plano.value_counts().to_dict()
    anchors["mix_canal"] = b.canal_cobranca.value_counts().to_dict()
    anchors["duplicados_funcionais_total"] = int(len(result.duplicates))
    return {"base": b.reset_index(), "serie_churn": serie, "anchors": anchors}


def snapshot_command(raw_dir: Path, out_dir: Path, config: dict) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    built = build_snapshot(raw_dir, config)
    base, serie = built["base"], built["serie_churn"]
    base.to_csv(out_dir / "base_analitica_corte.csv", index=False)
    base.to_parquet(out_dir / "base_analitica_corte.parquet", index=False)
    serie.to_csv(out_dir / "serie_churn_mensal.csv", index=False)
    manifest = {
        "schema_version": config["schema_version"],
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "inputs": SNAPSHOT_INPUTS,
        "rows": int(len(base)), "columns": int(base.shape[1]),
        "cutoff": config["cutoff"], "anchors": built["anchors"],
    }
    (out_dir / "snapshot_run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
    print(json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
    return built
