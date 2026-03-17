# QA Semana 4

Atualizado em 2026-03-11.

## Objetivo

Validar manualmente o fluxo completo da Semana 4:

- upload do arquivo retorno ETIPI/iNETConsig em `.txt`;
- reconciliação e baixa automática;
- pendências manuais e não descontados;
- histórico de importações;
- renovação automática de ciclos;
- permissões e comportamento básico de segurança.

## Pré-condições

- ambiente local iniciado conforme `docs/SETUP_LOCAL.md`;
- login com usuário `admin@abase.local` / `Admin@123`;
- backend, frontend, MySQL e Redis saudáveis em `docker compose ps`;
- banco com dados mínimos de teste para associados/contratos na competência validada;
- arquivo de referência disponível em `docs/ABASE (2).txt`.

## Cenário 1: upload válido

1. Acesse `/importacao`.
2. Faça upload de um `.txt` ETIPI válido.
3. Valide:
- o upload aceita apenas `.txt`;
- a tela informa que a competência é extraída do cabeçalho;
- o card "Última importação" mostra o arquivo e a competência detectada;
- o status transita para `processando` e depois `concluido`.

## Cenário 2: upload inválido

1. Tente enviar um `.csv` ou `.xlsx`.
2. Tente enviar um `.txt` vazio.
3. Valide:
- o frontend rejeita formato inválido;
- o backend rejeita extensão inválida;
- o backend rejeita arquivo vazio;
- nenhum item é persistido para arquivos inválidos.

## Cenário 3: status `1` com baixa automática

1. Envie arquivo com item ETIPI `1`.
2. Valide no resultado:
- item aparece na aba `Descontados`;
- `status bruto ETIPI` mostra `1`;
- `status normalizado` mostra `efetivado`;
- a parcela correspondente fica `descontado`;
- `data_pagamento` é preenchida;
- cards de encerramento/novo ciclo atualizam quando o ciclo fecha.

## Cenário 4: status `2`, `3` ou `S`

1. Envie arquivo com item ETIPI `2`, `3` ou `S`.
2. Valide:
- item aparece em `Não descontados`;
- a parcela fica `nao_descontado`;
- o associado fica `inadimplente` quando aplicável;
- `motivo_rejeicao`/`observacao` guarda a descrição humana do status.

## Cenário 5: status `4`, `5` ou `6`

1. Envie arquivo com item ETIPI `4`, `5` ou `6`.
2. Valide:
- item aparece em `Pendências manuais`;
- a parcela não recebe baixa automática;
- existe log de inconsistência em `ImportacaoLog`.

## Cenário 6: CPF não encontrado

1. Envie arquivo com CPF inexistente no cadastro.
2. Valide:
- item não quebra o processamento do arquivo;
- o resumo incrementa `não encontrados`;
- o item registra `resultado_processamento = nao_encontrado`.

## Cenário 7: divergência de valor

1. Envie item `status 1` com valor diferente da parcela.
2. Valide:
- não há baixa automática;
- o item vai para `Pendências manuais`;
- existe log de divergência de valor.

## Cenário 8: reprocessamento

1. Abra a última importação e acione `Reprocessar arquivo`.
2. Valide:
- o arquivo volta para `pendente/processando`;
- o processamento conclui sem duplicar itens;
- ciclos já abertos não são duplicados.

## Cenário 9: renovação de ciclos

1. Acesse `/renovacao-ciclos`.
2. Selecione a competência do arquivo processado.
3. Valide:
- os cards refletem a reconciliação do arquivo;
- o detalhamento mostra `status ETIPI`, `resultado importação`, `pagamento` e `ciclo`;
- itens renovados aparecem como `ciclo iniciado` ou `ciclo renovado`;
- itens rejeitados aparecem como `inadimplente`.

## Cenário 10: histórico de importações

1. Na tela `/importacao`, role até `Histórico de importações`.
2. Valide:
- colunas `Data/Hora`, `Arquivo`, `Sistema Origem`, `Referência`, `Total`, `Processados`, `Não encontrados`, `Erros` e `Status`;
- paginação funcionando nos endpoints de detalhe;
- referência exibida no formato `MM/YYYY`.

## Cenário 11: permissões

1. Faça login com usuário sem papel `TESOUREIRO` ou `ADMIN`.
2. Tente acessar `/importacao` e `/renovacao-ciclos`.
3. Valide:
- o backend retorna `403` para endpoints protegidos;
- upload e reprocessamento não ficam disponíveis para perfis não autorizados.

## Cenário 12: smoke técnico

Execute:

```bash
docker compose exec -T -e DJANGO_SETTINGS_MODULE=config.settings.testing backend python manage.py test apps.importacao apps.contratos -v 2
docker compose exec -T frontend pnpm --filter @abase/web test
docker compose exec -T frontend pnpm --filter @abase/web type-check
docker compose exec -T frontend pnpm --filter @abase/web build
docker compose exec -T backend python manage.py spectacular --file /app/schema.yaml --validate
```

Resultado esperado:

- testes backend verdes;
- testes Jest verdes;
- type-check verde;
- build do frontend verde;
- schema OpenAPI gerado sem erros.
