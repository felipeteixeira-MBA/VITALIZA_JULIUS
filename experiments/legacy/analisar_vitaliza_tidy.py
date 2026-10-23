# HISTÓRICO: não é pipeline canônico; verREADME eCHANGELOG antes de executar.
from pathlib import Path
import json
import numpy as np,pandas as pd

OUT=Path('vitaliza_tidy_eda');OUT.mkdir(exist_ok=True)
source=Path('vitaliza_tidy_panel.csv')
header=pd.read_csv(source,nrows=0).columns.tolist()
skip=['email','data_nascimento','cep_prefixo','cidade','data_cadastro_brt','sistema_atual_export','versao_app_atual_export','relogio_conectado_atual_export']
cols=[c for c in header if c not in skip]
cat=['sexo','uf','canal_aquisicao','plano_inicio_mes','plano_fim_mes','canal_cobranca_inicio_mes','canal_cobranca_fim_mes']
d=pd.read_csv(source,usecols=cols,dtype={c:'category' for c in cat})
assert not d.duplicated(['user_id','mes_referencia']).any()
assert d.loc[d.pagante_inicio_mes.eq(1),'churn_base_inicial_mes'].notna().all()
assert d.loc[d.pagante_inicio_mes.eq(0),'churn_base_inicial_mes'].isna().all()

# Full-file shape and null counts, streamed to avoid retaining personal columns.
nulls=pd.Series(0,index=header,dtype='int64');row_count=0
for chunk in pd.read_csv(source,chunksize=100000):nulls+=chunk.isna().sum();row_count+=len(chunk)
assert row_count==len(d)
nulltable=nulls.rename('nulos').reset_index().rename(columns={'index':'coluna'});nulltable['pct_nulos']=nulltable.nulos/len(d)

monthly=d.groupby('mes_referencia').agg(usuarios_cadastrados=('user_id','nunique'),pagantes_inicio=('pagante_inicio_mes','sum'),pagantes_fim=('pagante_fim_mes','sum'),novos_pagantes=('assinatura_paga_iniciada_mes','sum'),todos_fins_pagantes=('assinatura_paga_encerrada_mes','sum'),perdas_base_inicial=('churn_base_inicial_mes','sum'),novos_cadastros=('cadastro_no_mes','sum')).reset_index()
monthly['churn']=monthly.perdas_base_inicial/monthly.pagantes_inicio
monthly['saldo_confere']=monthly.pagantes_inicio+monthly.novos_pagantes-monthly.todos_fins_pagantes==monthly.pagantes_fim
assert monthly.saldo_confere.all()
periods=[]
for label,start,end in [('2024 · jul–dez','2024-07','2024-12'),('2025 · jan–dez','2025-01','2025-12'),('2025 · jan–set','2025-01','2025-09'),('2026 · jan–set','2026-01','2026-09')]:
 b=monthly[monthly.mes_referencia.between(start,end)];periods.append(dict(periodo=label,meses=len(b),exposicoes_pagantes=int(b.pagantes_inicio.sum()),perdas=int(b.perdas_base_inicial.sum()),churn_media_simples=b.churn.mean(),churn_ponderado=b.perdas_base_inicial.sum()/b.pagantes_inicio.sum()))
periods=pd.DataFrame(periods)
cut=d[d.mes_referencia.eq('2026-09')].copy();assert not cut.user_id.duplicated().any()
cut['situacao_no_corte']=np.where(cut.pagante_fim_mes.eq(1),'Pagante','Não pagante')
cut['faixa_treinos']=pd.cut(cut.treinos_validos_mes,[-np.inf,0,3,7,15,np.inf],labels=['0','1–3','4–7','8–15','16+']).astype('string')
profile=[]
for key in ['situacao_no_corte','sexo','uf','canal_aquisicao']:
 g=cut.groupby(key,observed=True,dropna=False).size().rename('n').reset_index().rename(columns={key:'categoria'});g['variavel']=key;g['share']=g.n/len(cut);profile.append(g)
profile=pd.concat(profile,ignore_index=True)
cut['faixa_idade']=pd.cut(cut.idade_anos_no_mes,[-np.inf,17,24,34,44,54,64,np.inf],labels=['Até17','18–24','25–34','35–44','45–54','55–64','65+']).astype('string').fillna('Não informada/inconsistente')
ages=cut.groupby('faixa_idade',observed=True).size().rename('n').reset_index();ages['share']=ages.n/len(cut)
paidcut=cut[cut.pagante_fim_mes.eq(1)]
cutplan=paidcut.groupby('plano_fim_mes',observed=True).size().rename('n').reset_index();cutplan['share']=cutplan.n/len(paidcut)
cutchannel=paidcut.groupby('canal_cobranca_fim_mes',observed=True).size().rename('n').reset_index();cutchannel['share']=cutchannel.n/len(paidcut)
cutuse=cut.groupby('situacao_no_corte').agg(n=('user_id','size'),com_treino=('treinos_validos_mes',lambda s:s.gt(0).sum()),sem_treino=('treinos_validos_mes',lambda s:s.eq(0).sum()),treinos_mediana=('treinos_validos_mes','median'),treinos_media=('treinos_validos_mes','mean'),minutos_mediana=('minutos_treino_mes','median'),cadastros_no_proprio_mes=('cadastro_no_mes','sum')).reset_index();cutuse['pct_sem_treino']=cutuse.sem_treino/cutuse.n;cutuse['pct_com_treino']=cutuse.com_treino/cutuse.n
cutdist=cut.groupby(['situacao_no_corte','faixa_treinos'],observed=True).size().rename('n').reset_index();cutdist['share_no_grupo']=cutdist.n/cutdist.groupby('situacao_no_corte').n.transform('sum')

eng=d[d.fonte_atividades_coberta.eq(1)].copy()
eng_month=eng.groupby('mes_referencia').agg(usuarios=('user_id','nunique'),com_treino=('treinos_validos_mes',lambda s:s.gt(0).sum()),treinos=('treinos_validos_mes','sum'),minutos=('minutos_treino_mes','sum'),treinos_mediana=('treinos_validos_mes','median'),distancia_km=('distancia_km_mes',lambda s:s.sum(min_count=1)),treinos_com_fc=('treinos_com_fc_mes','sum')).reset_index();eng_month['pct_com_treino']=eng_month.com_treino/eng_month.usuarios;eng_month['minutos_por_treino']=eng_month.minutos/eng_month.treinos
eng_numbers={c:eng[c].sum() for c in ['treinos_registrados_mes','treinos_validos_mes','treinos_duracao_invalida_mes','minutos_treino_mes','distancia_km_mes','treinos_com_fc_mes']}
fc_weighted=(eng.fc_media_treinos_mes*eng.treinos_com_fc_mes).sum()/eng.treinos_com_fc_mes.sum()

base=d[d.pagante_inicio_mes.eq(1)&d.mes_referencia.between('2026-01','2026-09')].copy()
groups={}
for var in ['plano_inicio_mes','canal_cobranca_inicio_mes','canal_aquisicao']:
 g=base.groupby(var,observed=True,dropna=False).agg(exposicoes=('user_id','size'),perdas=('churn_base_inicial_mes','sum')).reset_index();g['churn_ponderado']=g.perdas/g.exposicoes;groups[var]=g
plan_month=base.groupby(['mes_referencia','plano_inicio_mes'],observed=True).agg(base_inicial=('user_id','size'),perdas=('churn_base_inicial_mes','sum')).reset_index();plan_month['churn']=plan_month.perdas/plan_month.base_inicial

# Strictly prior calendar month, joining unique keys. No same-month behavioral prediction claim.
previous=eng[['user_id','mes_referencia','treinos_validos_mes','cobrancas_recusadas_mes','tickets_abertos_mes']].copy()
previous['mes_referencia']=(pd.to_datetime(previous.mes_referencia+'-01')+pd.offsets.MonthBegin(1)).dt.strftime('%Y-%m')
previous=previous.rename(columns={'treinos_validos_mes':'treinos_mes_anterior','cobrancas_recusadas_mes':'recusas_mes_anterior','tickets_abertos_mes':'tickets_mes_anterior'})
lag=base[base.mes_referencia.between('2026-02','2026-09')].merge(previous,on=['user_id','mes_referencia'],how='left',validate='one_to_one')
lag['faixa_uso_anterior']=pd.cut(lag.treinos_mes_anterior,[-np.inf,0,3,7,np.inf],labels=['0','1–3','4–7','8+']).astype('string').fillna('Sem observação')
lag['recusa_anterior']=np.where(lag.recusas_mes_anterior.isna(),'Sem observação',np.where(lag.recusas_mes_anterior.gt(0),'Com recusa','Sem recusa'))
lag['suporte_anterior']=np.where(lag.tickets_mes_anterior.isna(),'Sem observação',np.where(lag.tickets_mes_anterior.gt(0),'Com chamado','Sem chamado'))
signals={}
for c in ['faixa_uso_anterior','recusa_anterior','suporte_anterior']:
 g=lag.groupby(c,observed=True,dropna=False).agg(exposicoes=('user_id','size'),usuarios_distintos=('user_id','nunique'),perdas=('churn_base_inicial_mes','sum')).reset_index();g['churn_seguinte']=g.perdas/g.exposicoes;signals[c]=g
lag_by_plan=lag.groupby(['plano_inicio_mes','faixa_uso_anterior'],observed=True).agg(exposicoes=('user_id','size'),perdas=('churn_base_inicial_mes','sum')).reset_index();lag_by_plan['churn_seguinte']=lag_by_plan.perdas/lag_by_plan.exposicoes

pay_month=d.groupby('mes_referencia').agg(tentativas=('tentativas_pagamento_mes','sum'),aprovadas=('cobrancas_aprovadas_mes','sum'),recusadas=('cobrancas_recusadas_mes','sum'),estornos=('estornos_mes','sum'),chargebacks=('chargebacks_mes','sum'),valor_aprovado=('valor_aprovado_mes','sum'),valor_ajustes=('valor_ajustes_mes','sum')).reset_index();pay_month['fracao_recusa_aprovado_recusado']=pay_month.recusadas/(pay_month.aprovadas+pay_month.recusadas)
sup=d[d.fonte_suporte_coberta.eq(1)].groupby('mes_referencia').agg(contas=('user_id','size'),tickets_abertos=('tickets_abertos_mes','sum'),usuarios_com_ticket=('tickets_abertos_mes',lambda s:s.gt(0).sum())).reset_index();sup['tickets_por_mil_contas']=1000*sup.tickets_abertos/sup.contas
quality=[]
for label,subset,c in [('Atividades antes2026',d[d.mes_referencia.lt('2026-01')],'treinos_validos_mes'),('Atividades2026',eng,'treinos_validos_mes'),('Suporte antes07/2025',d[d.mes_referencia.lt('2025-07')],'tickets_abertos_mes'),('Churn entre não pagantes iniciais',d[d.pagante_inicio_mes.eq(0)],'churn_base_inicial_mes')]:quality.append(dict(checagem=label,linhas=len(subset),nulos=int(subset[c].isna().sum()),zeros=int(subset[c].eq(0).sum())))
quality=pd.DataFrame(quality)
tables={'resumo_periodos':periods,'serie_mensal':monthly,'perfil_setembro':profile,'idade_setembro':ages,'planos_pagantes_corte':cutplan,'canais_pagantes_corte':cutchannel,'uso_setembro':cutuse,'faixas_uso_setembro':cutdist,'engajamento_mensal':eng_month,'churn_planos_2026':groups['plano_inicio_mes'],'churn_canais_2026':groups['canal_cobranca_inicio_mes'],'churn_aquisicao_2026':groups['canal_aquisicao'],'churn_plano_mensal':plan_month,'uso_anterior_churn':signals['faixa_uso_anterior'],'recusa_anterior_churn':signals['recusa_anterior'],'suporte_anterior_churn':signals['suporte_anterior'],'pagamentos_mensais':pay_month,'suporte_mensal':sup,'nulos_por_coluna':nulltable,'checagens_cobertura':quality}
tables['uso_anterior_por_plano']=lag_by_plan
meta={'data_geracao':'2026-10-22','source':'vitaliza_tidy_panel.csv','linhas':len(d),'colunas':len(header),'usuarios':int(d.user_id.nunique()),'meses':int(d.mes_referencia.nunique()),'inicio':d.mes_referencia.min(),'fim':d.mes_referencia.max(),'duplicatas':int(d.duplicated(['user_id','mes_referencia']).sum()),'celulas_nulas':int(nulls.sum()),'usuarios_corte':len(cut),'pagantes_corte':len(paidcut),'share_pagante_corte':len(paidcut)/len(cut),'idade_mediana_corte':float(cut.idade_anos_no_mes.median()),'usuarios_idade_valida_corte':int(cut.idade_anos_no_mes.notna().sum()),'exposicoes_engajamento':len(eng),'usuarios_com_treino_2026':int(eng.loc[eng.treinos_validos_mes.gt(0),'user_id'].nunique()),'treinos_validos':int(eng_numbers['treinos_validos_mes']),'treinos_invalidos':int(eng_numbers['treinos_duracao_invalida_mes']),'minutos_treino':float(eng_numbers['minutos_treino_mes']),'minutos_por_treino':float(eng_numbers['minutos_treino_mes']/eng_numbers['treinos_validos_mes']),'fc_media_ponderada_por_observacao':float(fc_weighted),'n_treinos_com_fc':int(eng.treinos_com_fc_mes.sum()),'n_lag':len(lag),'n_lag_usuarios':int(lag.user_id.nunique()),'lag_inicio':'2026-02','lag_fim':'2026-09','lag_mes_anterior_ausente':int(lag.treinos_mes_anterior.isna().sum()),'pagamentos_tentativas':int(pay_month.tentativas.sum()),'pagamentos_aprovados':int(pay_month.aprovadas.sum()),'pagamentos_recusados':int(pay_month.recusadas.sum()),'valor_aprovado_total':float(pay_month.valor_aprovado.sum()),'valor_ajustes_total':float(pay_month.valor_ajustes.sum()),'tickets_total':int(sup.tickets_abertos.sum())}
with pd.ExcelWriter(OUT/'tabelas_eda.xlsx',engine='openpyxl') as w:
 pd.DataFrame([meta]).T.reset_index().rename(columns={'index':'metrica',0:'valor'}).to_excel(w,sheet_name='resumo',index=False)
 for k,v in tables.items():v.to_excel(w,sheet_name=k[:31],index=False)
 for sh in w.sheets.values():
  sh.freeze_panes='A2';sh.auto_filter.ref=sh.dimensions
  for c in sh.columns:sh.column_dimensions[c[0].column_letter].width=min(50,max(15,len(str(c[0].value))+3))
j={k:v.astype(object).where(v.notna(),None).to_dict('records') for k,v in tables.items()};j['meta']=meta
(OUT/'dados_eda.json').write_text(json.dumps(j,ensure_ascii=False,indent=2,default=str))
print('META',json.dumps(meta,ensure_ascii=False,indent=2));print('PERIODOS\n',periods.to_string(index=False));print('USO SETEMBRO\n',cutuse.to_string(index=False));print('PLANOS2026\n',groups['plano_inicio_mes'].to_string(index=False));print('CANAIS2026\n',groups['canal_cobranca_inicio_mes'].to_string(index=False));
for k,v in signals.items():print(k,'\n',v.to_string(index=False))
print('DONE')
