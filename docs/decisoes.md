# Decisões de negócio, validações e lições do case

Complementa `docs/definicoes.md` (contratos de dados e regras técnicas) com o
registro de negócio: definições do enunciado, volumes da auditoria de qualidade,
validações independentes e lições metodológicas. Migrado do repositório
`caseVitalize` em 22/10/2026.

## Definições do enunciado

| Conceito | Regra adotada |
| --- | --- |
| Pagante ativo | Assinatura ativa em plano mensal ou anual; **exclui 60 cortesias** → 14.753 no corte |
| Churn mensal | Perdas da base inicial ÷ pagantes no início do mês |
| Corte | 30/09/2026; nenhuma variável usa informação posterior |
| Renovação desligada | NÃO é churn — acesso segue até o fim do período pago |

Pontos de conferência do enunciado, todos reproduzidos: 8.540 pagantes em
jan/2025; médias de churn 5,61% (jan–set/2025) e 6,62% (jan–set/2026);
abr/2026 = 1.154/14.237 = 8,11%; 14.753 pagantes e 60 cortesias no corte;
cupom −1,92 p.p. até o corte (IC95% 0,60–3,24).

## Auditoria de qualidade — volumes

| Problema | Volume | Tratamento |
| --- | --- | --- |
| `pagamentos.valor` em 3 formatos | 19.750 registros com "R$" | Normalização para centavos |
| Duplicidade funcional em pagamentos | 1.941 aprovados / R$ 118.295,90 (jul/24–set/26); 93 / R$ 6.830,70 em set/26 | 1 ocorrência por chave; NÃO excluir toda tentativa > 1 |
| Treinos com duração ≤ 0 | 3.649 | Fora do engajamento |
| Datas de nascimento implausíveis | 194 futuras + regra de 110 anos | Sinalizadas |
| Cadastros posteriores ao corte | 119 contas | Segregados |
| Timestamps mistos (UTC × Brasília) | eventos e pagamentos | Conversão antes de derivar o mês |

## Validação independente (22/10/2026)

A reconciliação financeira foi reproduzida por duas vias independentes
(pipeline deste repositório e recálculo externo em Claude, direto do CSV
bruto), batendo centavo a centavo com o slide do professor:

| Etapa — setembro/2026 | Valor |
| --- | --- |
| Aprovadas no mês (Brasília), antes da dedup | R$ 499.402,40 (7.176 reg.) |
| Duplicidades removidas | 93 / −R$ 6.830,70 |
| **Bruto deduplicado** | **R$ 492.571,70** |
| Taxas | −R$ 56.129,35 |
| **Líquido de taxas** | **R$ 436.442,35** |

Jan–set/2026: bruto dedup R$ 4.090.356,60; líquido R$ 3.629.311,33.
Os valores mês a mês estão em `reports/validated/` e são verificados por
`tests/test_validacao_independente.py` (marcado `integration`).

## Lições registradas

1. **Conciliar somas não valida regra de negócio.** Fonte bruta e painel
   "batiam" porque carregavam a mesma duplicidade. Teste de regra ≠ teste de
   total.
2. **Paradoxo de Simpson no uso:** no agregado, zero treinos no mês anterior
   parece churnar menos que 1–3 treinos; por plano, inverte (96,7% das
   observações com zero treinos são de anuais).
3. **Associação ≠ causa.** Recusa de cobrança (26,6% vs 5,9%) e queda ≥50% de
   uso (12,1% vs 4,0%) são sinais diagnósticos.
4. **Heatmaps:** sem ganho preditivo no desenho testado (AUC 0,82558 →
   0,82617); a tinta correlaciona com volume de treino já tabelado.
5. **Horizonte muda a conclusão da campanha:** 30 dias, nada conclusivo; até o
   corte, cupom −1,92 p.p. — exploratório.

## Versões

| Data | Mudança |
| --- | --- |
| 22/10/2026 | Deduplicação funcional definida e validada; TIDY v1 substituído nas finanças; publicação no GitHub do grupo; migração do conteúdo do repositório `caseVitalize`. |
