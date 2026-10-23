# HISTÓRICO: não é pipeline canônico; verREADME eCHANGELOG antes de executar.
from pathlib import Path
from playwright.sync_api import sync_playwright
import fitz,json

root=Path('.').resolve();html=root/'artifacts/da9bffe9-66be-4000-aaaf-c4ecb556ad57/index.html'
out=root/'Vitaliza_CRISP_DM_aula_completa.pdf'
css='''
@page {size:1120px 1750px; margin:42px 36px 48px;}
@media print {
 html{scroll-behavior:auto!important}body{font-size:15px!important;line-height:1.65!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
 main{margin:0!important;padding:0!important;width:auto!important}
 .hero{padding:40px!important;margin-bottom:26px!important;border-radius:16px!important}
 .hero h1{font-size:52px!important}.hero p{font-size:18px!important}
 section{padding:25px 0!important;break-before:auto!important} .hero{break-after:page!important} .eyebrow,h2,h3{break-after:avoid!important} .lead{break-before:avoid!important}
 h2{font-size:29px!important}h3{font-size:19px!important}
 .table-wrap{overflow:visible!important;max-height:none!important}
 table{table-layout:auto;width:100%!important;font-size:11px!important}
 th,td{padding:8px!important;min-width:0!important;overflow-wrap:anywhere!important}
 th{position:static!important;white-space:normal!important}
 tr{break-inside:avoid!important} p,li{orphans:3;widows:3} li{break-inside:avoid!important}
 .plotly-graph-div,.jschart,.io,.timeline,.formula,.quiz-card{break-inside:avoid!important}
 .two,.three,.four,.phase-grid{break-inside:avoid!important}
 details{break-inside:avoid!important}
 .chart-toolbar{display:flex!important}.controls{display:grid!important}
 .modebar{display:none!important}
 .caption{font-size:12px!important}
}
'''
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 page=b.new_page(viewport={'width':1120,'height':1750},device_scale_factor=1)
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(html.as_uri(),wait_until='load')
 page.wait_for_function('typeof Plotly !== "undefined" && document.querySelectorAll(".main-svg").length>=10')
 page.evaluate('document.fonts.ready')
 page.add_style_tag(content=css)
 page.emulate_media(media='print')
 # Preserve initial state of all interactive controls. Reflow charts to print content width.
 page.evaluate('''async()=>{await document.fonts.ready;await Promise.all(Array.from(document.querySelectorAll('.js-plotly-plot')).map(el=>Plotly.Plots.resize(el)));}''')
 page.wait_for_timeout(700)
 page.pdf(path=str(out),prefer_css_page_size=True,print_background=True,display_header_footer=True,header_template='<div></div>',footer_template='<div style="font:10px Arial;color:#64748b;width:100%;padding:0 36px;display:flex;justify-content:space-between"><span>VITALIZA · CRISP-DM na prática · Dados até 30/09/2026</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')
 page.screenshot(path=str(root/'pdf_qa_browser.png'),full_page=False)
 print('JS errors:',errors)
 print('Charts:',page.locator('.js-plotly-plot').count())
 b.close()
doc=fitz.open(out);print('Pages:',len(doc));print('Bytes:',out.stat().st_size)
qa=root/'pdf_qa';qa.mkdir(exist_ok=True)
for i in range(len(doc)):
 page=doc[i];page.get_pixmap(matrix=fitz.Matrix(.55,.55),alpha=False).save(qa/f'pagina_{i+1:02d}.png')
print('Characters extracted:',sum(len(p.get_text()) for p in doc))
print('Page overview:')
for i,p in enumerate(doc):print(i+1, len(p.get_text()),p.get_text()[:85].replace('\n',' / '))
