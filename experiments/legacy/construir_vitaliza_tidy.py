# HISTÓRICO: não é pipeline canônico; verREADME eCHANGELOG antes de executar.
from pathlib import Path
import gc,json,zipfile,unicodedata
import numpy as np,pandas as pd

O=Path('vitaliza_tidy_documentacao');O.mkdir(exist_ok=True)
CUT=pd.Timestamp('2026-09-30');MONTHS=pd.date_range('2024-07-01','2026-09-01',freq='MS')
audit=[]
def record(item,value,note=''):audit.append(dict(checagem=item,valor=value,observacao=note))
def brt(s):
 s=s.astype('string').str.strip();aware=s.str.contains(r'Z$|[+-]\d\d:\d\d$',na=False)
 out=pd.Series(pd.NaT,index=s.index,dtype='datetime64[ns]')
 out.loc[aware]=pd.to_datetime(s[aware],format='mixed',errors='coerce',utc=True).dt.tz_convert('America/Sao_Paulo').dt.tz_localize(None)
 out.loc[~aware]=pd.to_datetime(s[~aware],format='mixed',errors='coerce')
 return out
def normalize_text(s):return s.astype('string').str.strip().str.replace(r'\s+',' ',regex=True).str.lower()
def money(s):
 s=s.astype('string').str.strip().str.replace(r'[^\d,\.\-]','',regex=True)
 comma=s.str.contains(',',regex=False,na=False);s.loc[comma]=s.loc[comma].str.replace('.','',regex=False).str.replace(',','.',regex=False)
 return pd.to_numeric(s,errors='coerce').astype('float64')

U=pd.read_csv('usuarios.csv',dtype='string');assert U.user_id.notna().all() and not U.user_id.duplicated().any()
record('usuarios_lidos',len(U));U['data_cadastro_brt']=brt(U.data_cadastro)
assert U.data_cadastro_brt.notna().all()
after_cut=U.data_cadastro_brt.ge(CUT+pd.Timedelta(days=1))
record('cadastros_posteriores_ao_corte',int(after_cut.sum()),'Não entram no painel histórico até30/09/2026; datas não são inventadas nem retrocedidas.')
U.loc[after_cut,['user_id','data_cadastro_brt']].to_csv(O/'cadastros_fora_do_corte.csv',index=False)
for col in ['email','sexo','cidade','canal_aquisicao','sistema','versao_app','relogio_conectado']:U[col]=normalize_text(U[col])
U['uf']=U.uf.str.strip().str.upper()
valid_uf={'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'}
baduf=U.uf.notna()&~U.uf.isin(valid_uf);record('uf_invalida',int(baduf.sum()));U.loc[baduf,'uf']=pd.NA
U['sexo']=U.sexo.replace({'f':'feminino','fem':'feminino','m':'masculino','masc':'masculino'})
U['cep_prefixo']=U.cep_prefixo.str.strip()
short_cep=U.cep_prefixo.str.fullmatch(r'\d{1,2}',na=False);record('cep_prefixo_zeros_esquerda_restaurados',int(short_cep.sum()),'Padronização formal para3dígitos; não é validação geográfica do CEP.')
U.loc[short_cep,'cep_prefixo']=U.loc[short_cep,'cep_prefixo'].str.zfill(3)
badcep=U.cep_prefixo.notna()&~U.cep_prefixo.str.fullmatch(r'\d{3}',na=False);record('cep_prefixo_formato_invalido',int(badcep.sum()));U.loc[badcep,'cep_prefixo']=pd.NA
birth=pd.to_datetime(U.data_nascimento,format='mixed',errors='coerce');missing_birth=U.data_nascimento.isna();birth_parse_error=U.data_nascimento.notna()&birth.isna()
age_cut=(CUT-birth).dt.days/365.2425;future=birth.gt(CUT);after_register=birth.gt(U.data_cadastro_brt.dt.normalize());too_old=age_cut.gt(110)
bad_birth=birth_parse_error|future|after_register|too_old
record('nascimento_ausente_original',int(missing_birth.sum()));record('nascimento_futuro',int(future.sum()));record('nascimento_posterior_cadastro',int(after_register.sum()));record('idade_acima_110_no_corte',int(too_old.sum()));record('nascimento_inconsistente_total',int(bad_birth.sum()),'União das regras, sem excluir o usuário; limite110anos é regra explícita de plausibilidade.')
U['data_nascimento']=birth.mask(bad_birth);U['nascimento_inconsistente']=bad_birth.astype('int8')
U.rename(columns={'sistema':'sistema_atual_export','versao_app':'versao_app_atual_export','relogio_conectado':'relogio_conectado_atual_export'},inplace=True)
U.drop(columns=['data_cadastro'],inplace=True)
# Repeated text is categorical in memory; exported CSV is ordinary text.
for col in ['sexo','cidade','uf','canal_aquisicao','sistema_atual_export','versao_app_atual_export','relogio_conectado_atual_export']:U[col]=U[col].astype('category')

# Aggregate activity independently, after filtering invalid durations.
A=pd.read_parquet('atividades.parquet');record('atividades_lidas',len(A));assert not A.atividade_id.duplicated().any()
A['dt']=brt(A.inicio);record('atividades_data_invalida',int(A.dt.isna().sum()));assert A.dt.notna().all()
outside_activity=A.dt.ge(CUT+pd.Timedelta(days=1))|A.dt.lt(MONTHS[0])
record('atividades_fora_janela_historica',int(outside_activity.sum()),'Segregadas após interpretar datas em Brasília; não trazidas artificialmente para setembro.')
A.loc[outside_activity].to_csv(O/'atividades_fora_do_corte.csv',index=False)
A=A.loc[~outside_activity].copy();record('atividades_dentro_da_janela',len(A))
A['mes_referencia']=A.dt.dt.strftime('%Y-%m');A['duracao_min']=pd.to_numeric(A.duracao_min,errors='coerce');valid=A.duracao_min.gt(0)
record('treinos_duracao_invalida_excluidos',int((~valid).sum()),'Excluídos de TODOS os agregados de engajamento; mantidos apenas como contagem de qualidade.')
raw_activity=A.groupby(['user_id','mes_referencia']).agg(treinos_registrados_mes=('atividade_id','size')).reset_index()
bad_activity=A.loc[~valid].groupby(['user_id','mes_referencia']).size().rename('treinos_duracao_invalida_mes').reset_index()
G=A.loc[valid].copy();G['dia']=G.dt.dt.normalize()
G['distancia_km']=pd.to_numeric(G.distancia_km,errors='coerce');G['fc_media']=pd.to_numeric(G.fc_media,errors='coerce')
record('distancia_nula_treinos_validos',int(G.distancia_km.isna().sum()));record('fc_nula_treinos_validos',int(G.fc_media.isna().sum()))
activity=G.groupby(['user_id','mes_referencia']).agg(treinos_validos_mes=('atividade_id','size'),minutos_treino_mes=('duracao_min','sum'),dias_com_treino_mes=('dia','nunique'),distancia_km_mes=('distancia_km',lambda x:x.sum(min_count=1)),treinos_com_distancia_mes=('distancia_km','count'),fc_media_treinos_mes=('fc_media','mean'),treinos_com_fc_mes=('fc_media','count')).reset_index()
activity=raw_activity.merge(activity,on=['user_id','mes_referencia'],how='left',validate='one_to_one').merge(bad_activity,on=['user_id','mes_referencia'],how='left',validate='one_to_one')
activity_counts=['treinos_registrados_mes','treinos_validos_mes','dias_com_treino_mes','treinos_com_distancia_mes','treinos_com_fc_mes','treinos_duracao_invalida_mes']
activity_fill_zero=activity_counts+['minutos_treino_mes']
for c in activity_fill_zero:activity[c]=activity[c].fillna(0)
activity_totals={'treinos_registrados_mes':len(A),'treinos_validos_mes':int(valid.sum()),'minutos_treino_mes':float(G.duracao_min.sum()),'treinos_duracao_invalida_mes':int((~valid).sum()),'distancia_km_mes':float(G.distancia_km.sum())}
activity.to_parquet(O/'atividades_agregadas.parquet',index=False)
del A,G,valid,raw_activity,bad_activity;gc.collect()

# Payment parsing and aggregation, never joined to raw activity rows.
P=pd.read_csv('pagamentos.csv',dtype={'user_id':'string','valor':'string'},low_memory=False);record('pagamentos_lidos',len(P));assert not P.pagamento_id.duplicated().any()
P['valor_num']=money(P.valor);record('pagamentos_valor_invalido',int(P.valor_num.isna().sum()));assert P.valor_num.notna().all()
P['dt']=brt(P.data_hora);record('pagamentos_data_invalida',int(P.dt.isna().sum()));assert P.dt.notna().all()
record('pagamentos_UTC_convertidos',int(P.data_hora.str.endswith('Z',na=False).sum()));record('pagamentos_naive_assumidos_Brasilia',int((~P.data_hora.str.endswith('Z',na=False)).sum()))
P['status']=normalize_text(P.status);P['mes_referencia']=P.dt.dt.strftime('%Y-%m')
allowed={'aprovado','recusado','estornado','chargeback'};assert set(P.status.dropna().unique())<=allowed
for status in allowed:P['qtd_'+status]=(P.status==status).astype('int8')
P['valor_aprovado']=P.valor_num.where(P.status.eq('aprovado'),0.0);P['valor_ajustes']=P.valor_num.where(P.status.isin(['estornado','chargeback']),0.0)
pay=P.groupby(['user_id','mes_referencia']).agg(tentativas_pagamento_mes=('pagamento_id','size'),cobrancas_aprovadas_mes=('qtd_aprovado','sum'),cobrancas_recusadas_mes=('qtd_recusado','sum'),estornos_mes=('qtd_estornado','sum'),chargebacks_mes=('qtd_chargeback','sum'),valor_aprovado_mes=('valor_aprovado','sum'),valor_ajustes_mes=('valor_ajustes','sum')).reset_index()
pay_counts=['tentativas_pagamento_mes','cobrancas_aprovadas_mes','cobrancas_recusadas_mes','estornos_mes','chargebacks_mes'];pay_values=['valor_aprovado_mes','valor_ajustes_mes'];pay_totals={c:float(pay[c].sum()) for c in pay_counts+pay_values}
record('pagamentos_negativos_preservados',int(P.valor_num.lt(0).sum()),'Preservados como ajustes; não convertidos em zero ou módulo.')
pay.to_parquet(O/'pagamentos_agregados.parquet',index=False);del P;gc.collect()

T=pd.read_csv('tickets_suporte.csv',low_memory=False);record('tickets_lidos',len(T));assert not T.ticket_id.duplicated().any();T['dt']=brt(T.aberto_em);assert T.dt.notna().all();T['mes_referencia']=T.dt.dt.strftime('%Y-%m')
tickets=T.groupby(['user_id','mes_referencia']).size().rename('tickets_abertos_mes').reset_index();tickets_total=len(T);tickets.to_parquet(O/'tickets_agregados.parquet',index=False);del T;gc.collect()

# Historical paid-cycle status, with events for historical attributes.
S=pd.read_csv('assinaturas.csv');record('assinaturas_lidas',len(S));record('usuarios_com_multiplas_assinaturas',int(S.user_id.duplicated().sum()));assert not S.user_id.duplicated().any(), 'Atenção: reestruturar intervalos para múltiplos ciclos antes de continuar.'
E=pd.read_csv('eventos_assinatura.csv',low_memory=False);E['dt']=brt(E.data_hora);assert E.dt.notna().all();E=E.sort_values('dt')
paid=S[S.plano_atual.isin(['mensal','anual'])].copy();start=E[E.evento.eq('assinatura_iniciada')].set_index('user_id').dt.dt.normalize();end=E[E.evento.eq('assinatura_expirada')].set_index('user_id').dt.dt.normalize()
assert not start.index.duplicated().any() and not end.index.duplicated().any()
paid['s']=paid.user_id.map(start).fillna(pd.to_datetime(paid.inicio));paid['t']=paid.user_id.map(end)
attr=E[E.plano.isin(['mensal','anual'])];monthly_status=[]
for ref in MONTHS:
 nxt=ref+pd.offsets.MonthBegin(1);b=paid[paid.s.lt(nxt)].copy();b['mes_referencia']=ref.strftime('%Y-%m')
 b['pagante_inicio_mes']=b.s.lt(ref)&(b.t.isna()|b.t.ge(ref));b['pagante_fim_mes']=b.s.lt(nxt)&(b.t.isna()|b.t.ge(nxt))
 b['assinatura_paga_iniciada_mes']=b.s.ge(ref)&b.s.lt(nxt);b['assinatura_paga_encerrada_mes']=b.t.ge(ref)&b.t.lt(nxt)
 b['churn_base_inicial_mes']=b.assinatura_paga_encerrada_mes.where(b.pagante_inicio_mes,pd.NA).astype('boolean')
 for moment,point,flag in [('inicio',ref,'pagante_inicio_mes'),('fim',nxt,'pagante_fim_mes')]:
  known=attr[attr.dt.lt(point)].drop_duplicates('user_id',keep='last').set_index('user_id')
  for new,old in [('plano','plano'),('canal_cobranca','canal_cobranca')]:
   values=b.user_id.map(known[old]).fillna('desconhecido');b[new+'_'+moment+'_mes']=values.where(b[flag],None)
 keep=['user_id','mes_referencia','pagante_inicio_mes','pagante_fim_mes','assinatura_paga_iniciada_mes','assinatura_paga_encerrada_mes','churn_base_inicial_mes','plano_inicio_mes','plano_fim_mes','canal_cobranca_inicio_mes','canal_cobranca_fim_mes']
 monthly_status.append(b[keep])
status=pd.concat(monthly_status,ignore_index=True);assert not status.duplicated(['user_id','mes_referencia']).any()
del E,attr,monthly_status,S,paid;gc.collect()

# Panel spine: all accounts registered by each month-end, including free accounts.
spine=[]
for ref in MONTHS:
 nxt=ref+pd.offsets.MonthBegin(1);ids=U.loc[U.data_cadastro_brt.lt(nxt),['user_id']].copy();ids['mes_referencia']=ref.strftime('%Y-%m');spine.append(ids)
panel=pd.concat(spine,ignore_index=True);del spine;assert not panel.duplicated(['user_id','mes_referencia']).any()
n_rows=len(panel);panel=panel.merge(U,on='user_id',how='left',validate='many_to_one');del U;gc.collect()
keys=['user_id','mes_referencia']
for name,agg in [('atividades',activity),('pagamentos',pay),('tickets',tickets),('historico_assinatura',status)]:
 assert not agg.duplicated(keys).any()
 assert agg.user_id.isin(panel.user_id).all(), 'Usuário órfão em '+name
 panel=panel.merge(agg,on=keys,how='left',validate='one_to_one');assert len(panel)==n_rows
 record('linhas_apos_join_'+name,len(panel),'LEFT JOIN com validaçãoone_to_one; não há join de logs brutos.')
del activity,pay,tickets,status;gc.collect()
panel['fonte_atividades_coberta']=panel.mes_referencia.between('2026-01','2026-09').astype('int8')
panel['fonte_pagamentos_coberta']=panel.mes_referencia.between('2024-07','2026-09').astype('int8')
panel['fonte_suporte_coberta']=panel.mes_referencia.between('2025-07','2026-09').astype('int8')
for c in activity_fill_zero:
 panel.loc[panel.fonte_atividades_coberta.eq(1),c]=panel.loc[panel.fonte_atividades_coberta.eq(1),c].fillna(0)
 panel.loc[panel.fonte_atividades_coberta.eq(0),c]=np.nan
for c in pay_counts+pay_values:panel.loc[panel.fonte_pagamentos_coberta.eq(1),c]=panel.loc[panel.fonte_pagamentos_coberta.eq(1),c].fillna(0)
panel.loc[panel.fonte_suporte_coberta.eq(1),'tickets_abertos_mes']=panel.loc[panel.fonte_suporte_coberta.eq(1),'tickets_abertos_mes'].fillna(0)
panel.loc[panel.fonte_suporte_coberta.eq(0),'tickets_abertos_mes']=np.nan
# A missing conditional mean/sum stays missing: no artificial zero for FC/distance.
for c in activity_counts+pay_counts+['tickets_abertos_mes']:panel[c]=panel[c].astype('Int32')
for c in ['pagante_inicio_mes','pagante_fim_mes','assinatura_paga_iniciada_mes','assinatura_paga_encerrada_mes']:panel[c]=panel[c].astype('boolean').fillna(False).astype('int8')
panel['churn_base_inicial_mes']=panel.churn_base_inicial_mes.astype('Int8');panel.loc[panel.pagante_inicio_mes.eq(1)&panel.churn_base_inicial_mes.isna(),'churn_base_inicial_mes']=0
for c in ['plano_inicio_mes','plano_fim_mes','canal_cobranca_inicio_mes','canal_cobranca_fim_mes']:panel[c]=panel[c].astype('category')
lastday=pd.to_datetime(panel.mes_referencia+'-01')+pd.offsets.MonthEnd(0)
birth=panel.data_nascimento;age=lastday.dt.year-birth.dt.year-((lastday.dt.month<birth.dt.month)|((lastday.dt.month==birth.dt.month)&(lastday.dt.day<birth.dt.day))).astype(int)
panel['idade_anos_no_mes']=age.astype('Int16')
cad=panel.data_cadastro_brt.dt.normalize();panel['cadastro_no_mes']=cad.dt.strftime('%Y-%m').eq(panel.mes_referencia).astype('int8')
days=(lastday-cad).dt.days+1;panel['dias_observaveis_mes']=np.minimum(days,lastday.dt.days_in_month).astype('int8')
assert panel.dias_observaveis_mes.between(1,31).all()
panel['data_cadastro_brt']=panel.data_cadastro_brt.dt.strftime('%Y-%m-%dT%H:%M:%S-03:00');panel['data_nascimento']=panel.data_nascimento.dt.strftime('%Y-%m-%d').astype('string')

# Hard reconciliation against independently aggregated inputs.
controls=[]
expected={**activity_totals,**pay_totals,'tickets_abertos_mes':tickets_total}
for c,v in expected.items():
 observed=float(panel[c].sum());ok=bool(np.isclose(observed,v,atol=1e-6,rtol=1e-10));controls.append(dict(campo=c,total_fonte=v,total_painel=observed,confere=ok));assert ok,(c,v,observed)
assert (panel.treinos_registrados_mes.fillna(0)==panel.treinos_validos_mes.fillna(0)+panel.treinos_duracao_invalida_mes.fillna(0)).all()
assert (panel.tentativas_pagamento_mes==panel.cobrancas_aprovadas_mes+panel.cobrancas_recusadas_mes+panel.estornos_mes+panel.chargebacks_mes).all()
dup=int(panel.duplicated(keys).sum());assert dup==0
series=panel.groupby('mes_referencia').agg(usuarios=('user_id','nunique'),pagantes_inicio=('pagante_inicio_mes','sum'),pagantes_fim=('pagante_fim_mes','sum'),perdas_base_inicial=('churn_base_inicial_mes','sum')).reset_index();series['churn']=series.perdas_base_inicial/series.pagantes_inicio
assert int(series.loc[series.mes_referencia.eq('2025-01'),'pagantes_inicio'].iloc[0])==8540
assert int(series.loc[series.mes_referencia.eq('2026-04'),'perdas_base_inicial'].iloc[0])==1154
assert int(series.loc[series.mes_referencia.eq('2026-09'),'pagantes_fim'].iloc[0])==14753
nulls=pd.DataFrame({'coluna':panel.columns,'tipo':panel.dtypes.astype(str).values,'nulos':panel.isna().sum().values});nulls['pct_nulos']=nulls.nulos/len(panel)
record('linhas_painel',len(panel));record('colunas_painel',panel.shape[1]);record('usuarios_unicos',panel.user_id.nunique());record('duplicatas_user_mes',dup);record('celulas_nulas_restantes',int(panel.isna().sum().sum()))
record('pagantes_corte',int(series.iloc[-1].pagantes_fim));record('periodos',len(MONTHS),'2024-07 a2026-09; somente meses após cadastro, incluindo mês de cadastro.')
fields=pd.DataFrame([
 ['user_id + mes_referencia','Chave única; mês em Brasília; universo inclui gratuitos e ex-pagantes.'],
 ['treinos_validos_mes / minutos_treino_mes','Somente treinos com duração>0. Sem registro em janela coberta=0; antes2026=NaN.'],
 ['treinos_registrados_mes / treinos_duracao_invalida_mes','Contagens de qualidade; inválidos não entram no engajamento.'],
 ['distancia_km_mes','Soma com min_count=1; todos nulos ou nenhum treino=NaN, não zero.'],
 ['fc_media_treinos_mes','Média simples por treino válido com FC informada; nulos ignorados e nunca zerados.'],
 ['treinos_com_distancia_mes / treinos_com_fc_mes','Denominadores das medidas condicionais;0quando não há observação, em período coberto.'],
 ['tentativas_pagamento_mes','Quantidade de registros da fonte por usuário-mês, incluindo os quatro status do dicionário.'],
 ['cobrancas_aprovadas_mes / cobrancas_recusadas_mes','Contagem por status após normalização.'],
 ['valor_aprovado_mes / valor_ajustes_mes','Valores float agregados por status; ajustes preservam sinal. Não são receita reconhecida nem MRR.'],
 ['tickets_abertos_mes','Contagem de aberturas; antes07/2025=NaN, sem ticket em fonte coberta=0.'],
 ['pagante_inicio_mes / pagante_fim_mes','Reconstrução com eventos e início legado; exclui trial e cortesia da base paga.'],
 ['churn_base_inicial_mes','1se ciclo da base paga inicial expira no mês;0se não;NaNse não era pagante inicial.'],
 ['plano_... / canal_cobranca_...','Último evento histórico válido antes da referência;desconhecidose pagante sem evidência;NaNse não pagante.'],
 ['nascimento_inconsistente','Data inválida, futura, posterior ao cadastro ou idade>110 no corte: data viraNaN; usuário mantido.'],
 ['*_atual_export','Atributos atuais sobrescritos do cadastro; NÃO representam snapshots históricos e podem vazar futuro em modelagem.'],
 ['dias_observaveis_mes','Dias do mês desde o cadastro, inclusive o dia inicial; permite reconhecer meses parciais.'],
 ],columns=['campo','definicao'])
panel.to_csv('vitaliza_tidy_panel.csv',index=False,encoding='utf-8-sig',float_format='%.6f',na_rep='')
panel.to_parquet(O/'vitaliza_tidy_panel.parquet',index=False)
nulls.to_csv(O/'nulos_por_coluna.csv',index=False)
with pd.ExcelWriter(O/'vitaliza_tidy_auditoria.xlsx',engine='openpyxl') as w:
 for name,d in [('resumo',pd.DataFrame(audit)),('nulos',nulls),('controle_totais',pd.DataFrame(controls)),('serie_mensal',series),('dicionario',fields)]:
  d.to_excel(w,sheet_name=name,index=False);w.sheets[name].freeze_panes='A2'
  for col in w.sheets[name].columns:w.sheets[name].column_dimensions[col[0].column_letter].width=min(65,max(15,len(str(col[0].value))+3))
summary=dict(shape=list(panel.shape),usuarios=int(panel.user_id.nunique()),periodos=27,inicio='2024-07',fim='2026-09',duplicatas=dup,nulos_total=int(panel.isna().sum().sum()),bytes_csv=Path('vitaliza_tidy_panel.csv').stat().st_size,treinos_invalidos_excluidos=activity_totals['treinos_duracao_invalida_mes'],birth_inconsistentes=int(bad_birth.sum()))
(O/'resumo.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
(O/'LEIA_ME.md').write_text('''# Vitaliza — painel TIDY
Uma linha poruser_id×mes_referencia. Universo: todas as contas cadastradas até o fechamento de cada mês; não somente pagantes. Janela julho/2024–setembro/2026. Não há linhas anteriores ao cadastro.

Pagamentos comZ foram convertidos deUTC paraAmerica/Sao_Paulo; datas sem fuso assumidasBrasília conforme origem. Meses são derivados SOMENTE depois dessa conversão. Datas cadastrais e de suporte sem fuso seguemBrasília. CSV usaUTF-8 comBOM, delimitadorvírgula e ponto decimal. Valores float com6casas na escrita; cálculos e Parquet preservam precisão original.

Fontes: usuarios, assinaturas, eventos_assinatura, atividades, pagamentos e tickets_suporte. Uso_mensal doBI não foi usado como substituto dos treinos brutos; feed/onboarding/amizades/imagens não entram nesta consolidação operacional solicitada.

Foram segregadas119contas com cadastro posterior ao corte, sem observações nas fontes de logs verificadas, e34treinos com data posterior ao corte. Não foram retrodatados. Os arquivos de exceção ficam nesta pasta. Isso explica64.829usuários históricos, em vez das64.948linhas do cadastro bruto. Prefixos deCEP numéricos com1ou2dígitos foram preenchidos à esquerda até3caracteres; isso não verifica existência geográfica.

Agregação: cada log foi agregado isoladamente porusuário-mês antes dos joins. Validaçãoone_to_one nos joins de agregados, many_to_one apenas no cadastro. Contagens e somas finais foram reconciliadas com agregações independentes.

Zero significa nenhum registro dentro da cobertura conhecida da fonte; não prova ausência real de comportamento fora do sistema. NaN representa fora da cobertura ou medida não aplicável/não informada. Atividades só cobrem2026; suporte começa07/2025; pagamentos07/2024. Não preencher FC ou distância comzero. Nascimento inconsistente viraNaN, sem excluir a conta; menores de18anos não foram automaticamente removidos.

Colunas de cadastro comsufixo_atual_export são retratos atuais e NÃO podem ser usadas ingenuamente para prever cortes históricos. Cidade/UF também são cadastro exportado, sem histórico de mudança. O estado pago foi reconstruído por eventos; renovação desligada e cancelamento web não são expiração. Fim pelo eventoassinatura_expirada; reembolso não gera segunda perda. Carência não encerra automaticamente o ciclo pago. Há uma assinatura por conta nesta entrega; múltiplos ciclos exigiriam nova reconstrução antes do mesmo pipeline.

Churn_base_inicial_mes ficaNaN para não pagantes iniciais, para evitar classificá-los artificialmente como retidos. Duração>0 é condição para todos os agregados de engajamento, inclusive médias deFC e distância. Taxas, LTV, previsão e retorno de campanha não foram recalculados como parte desta entrega.

O arquivo contém e-mail e atributos cadastrais fornecidos pelo usuário; trate como dados pessoais. Evite publicação pública sem remover esses campos. Para reproduzir, execute o script na pasta com os seis arquivos fonte, com pandas,numpy,pyarrow eopenpyxl.
''',encoding='utf-8')
import shutil
src=Path(__file__).resolve();dest=(O/src.name).resolve()
if src!=dest:shutil.copyfile(src,dest)
with zipfile.ZipFile('vitaliza_tidy_panel.zip','w',zipfile.ZIP_DEFLATED) as z:z.write('vitaliza_tidy_panel.csv')
print('SUMMARY',summary);print('NULLS\n',nulls.to_string(index=False));print('CHECKS\n',pd.DataFrame(audit).to_string(index=False));print('CONTROLS\n',pd.DataFrame(controls).to_string(index=False));print('SERIES\n',series.tail(5).to_string(index=False));print('OUTPUT vitaliza_tidy_panel.csv',flush=True)
