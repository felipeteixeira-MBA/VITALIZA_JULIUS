# HISTÓRICO: não é pipeline canônico; verREADME eCHANGELOG antes de executar.
from pathlib import Path
import zipfile,io,hashlib,re,json
from collections import Counter
from PIL import Image,ImageOps,ImageDraw
import numpy as np,pandas as pd

OUT=Path('heatmaps_auditoria');OUT.mkdir(exist_ok=True)
users=set(pd.read_csv('usuarios.csv',usecols=['user_id']).user_id)
subscriptions=pd.read_csv('assinaturas.csv');subscriptions['inicio']=pd.to_datetime(subscriptions.inicio);subscriptions['data_fim']=pd.to_datetime(subscriptions.data_fim)
rows=[];palette=Counter();samples={};date_stats=[]
for p in sorted(Path('.').glob('heatmaps_2026-*.zip')):
 date=re.search(r'\d{4}-\d{2}-\d{2}',p.name)[0];ref=pd.Timestamp(date)+pd.Timedelta(days=1)
 active=set(subscriptions.loc[subscriptions.plano_atual.isin(['mensal','anual'])&subscriptions.inicio.lt(ref)&(subscriptions.data_fim.isna()|subscriptions.data_fim.ge(ref)),'user_id'])
 goodims=[]
 with zipfile.ZipFile(p) as z:
  for fileindex,info in enumerate(z.infolist()):
   if info.is_dir():continue
   name=info.filename;stem=Path(name).stem;safe=not Path(name).is_absolute() and '..' not in Path(name).parts
   r=dict(data=date,caminho=name,user_id=stem,bytes=info.file_size,nome_padrao=bool(re.fullmatch(r'u_[0-9a-f]{8}',stem)),usuario_cadastrado=stem in users,pagante_na_data=stem in active,seguro=safe,valida=False,erro=None,largura=None,altura=None,modo=None,sha256=None)
   if not safe:r['erro']='caminho_inseguro';rows.append(r);continue
   if info.file_size>25_000_000:r['erro']='acima_limite_auditoria';rows.append(r);continue
   try:
    raw=z.read(info);r['sha256']=hashlib.sha256(raw).hexdigest()
    with Image.open(io.BytesIO(raw)) as im:
     im.load();r.update(valida=True,largura=im.width,altura=im.height,modo=im.mode)
     if len(goodims)<8 and r['usuario_cadastrado'] and r['pagante_na_data']:
      goodims.append((stem,im.convert('RGB').copy()))
     if fileindex<8 or fileindex%500==0:
      ar=np.asarray(im.convert('RGB'));colors,counts=np.unique(ar.reshape(-1,3),axis=0,return_counts=True);palette.update({tuple(map(int,c)):int(n) for c,n in zip(colors,counts)})
   except Exception as exc:r['erro']=type(exc).__name__+': '+str(exc)[:160]
   rows.append(r)
 samples[date]=goodims
 date_stats.append(dict(data=date,pagantes_referencia=len(active),arquivos_zip=sum(1 for i in z.infolist() if not i.is_dir()) if False else sum(r['data']==date for r in rows)))
df=pd.DataFrame(rows)
df['metadado_macos']=df.caminho.str.startswith('__MACOSX/')|df.caminho.str.split('/').str[-1].str.startswith('._')
df['tipo_entrada']=np.where(df.metadado_macos,'metadado_auxiliar_macos','imagem_candidata')
df['id_repetido_na_data']=df.duplicated(['data','user_id'],keep=False)
df['conteudo_repetido_na_data']=df.sha256.notna()&df.duplicated(['data','sha256'],keep=False)
df.to_csv(OUT/'inventario_imagens.csv',index=False)
issues=df[(~df.valida)|(~df.nome_padrao)|(~df.usuario_cadastrado)|(~df.pagante_na_data)|df.id_repetido_na_data].copy();issues.to_csv(OUT/'inconsistencias_imagens.csv',index=False)
sr=[]
for date,g in df.groupby('data'):
 real=g[~g.metadado_macos]
 sr.append(dict(data=date,arquivos=len(g),metadados_macos=int(g.metadado_macos.sum()),imagens_candidatas=len(real),validas=int(real.valida.sum()),invalidas_reais=int((~real.valida).sum()),usuarios_distintos=real.user_id.nunique(),nomes_fora_padrao=int((~real.nome_padrao).sum()),usuarios_desconhecidos=int((~real.usuario_cadastrado).sum()),nao_pagantes_na_data=int((~real.pagante_na_data).sum()),ids_repetidos=int(real.id_repetido_na_data.sum()),conteudos_repetidos=int(real.conteudo_repetido_na_data.sum())))
summary=pd.DataFrame(sr)
summary=summary.merge(pd.DataFrame(date_stats)[['data','pagantes_referencia']],on='data');summary['cobertura_validas_em_pagantes']=df[df.valida&df.pagante_na_data].groupby('data').user_id.nunique().reindex(summary.data).to_numpy()/summary.pagantes_referencia
summary.to_csv(OUT/'resumo_auditoria.csv',index=False)
pd.DataFrame([{'R':c[0],'G':c[1],'B':c[2],'pixels_amostra':n} for c,n in palette.most_common(40)]).to_csv(OUT/'paleta_amostra.csv',index=False)
for date,ims in samples.items():
 if not ims:continue
 canvas=Image.new('RGB',(4*320,2*350),'#edf1f5');draw=ImageDraw.Draw(canvas)
 for i,(uid,im) in enumerate(ims):
  im.thumbnail((300,300));x=i%4*320+(320-im.width)//2;y=i//4*350+12;canvas.paste(im,(x,y));draw.text((i%4*320+15,i//4*350+318),date+' | '+uid,fill='#23344b')
 canvas.save(OUT/('amostra_'+date+'.png'))
with pd.ExcelWriter(OUT/'auditoria_heatmaps.xlsx') as w:
 summary.to_excel(w,sheet_name='resumo',index=False);issues.to_excel(w,sheet_name='inconsistencias',index=False);df.to_excel(w,sheet_name='inventario',index=False)
print('RESUMO\n',summary.to_string(index=False));print('INCONSISTENCIAS\n',issues.to_string(index=False));print('DIMENSOES\n',df.groupby(['data','largura','altura','modo'],dropna=False).size().to_string());print('PALETA\n',palette.most_common(15))
