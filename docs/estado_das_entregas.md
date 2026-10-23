# Registro de estado e limitações

| Entrega | Estado | Uso permitido neste projeto |
|---|---|---|
| Painel TIDY V1 | Substituído nas finanças | Referência histórica; não usar seus totais como faturamento final |
| Reconciliação de setembro/2026 | Validada no critério declarado | Bruto aprovado deduplicado e líquido das taxas |
| Painel TIDY V2 | Canônico após teste local | Comportamento e contagens históricas; atenção a cobertura e atributos atuais |
| Clusters/personas anteriores | Exploratórios | Estáveis à reamostragem, sensíveis às features; não classes naturais provadas |
| Modelos de heatmaps | Pesquisa | OOF na mesma coorte; sem ganho incremental demonstrado no desenho testado |
| Scores de setembro | Não operacionais | Não usar como fila de CRM ou uplift; falta validação temporal |
| Relatórios HTML históricos | Marcados com aviso | Estudo do método; finanças antigas podem estar desatualizadas |
| GitHub Actions | Configurado | Ainda não executado em servidor remoto |
| Publicação GitHub | Não realizada | Nenhum push, repositório remoto ou credencial adicionados |

O arquivo CSV grande anterior não foi sobrescrito. A versão atual é gerada separadamente em `data/processed/`. Manter código e configuração sem registrar esta mudança não bastaria para reprodução.

### O que ainda não foi demonstrado

Causalidade de preço, benefício de contato por pessoa, dano a Sleeping Dogs, lucro de uma política, utilidade geral de qualquer método de visão, generalização temporal dos modelos e desempenho real em novembro/2026. Não converter correlação ou OOF dentro de uma coorte em promessa operacional.

### EDA do novo painel

A primeira EDA identificou inversão agregada versus estratificada por plano entre zero e1–3treinos. Churn e engajamento não mudam com a deduplicação financeira, mas totais e contagens de pagamentos precisam ser recalculados usando aV2. Os arquivos de experimentos ainda usam caminhos e produtos do ambiente original; não são automaticamente atualizados pelo construtor canônico.
