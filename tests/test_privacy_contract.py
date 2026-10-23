from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

def test_gitignore_covers_private_inputs_and_credentials():
    text=(ROOT/'.gitignore').read_text()
    for expected in ['data/raw/*','data/processed/*','.env','*.parquet','*.joblib','*.xlsx']:
        assert expected in text

def test_config_is_explicit_about_case_cutoff_and_rates():
    cfg=json.loads((ROOT/'config/case.json').read_text())
    assert cfg['cutoff']=='2026-09-30'
    assert cfg['fee_basis_points']['app_store']==1500
    assert cfg['fee_basis_points']['pix_automatico']==99

def test_workflow_does_not_require_private_dataset_or_write_permission():
    text=(ROOT/'.github/workflows/ci.yml').read_text()
    assert 'not integration' in text
    assert 'contents: read' in text
    assert 'contents: write' not in text
