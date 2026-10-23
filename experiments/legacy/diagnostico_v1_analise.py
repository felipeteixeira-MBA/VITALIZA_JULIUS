# HISTÓRICO: não é pipeline canônico; verREADME eCHANGELOG antes de executar.
from pathlib import Path
import json,warnings
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score,adjusted_rand_score,davies_bouldin_score
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from threadpoolctl import threadpool_limits
import statsmodels.api as sm
from statsmodels.stats.proportion import proportion_confint
from statsmodels.stats.multitest import multipletests
warnings.filterwarnings('ignore',category=FutureWarning)
OUT=Path('diagnostico_v1');OUT.mkdir(exist_ok=True)
R={p.stem:pd.read_csv(p,low_memory=False) for p in Path('.').glob('*.csv')}
def dt(s):
 s=s.astype('string').str.strip();z=s.str.contains(r'Z$|[+-]\d\d:\d\d$',na=False);o=pd.Series(pd.NaT,index=s.index,dtype='datetime64[ns]')
 o.loc[z]=pd.to_datetime(s[z],format='mixed',errors='coerce',utc=True).dt.tz_convert('America/Sao_Paulo').dt.tz_localize(None)
 o.loc[~z]=pd.to_datetime(s[~z],format='mixed',errors='coerce');return o
E=R['eventos_assinatura'].copy();E['dt']=dt(E.data_hora);E=E.sort_values('dt')
A=R['assinaturas'].copy();A['s']=pd.to_datetime(A.inicio)
P=R['pagamentos'].copy();P['dt']=dt(P.data_hora);P['valor_num']=pd.to_numeric(P.valor.astype(str).str.replace('R$','',regex=False).str.replace(' ','',regex=False).str.replace(',','.',regex=False),errors='coerce')
U=R['usuarios'].copy();U['sexo_clean']=U.sexo.str.lower().str.strip().replace({'f':'feminino','fem':'feminino','m':'masculino','masc':'masculino'}).fillna('nao_informado');U['sistema_clean']=U.sistema.str.lower()
birth=pd.to_datetime(U.data_nascimento,format='mixed',errors='coerce');U['idade_corte']=(pd.Timestamp('2026-09-30')-birth).dt.days/365.2425;U.loc[~U.idade_corte.between(0,110),'idade_corte']=np.nan
US=R['uso_mensal'].copy();US['month']=pd.to_datetime(US.mes+'-01')
ACT=pd.read_parquet('atividades.parquet');ACT['dt']=dt(ACT.inicio);ACT['tipo_clean']=ACT.tipo.str.lower().str.strip().replace({'run':'corrida','walk':'caminhada','ride':'pedal','strength':'forca'})
T=R['tickets_suporte'].copy();T['dt']=dt(T.aberto_em)
F=R['amizades'].copy();F['dt']=dt(F.desde)
paid=A[A.plano_atual.isin(['mensal','anual'])].copy()
st=E[E.evento.eq('assinatura_iniciada')].set_index('user_id').dt.dt.normalize();en=E[E.evento.eq('assinatura_expirada')].set_index('user_id').dt.dt.normalize()
paid['s']=paid.user_id.map(st).fillna(paid.s);paid['t']=paid.user_id.map(en)
pe=E[E.plano.isin(['mensal','anual'])]
fe=E[E.evento.isin(['renovacao_automatica_desligada','renovacao_automatica_religada'])]
fees={'app_store':.15,'google_play':.15,'web_cartao':.035,'web_pix':.0099}
def snapshot(ref):
 ref=pd.Timestamp(ref);b=paid[(paid.s<ref)&(paid.t.isna()|paid.t.ge(ref))].copy()
 last=pe[pe.dt<ref].drop_duplicates('user_id',keep='last').set_index('user_id');b['plano']=b.user_id.map(last.plano).fillna('desconhecido');b['canal']=b.user_id.map(last.canal_cobranca).fillna('desconhecido')
 flags=fe[fe.dt<ref].drop_duplicates('user_id',keep='last').set_index('user_id').evento;b['renovacao_off']=b.user_id.map(flags).eq('renovacao_automatica_desligada');b['renovacao_unknown']=~b.user_id.isin(flags.index)
 b['tenure_dias']=(ref-b.s).dt.days;b['faixa_tenure']=pd.cut(b.tenure_dias,[0,30,90,180,365,np.inf],labels=['ate30','31a90','91a180','181a365','mais365'],include_lowest=True).astype(str)
 b=b.merge(U[['user_id','sexo_clean','idade_corte','canal_aquisicao','sistema_clean','uf']],on='user_id',validate='one_to_one')
 m=(ref-pd.offsets.MonthBegin(1)).strftime('%Y-%m');m1=(ref-pd.offsets.MonthBegin(2)).strftime('%Y-%m');m2=(ref-pd.offsets.MonthBegin(3)).strftime('%Y-%m')
 cols=['atividades','sessoes_app','dias_ativos','minutos','atividades_ar_livre','atividades_video']
 for label,month in [('recente',m),('anterior',m1),('antes',m2)]:
  q=US[US.mes.eq(month)][['user_id']+cols].rename(columns={c:c+'_'+label for c in cols});b=b.merge(q,on='user_id',how='left',validate='one_to_one')
 days=(ref-pd.offsets.MonthBegin(1)).days_in_month;b['sessoes_semana']=b.sessoes_app_recente/days*7;b['dias_ativos_frac']=b.dias_ativos_recente/days
 b['video_share']=b.atividades_video_recente/b.atividades_recente.replace(0,np.nan);b['video_share']=b.video_share.mask(b.atividades_recente.eq(0),0)
 base=b[['atividades_anterior','atividades_antes']].mean(axis=1);b['trend_log']=np.log((b.atividades_recente+1)/(base+1));b['queda50']=b.atividades_anterior.gt(0)&b.atividades_recente.le(.5*b.atividades_anterior);b['uso_missing']=b.atividades_recente.isna()
 b['queda_comparavel']=b.atividades_anterior.gt(0)&b.atividades_recente.notna();b['queda50_grupo']=np.where(~b.queda_comparavel,'nao_comparavel',np.where(b.queda50,'queda50','sem_queda50'))
 b['recusa30']=b.user_id.isin(P[(P.dt>=ref-pd.Timedelta(days=30))&(P.dt<ref)&P.status.eq('recusado')].user_id)
 b['ticket30']=b.user_id.isin(T[(T.dt>=ref-pd.Timedelta(days=30))&(T.dt<ref)].user_id)
 f=F[F.dt<ref];following=f.groupby('seguidor_id').size();followers=f.groupby('seguido_id').size();b['seguindo']=b.user_id.map(following).fillna(0);b['seguidores']=b.user_id.map(followers).fillna(0)
 a=ACT[(ACT.dt>=ref-pd.Timedelta(days=30))&(ACT.dt<ref)].copy();a['dia']=a.dt.dt.normalize()
 b['companhia30']=b.user_id.map(a[a.treino_com.notna()].groupby('user_id').size()).fillna(0);b['treinos30']=b.user_id.map(a.groupby('user_id').size()).fillna(0)
 lasta=ACT[ACT.dt<ref].groupby('user_id').dt.max();b['dias_sem_treino']=(ref-b.user_id.map(lasta)).dt.total_seconds()/86400
 a=a.sort_values(['user_id','dt']);a['gap']=a.groupby('user_id').dt.diff().dt.total_seconds()/86400;b['gap_mediano_dias']=b.user_id.map(a.groupby('user_id').gap.median())
 # Latest successful positive billing is a current-cycle revenue proxy, not accrual accounting.
 pp=P[(P.dt<ref)&P.status.eq('aprovado')&P.valor_num.gt(0)].sort_values('dt').drop_duplicates('user_id',keep='last').set_index('user_id')
 b['ultima_cobranca']=b.user_id.map(pp.valor_num);b['preco_fallback']=b.ultima_cobranca.isna()
 b['mrr_proxy']=np.where(b.plano.eq('anual'),b.ultima_cobranca.fillna(299.9)/12,np.where(b.plano.eq('mensal'),b.ultima_cobranca.fillna(39.9),np.nan))
 b['mrr_liquido_proxy']=b.mrr_proxy*(1-b.canal.map(fees));b['contrib_mes_proxy']=b.mrr_liquido_proxy-4.2
 b['ref']=ref
 # Rule segments are mutually exclusive, assigned before looking at future outcomes.
 persistent=(b.tenure_dias.gt(180)&b.sessoes_app_recente.div(days).mul(7).lt(.5)&b.sessoes_app_anterior.div((ref-pd.offsets.MonthBegin(2)).days_in_month).mul(7).lt(.5)&b.sessoes_app_antes.div((ref-pd.offsets.MonthBegin(3)).days_in_month).mul(7).lt(.5))
 b['baixo_uso_persistente']=persistent
 b['regra']=np.select([b.uso_missing,b.tenure_dias.le(30),persistent,b.queda50],['Dados insuficientes','Entrada recente','Baixo uso persistente','Queda recente'],default='Demais perfis')
 return b

L=snapshot('2026-08-01');L['churn60']=L.t.ge('2026-08-01')&L.t.lt('2026-09-30')
C=snapshot('2026-10-01')
print('SNAPSHOTS',len(L),len(C),'churn60',L.churn60.mean(),'missing',L.uso_missing.sum(),C.uso_missing.sum(),flush=True)
def rate_table(df,key,outcome='churn60'):
 g=df.groupby(key,dropna=False,observed=True).agg(n=('user_id','size'),perdas=(outcome,'sum'),mrr_proxy=('mrr_proxy','sum'),contrib_proxy=('contrib_mes_proxy','sum')).reset_index();g['churn']=g.perdas/g.n
 ci=proportion_confint(g.perdas,g.n,method='wilson');g['ic95_inf']=ci[0];g['ic95_sup']=ci[1];return g

# Inventory: audit every available file, record actual coverage and columns.
datecols={'usuarios':'data_cadastro','assinaturas':'inicio','amizades':'desde','campanha_ago26':'enviado_em','eventos_assinatura':'data_hora','pagamentos':'data_hora','uso_mensal':'mes','onboarding':'respondido_em','pesquisa_saida':'respondido_em','feed_posts':'data_hora','tickets_suporte':'aberto_em','atividades':'inicio'}
grain={'usuarios':'conta','assinaturas':'assinatura','amizades':'relação direcionada','campanha_ago26':'sorteado','eventos_assinatura':'evento','pagamentos':'tentativa de cobrança','uso_mensal':'usuário-mês','onboarding':'resposta de entrada','pesquisa_saida':'resposta de saída','feed_posts':'post','tickets_suporte':'ticket','atividades':'treino'}
inventory=[];nulls=[]
for name,d in dict(R,atividades=ACT.drop(columns=['dt','tipo_clean'])).items():
 times=dt(d[datecols[name]])
 inventory.append(dict(fonte=name,registros=len(d),variaveis=len(d.columns),granularidade=grain[name],inicio=times.min(),fim=times.max(),datas_invalidas=int((d[datecols[name]].notna()&times.isna()).sum()),duplicatas_exatas=int(d.duplicated().sum())))
 for col in d:nulls.append(dict(fonte=name,variavel=col,nulos=int(d[col].isna().sum()),pct_nulos=float(d[col].isna().mean())))
inventory=pd.DataFrame(inventory);nulls=pd.DataFrame(nulls)

# Statistical analysis: one person per landmark, subsequent fully observed 60-day outcome.
columns=['log_sessoes','queda50','video_share','recusa30','ticket30','renovacao_off','renovacao_unknown','log_tenure','anual','uso_missing']
Z=pd.DataFrame(index=L.index);Z['log_sessoes']=np.log1p(L.sessoes_semana);Z['queda50']=L.queda50.astype(int);Z['video_share']=L.video_share;Z['recusa30']=L.recusa30.astype(int);Z['ticket30']=L.ticket30.astype(int);Z['renovacao_off']=L.renovacao_off.astype(int);Z['renovacao_unknown']=L.renovacao_unknown.astype(int);Z['log_tenure']=np.log1p(L.tenure_dias);Z['anual']=L.plano.eq('anual').astype(int);Z['uso_missing']=L.uso_missing.astype(int)
Z['queda_nao_comparavel']=(~L.queda_comparavel).astype(int)
channel=pd.get_dummies(L.canal,prefix='canal',drop_first=True,dtype=float);Z=pd.concat([Z,channel],axis=1).astype(float);Z=Z.fillna(Z.median());Z=Z.loc[:,Z.nunique()>1]
with threadpool_limits(limits=2):model=sm.GLM(L.churn60.astype(int),sm.add_constant(Z),family=sm.families.Binomial()).fit(cov_type='HC3')
coef=pd.DataFrame({'variavel':model.params.index,'coef':model.params.values,'OR':np.exp(model.params.values),'ic95_inf':np.exp(model.conf_int()[0].values),'ic95_sup':np.exp(model.conf_int()[1].values),'p_valor':model.pvalues.values});coef['q_BH']=multipletests(coef.p_valor,method='fdr_bh')[1]
# Nested specifications reveal conditional/overadjustment sensitivity; none is a causal model.
nested=[]
specs={'basico':['queda50','queda_nao_comparavel','log_tenure','anual']+list(channel.columns),'com_engajamento':[c for c in Z.columns if c not in ['renovacao_off','renovacao_unknown']],'com_aviso_cancelamento':list(Z.columns)}
with threadpool_limits(limits=2):
 for spec,cols in specs.items():
  cols=[c for c in cols if c in Z]
  fit=sm.GLM(L.churn60.astype(int),sm.add_constant(Z[cols]),family=sm.families.Binomial()).fit(cov_type='HC3')
  for var in ['queda50','log_tenure','ticket30']:
   if var not in cols:continue
   ci=fit.conf_int().loc[var];nested.append(dict(especificacao=spec,variavel=var,OR=np.exp(fit.params[var]),ic95_inf=np.exp(ci.iloc[0]),ic95_sup=np.exp(ci.iloc[1]),p_valor=fit.pvalues[var]))
nested=pd.DataFrame(nested)
# Nonlinearity sensitivity for tenure: replace log-tenure by explicit age groups.
agecat=pd.Categorical(L.faixa_tenure,categories=['mais365','ate30','31a90','91a180','181a365']);aged=pd.get_dummies(agecat,prefix='tenure',drop_first=True,dtype=float);aged.index=L.index
za=pd.concat([Z.drop(columns=['log_tenure']),aged],axis=1)
with threadpool_limits(limits=2):agefit=sm.GLM(L.churn60.astype(int),sm.add_constant(za),family=sm.families.Binomial()).fit(cov_type='HC3')
agecoefs=[]
for var in aged:
 ci=agefit.conf_int().loc[var];agecoefs.append(dict(variavel=var,referencia='mais365',OR=np.exp(agefit.params[var]),ic95_inf=np.exp(ci.iloc[0]),ic95_sup=np.exp(ci.iloc[1]),p_valor=agefit.pvalues[var]))
agecoefs=pd.DataFrame(agecoefs);rmat=np.zeros((len(aged.columns),len(agefit.params)))
for i,var in enumerate(aged):rmat[i,list(agefit.params.index).index(var)]=1
agewald=agefit.wald_test(rmat,scalar=True);age_global_p=float(agewald.pvalue)
stat_tests=[]
for name in ['sessoes_semana','atividades_recente','tenure_dias','video_share','dias_sem_treino']:
 x=L.loc[L.churn60,name].dropna();y=L.loc[~L.churn60,name].dropna();mw=stats.mannwhitneyu(x,y,alternative='two-sided');stat_tests.append(dict(variavel=name,n_perdas=len(x),n_retidos=len(y),mediana_perdas=x.median(),mediana_retidos=y.median(),p_valor=mw.pvalue,rank_biserial=2*mw.statistic/(len(x)*len(y))-1))
stat_tests=pd.DataFrame(stat_tests);stat_tests['q_BH']=multipletests(stat_tests.p_valor,method='fdr_bh')[1]
corrvars=['atividades_recente','sessoes_app_recente','dias_ativos_recente','minutos_recente','video_share','trend_log','tenure_dias','seguidores','companhia30'];corr=L[corrvars].corr(method='spearman')
vif_rows=[]
from statsmodels.stats.outliers_influence import variance_inflation_factor
for i,c in enumerate(Z.columns):vif_rows.append(dict(variavel=c,VIF=variance_inflation_factor(sm.add_constant(Z).values,i+1)))
vif=pd.DataFrame(vif_rows)

# Unsupervised segmentation; no churn, payments, cancellation flag, or demographic variables in clustering.
features=['log_sessoes','trend_log','video_share','log_tenure','log_seguidores']
def feature_frame(b):
 d=pd.DataFrame({'log_sessoes':np.log1p(b.sessoes_semana),'trend_log':b.trend_log,'video_share':b.video_share,'log_tenure':np.log1p(b.tenure_dias),'log_seguidores':np.log1p(b.seguidores)});return d
good=~L.uso_missing;FG=feature_frame(L.loc[good]);bounds=pd.DataFrame({'lo':FG.quantile(.01),'hi':FG.quantile(.99)})
FG=FG.clip(lower=bounds.lo,upper=bounds.hi,axis=1);imp=SimpleImputer(strategy='median');scaler=StandardScaler();X=scaler.fit_transform(imp.fit_transform(FG));rng=np.random.default_rng(2026)
metrics=[];models={};stab_details=[]
with threadpool_limits(limits=2):
 for k in range(2,7):
  km=KMeans(n_clusters=k,n_init=15,random_state=42).fit(X);labels=km.labels_;models[k]=km
  sil=silhouette_score(X,labels,sample_size=min(2500,len(X)),random_state=42);ari=[]
  for seed in [7,19,61,97,121]:
   rr=np.random.default_rng(seed);idx=rr.choice(len(X),int(.8*len(X)),replace=False);kb=KMeans(n_clusters=k,n_init=8,random_state=seed).fit(X[idx]);ari.append(adjusted_rand_score(labels,kb.predict(X)))
  sizes=np.bincount(labels,minlength=k)/len(X);metrics.append(dict(k=k,silhouette=sil,davies_bouldin=davies_bouldin_score(X,labels),min_share=sizes.min(),ARI_medio=np.mean(ari),ARI_min=np.min(ari),inertia=km.inertia_));stab_details.extend([dict(k=k,repeticao=i+1,ARI=v) for i,v in enumerate(ari)])
  print('K',k,metrics[-1],flush=True)
metrics=pd.DataFrame(metrics);eligible=metrics[(metrics.min_share>=.05)&(metrics.ARI_medio>=.75)];best=eligible.silhouette.max() if len(eligible) else metrics.silhouette.max();near=eligible[eligible.silhouette>=best-.02]
preferred=near[near.k.isin([3,4])];K=int(preferred.k.min()) if len(preferred) else int((eligible if len(eligible) else metrics).sort_values('silhouette',ascending=False).iloc[0].k)
km=models[K];labels=km.labels_
# Sensitivity to redundant activity-day feature, intentionally omitted in primary features.
alt=feature_frame(L.loc[good]);alt['dias_ativos_frac']=L.loc[good,'dias_ativos_frac'];alt=alt.clip(lower=alt.quantile(.01),upper=alt.quantile(.99),axis=1);altX=StandardScaler().fit_transform(SimpleImputer(strategy='median').fit_transform(alt))
with threadpool_limits(limits=2):altkm=KMeans(n_clusters=K,n_init=15,random_state=42).fit(altX)
redundancy_ARI=adjusted_rand_score(labels,altkm.labels_)
raworder=L.loc[good].assign(cl=labels).groupby('cl').sessoes_semana.median().sort_values().index.tolist();mapping={old:f'S{i+1}' for i,old in enumerate(raworder)}
L['segmento']='Sem dado recente';L.loc[good,'segmento']=[mapping[x] for x in labels]
gC=~C.uso_missing;XC=scaler.transform(imp.transform(feature_frame(C.loc[gC]).clip(lower=bounds.lo,upper=bounds.hi,axis=1)));C['segmento']='Sem dado recente';C.loc[gC,'segmento']=[mapping[x] for x in km.predict(XC)]
profiles=[]
for seg,b in L.groupby('segmento'):
 cg=C[C.segmento.eq(seg)];n=len(b);loss=b.churn60.sum();ci=proportion_confint(loss,n,method='wilson')
 profiles.append(dict(segmento=seg,n_julho=n,share_julho=n/len(L),perdas60=int(loss),churn60=loss/n,ic95_inf=ci[0],ic95_sup=ci[1],n_setembro=len(cg),share_setembro=len(cg)/len(C),tenure_mediano=b.tenure_dias.median(),sessoes_semana_mediana=b.sessoes_semana.median(),atividades_mediana=b.atividades_recente.median(),video_share_medio=b.video_share.mean(),trend_mediana=b.trend_log.median(),seguidores_mediana=b.seguidores.median(),pct_anual=b.plano.eq('anual').mean(),mrr_julho=b.mrr_proxy.sum(),mrr_setembro=cg.mrr_proxy.sum(),contrib_setembro=cg.contrib_mes_proxy.sum(),mrr_exposto_proxy=cg.mrr_proxy.sum()*loss/n,mrr_perdido_observado_julho=b.loc[b.churn60,'mrr_proxy'].sum(),pct_baixo_uso_persistente=b.baixo_uso_persistente.mean()))
profiles=pd.DataFrame(profiles)
chi=stats.chi2_contingency(pd.crosstab(L.loc[good,'segmento'],L.loc[good,'churn60']));cluster_chi=dict(chi2=chi.statistic,p_valor=chi.pvalue,df=int(chi.dof),cramers_v=np.sqrt(chi.statistic/good.sum()))
with threadpool_limits(limits=2):pca=PCA(2,random_state=42).fit(X)
idx=rng.choice(len(X),min(2200,len(X)),replace=False);pc=pca.transform(X[idx]);scatter=pd.DataFrame({'PC1':pc[:,0],'PC2':pc[:,1],'segmento':[mapping[labels[i]] for i in idx]})
centroids=L.loc[good].groupby('segmento')[['sessoes_semana','dias_ativos_frac','trend_log','video_share','tenure_dias','seguidores']].median()
zcent=pd.DataFrame(km.cluster_centers_,columns=features,index=[mapping[i] for i in range(K)]).sort_index()
cross=pd.crosstab(L.regra,L.segmento).reset_index();rule_stats=rate_table(L,'regra');rules_cut=C.groupby('regra').agg(n=('user_id','size'),mrr_proxy=('mrr_proxy','sum'),tenure_mediano=('tenure_dias','median'),sessoes_semana_mediana=('sessoes_semana','median')).reset_index()

# Early loss: complete 60-day cohorts only, no future beyond data cut.
new=paid[paid.s.ge('2025-01-01')&paid.s.le('2026-07-31')].copy();new['dur']=(new.t-new.s).dt.days
early=new.dur.ge(0)&new.dur.lt(30);late=new.dur.ge(30)&new.dur.lt(60);survive=~early
earlytab=pd.DataFrame([{'janela':'dias 0–29','em_risco':len(new),'perdas':int(early.sum()),'incidencia':early.mean()},{'janela':'dias 30–59 entre sobreviventes','em_risco':int(survive.sum()),'perdas':int(late.sum()),'incidencia':late.sum()/survive.sum()}])
# Kaplan-Meier for incident cohorts with censoring at Oct 1 (full new cohort since Jan 2025).
coh=paid[paid.s.ge('2025-01-01')].copy();coh['coorte']=coh.s.dt.to_period('Q').astype(str);coh['event']=coh.t.notna();coh['duration']=(coh.t.fillna(pd.Timestamp('2026-10-01'))-coh.s).dt.days
kmrows=[]
for co,b in coh.groupby('coorte'):
 surv=1.;steps={0:1.}
 for t,cnt in b[b.event].groupby('duration').size().sort_index().items():
  at=(b.duration>=t).sum();surv*=1-cnt/at;steps[int(t)]=surv
 for day in [0,30,60,90,180,270,365]:
  at=(b.duration>=day).sum()
  if at==0:continue
  valid=[t for t in steps if t<=day];kmrows.append(dict(coorte=co,dia=day,retencao_KM=steps[max(valid)],n_coorte=len(b),n_em_risco=int(at)))
kmcurve=pd.DataFrame(kmrows)

# Financial reconciliation and explicit observed/estimated scopes.
prior=pd.ExcelFile('entregas_vitaliza/analises_vitaliza.xlsx');old={s:pd.read_excel(prior,s) for s in prior.sheet_names}
S=old['serie_mensal'];P['mes']=P.dt.dt.strftime('%Y-%m');billing=P[P.status.isin(['aprovado','estornado','chargeback'])].groupby(['mes','status']).valor_num.sum().unstack(fill_value=0).reset_index();billing['fluxo_cobrancas_ajustado']=billing.get('aprovado',0)+billing.get('estornado',0)+billing.get('chargeback',0)
revseries=[]
for month in S.mes:
 ref=pd.Timestamp(month+'-01');prev=paid[(paid.s<ref)&(paid.t.isna()|paid.t.ge(ref))].copy();last=pe[pe.dt<ref].drop_duplicates('user_id',keep='last').set_index('user_id');prev['plano']=prev.user_id.map(last.plano)
 pp=P[(P.dt<ref)&P.status.eq('aprovado')&P.valor_num.gt(0)].sort_values('dt').drop_duplicates('user_id',keep='last').set_index('user_id');val=prev.user_id.map(pp.valor_num);mr=np.where(prev.plano.eq('anual'),val/12,np.where(prev.plano.eq('mensal'),val,np.nan));prev['mrr']=mr
 nxt=ref+pd.offsets.MonthBegin(1);lost=prev.t.ge(ref)&prev.t.lt(nxt);revseries.append(dict(mes=month,base_inicial=len(prev),base_com_preco=int(prev.mrr.notna().sum()),mrr_inicial_proxy=prev.mrr.sum(),mrr_perdido_base_inicial_proxy=prev.loc[lost,'mrr'].sum(),churn_receita_proxy=prev.loc[lost,'mrr'].sum()/prev.mrr.sum()))
revseries=pd.DataFrame(revseries)
activegross=C.mrr_proxy.sum();net=C.mrr_liquido_proxy.sum();contrib=C.contrib_mes_proxy.sum();sept=revseries.iloc[-1]
finance=pd.DataFrame([
 ['Pagantes',27901,len(C),'30/09/2026; exclui 60 cortesias'],
 ['Ticket mensal equivalente',39.9,C.mrr_proxy.mean(),'Última cobrança positiva, anual /12; proxy'],
 ['MRR bruto',27901*39.9,activegross,'Run-rate proxy; não é receita reconhecida nem caixa'],
 ['ARR bruto',13350000,activegross*12,'12 × MRR proxy; não é receita anual realizada'],
 ['Churn de clientes mensal',.102,float(S.iloc[-1].churn),'Setembro/2026, base inicial'],
 ['Churn de receita mensal',None,float(sept.churn_receita_proxy),'Setembro; valores equivalentes da base inicial'],
 ['MRR perdido no mês',113500,float(sept.mrr_perdido_base_inicial_proxy),'Setembro; bruto equivalente de quem saiu da base inicial'],
 ['LTV/CAC',2.02,None,'Não identificado: vida futura/margem por coorte/CAC individual não disponíveis']
 ],columns=['indicador','narrativa_aula','dataset','definicao'])
sensitivity=[]
for delta in [.005,.01,.02]:
 for contact,unit in [('email',.01),('whatsapp',.4)]:
  n=1000;pres=n*delta;gross=pres*C.contrib_mes_proxy.mean()
  sensitivity.append(dict(canal=contact,contatos=n,efeito_hipotetico_pp=delta*100,retidos_incrementais=pres,margem_mes_por_retido=C.contrib_mes_proxy.mean(),contribuicao_1mes=gross,custo_contato=n*unit,custo_oferta=0,custo_IA_assumido=0,saldo_hipotetico=gross-n*unit))
sensitivity=pd.DataFrame(sensitivity)
# Coverage and signal time before final expiration, no claim to click telemetry.
ends=E[E.evento.eq('assinatura_expirada')&E.dt.ge('2026-06-01')&E.dt.lt('2026-10-01')].copy();ends['web']=ends.canal_cobranca.isin(['web_cartao','web_pix'])
coverage=ends.groupby('web').size().reset_index(name='fins');coverage['share']=coverage.fins/len(ends)
signal_e=fe[fe.evento.eq('renovacao_automatica_desligada')][['user_id','dt']].rename(columns={'dt':'sinal_dt'});j=ends[['user_id','dt','canal_cobranca']].merge(signal_e,on='user_id');j=j[j.sinal_dt<j.dt].sort_values('sinal_dt').drop_duplicates('user_id',keep='last');j['antecedencia_dias']=(j.dt-j.sinal_dt).dt.total_seconds()/86400
leads=j.groupby('canal_cobranca').agg(n_com_sinal=('user_id','size'),mediana_dias=('antecedencia_dias','median'),p25=('antecedencia_dias',lambda s:s.quantile(.25)),p75=('antecedencia_dias',lambda s:s.quantile(.75))).reset_index()
lowone=C[C.tenure_dias.gt(180)&C.sessoes_semana.lt(.5)]
sleep=pd.DataFrame([{'regra':'mais180dias_e_sessoes_ultimo_mes_menor0.5_semana','n':len(lowone),'mrr_proxy':lowone.mrr_proxy.sum(),'arr_proxy':12*lowone.mrr_proxy.sum()},{'regra':'mesma_regra_persistente_3meses','n':int(C.baixo_uso_persistente.sum()),'mrr_proxy':C.loc[C.baixo_uso_persistente,'mrr_proxy'].sum(),'arr_proxy':12*C.loc[C.baixo_uso_persistente,'mrr_proxy'].sum()}])
sleep_exp=pd.read_csv('entregas_vitaliza/campanha_resultados_individuais.csv')[['user_id','grupo','churn_30d']].merge(L[['user_id','baixo_uso_persistente']],on='user_id',how='inner');sleep_exp=sleep_exp[sleep_exp.baixo_uso_persistente];sleep_exp_tab=sleep_exp.groupby('grupo').agg(n=('user_id','size'),perdas=('churn_30d','sum')).reset_index();sleep_exp_tab['churn']=sleep_exp_tab.perdas/sleep_exp_tab.n

# Hypothesis register with methods, falsifiable scope, numerical results and explicit uncertainty.
by={c:rate_table(L,c) for c in ['recusa30','ticket30','faixa_tenure','plano','regra']};by['queda50']=rate_table(L,'queda50_grupo')
def or_result(var):
 r=coef[coef.variavel.eq(var)].iloc[0];return f'OR ajustada={r.OR:.3f}; IC95% {r.ic95_inf:.3f}–{r.ic95_sup:.3f}; p={r.p_valor:.3g}; qBH={r.q_BH:.3g}'
rho=stats.spearmanr(L.mrr_proxy,L.churn60,nan_policy='omit')
h=[]
def hypo(id,pergunta,mecanismo,vars,metodo,evidencia,status,limite):h.append(dict(id=id,pergunta=pergunta,mecanismo=mecanismo,variaveis=vars,metodo=metodo,evidencia=evidencia,status=status,limitacoes=limite))
hypo('H1','A perda se concentra nos primeiros 30 dias pagos?','Abandono precoce após conversão.','s, t, duração paga','Incidência em 0–29 e 30–59 dias nas mesmas coortes com 60 dias completos',f'N={len(new)}; primeiros30={early.mean():.2%}; 30–59 entre sobreviventes={late.sum()/survive.sum():.2%}.','Contrariada' if early.mean()<late.sum()/survive.sum() else 'Sustentada descritivamente','Refuta apenas a definição escolhida de concentração; exclui trial e não compara formalmente dois grupos independentes.')
hypo('H2','Redução de uso precede mais saídas?','Desengajamento progressivo.','atividades julho/junho, alvo60','Landmark independente + logística ajustada HC3',or_result('queda50'),'Sustentada como associação' if coef.set_index('variavel').loc['queda50','ic95_inf']>1 else 'Inconclusiva','Queda50 compara meses com referência positiva; sem randomização. Julho antecede agosto; parte da janela observa campanha.')
hypo('H3','Tempo de casa se associa à perda posterior?','Ciclo de vida e oportunidade de renovação.','tenure, plano, y60','Logística log-linear e sensibilidade por faixas; Wald robusto global',or_result('log_tenure')+f'; teste por faixas p={age_global_p:.3g}','Sustentada como associação' if coef.set_index('variavel').loc['log_tenure','q_BH']<.05 else ('Sustentada apenas na sensibilidade por faixas' if age_global_p<.05 else 'Inconclusiva'),'Teste por faixas exploratório sem correção global; não demonstra influência causal nem capta oportunidade de renovação diretamente. Forma funcional muda a resposta.')
hypo('H4','Há pagantes antigos com uso muito baixo?','Assinatura vigente com baixa frequência observada.','tenure, sessões, preço atual','Regra explícita no corte, sem usar churn',f'Último mês: {len(lowone)}; persistentes 3meses: {int(C.baixo_uso_persistente.sum())}; ARR proxy último mês={12*lowone.mrr_proxy.sum():.2f}.','Sustentada descritivamente','Baixo uso não demonstra esquecimento nem efeito nocivo do contato; <0,5 sessão/semana normalizada pelo mês.')
hypo('H5','O mix de funcionalidades se associa à retenção?','Preferência por vídeo/ar livre e engajamento.','video_share, y60','Logística para participação de vídeo 0–1',or_result('video_share'),'Sustentada como associação' if coef.set_index('variavel').loc['video_share','q_BH']<.05 else 'Inconclusiva','Apenas vídeo/ar livre observáveis. Meditação/nutrição/sono não identificáveis; yoga não foi equiparada a meditação.')
sr=stat_tests[stat_tests.variavel.eq('sessoes_semana')].iloc[0]
hypo('H6','Comportamento recente distingue quem sai?','Uso sinaliza risco antes da expiração.','sessoes_semana, y60','Mann–Whitney + efeito rank-biserial; regressão ajustada',f'Medianas: perdas={sr.mediana_perdas:.3f}, retidos={sr.mediana_retidos:.3f}; rb={sr.rank_biserial:.3f}; q={sr.q_BH:.3g}; '+or_result('log_sessoes'),'Sustentada como associação','Não equivale a acurácia de um modelo; não houve validação temporal de um classificador.')
hypo('H7','O churn difere por perfil comportamental?','Exposição e necessidades heterogêneas.','clusters sem alvo; y60','Qui-quadrado global por segmento e IC Wilson',f'chi2={chi.statistic:.2f}; p={chi.pvalue:.3g}; V de Cramér={cluster_chi["cramers_v"]:.3f}; k={K}.','Sustentada como associação' if chi.pvalue<.05 else 'Inconclusiva','Clusters ajustados com features sem alvo; inferência exploratória, não prova mecanismo nem extrapolação temporal.')
hypo('H8','Há diferenças entre saídas com/sem clique em cancelar?','Jornadas de cancelamento diferentes.','telemetria UI de clique, canal e fim','Não executável exatamente; canal do site é proxy de alcance técnico',f'Jun-set: {int(ends.web.sum())}/{len(ends)} fins pelo site={ends.web.mean():.2%}.','Não testável com os dados','Não há log de clique em cancelar nem tela das lojas. Não rotular saídas de loja como sem clique; 349/1060 é narrativa não verificada.')
hypo('H9','Risco e valor econômico são proporcionais?','Preço e risco medem dimensões distintas.','MRR proxy, y60, segmento','Spearman entre receita individual equivalente e saída; matriz por segmento',f'rho={rho.statistic:.3f}; p={rho.pvalue:.3g}; MRR total proxy={activegross:.2f}.','Inconclusiva','Receita é dominada por plano; correlação não define proporcionalidade de risco individual, não estimado/calibrado.')
hypo('H10','Há padrões distintos de desengajamento?','Níveis/mix/tendência/ciclo diferentes.','cinco features sem alvo','K-Means k2–6; silhouette, ARI em 5 subamostras; regras',f'k={K}; silhouette={metrics.set_index("k").loc[K,"silhouette"]:.3f}; ARI médio={metrics.set_index("k").loc[K,"ARI_medio"]:.3f}.','Sustentada exploratoriamente' if metrics.set_index('k').loc[K,'ARI_medio']>=.75 else 'Inconclusiva','K-Means particiona mesmo dados contínuos. Estabilidade não prova grupos naturais nem estratégias diferentes eficazes.')
hypo('H11','Recusas anteriores sinalizam perda?','Fricção de cobrança.','recusa30, eventos, y60','Logística ajustada; OR HC3',or_result('recusa30'),'Sustentada como associação' if coef.set_index('variavel').loc['recusa30','ic95_inf']>1 else 'Inconclusiva','Nem toda recusa causa saída; algum churn é involuntário, outros mecanismos convivem.')
hypo('H12','Suporte anterior sinaliza perda?','Problemas ou pedido de cancelamento.','abertura_ticket30, y60','Logística ajustada; OR HC3',or_result('ticket30'),'Sustentada como associação' if coef.set_index('variavel').loc['ticket30','ic95_inf']>1 else 'Inconclusiva','Abertura não é problema técnico por definição; categoria e texto não usados para causalidade.')
hypo('H13','Cupom reduz churn após a campanha?','Mudança de preço incentiva permanência.','grupo sorteado, expiração','ITT; diferença de proporções; IC95%; horizontes alternativos','30d: +0,84pp, IC[-0,18;1,86]; até corte: +1,92pp, IC[0,60;3,24].','Sustentada apenas no horizonte exploratório até corte','Sem pré-registro; custos/resgate e efeito por segmento não demonstrados; 48 inconsistências no horário exato.')
hypo('H14','O reajuste explica sozinho a piora de 2026?','Preço maior pode incentivar saída.','churn mensal e marco 01/03','Inspeção temporal e hipóteses alternativas','Jan/2026 churn=7,30%, já acima de jan/2025=6,25%; ambos planos pioram.','Contrariada na forma exclusiva','Não quantifica contribuição do reajuste; requer estudo temporal ajustado com controle defensável.')
hypotheses=pd.DataFrame(h)

# Additional useful descriptive outputs.
demographics=[]
for col in ['plano','canal','sexo_clean','uf','canal_aquisicao','faixa_tenure']:
 g=C.groupby(col,dropna=False).size().rename('n').reset_index().rename(columns={col:'categoria'});g['variavel']=col;g['share']=g.n/len(C);demographics.append(g)
demographics=pd.concat(demographics,ignore_index=True)
customer_stats=pd.DataFrame([dict(variavel=c,n=int(C[c].notna().sum()),media=C[c].mean(),mediana=C[c].median(),p25=C[c].quantile(.25),p75=C[c].quantile(.75),p95=C[c].quantile(.95)) for c in ['idade_corte','tenure_dias','sessoes_semana','atividades_recente','dias_ativos_frac','dias_sem_treino','gap_mediano_dias','mrr_proxy']])
ft=ACT.groupby('tipo_clean').agg(treinos=('atividade_id','size'),usuarios=('user_id','nunique'),duracao_invalida=('duracao_min',lambda s:s.le(0).sum())).reset_index();ft['share_treinos']=ft.treinos/len(ACT)
plans=C.groupby('plano').agg(n=('user_id','size'),mrr_proxy=('mrr_proxy','sum'),media_mrr=('mrr_proxy','mean'),contrib_proxy=('contrib_mes_proxy','sum')).reset_index()
trace=pd.DataFrame([
 ['pagante','eventos + inicio legado','intervalo vigente; plano mensal/anual; exclui cortesia/trial','usuário × referência','não usar status atual retrospectivamente'],
 ['churn60','assinatura_expirada','t em [01/08,30/09), 60 dias','usuário, landmark 31/07','não disponível para corte final de setembro'],
 ['sessoes_semana','uso_mensal.sessoes_app','sessões do mês /dias_mes ×7','usuário × referência','não preencher ausência com zero'],
 ['queda50','uso_mensal.atividades','recente <=50% anterior; referência anterior >0','usuário × referência','meses-calendário, não janela móvel de dias'],
 ['trend_log','uso_mensal.atividades','log((recente+1)/(média2anteriores+1))','usuário × referência','variável de cluster; não é o alvo'],
 ['queda_nao_comparavel','uso_mensal.atividades','referência ausente/zero ou recente ausente, indicador separado na regressão','usuário × referência','não comparar ausência ou base zero com queda50=False'],
 ['recusa30 / ticket30','pagamentos / tickets','evento nos 30 dias anteriores','usuário × referência','abertura ticket somente; sem status posterior'],
 ['video_share','uso_mensal','vídeo / total; zero treino observado ->0','usuário × referência','zero estrutural sem preferência; pode influenciar cluster'],
 ['seguidores / companhia30','amizades / atividades','relações anteriores / treinos com companhia anteriores','usuário × referência','seguir não é treinar acompanhado'],
 ['mrr_proxy','pagamentos + plano/canal históricos','última cobrança aprovada positiva; anual /12','usuário × referência','proxy run-rate; preço anterior pode não refletir oferta futura'],
 ['receita exposta proxy','segmentos julho + MRR setembro','MRR_setembro × taxa60_julho do segmento','segmento','transferência temporal não validada; não é previsão individual'],
 ['idade / sexo','usuarios','idade no corte; faixa0–110; padronizar categorias sexo','usuário','demografia não entrou no clustering'],
 ],columns=['variavel','fonte','transformacao','granularidade','cuidado'])

tables={'inventario':inventory,'nulos':nulls,'rastreabilidade':trace,'hipoteses':hypotheses,'coef_associacoes':coef,'modelos_aninhados':nested,'tenure_categorico':agecoefs,'testes_naoparametricos':stat_tests,'multicolinearidade_VIF':vif,'correlacao_spearman':corr.reset_index(),'cluster_metricas':metrics,'cluster_estabilidade':pd.DataFrame(stab_details),'segmentos':profiles,'centroides_z':zcent.reset_index().rename(columns={'index':'segmento'}),'centroides_medianos':centroids.reset_index(),'regras_vs_clusters':cross,'regras_julho':rule_stats,'regras_setembro':rules_cut,'abandono_inicial':earlytab,'retencao_KM':kmcurve,'financeiro_reconciliacao':finance,'MRR_por_plano':plans,'receita_mensal_proxy':revseries,'fluxo_cobrancas':billing,'sensibilidade':sensitivity,'alcance_site':coverage,'antecedencia_sinal':leads,'baixo_uso_antigos':sleep,'experimento_baixo_uso':sleep_exp_tab,'perfil_corte':demographics,'resumos_corte':customer_stats,'funcionalidades':ft}
for name,d in by.items():tables['taxa_'+name]=d
for name in ['serie_mensal','campanha_efeitos','campanha_sensibilidade','regras_qualidade','reconciliacao']:tables[name]=old[name]
with pd.ExcelWriter(OUT/'diagnostico_tabelas.xlsx',engine='openpyxl') as w:
 for name,d in tables.items():
  d.to_excel(w,sheet_name=name[:31],index=False);ws=w.sheets[name[:31]];ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
  for col in ws.columns:ws.column_dimensions[col[0].column_letter].width=min(60,max(14,len(str(col[0].value))+3))
for n,d in [('landmark_julho',L),('pagantes_setembro',C)]:d.drop(columns=['email'],errors='ignore').to_parquet(OUT/(n+'.parquet'),index=False)
for n in ['hipoteses','segmentos','inventario','rastreabilidade']:tables[n].to_csv(OUT/(n+'.csv'),index=False)
scatter.to_csv(OUT/'pca_amostra_anonima.csv',index=False)
jsondata={k:v.astype(object).where(v.notna(),None).to_dict('records') for k,v in tables.items()}
jsondata['pca']=json.loads(scatter.to_json(orient='records'));jsondata['meta']={'K':K,'features':features,'landmark_n':len(L),'churn60':L.churn60.mean(),'corte_n':len(C),'mrr_proxy':activegross,'mrr_net_proxy':net,'contrib_proxy':contrib,'arr_proxy':activegross*12,'faltantes_julho':int(L.uso_missing.sum()),'faltantes_setembro':int(C.uso_missing.sum()),'pca_explicado':pca.explained_variance_ratio_.tolist(),'cluster_chi':cluster_chi,'n_baixo_uso':len(lowone),'n_persistente':int(C.baixo_uso_persistente.sum()),'unknown_plano_landmark':int(L.plano.eq('desconhecido').sum()),'preco_fallback_corte':int(C.preco_fallback.sum()),'n_novos60':len(new),'rho_mrr_churn':float(rho.statistic),'redundancia_ARI':redundancy_ARI}
(OUT/'dados_relatorio.json').write_text(json.dumps(jsondata,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
# Pipeline parameters and reproducible fitted transformations.
import joblib
joblib.dump(dict(model=km,imputer=imp,scaler=scaler,bounds=bounds,label_mapping=mapping,features=features),OUT/'transformacoes_clusters.joblib')
(OUT/'protocolo.txt').write_text('Corte de calibração não supervisionada: encerramento de 31/07/2026. Features disponíveis antes de 01/08/2026. Desfecho60 em [01/08,30/09). Corte operacional: encerramento de30/09/2026, sem alvo observado. K2–6, mínimo5%, ARI médio>=0,75, preferência3/4 se silhouette até0,02 da melhor elegível; sem escolha por churn. Winsor1–99%, mediana e StandardScaler ajustados só em julho. 5 reamostragens80% sem reposição; não bootstrap clássico. Logística é associativa, sem desempenho preditivo validado. Q-BH exploratório por família de coeficientes/testes, não correção global de toda a investigação. Plano/canal históricos por eventos; início legado pelo cadastro. Dados do atual cadastro demográfico somente perfil de setembro. Nenhuma narrativa financeira da aula substitui os dados do enunciado.',encoding='utf-8')
print('META',jsondata['meta']);print('PROFILES\n',profiles.to_string(index=False));print('HYPOTHESES\n',hypotheses[['id','status','evidencia']].to_string(index=False));print('FINANCE\n',finance.to_string(index=False));print('DONE',flush=True)
