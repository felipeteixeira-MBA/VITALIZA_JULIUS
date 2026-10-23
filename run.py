"""Entrypoint que funciona sem instalação editável do projeto."""
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from vitaliza_case.cli import main

if __name__=='__main__':main()
