# HISTÓRICO: não é pipeline canônico; verREADME eCHANGELOG antes de executar.
from pathlib import Path
import io,json,time,zipfile,re,hashlib
import numpy as np,pandas as pd
from PIL import Image,ImageDraw
from scipy import ndimage,stats
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler,OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score,average_precision_score,brier_score_loss,log_loss
from statsmodels.stats.proportion import proportion_confint
from statsmodels.stats.multitest import multipletests
from threadpoolctl import threadpool_limits
import joblib

OUT=Path('heatmaps_integrados');OUT.mkdir(exist_ok=True)
BASE={'neutro':(236,233,226),'vias_claras':(252,252,250),'parque':(197,226,175),'agua':(170,207,230),'avenida':(250,236,190),'praia':(240,228,196)}
def packed(a):return a[...,0].astype(np.int64)*65536+a[...,1].astype(np.int64)*256+a[...,2]
basecodes={k:int(packed(np.array(v))) for k,v in BASE.items()};codes=np.array(list(basecodes.values()));Y,X=np.mgrid[0:192,0:192];X=X/191;Y=Y/191
def extract(im):
 im.load()
 if im.mode=='P':
  a=np.array(im);pal=np.array(im.getpalette(),dtype=np.uint8).reshape(-1,3);pc=packed(pal);isink=~np.isin(pc,codes);mask=isink[a];rgb=pal[a]
 else:
  rgb=np.array(im.convert('RGB'));mask=~np.isin(packed(rgb),codes)
 # Image-space characteristics: no claim of physical distance, visits or real geography.
 ink=int(mask.sum());r={'tinta_pixels':ink,'tinta_frac':ink/mask.size}
 warm=(rgb[:,:,0].astype(int)>rgb[:,:,1].astype(int))&(rgb[:,:,0].astype(int)>rgb[:,:,2].astype(int))&mask
 r['tinta_quente_concordancia']=warm.sum()/ink if ink else np.nan
 grid=mask.reshape(6,32,6,32).sum(axis=(1,3)).astype(float);prob=grid.ravel()/ink if ink else np.zeros(36);nz=prob[prob>0]
 r['grade_ocupada_frac']=float((grid>=8).mean());r['entropia_espacial']=float(-(nz*np.log(nz)).sum()/np.log(36)) if len(nz) else 0
 r['concentracao_grade_max']=float(prob.max());r['quadrante_max']=float(mask.reshape(2,96,2,96).sum(axis=(1,3)).max()/ink) if ink else 0
 if ink:
  yy,xx=np.where(mask);r['bbox_frac']=(xx.max()-xx.min()+1)*(yy.max()-yy.min()+1)/mask.size
  r['dispersao_espacial']=float(np.sqrt(np.var(X[mask])+np.var(Y[mask])))
  rg=(rgb[:,:,0].astype(float)-rgb[:,:,1].astype(float))[mask];r['contraste_rg_medio']=float(rg.mean()/255);r['contraste_rg_p90']=float(np.percentile(rg,90)/255)
  r['tinta_vermelha_frac']=float((rg>=80).mean())
  _,comps=ndimage.label(mask,structure=np.ones((3,3)));r['componentes_graficos']=int(comps)
 else:
  for k in ['bbox_frac','dispersao_espacial','contraste_rg_medio','contraste_rg_p90','tinta_vermelha_frac','componentes_graficos']:r[k]=0
 bc=packed(rgb)
 for k,v in basecodes.items():r['fundo_'+k+'_frac']=float((bc==v).mean())
 return r,mask

records=[];archivepaths={};start=time.time()
for date in ['2026-07-31','2026-09-30']:
 p=Path('heatmaps_'+date+'.zip')
 with zipfile.ZipFile(p) as z:
  names=[n for n in z.namelist() if re.fullmatch(r'u_[0-9a-f]{8}\.png',Path(n).name) and not n.startswith('__MACOSX/')]
  for i,name in enumerate(names):
   with Image.open(io.BytesIO(z.read(name))) as im:
    if im.size!=(192,192):raise ValueError('dimensões inesperadas: '+name)
    r,mask=extract(im)
   r.update(data=date,user_id=Path(name).stem,caminho_zip=name);records.append(r);archivepaths[(date,Path(name).stem)]=name
  print('EXTRACT',date,len(names),'seconds',round(time.time()-start),flush=True)
F=pd.DataFrame(records);F.to_parquet(OUT/'variaveis_visuais.parquet',index=False);F.to_csv(OUT/'variaveis_visuais.csv',index=False)
L=pd.read_parquet('diagnostico_v1/landmark_julho.parquet');C=pd.read_parquet('diagnostico_v1/pagantes_setembro.parquet')
imgcols=[c for c in F if c not in ['data','user_id','caminho_zip']]
for d,date in [(L,'2026-07-31'),(C,'2026-09-30')]:
 q=F[F.data.eq(date)].set_index('user_id')
 for col in imgcols:d[col]=d.user_id.map(q[col])
 d['tem_heatmap']=d.user_id.isin(q.index).astype(int)

def dt(s):
 s=s.astype('string').str.strip();z=s.str.contains(r'Z$|[+-]\d\d:\d\d$',na=False);o=pd.Series(pd.NaT,index=s.index,dtype='datetime64[ns]');o.loc[z]=pd.to_datetime(s[z],format='mixed',errors='coerce',utc=True).dt.tz_convert('America/Sao_Paulo').dt.tz_localize(None);o.loc[~z]=pd.to_datetime(s[~z],format='mixed',errors='coerce');return o
ACT=pd.read_parquet('atividades.parquet');ACT['dt']=dt(ACT.inicio);ACT['tipo_clean']=ACT.tipo.str.lower().replace({'run':'corrida','walk':'caminhada','ride':'pedal','strength':'forca'})
outdoor_types=['corrida','caminhada','pedal']
def exact90(b,ref):
 ref=pd.Timestamp(ref);a=ACT[ACT.dt.ge(ref-pd.Timedelta(days=90))&ACT.dt.lt(ref)].copy();a['outdoor']=a.tipo_clean.isin(outdoor_types);a['dia']=a.dt.dt.normalize();a['duracao_valida']=a.duracao_min.where(a.duracao_min.gt(0));a['distancia_valida']=a.distancia_km.where(a.distancia_km.ge(0));a['watch']=a.origem.isin(['garmin','apple_health']);a['companhia']=a.treino_com.notna()
 a['outdoor_gps']=a.outdoor&a.gps_ok.fillna(False)
 g=a.groupby('user_id').agg(treinos90=('atividade_id','size'),outdoor90=('outdoor','sum'),outdoor_gps90=('outdoor_gps','sum'),dias90=('dia','nunique'),duracao90=('duracao_valida','sum'),km90=('distancia_valida','sum'),watch90=('watch','mean'),companhia90=('companhia','sum'))
 for col in g:b[col]=b.user_id.map(g[col]).fillna(0)
 b['videos90']=b.treinos90-b.outdoor90
 return b
L=exact90(L,'2026-08-01');C=exact90(C,'2026-10-01')
# Presence audit is kept separate from the value of image pixels.
presence=[]
for date,b in [('2026-07-31',L),('2026-09-30',C)]:
 monthly=b[['atividades_ar_livre_recente','atividades_ar_livre_anterior','atividades_ar_livre_antes']].sum(axis=1,min_count=1)
 presence.append(dict(data=date,pagantes=len(b),com_imagem=int(b.tem_heatmap.sum()),sem_imagem=int((1-b.tem_heatmap).sum()),outdoor90_zero=int(b.outdoor90.eq(0).sum()),imagem_sem_outdoor90=int((b.tem_heatmap.eq(1)&b.outdoor90.eq(0)).sum()),outdoor90_sem_imagem=int((b.tem_heatmap.eq(0)&b.outdoor90.gt(0)).sum()),imagem_sem_tinta=int((b.tem_heatmap.eq(1)&b.tinta_pixels.eq(0)).sum()),imagem_zero_eventos_com_BI_positivo=int((b.tem_heatmap.eq(1)&b.outdoor90.eq(0)&monthly.gt(0)).sum()),imagem_zero_eventos_e_BI_zero=int((b.tem_heatmap.eq(1)&b.outdoor90.eq(0)&monthly.eq(0)).sum()),sem_imagem_outdoor_sem_GPS=int((b.tem_heatmap.eq(0)&b.outdoor90.gt(0)&b.outdoor_gps90.eq(0)).sum())))
presence=pd.DataFrame(presence)

visual=['tinta_frac','grade_ocupada_frac','entropia_espacial','concentracao_grade_max','quadrante_max','bbox_frac','dispersao_espacial','contraste_rg_medio','tinta_vermelha_frac']
context=['fundo_parque_frac','fundo_agua_frac','fundo_avenida_frac','fundo_praia_frac']
quality=F.groupby('data').agg(n=('user_id','size'),tinta_min=('tinta_frac','min'),tinta_max=('tinta_frac','max'),concordancia_min=('tinta_quente_concordancia','min'),concordancia_media=('tinta_quente_concordancia','mean'),entropia_min=('entropia_espacial','min'),entropia_max=('entropia_espacial','max')).reset_index()

# Exploratory relations, not causal tests or feature selection for model tuning.
rho=[]
for v in visual+context:
 ok=L[v].notna();r=stats.spearmanr(L.loc[ok,v],L.loc[ok,'outdoor90']);rho.append(dict(visual=v,n=int(ok.sum()),rho_com_outdoor90=r.statistic,p_valor=r.pvalue))
rho=pd.DataFrame(rho);rho['qBH']=multipletests(rho.p_valor,method='fdr_bh')[1]
quartiles=[];bins={}
for v in ['tinta_frac','entropia_espacial','contraste_rg_medio']:
 q,bounds=pd.qcut(L.loc[L.tem_heatmap.eq(1),v],q=4,labels=False,retbins=True,duplicates='drop');bins[v]=bounds.tolist()
 tmp=L.loc[q.index,['user_id','churn60']].copy();tmp['quartil']=q+1
 for name,g in tmp.groupby('quartil'):
  ci=proportion_confint(g.churn60.sum(),len(g),method='wilson');quartiles.append(dict(visual=v,quartil=int(name),n=len(g),perdas=int(g.churn60.sum()),churn60=g.churn60.mean(),ic95_inf=ci[0],ic95_sup=ci[1]))
quartiles=pd.DataFrame(quartiles)

# Predictive ablation: same prospective target, same stratified folds and fixed logistic model.
# No temporal image validation is possible with just this one fully followed image date.
def design(b):
 d=pd.DataFrame(index=b.index)
 logs=['sessoes_semana','atividades_recente','atividades_anterior','atividades_antes','minutos_recente','tenure_dias','seguidores','seguindo','companhia30','dias_sem_treino','outdoor90','videos90','dias90','duracao90','km90','companhia90']
 for col in logs:d['log_'+col]=np.log1p(b[col].clip(lower=0))
 for col in ['video_share','trend_log','watch90','recusa30','ticket30','renovacao_off','renovacao_unknown','uso_missing','queda50']:d[col]=b[col].astype(float)
 d['queda_nao_comparavel']=(~b.queda_comparavel).astype(float)
 d['plano']=b.plano;d['canal']=b.canal
 d['tem_heatmap']=b.tem_heatmap.astype(float)
 for col in visual+context:d[col]=b[col]
 return d.replace([np.inf,-np.inf],np.nan)
DX=design(L);CX=design(C);base=[c for c in DX if c not in visual+context+['tem_heatmap']]
specs={'Tabelas':base,'Tabelas + disponibilidade':base+['tem_heatmap'],'Tabelas + geometria':base+['tem_heatmap']+visual,'Tabelas + geometria + fundo':base+['tem_heatmap']+visual+context}
no_notice=[c for c in base if c not in ['renovacao_off','renovacao_unknown']]
specs['Sem renovação: tabelas']=no_notice
specs['Sem renovação: + geometria']=no_notice+['tem_heatmap']+visual
def pipeline(cols):
 cat=[c for c in cols if c in ['plano','canal']];num=[c for c in cols if c not in cat]
 pre=ColumnTransformer([('num',Pipeline([('imp',SimpleImputer(strategy='median')),('scale',StandardScaler())]),num),('cat',OneHotEncoder(handle_unknown='ignore',drop='first',sparse_output=False),cat)])
 return Pipeline([('pre',pre),('lr',LogisticRegression(C=1,max_iter=2500,solver='lbfgs',random_state=2026))])
folds=list(StratifiedKFold(n_splits=5,shuffle=True,random_state=2026).split(DX,L.churn60));y=L.churn60.astype(int).to_numpy();preds={};foldresults=[];models={};metrics=[]
with threadpool_limits(limits=2):
 for name,cols in specs.items():
  pred=np.zeros(len(L))
  for k,(tr,te) in enumerate(folds):
   model=pipeline(cols);model.fit(DX.iloc[tr][cols],y[tr]);pred[te]=model.predict_proba(DX.iloc[te][cols])[:,1]
   foldresults.append(dict(modelo=name,fold=k+1,n_teste=len(te),eventos=int(y[te].sum()),AUC=roc_auc_score(y[te],pred[te]),AP=average_precision_score(y[te],pred[te]),Brier=brier_score_loss(y[te],pred[te])))
  preds[name]=pred
  top=np.argsort(pred)[-1500:];model=pipeline(cols);model.fit(DX[cols],y);models[name]=model
  metrics.append(dict(modelo=name,n=len(L),eventos=int(y.sum()),AUC=roc_auc_score(y,pred),AP=average_precision_score(y,pred),Brier=brier_score_loss(y,pred),LogLoss=log_loss(y,pred),precision_top1500=y[top].mean(),recall_top1500=y[top].sum()/y.sum(),media_risco_oof=pred.mean()))
  print('MODEL',metrics[-1],flush=True)
metrics=pd.DataFrame(metrics);foldresults=pd.DataFrame(foldresults)
L['risco_oof_tabelas']=preds['Tabelas'];L['risco_oof_geometria']=preds['Tabelas + geometria'];L['risco_oof_fundo']=preds['Tabelas + geometria + fundo']
# September probabilities are generated only as provisional research outputs, never a validated CRM list.
C['risco_pesquisa_tabelas']=models['Tabelas'].predict_proba(CX[specs['Tabelas']])[:,1]
C['risco_pesquisa_geometria']=models['Tabelas + geometria'].predict_proba(CX[specs['Tabelas + geometria']])[:,1]

# Conditional paired bootstrap of fixed OOF predictions. This is not full repeated model validation.
rng=np.random.default_rng(2026);neg=np.flatnonzero(y==0);pos=np.flatnonzero(y==1);contrasts=[('Geometria vs disponibilidade','Tabelas + disponibilidade','Tabelas + geometria'),('Geometria vs tabelas','Tabelas','Tabelas + geometria'),('Fundo adicional vs geometria','Tabelas + geometria','Tabelas + geometria + fundo'),('Sem renovação: imagem vs tabelas','Sem renovação: tabelas','Sem renovação: + geometria')];diffs=[]
for label,a,b in contrasts:
 vals=[]
 for i in range(600):
  ix=np.r_[rng.choice(neg,len(neg),replace=True),rng.choice(pos,len(pos),replace=True)];vals.append(roc_auc_score(y[ix],preds[b][ix])-roc_auc_score(y[ix],preds[a][ix]))
 diffs.append(dict(comparacao=label,delta_AUC=roc_auc_score(y,preds[b])-roc_auc_score(y,preds[a]),IC95_cond_inf=np.quantile(vals,.025),IC95_cond_sup=np.quantile(vals,.975),n_bootstrap=600))
diffs=pd.DataFrame(diffs)
# Calibration is descriptive for research OOF predictions.
calibration=[]
for name in ['Tabelas','Tabelas + geometria','Tabelas + geometria + fundo']:
 tmp=pd.DataFrame({'p':preds[name],'y':y});tmp['faixa']=pd.qcut(tmp.p,10,labels=False,duplicates='drop')
 for dec,g in tmp.groupby('faixa'):calibration.append(dict(modelo=name,decil=int(dec+1),n=len(g),risco_medio=g.p.mean(),frequencia=g.y.mean()))
calibration=pd.DataFrame(calibration)

# Keep the original segmentation; images enrich profiles rather than silently redefine them.
profiles=[]
for date,b in [('2026-07-31',L),('2026-09-30',C)]:
 for seg,g in b.groupby('segmento'):
  obs=g[g.tem_heatmap.eq(1)]
  r=dict(data=date,segmento=seg,n=len(g),n_imagem=len(obs),cobertura_imagem=len(obs)/len(g),tinta_mediana=obs.tinta_frac.median(),entropia_mediana=obs.entropia_espacial.median(),contraste_mediano=obs.contraste_rg_medio.median(),grade_mediana=obs.grade_ocupada_frac.median(),outdoor90_mediano=obs.outdoor90.median())
  if date=='2026-07-31':r['churn60']=g.churn60.mean()
  profiles.append(r)
profiles=pd.DataFrame(profiles)
paired=F[F.data.eq('2026-07-31')].merge(F[F.data.eq('2026-09-30')],on='user_id',suffixes=('_jul','_set'),validate='one_to_one');pair_stats=[]
for v in ['tinta_frac','entropia_espacial','contraste_rg_medio']:
 diff=paired[v+'_set']-paired[v+'_jul'];w=stats.wilcoxon(diff,zero_method='wilcox')
 pair_stats.append(dict(variavel=v,n=len(paired),mediana_julho=paired[v+'_jul'].median(),mediana_setembro=paired[v+'_set'].median(),mediana_diferenca=diff.median(),p_valor=w.pvalue))
pair_stats=pd.DataFrame(pair_stats)

# Three original/mask panels selected by feature quantiles, without looking at outcomes.
target=F[F.data.eq('2026-07-31')].sort_values('tinta_frac');ixs=[0,len(target)//4,len(target)//2,3*len(target)//4,len(target)-1];selected=target.iloc[ixs]
panels=Image.new('RGB',(5*205,440),'#eef3f1');draw=ImageDraw.Draw(panels)
with zipfile.ZipFile('heatmaps_2026-07-31.zip') as z:
 for i,r in enumerate(selected.itertuples()):
  im=Image.open(io.BytesIO(z.read(r.caminho_zip))).convert('RGB');_,mask=extract(im);ms=np.full((192,192,3),245,dtype=np.uint8);ms[mask]=[117,83,178];panels.paste(im,(i*205+6,8));panels.paste(Image.fromarray(ms),(i*205+6,224));draw.text((i*205+6,204),f'Tinta: {r.tinta_frac:.1%}',fill='#24443d')
panels.save(OUT/'exemplos_original_mascara.png')

data_dict=pd.DataFrame([
 ['tem_heatmap','Disponibilidade da imagem na data','0/1','Não é inatividade; controlada antes de medir valor de pixels.'],
 ['tinta_frac','Pixels que não são uma das seis cores exatas de fundo','fração da imagem','Tinta gráfica; não quilômetros nem volume fisiológico.'],
 ['grade_ocupada_frac','Células6×6 com pelo menos8pixels de tinta','fração36células','Dispersão no enquadramento, não diversidade real de destinos.'],
 ['entropia_espacial','Shannon das massas de tinta em36células, dividido porlog36','0–1','Maior dispersão visual, não regularidade temporal.'],
 ['concentracao_grade_max / quadrante_max','Maior fração da tinta em célula/quadrante','0–1','Concentração espacial na imagem.'],
 ['bbox_frac / dispersao_espacial','Área do retângulo / desvio espacial combinado','fração / coordenada normalizada','Dependente de escala/enquadramento que não conhecemos.'],
 ['contraste_rg_medio / tinta_vermelha_frac','R−G médio/255 e fração comR−G≥80','0–1','Chroma da paleta; não contagem calibrada de passagens.'],
 ['fundo_parque/agua/avenida/praia_frac','Pixels exatos das cores remanescentes de fundo','fração da imagem','Contexto desenhado, não preferência comprovada nem sobreposição da rota.'],
 ['componentes_graficos','Componentes conexos8vizinhos da máscara','contagem','Pode variar com renderização; não usado no modelo principal.'],
 ],columns=['variavel','definicao','unidade','limite'])
model_specs=pd.DataFrame([dict(modelo=name,n_variaveis=len(cols),variaveis='; '.join(cols)) for name,cols in specs.items()])
tables={'disponibilidade':presence,'qualidade_mascara':quality,'dicionario_visual':data_dict,'correlacao_treinos90':rho,'quartis_churn':quartiles,'metricas_OOF':metrics,'metricas_por_fold':foldresults,'delta_AUC_boot_condicional':diffs,'calibracao_OOF':calibration,'perfis_com_imagem':profiles,'mudancas_pareadas':pair_stats,'especificacoes_modelos':model_specs}
with pd.ExcelWriter(OUT/'analises_heatmaps.xlsx',engine='openpyxl') as w:
 for name,d in tables.items():
  d.to_excel(w,sheet_name=name[:31],index=False);w.sheets[name[:31]].freeze_panes='A2'
L.to_parquet(OUT/'landmark_julho_com_imagens.parquet',index=False);C.to_parquet(OUT/'pagantes_setembro_com_imagens.parquet',index=False)
profiles.to_csv(OUT/'perfis_visuais_segmentos.csv',index=False)
joblib.dump(dict(modelos=models,especificacoes=specs,visual=visual,contexto=context,bases_rgb=BASE),OUT/'modelos_pesquisa.joblib')
meta=dict(n_julho=len(L),n_imagens_julho=int(L.tem_heatmap.sum()),n_setembro=len(C),n_imagens_setembro=int(C.tem_heatmap.sum()),n_pares=len(paired),prevalencia=float(y.mean()),metodo='Regressão logísticaL2 C1;5folds estratificados aleatórios; sem validação temporal de imagens',visual=visual,contexto=context,seconds=time.time()-start,IA_extracao_chamadas=0)
data={k:v.astype(object).where(v.notna(),None).to_dict('records') for k,v in tables.items()};data['meta']=meta
(OUT/'resultados_heatmaps.json').write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
(OUT/'PROTOCOLO.md').write_text('''# Heatmaps — protocolo
Extrator de pixels determinístico, sem uso do alvo para construir máscaras ou escolher exemplos. Fontes: dois ZIPs e snapshots anteriores. Entradas macOS excluídas.
Fundo: seis cores exatas verificadas na paleta dos PNGs fornecidos. Toda tinta residual é proxy de sobreposição gráfica; ver teste de concordância quente, limites de enquadramento e exemplos de máscara. Não há validação humana externa nem acurácia semântica rotulada. A concordância de cores não substitui essa validação.
Julho: referência no encerramento31/07, alvo em[01/08,30/09),60dias. Setembro: referência encerramento30/09, sem alvo observado. Imagens de setembro nunca entram na validação de julho.
Baseline estruturado inclui uso, mix, sinais de cobrança/suporte/renovação, plano/canal e contagens exatas dos90dias de atividades, para não atribuir à imagem informação de frequência já disponível.
Mesmos5folds estratificados aleatórios(seed2026) nos quatro modelos. Medianas, escala e one-hot ajustados dentro de cada treino. C=1 fixo, sem seleção por resultados do teste. Métricas OOF diagnósticas na mesma coorte; não há teste temporal externo. O contexto histórico inclui a campanha de agosto.
Bootstrap pareado estratificado600vezes sobre previsões OOF FIXAS. Os intervalos não repetem o treinamento, não incluem toda a incerteza de ajuste ou de transferir no tempo. Não são evidência de prontidão operacional.
Manter os clusters originais: imagens enriquecem seus perfis, não redefinem personas automaticamente. Probabilidades de setembro são produtos de pesquisa provisórios, sem calibração temporal validada; não são uma lista aprovada de CRM, nem uplift ou ROI.
Testes de correlação, quartis e pares são exploratórios; pares condicionam sobrevivência e disponibilidade de imagem em ambas datas. Ausência de mapa não equivale a zero uso.
Nenhuma chamada de IA para extração foi realizada; custo monetário de compute/armazenamento e tempo humano não foi estimado. Não inferir custo total zero.
''',encoding='utf-8')
print('PRESENCE\n',presence.to_string(index=False));print('QUALITY\n',quality.to_string(index=False));print('METRICS\n',metrics.to_string(index=False));print('DELTAS\n',diffs.to_string(index=False));print('PROFILE\n',profiles.to_string(index=False));print('TIME',meta['seconds'],flush=True)
