# Contratos de dados e decisões

## Grão e cobertura

Uma linha por conta e mês; todas as contas já cadastradas, não apenas pagantes. Janela de julho/2024 a setembro/2026. Os 119 cadastros posteriores ao corte não são retrodatados. Há 34 treinos posteriores ao corte segregados. As fontes não têm a mesma cobertura: atividades começam em2026, suporte em07/2025 e pagamentos em07/2024.

Zero significa nenhum registro na janela coberta. Nulo também pode significar fora de cobertura ou medida não aplicável. FC e distância não são preenchidas com zero. Treinos de duração não positiva ficam fora do engajamento, mas são contados na auditoria. O limite de110anos para plausibilidade de nascimento é uma regra configurável, não validação externa da identidade.

## Assinatura e churn

Os eventos de início/expiração são a fonte histórica, com início legado do cadastro para ciclos anteriores aos logs. Desligar renovação e cancelar no site não encerram automaticamente o período pago. Não contar reembolso e expiração como duas perdas do mesmo ciclo. A base entregue tem uma assinatura por usuário; o construtor interrompe se houver múltiplos ciclos sem reconstrução própria.

Churn mensal = perdas da base inicial / pagantes iniciais. Quem entrou e saiu no mês afeta o saldo, mas não esse numerador. Não pagantes iniciais têm alvo nulo, não zero. O estado atual do cadastro não preenche retroativamente plano/canal. Atributos com sufixo de exportação são atuais e podem vazar futuro em modelagem.

## Finanças

Datas com offset são convertidas para America/Sao_Paulo. Datas naive são assumidas Brasília; a origem deve confirmar essa regra antes de produção. O mês deriva somente depois da conversão. Valores monetários são normalizados em centavos inteiros. Taxas são calculadas em microreais inteiros, sem arredondamento por evento; o arredondamento de exibição é half-up.

Duplicidade operacional: mesmo usuário, timestamp normalizado, valor em centavos, método, status e tentativa. `pagamento_id` é excluído dessa chave porque foi justamente o campo diferente nas cópias. O pipeline mantém uma ocorrência determinística e salva as descartadas em área privada. A chave não substitui a necessidade de um ID real de transação em produção.

Antes dos joins, cada fonte é agregada isoladamente. Join de agregados valida um-para-um; cadastro valida muitos-para-um. Os totais finais devem reconciliar com as fontes JÁ tratadas, e não com os registros brutos duplicados.

## Campos novos da V2

- Registros de pagamento brutos e duplicados: preservam o volume original e as exclusões.
- Valor aprovado bruto dos registros e valor aprovado duplicado: explicitam a passagem até o bruto corrigido.
- Taxas sobre aprovados e valor aprovado líquido de taxas: cálculo segundo os parâmetros do caso.

`valor_aprovado_mes`, `cobrancas_aprovadas_mes` e `tentativas_pagamento_mes` mudam de definição para eventos únicos após deduplicação. Consulte o changelog antes de comparar versões.
