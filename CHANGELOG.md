# Alterações

## 0.3.0 — base analítica do corte, 28/10/2026

- Adiciona `src/vitaliza_case/snapshot.py` e o comando `python run.py snapshot`: uma linha por assinante pagante ativo em 30/09/2026 (14.753 × 61), integrando os 12 arquivos do data room.
- Reutiliza o pipeline financeiro canônico (dedup funcional, centavos, Brasília) e implementa a série oficial de churn do dicionário §11.
- Trava as âncoras do enunciado em `tests/test_snapshot_corte.py` (marcado `integration`): pagantes, cortesias, MRR, churn set/abr, médias anuais, mix de plano/canal e duplicados funcionais.
- Estende `docs/manifesto_fontes.json` de 6 para 12 insumos, com bytes e sha256.
- Atualiza README, decisões e estado das entregas; alvo `snapshot` no Makefile.

## 0.2.0 — preparação local de22/10/2026

- Introduz chave de negócio para cópias de pagamento, independente de pagamento_id.
- Mantém retentativas legítimas e pagamentos distintos do mesmo usuário/mês.
- Calcula dinheiro em centavos e taxas em microreais; arredonda apenas no total exibido.
- Acrescenta colunas para dados brutos, exclusões, taxas e líquido ao painel.
- Preserva os produtosV1; geraV2sem sobrescrita.
- Inclui testes de moeda, datas, status, retentativas, grão, limites e referências reais locais.
- Protege dados e credenciais com regras de exclusão e revisão do conteúdo rastreado.
- Acrescenta entrada de execução, documentação, estruturaGit e workflow deCI sem dados privados.

## V1 e experimentos históricos

As versões anteriores detectavam zero duplicatas exatas porque IDs de pagamento diferentes tornavam as linhas diferentes. Os totais financeiros que incluíam essas cópias foram substituídos. Essa correção não equivale a identificar com certeza todas as cobranças bancárias reais: falta um ID de transação/cobrança para uma reconciliação de produção.
