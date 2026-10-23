# HISTÓRICO: não é pipeline canônico; verREADME eCHANGELOG antes de executar.
from pathlib import Path
import json
import numpy as np,pandas as pd
from sklearn.metrics import roc_auc_score,average_precision_score,brier_score_loss
P=Path('heatmaps_integrados');J=json.loads((P/'resultados_heatmaps.json').read_text());L=pd.read_parquet(P/'landmark_julho_com_imagens.parquet');C=pd.read_parquet(P/'pagantes_setembro_com_imagens.parquet')
coherent=((L.tem_heatmap.eq(1)&L.outdoor90.gt(0)&L.tinta_pixels.gt(0))|(L.tem_heatmap.eq(0)&L.outdoor90.eq(0)))
d=L[coherent];y=d.churn60.astype(int).to_numpy();a=d.risco_oof_tabelas.to_numpy();b=d.risco_oof_geometria.to_numpy()
rng=np.random.default_rng(2042);pos=np.flatnonzero(y==1);neg=np.flatnonzero(y==0);vals=[]
for i in range(600):
 ix=np.r_[rng.choice(pos,len(pos),True),rng.choice(neg,len(neg),True)];vals.append(roc_auc_score(y[ix],b[ix])-roc_auc_score(y[ix],a[ix]))
sens=pd.DataFrame([dict(analise='Avaliação em casos coerentes; sem re-treino',n=len(d),eventos=int(y.sum()),AUC_tabelas=roc_auc_score(y,a),AUC_geometria=roc_auc_score(y,b),delta_AUC=roc_auc_score(y,b)-roc_auc_score(y,a),IC95_cond_inf=np.quantile(vals,.025),IC95_cond_sup=np.quantile(vals,.975),AP_tabelas=average_precision_score(y,a),AP_geometria=average_precision_score(y,b),Brier_tabelas=brier_score_loss(y,a),Brier_geometria=brier_score_loss(y,b))])
issues=[]
for date,b in [('2026-07-31',L),('2026-09-30',C)]:
 for condition,label in [(b.tem_heatmap.eq(1)&b.outdoor90.eq(0),'imagem_sem_evento_ar_livre_90dias'),(b.tem_heatmap.eq(0)&b.outdoor90.gt(0),'evento_ar_livre_sem_imagem'),(b.tem_heatmap.eq(1)&b.tinta_pixels.eq(0),'imagem_sem_tinta_detectada')]:
  t=b.loc[condition,['user_id','outdoor90','tinta_pixels','tem_heatmap']].copy();t['data']=date;t['motivo']=label;issues.append(t)
issues=pd.concat(issues,ignore_index=True);issues.to_csv(P/'casos_a_reconciliar.csv',index=False)
J['sensibilidade_coerencia']=sens.astype(object).where(sens.notna(),None).to_dict('records');(P/'resultados_heatmaps.json').write_text(json.dumps(J,ensure_ascii=False,indent=2),encoding='utf-8')
with pd.ExcelWriter(P/'analises_heatmaps.xlsx',engine='openpyxl',mode='a',if_sheet_exists='replace') as w:
 sens.to_excel(w,sheet_name='sensibilidade_coerencia',index=False);issues.to_excel(w,sheet_name='casos_a_reconciliar',index=False)
print(sens.to_string(index=False))
