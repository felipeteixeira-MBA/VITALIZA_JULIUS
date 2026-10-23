from pathlib import Path
import argparse,json,hashlib,platform
from datetime import datetime,timezone
import pandas as pd
from .finance import aggregate_payments,monthly_financial_report,load_config,rounded_cents

ROOT = Path(__file__).resolve().parents[2]

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda:file.read(2**20),b''):h.update(chunk)
    return h.hexdigest()

def finance_command(raw_dir: Path, out_dir: Path, config: dict):
    out_dir.mkdir(parents=True,exist_ok=True)
    path=raw_dir/'pagamentos.csv'
    raw=pd.read_csv(path,dtype={'valor':'string'})
    result=aggregate_payments(raw,config['fee_basis_points'],config['start_month'],config['cutoff'])
    result.monthly.to_parquet(out_dir/'pagamentos_agregados_v2.parquet',index=False)
    result.duplicates.to_parquet(out_dir/'pagamentos_duplicados.parquet',index=False)
    report=monthly_financial_report(result)
    report.to_csv(out_dir/'financeiro_mensal_v2.csv',index=False,float_format='%.6f')
    report[report.mes_referencia.str.startswith('2026')].to_csv(out_dir/'financeiro_2026_v2.csv',index=False,float_format='%.6f')
    manifest={
        'schema_version':config['schema_version'],'executed_at_utc':datetime.now(timezone.utc).isoformat(),
        'python':platform.python_version(),'input_name':path.name,'input_sha256':sha256(path),
        'input_rows':len(raw),'window_rows':len(result.normalized),'unique_rows':len(result.unique),
        'duplicate_rows':len(result.duplicates),'duplicate_key':config['business_duplicate_key'],
        'fee_basis_points':config['fee_basis_points'],'cutoff':config['cutoff']
    }
    (out_dir/'finance_run_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(report[report.mes_referencia.eq('2026-09')].to_string(index=False))
    return result,report

def main():
    parser=argparse.ArgumentParser(description='Harness local do case Vitaliza; sem publicação automática.')
    parser.add_argument('command',choices=['finance','panel'])
    parser.add_argument('--raw-dir',type=Path,default=ROOT/'data/raw')
    parser.add_argument('--out-dir',type=Path,default=ROOT/'data/processed')
    parser.add_argument('--config',type=Path,default=ROOT/'config/case.json')
    args=parser.parse_args();config=load_config(args.config)
    if args.command=='finance':
        finance_command(args.raw_dir,args.out_dir,config)
    else:
        from .tidy import build_panel
        build_panel(args.raw_dir,args.out_dir,config)

if __name__=='__main__':main()
