# Publicação posterior, com autorização

## Antes de enviar

1. Recomenda-se um repositório privado inicialmente.
2. Confirme permissão de compartilhar código, material acadêmico e relatórios.
3. Verifique que bases e credenciais não aparecem na lista de arquivos rastreados.
4. Execute testes unitários; se tiver os insumos, execute também integração e a construção do painel.
5. Não use um CSV antigo ou relatórios históricos como referência financeira atual.

O pacote fonte não inclui a pasta oculta `.git`. Um Git bundle separado preserva o commit inicial e pode ser clonado em uma máquina local. Nenhum dos dois inclui os insumos privados.

### A partir do pacote fonte

```bash
git init -b main
# Configure sua identidade local, sem inserir senha/token nos arquivos.
git add .
git status
git commit -m "Estrutura inicial e finanças corrigidas"
```

### Depois que VOCÊ criar/escolher o repositório

Use a URL de um repositório que você controla e autentique pelo fluxo seguro da sua ferramentaGit. O envio só deve ser executado após sua revisão e autorização.

```bash
git remote add origin URL_DO_SEU_REPOSITORIO
git push -u origin main
```

Esses comandos são instruções futuras; **não foram executados contra um serviço remoto nesta preparação**. Não cole tokens em URLs, scripts, mensagens ou arquivos versionados.

O CI preparado executa somente testes sintéticos, sem necessidade de dados privados. Os testes de integração local são explicitamente marcados e pulam quando os arquivos não estão presentes. Não há workflow de publicação automática dos relatórios ou das bases.
