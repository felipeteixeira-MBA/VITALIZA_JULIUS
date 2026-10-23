# Vitaliza — ambiente analítico reproduzível

Projeto educacional do case Vitaliza, organizado a partir do trabalho realizado no Julius. Reúne pipeline TIDY, reconciliação financeira, testes e histórico de experimentos. **Não é um sistema de produção, uma previsão validada temporalmente ou recomendação de campanha.**

## Estado atual

- Versão canônica: **0.2.0**, esquema TIDY **2.0.0**.
- Corte: **30/09/2026**, mês de referência em Brasília.
- Painel: **946.907 linhas × 52 colunas**, 64.829 usuários e 27 meses.
- Chave: `user_id × mes_referencia`, sem repetição.
- Finanças corrigidas por duplicidade funcional; a V1 era consistente na soma, mas carregava transações duplicadas.
- Testes unitários e integração local executados; consulte o registro de validação.
- CI configurado, mas **não executado no GitHub nesta preparação**.
- Nenhum repositório remoto foi criado, conectado ou atualizado.

## Começar

Recomendado: Python 3.13. As versões usadas na validação estão fixadas no arquivo de dependências.

```bash
python -m pip install -r requirements.lock.txt
python -m pytest -m "not integration" -q
```

Coloque os seis insumos autorizados em `data/raw/`: cadastro, assinaturas, eventos de assinatura, pagamentos, atividades Parquet e tickets. Eles **não acompanham o pacote Git e não devem ser enviados por engano**.

```bash
python run.py finance
python run.py panel
python -m pytest -m integration -q
```

Os comandos também aceitam `--raw-dir`, `--out-dir` e `--config`. As saídas vão para `data/processed/`, ignorado pelo Git. O pipeline não modifica os arquivos brutos. Use o CSV/Parquet V2 produzido, não o painel V1, para novas análises financeiras.

## Estrutura

```text
config/               corte, fuso, taxas e referências do caso
src/vitaliza_case/    normalização, finanças, TIDY e CLI
tests/                fixtures sintéticas e regressões locais
docs/                 decisões, definições e limitações
reports/validated/   relatórios financeiros agregados corrigidos
reports/historical/  relatórios anteriores marcados como históricos
reports/generated/   saídas locais; não versionadas por padrão
experiments/legacy/  scripts anteriores; não são pipeline canônico
data/raw/             insumos privados locais, ignorados
data/processed/       derivados por usuário, ignorados
```

## A correção que motivou o harness

Em setembro, somar aprovações após ajustar o fuso produzia R$499.402,40. Havia **93 registros aprovados duplicados**, com R$6.830,70. Eles tinham IDs diferentes, mas mesmo usuário, instante normalizado, valor, método, status e tentativa. O bruto aprovado deduplicado é **R$492.571,70** e o líquido das taxas é **R$436.442,35**, com arredondamento somente no total apresentado.

Não se exclui toda tentativa maior que 1. Também não se mantém apenas uma aprovação por usuário/mês: isso eliminaria registros de instantes diferentes, potencialmente legítimos. Em produção, esta chave substituta deve ser validada contra um ID real de cobrança/transação; o data room não o fornece.

## Definições que não podem ser confundidas

- **Bruto de registros:** soma antes da deduplicação; serve para auditoria, não como faturamento final.
- **Bruto aprovado deduplicado:** uma ocorrência de cada evento aprovado segundo a chave operacional.
- **Líquido das taxas:** bruto deduplicado menos 15% nas lojas, 3,5% no cartão ou 0,99% no Pix.
- **Ajustes:** estornos e chargebacks preservados separadamente, com sinal. Não se presume o tratamento econômico da taxa devolvida nem o vínculo exato à cobrança original.
- **Líquido das taxas não é lucro, receita contábil, MRR ou caixa bancário comprovado.**

## O que é seguro versionar

Código, testes sintéticos, parâmetros, documentação e estatísticas agregadas revisadas. `.gitignore` exclui bases, credenciais e derivados individuais. Relatórios históricos têm aviso visível: seus totais financeiros não são atuais. Não inclua os PDFs, transcrições ou screenshots da aula sem revisar a autorização de compartilhamento.

Comece com um repositório **privado**. A existência do `.gitignore` não limpa um arquivo já enviado em commits; revise a lista de arquivos antes do primeiro push.

## GitHub

Este pacote é local. Autenticação e escolha do repositório são uma etapa posterior e exigem sua autorização. Não cole senha ou token em código, chat ou commits. Consulte `docs/publicacao.md`.

## Licença e uso acadêmico

Licença do código a definir pelo responsável. Não há autorização implícita de redistribuição dos dados ou materiais do curso. As bases são do case educacional; sua natureza sintética não dispensa revisar identificadores e condições de uso.
