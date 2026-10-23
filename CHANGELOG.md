# Alterações

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
