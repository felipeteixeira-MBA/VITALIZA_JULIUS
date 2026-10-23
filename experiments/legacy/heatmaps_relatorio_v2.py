# HISTÓRICO: não é pipeline canônico; verREADME eCHANGELOG antes de executar.
from pathlib import Path
import json,base64,shutil,zipfile,importlib.metadata
import numpy as np,pandas as pd
import plotly.graph_objects as go

O=Path('heatmaps_integrados');J=json.loads((O/'resultados_heatmaps.json').read_text());M=J['meta'];D={k:pd.DataFrame(v) for k,v in J.items() if k!='meta'}
def pct(v,d=2):return f'{100*v:.{d}f}%'.replace('.',',')
def table(d,pc=()):
 d=d.copy()
 for c in d:
  if c in pc:d[c]=d[c].map(lambda v:'—' if pd.isna(v) else pct(v))
  elif pd.api.types.is_float_dtype(d[c]):d[c]=d[c].map(lambda v:'—' if pd.isna(v) else ('abaixo da precisão numérica' if v==0 and c in ['p_valor','qBH'] else f'{v:.6g}'))
 return '<div class="table-wrap">'+d.to_html(index=False,border=0)+'</div>'
def chart(f,id,h=385):
 f.update_layout(template='plotly_white',height=h,margin=dict(l=70,r=25,t=45,b=65),font=dict(family='Arial',size=12,color='#273b46'),paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',colorway=['#116e69','#7453b2','#ed7c6a','#729aa6'],legend=dict(orientation='h',y=1.16))
 f.update_xaxes(automargin=True);f.update_yaxes(automargin=True)
 return f.to_html(full_html=False,include_plotlyjs=False,div_id='hm-'+id,config={'responsive':True,'displaylogo':False})
def note(t,b,coral=False):return '<aside class="callout '+('coral' if coral else 'teal')+'"><b>'+t+'</b><p>'+b+'</p></aside>'
def src(t):return '<p class="evidence">'+t+'</p>'
metric=D['metricas_OOF'].set_index('modelo');delta=D['delta_AUC_boot_condicional'];core=metric.iloc[:4].reset_index()

f=go.Figure();f.add_trace(go.Scatter(x=delta.delta_AUC,y=delta.comparacao,mode='markers',marker=dict(size=12,color=['#116e69','#7453b2','#ed7c6a','#729aa6']),error_x=dict(type='data',symmetric=False,array=delta.IC95_cond_sup-delta.delta_AUC,arrayminus=delta.delta_AUC-delta.IC95_cond_inf)));f.add_vline(x=0,line_dash='dash',line_color='#8a9b9b');f.update_layout(xaxis_title='ΔROC-AUC · positivo favorece imagem/variável adicional',yaxis=dict(autorange='reversed'));delta_chart=chart(f,'delta',390)
f=go.Figure();q=D['quartis_churn'];q=q[q.visual.eq('tinta_frac')];f.add_trace(go.Bar(x=['Q'+str(int(x)) for x in q.quartil],y=q.churn60*100,marker_color=['#ed7c6a','#7453b2','#16867e','#116e69'],error_y=dict(type='data',symmetric=False,array=(q.ic95_sup-q.churn60)*100,arrayminus=(q.churn60-q.ic95_inf)*100),customdata=q[['n','perdas']],hovertemplate='%{x}<br>Churn60 %{y:.2f}%<br>n %{customdata[0]:,}; perdas %{customdata[1]:,}<extra></extra>'));f.update_layout(xaxis_title='Quartil da fração de tinta em julho · menor → maior',yaxis_title='Churn60 observado (%)');quartile_chart=chart(f,'quartis')
f=go.Figure();r=D['correlacao_treinos90'];r=r[r.visual.isin(M['visual'])].sort_values('rho_com_outdoor90');f.add_trace(go.Bar(x=r.rho_com_outdoor90,y=r.visual,orientation='h',marker_color=['#7453b2' if x<0 else '#116e69' for x in r.rho_com_outdoor90]));f.update_layout(xaxis=dict(title='Spearman com nº de treinos ao ar livre nos90dias anteriores',range=[-1,1]));rho_chart=chart(f,'rho',420)
f=go.Figure();p=D['perfis_com_imagem'];p=p[p.data.eq('2026-07-31')];f.add_trace(go.Bar(x=p.segmento,y=p.cobertura_imagem*100,customdata=p[['n','n_imagem']],marker_color=['#ed7c6a','#7453b2','#116e69','#729aa6'],hovertemplate='%{x}<br>Cobertura %{y:.2f}%<br>n %{customdata[0]:,}; imagens %{customdata[1]:,}<extra></extra>'));f.update_layout(yaxis_title='Pagantes do segmento com heatmap (%)');coverage_chart=chart(f,'cobertura')
f=go.Figure();f.add_trace(go.Scatter(x=[0,1],y=[0,1],mode='lines',name='Referência ideal',line=dict(dash='dash',color='#9aabab')))
for model,g in D['calibracao_OOF'].groupby('modelo'):f.add_trace(go.Scatter(x=g.risco_medio,y=g.frequencia,mode='lines+markers',name=model,customdata=g[['n','decil']],hovertemplate='%{fullData.name}<br>Risco médio %{x:.2%}<br>Frequência %{y:.2%}<br>n %{customdata[0]:,}<extra></extra>'))
f.update_layout(xaxis=dict(title='Probabilidade média OOF',tickformat='.0%'),yaxis=dict(title='Frequência observada',tickformat='.0%'));cal_chart=chart(f,'calibracao',400)

img=base64.b64encode((O/'exemplos_original_mascara.png').read_bytes()).decode()
sections=[]
def add(t):sections.append(t)
add('''<section id="heatmaps-v2"><span class="eyebrow">14 · HEATMAPS &amp; INCREMENTAL VALUE · NOVO NA V2</span><h2>Agora as imagens entraram. Elas melhoraram o diagnóstico?</h2><p class="lead">Processamos25.473 imagens reais dos ZIPs, extraímos19medidas de pixels e fizemos uma ablação preditiva com controle de disponibilidade. A resposta, com os métodos testados, é: <b>ganho incremental não demonstrado</b>.</p>''')
add(f'''<div class="kpis"><div><small>IMAGENS PROCESSADAS</small><b>25.473</b><span>12.426 de julho +13.047 de setembro.</span></div><div><small>VALIDAÇÃO OOF</small><b>14.032 pessoas</b><span>1.469 saídas em60dias;5folds estratificados.</span></div><div><small>ΔAUC · PIXELS ALÉM DA PRESENÇA</small><b>{delta.iloc[0].delta_AUC:+.6f}</b><span>IC condicional cruza zero.</span></div><div><small>PROCESSAMENTO DAS IMAGENS</small><b>Python · pixels</b><span>Sem chamada multimodal; sem validação semântica humana independente.</span></div></div>''')
add(note('O que muda — e o que não muda','Os três clusters originais foram preservados e receberam descrições visuais. Receita, personas comportamentais e hipóteses da V1 não foram silenciosamente redefinidas. Nesta V2 há uma avaliação preditiva <b>dentro da coorte de julho</b>, mas ainda não existe teste temporal externo nem uma lista de CRM aprovada.'))
add('''<h3>14.1 · Entradas, processo e saídas</h3><div class="three"><div class="card"><h3>Entrada</h3><p>Dois ZIPs;192×192pixels por imagem; IDs associados às tabelas; cinco metadados de macOS excluídos.</p></div><div class="card"><h3>Processo</h3><p>Separar tinta e fundo; medir área, dispersão e chroma; unir por usuário+data; comparar modelos nos mesmos folds.</p></div><div class="card"><h3>Saída</h3><p>Variáveis visuais, perfis enriquecidos, auditoria cruzada, métricas OOF, sensibilidade e código reproduzível.</p></div></div>''')
add('<h3>14.2 · Como uma imagem virou variável</h3><img alt="Cinco heatmaps de julho e suas máscaras de tinta correspondentes; seleção por quantis sem olhar o churn" style="display:block;width:100%;height:auto;border:1px solid #dce5e3;border-radius:10px" src="data:image/png;base64,'+img+'">')
add(src('Linha superior: PNGs originais; inferior: tinta residual em roxo. Exemplos escolhidos por quantis da área de tinta, sem consultar o alvo. O primeiro mostra um caso sem tinta detectada — uma inconsistência a investigar, não prova de inatividade.'))
add('''<p>Os seis tons exatos de fundo foram identificados na paleta: neutro, vias claras, parque, água, avenida e praia. A máscara residual mede a <b>tinta no enquadramento</b>. Sua concordância média com pixels quentes é&gt;99,99%, um teste técnico de paleta — <b>não uma acurácia semântica contra rótulos humanos</b>.</p>''')
add(table(D['dicionario_visual']))
add(note('O que não inferimos de um PNG estilizado','Não extraímos quilômetros, endereço, “treina na praia”, quantidade real de passagens, duração nem intensidade fisiológica. Fração verde de fundo não comprova que a rota passou por um parque. Escala e enquadramento não foram calibrados fisicamente. Não houve comparação com modelo multimodal ou validação por amostra humana rotulada.','coral'))
add('''<h3>14.3 · Uma auditoria nova: imagem íntegra não garante fontes coerentes</h3>''')
add(table(D['disponibilidade']))
add(note('316casos em julho e349em setembro precisam de reconciliação','Nesses casos há heatmap, mas nenhum evento de treino ao ar livre na janela exata de90dias reconstruída em atividades.parquet. Também há5/6imagens sem tinta detectada. Datas de captura, regras de GPS, sincronização, janela e relação com o BI precisam ser verificadas. <b>Não decidimos automaticamente qual fonte está errada.</b> Os533/610casos com treino mas sem mapa indicam cobertura a reconciliar; a condição “só existe mapa se…” não garante o inverso.','coral'))
add('<details><summary>Detalhe da extração, paleta e divergências</summary>'+table(D['qualidade_mascara'])+'<p>A auditoria de arquivo anterior continua válida: IDs existem, correspondem a pagantes e os PNGs decodificam. A auditoria desta etapa é diferente: compara a coerência semântica de fontes. Arquivos de casos a reconciliar foram exportados com usuário, data e motivo.</p></details>')
add('''<h3>14.4 · Há associação visual com churn?</h3>'''+quartile_chart)
add(src('12.426 usuários com imagem em julho; quartis definidos na imagem de julho; desfecho em01/08–29/09; IC95%Wilson. Usuários sem imagem ficam fora deste gráfico, não são imputados como tinta zero.'))
add('''<p>No quartil de menor tinta, o churn60 é11,66%; no maior,8,18%. Porém, isso é uma <b>associação bruta</b>. A imagem acumula90dias e não representa apenas a frequência da última semana/mês.</p>'''+rho_chart)
add(note('Associação não é ganho incremental','Fração de tinta tem Spearman≈0,715 com os treinos ao ar livre nos90dias. Parte do que parece um novo sinal visual pode apenas reproduzir a frequência já presente nas tabelas. Por isso, a comparação justa precisa de um baseline com esse histórico, não apenas cadastro.'))
add('''<h3>14.5 · O teste justo: quatro ablações, mesmos usuários e folds</h3><ol><li><b>Tabelas:</b> uso, mix, tendência, plano/canal, tempo de casa, rede, cobrança/suporte/renovação e atividade detalhada nos90dias.</li><li><b>+Disponibilidade:</b> controlar apenas a existência do mapa.</li><li><b>+Geometria:</b> disponibilidade mais9medidas de tinta, dispersão e chroma.</li><li><b>+Fundo:</b> acrescentar4frações de contexto desenhado.</li></ol><p>Regressão logísticaL2,C=1fixo. Medianas, escala e one-hot são ajustados <b>dentro de cada treino</b>. Cinco folds estratificados por pessoa, seed2026; nenhuma imagem de setembro entra nos testes de julho. Não foi feita busca de hiperparâmetros nem seleção de features por churn.</p>''')
add(table(core[['modelo','AUC','AP','Brier','LogLoss','precision_top1500','recall_top1500']],pc=['precision_top1500','recall_top1500']))
add(note('Resultado principal','Tabelas: ROC-AUC0,825578. Com geometria:0,826175. Mas, depois de controlar a simples disponibilidade, o delta é apenas+0,000065, com IC condicional aproximado[−0,001961;+0,001945]. AP, Brier e precisão no topo não melhoram de forma consistente. Isso não sustenta acrescentar esse processamento à operação por ganho preditivo.'))
add(delta_chart)
add(src('600reamostragens pareadas e estratificadas das previsões OOF FIXAS. Esses intervalos não repetem o treino e não capturam toda a incerteza do modelo nem a transferência temporal. São exploratórios, não um teste confirmatório de prontidão.'))
add('''<details><summary>Como ler as métricas — e o que não concluir</summary><ul><li><b>ROC-AUC:</b> ordenação de quem sai versus quem fica; maior é melhor, sem prometer acerto de cada pessoa.</li><li><b>AP:</b> average precision; usa precisão e recall ao variar o limiar. A prevalência da coorte é10,47%.</li><li><b>Brier/LogLoss:</b> erro de probabilidades; menores são melhores.</li><li><b>Topo1500:</b> comparação diagnóstica de ranking OOF, não1.500contatos aprovados nem estimativa de persuadíveis.</li></ul><p>O topo de tabelas contém641saídas observadas; geometria629, entre1.500 selecionados por score OOF. Não significa12clientes perdidos por intervenção: nenhuma intervenção foi aplicada por esse ranking.</p>'''+cal_chart+'</details>')
add('''<h3>14.6 · Duas tentativas de contrariar o resultado</h3><div class="two"><div class="card"><h3>Retirar o estado de renovação</h3><p>Será que os avisos explícitos escondiam o valor da imagem? Sem essas variáveis, AUC passa de0,761427(tabelas) para0,760313(+imagem). Delta−0,001114, com intervalo condicional cruzando zero. Retirar a coluna não equivale a estudar exclusivamente quem ainda não demonstrou intenção de sair.</p></div><div class="card"><h3>Avaliar só os casos coerentes</h3><p>Em13.178 casos consistentes entre presença do mapa e evento de ar livre, delta AUC≈+0,000865, novamente com intervalo cruzando zero. Aqui só restringimos a avaliação das mesmas previsões OOF; <b>não houve novo treino</b> excluindo divergências.</p></div></div>''')
add('<details><summary>Todos os resultados e sensibilidades</summary>'+table(D['metricas_OOF'])+table(D['delta_AUC_boot_condicional'])+table(D['sensibilidade_coerencia'])+'</details>')
add(note('O resultado negativo tem escopo','Não demonstramos que “qualquer IA visual seria inútil”. Testamos features determinísticas específicas com um classificador linear regularizado, nesta coorte. Representações mais ricas ou modelos não lineares poderiam mudar a resposta, mas precisariam de avaliação sem viés e dados temporais adicionais — não apenas de uma narrativa plausível.','coral'))
add('''<h3>14.7 · Como os três perfis ficam enriquecidos?</h3>'''+coverage_chart)
add(table(p[['segmento','n','n_imagem','cobertura_imagem','tinta_mediana','entropia_mediana','outdoor90_mediano']],pc=['cobertura_imagem','tinta_mediana']))
add('''<p><b>S1:</b> menor cobertura de imagem, mas maior tinta mediana entre os que têm mapa. Isso não contradiz necessariamente seu uso recente esparso: o mapa acumula90dias e a descrição de engajamento enfatiza o último mês. <b>S2/S3:</b> cobertura maior; características visuais permanecem descrições, sem prova de necessidade ou resposta a uma oferta.</p>''')
add('<details><summary>Perfis nas duas datas e mudanças pareadas</summary>'+table(D['perfis_com_imagem'],pc=['cobertura_imagem','tinta_mediana','churn60'])+table(D['mudancas_pareadas'])+'<p>Os10.546 pares pertencem a quem tem imagem nas duas datas e permanece elegível no corte seguinte. Isso condiciona sobrevivência/disponibilidade. Mudanças nesses pares <b>não testam se mudanças de rota causam retenção</b> e não podem entrar retrospectivamente no modelo de julho.</p></details>')
add('''<h3>14.8 · Decisão metodológica e próximos passos</h3><ul><li><b>Manter:</b> features extraídas, rastreabilidade, exemplos de máscara e perfis enriquecidos para investigação.</li><li><b>Não aprovar automaticamente:</b> feature pipeline de imagem em produção, gasto com modelo multimodal ou nova segmentação só porque os mapas são visualmente atraentes.</li><li><b>Reconciliar primeiro:</b> casos de imagem sem treino, registros de treino sem mapa e imagens sem tinta.</li><li><b>Validar:</b> amostra humana rotulada para semântica; se houver hipótese nova, comparar pixels e multimodal com protocolo comum.</li><li><b>Testar no tempo:</b> congelar transformações de julho e obter os desfechos da imagem de setembro até29/11/2026. Sem isso, a generalização temporal continua desconhecida.</li></ul>''')
add(note('Custo medido não é custo monetário','A execução de referência levou aproximadamente'+str(round(M['seconds']))+'segundos neste ambiente, incluindo leitura, features e avaliações. Não houve chamada a um serviço de visão/LLM para extrair imagens. Compute, armazenamento, revisão humana e IA de redação não foram precificados; logo, não calculamos custo total, lucro ou ROI desta inclusão.'))
add('''<p class="evidence">Fonte: ZIPs de heatmaps, snapshots anteriores e atividades.parquet. Dados educacionais sintéticos. As bases derivadas contêm probabilidades de pesquisa para setembro, claramente provisórias e sem validação temporal; não são uma fila aprovada de CRM nem uplift individual.</p></section>''')

newhyp=[
 dict(id='H15',pergunta='Os pixels acrescentam previsão além das tabelas?',mecanismo='Informação visual complementar à frequência e ao histórico.',variaveis='9medidas visuais, disponibilidade e baseline estruturado90dias',metodo='Ablação logísticaL2;5folds estratificados; bootstrap condicional OOF600vezes',evidencia='Geometria vs disponibilidade: ΔAUC+0,000065; ICcond.[−0,001961;+0,001945]. AP/Brier não melhoram.',status='Inconclusiva: ganho não demonstrado',limitacoes='Um classificador/uma coorte; não há teste temporal, equivalência ou validação humana semântica.',interpretacao='A associação bruta não trouxe ganho incremental demonstrável no desenho testado; não prova inutilidade universal de imagens.',n_observacoes=14032,periodo='Features anteriores01/08; alvo01/08–29/09; setembro fora do teste'),
 dict(id='H16',pergunta='A tinta visual se associa a volume de treino registrado?',mecanismo='O mapa acumula parte do mesmo histórico comportamental das tabelas.',variaveis='tinta_frac e outdoor90',metodo='Spearman exploratório entre medidas anteriores ao corte',evidencia='rho≈0,715; n12.426. Churn60 Q1=11,66%, Q4=8,18%, sem ajuste.',status='Sustentada como associação',limitacoes='Tinta não é distância nem visitas calibradas; quartis excluem quem não tem imagem.',interpretacao='Há redundância com frequência de90dias; associação não significa nova informação preditiva ou causa de retenção.',n_observacoes=12426,periodo='Imagem31/07 e90dias anteriores; churn nos60dias posteriores'),
 dict(id='H17',pergunta='Mapas e eventos concordam na janela de90dias?',mecanismo='Fontes deveriam representar atividades compatíveis na mesma referência.',variaveis='presença, tinta_pixels e eventos outdoor90',metodo='Reconciliação de usuário/data e janela exata',evidencia='Imagem sem evento outdoor90:316 em julho e349 em setembro; sem tinta:5 e6.',status='Contrariada sob a janela adotada',limitacoes='Não determina fonte errada; revisar captura, GPS, fuso, janela e sincronização.',interpretacao='Integridade de arquivo não garante consistência semântica; os casos devem ser auditados, não imputados automaticamente como inativos.',n_observacoes=25473,periodo='Imagens nas duas datas; não são25.473pessoas distintas')]
extra='''
<script>
const HM=__DATA__;
const HYP_IMG=__HYP__;
for(const r of HYP_IMG)if(!DB.hipoteses.some(x=>x.id===r.id))DB.hipoteses.push(r);
const h6=DB.hipoteses.find(x=>x.id==='H6');if(h6)h6.interpretacao='Na V1 examinamos distribuições e ajuste. A V2 acrescenta avaliação preditiva OOF na mesma coorte, sem generalização temporal demonstrada.';
for(const [key,values]of Object.entries(HM)){if(key==='meta'||!Array.isArray(values))continue;const name='img_'+key;DB[name]=values;const option=document.createElement('option');option.value=name;option.textContent=name;document.getElementById('table-select').appendChild(option)}
hypotheses();
</script>
'''.replace('__DATA__',json.dumps(J,ensure_ascii=False).replace('</','<\\/')).replace('__HYP__',json.dumps(newhyp,ensure_ascii=False))
base=Path('diagnostico_v1/relatorio_executivo.html').read_text()
base=base.replace('Diagnóstico Analítico V1','Diagnóstico Analítico V2 — Heatmaps integrados')
base=base.replace('DIAGNÓSTICO ANALÍTICO V1','DIAGNÓSTICO ANALÍTICO V2')
base=base.replace('<span>14 hipóteses</span>','<span>17 hipóteses ·3novas sobre imagens</span>')
base=base.replace('As imagens heatmaps_90d não estão.','Os heatmaps foram recebidos e integrados nesta V2; confira o capítulo14.')
base=base.replace('falta de imagens e de datas de atualização de curtidas','falta de validação humana rotulada das imagens e de datas de atualização de curtidas')
base=base.replace('Não houve anotação por IA de texto/imagem nem demonstração do seu valor.','Texto não foi extraído por IA. Imagens receberam extração determinística e avaliação OOF dentro da coorte, sem ganho incremental demonstrado; falta teste temporal externo.')
base=base.replace('Não há slides originais, imagens ou pesquisa externa de mercado confirmada.','Não há slides originais nem pesquisa externa de mercado confirmada. Os dois ZIPs de imagens foram adicionados nesta V2.')
base=base.replace('14 hipóteses: evidência que pode contrariar o briefing','17 hipóteses:14base +3sobre imagens')
base=base.replace('Clusters + associação','Clusters + associação + ablação de imagens')
base=base.replace('<div class="hero-tags">','<div class="hero-tags"><a style="color:#fff;text-decoration:none;background:#ffffff15;padding:6px10px;border-radius:6px" href="#heatmaps-v2">NOVO: ir à análise das imagens↓</a>',1)
base=base.replace('<div class="nav-bottom">','<a href="#heatmaps-v2">14 · Heatmaps &amp; validação</a><div class="nav-bottom">',1)
newfinding=note('Novo na V2 · Associar não é acrescentar informação','As imagens foram incorporadas. O ganho de ROC-AUC dos pixels sobre tabelas+disponibilidade é+0,000065, com intervalo exploratório cruzando zero. O capítulo14documenta extração, divergências, ablação e limites. <a href="#heatmaps-v2">Abrir análise completa das imagens→</a>')
base=base.replace('<section id="dilemma">',newfinding+'<section id="dilemma">',1)
footer='<div class="footer">'
base=base.replace(footer,''.join(sections)+footer,1)
base=base.replace('</body>',extra+'</body>')
(O/'relatorio_integrado_v2.html').write_text(base,encoding='utf-8')

# Combined analytical workbook; old results remain unchanged except hypothesis register extension.
shutil.copyfile('diagnostico_v1/diagnostico_tabelas.xlsx',O/'diagnostico_v2_tabelas.xlsx')
with pd.ExcelWriter(O/'diagnostico_v2_tabelas.xlsx',engine='openpyxl',mode='a',if_sheet_exists='replace') as w:
 h=pd.read_excel('diagnostico_v1/diagnostico_tabelas.xlsx',sheet_name='hipoteses')
 h.loc[h.id.eq('H6'),'interpretacao']='Na V1 examinamos distribuições e ajuste. A V2 acrescenta avaliação preditiva OOF na mesma coorte, sem generalização temporal demonstrada.'
 pd.concat([h,pd.DataFrame(newhyp)],ignore_index=True).to_excel(w,sheet_name='hipoteses',index=False)
 for name,d in D.items():d.to_excel(w,sheet_name=('img_'+name)[:31],index=False)
 issues=pd.read_csv(O/'casos_a_reconciliar.csv');issues.to_excel(w,sheet_name='img_casos_a_reconciliar',index=False)

for name in ['heatmaps_integracao.py','heatmaps_sensibilidade.py','heatmaps_relatorio_v2.py']:
 source=Path(__file__).resolve().with_name(name);target=(O/name).resolve()
 if source!=target:shutil.copyfile(source,target)
packages=['pandas','numpy','scipy','scikit-learn','statsmodels','threadpoolctl','pyarrow','openpyxl','plotly','joblib','Pillow']
(O/'requirements.txt').write_text('\n'.join(x+'=='+importlib.metadata.version(x) for x in packages)+'\n')
(O/'LEIA_ME.md').write_text('''# Vitaliza V2 — heatmaps integrados
Relatório completo atualizado com capítulo14. A V1 segue como insumo histórico; os resultados antigos não foram substituídos por suposições de imagem.

## Conteúdo
19medidas visuais porimagem em CSV/Parquet; snapshots enriquecidos; seis modelos de pesquisa; métricasOOF; sensibilidades; auditoria cruzada; planilha combinadaV2; exemplos de máscaras e código.

## Reproduzir
Extraia mantendo as pastas. Na raiz da pasta de trabalho devem existir os dois ZIPs originais de heatmaps e atividades.parquet (não duplicados neste pacote). A pasta diagnostico_v1 fornecida como insumo deve conter os dois snapshots originais, a planilha e o HTML anterior. Rode:
python -m pip install -r heatmaps_integrados/requirements.txt
python heatmaps_integrados/heatmaps_integracao.py
python heatmaps_integrados/heatmaps_sensibilidade.py
python heatmaps_integrados/heatmaps_relatorio_v2.py

## Cuidados
Variáveis são proxies gráficos, não distância, passagens ou geografia real. A extração não foi comparada a rótulos humanos nem a um modelo multimodal. Correlação bruta não demonstra ganho incremental. A comparação usouCV estratificada na mesma coorte, não teste temporal externo. Intervalos de delta são condicionais a previsõesOOF fixas.
Probabilidades de setembro nas bases derivadas são exclusivamente de pesquisa e não têm validação temporal ou uplift: NÃO são uma lista aprovada de contato. Modelos joblib devem ser carregados apenas quando a origem é confiável.
Nenhuma chamada multimodal foi realizada; custo monetário total não foi estimado. Não interpretar como custo total zero.
Casos a reconciliar incluem imagem sem evento outdoor90, evento sem imagem e máscara sem tinta. Não determinamos automaticamente qual fonte está errada. Parâmetros/cores estão no protocolo e no código.
No HTML, a tabulação de p_valor bruto zero representa limitação numérica de cálculos extremos; não probabilidade exatamente zero. Métricas e deltas do estudo são exploratórios.
''',encoding='utf-8')
with zipfile.ZipFile('Vitaliza_V2_heatmaps_reutilizavel.zip','w',zipfile.ZIP_DEFLATED) as z:
 for file in O.iterdir():z.write(file,arcname=str(file))
 for name in ['landmark_julho.parquet','pagantes_setembro.parquet','relatorio_executivo.html','diagnostico_tabelas.xlsx']:
  f=Path('diagnostico_v1')/name;z.write(f,arcname=str(f))
print('HTML V2:',len(base),'chars. New hypotheses:',len(newhyp));print('Workbook sheets:',len(pd.ExcelFile(O/'diagnostico_v2_tabelas.xlsx').sheet_names))
