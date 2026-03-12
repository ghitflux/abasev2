# Plano de Correcao: formatacao automatica do Kubb no container

## Objetivo

Eliminar o erro `Prettier not found` na etapa de formatacao do Kubb dentro do container do frontend, mantendo o codegen funcional e deixando a formatacao automatica dos arquivos gerados como parte explicita da stack.

## Contexto atual

- O codegen do Kubb ja esta funcionando no container, conforme registrado em `docs/CHECKLIST_COMPLETO_ABASE_V2.md`.
- A pendencia atual e apenas a formatacao automatica dos arquivos gerados.
- Em `apps/web/package.json`, o script `generate:api` executa `kubb --config kubb.config.js`.
- Em `apps/web/kubb.config.js`, nao existe configuracao explicita de `output.format`.
- No `@kubb/core` 4.33.2 instalado no projeto, `output.format` tem default `prettier`.
- O pacote `prettier` nao esta declarado em `apps/web/package.json` nem no `package.json` raiz.
- Nao existe `.husky/` no repositorio; o erro descrito como "hook de formatacao" aponta para a etapa interna de formatacao do proprio Kubb.

## Causa raiz

O Kubb tenta formatar os arquivos gerados usando `prettier` por padrao, mas o formatter nao faz parte das dependencias disponiveis no ambiente do frontend. Como a intencao atual e manter a formatacao automatica, a causa nao e o codegen em si, e sim a dependencia implicita de formatacao nao declarada no projeto.

## Recomendacao

Adotar a correcao explicita:

1. Declarar `prettier` como `devDependency` do workspace `apps/web`.
2. Tornar a intencao explicita no Kubb com `output.format: "prettier"` em `apps/web/kubb.config.js` e, se o arquivo TS continuar sendo mantido, espelhar a mesma decisao em `apps/web/kubb.config.ts`.
3. Adicionar uma configuracao minima do Prettier para evitar comportamento implicito e facilitar reproducao entre ambientes.

Essa abordagem e a mais direta porque preserva a formatacao automatica, reduz ambiguidade de configuracao e evita depender do default interno do Kubb.

## Plano de execucao

### 1. Confirmar a falha no ambiente correto

Executar a validacao dentro do servico `frontend`, que e o ambiente citado no problema:

```bash
docker compose exec frontend pnpm --filter @abase/web generate:api
docker compose exec frontend pnpm --filter @abase/web exec prettier --version
```

Resultado esperado antes da correcao:

- o codegen gera arquivos;
- a etapa de formatacao acusa `Prettier not found`;
- `prettier --version` falha no container.

### 2. Declarar o formatter como dependencia do frontend

Adicionar `prettier` em `apps/web/package.json` como `devDependency`.

Observacoes:

- manter a dependencia no mesmo workspace do `generate:api`, porque e ali que o contrato do script existe;
- evitar depender de instalacao global no container.

### 3. Tornar a configuracao do Kubb explicita

Ajustar `apps/web/kubb.config.js` para incluir:

```js
output: {
  path: "./src/gen",
  clean: true,
  format: "prettier",
}
```

Se `apps/web/kubb.config.ts` continuar sendo mantido como referencia, alinhar o mesmo valor nele para nao criar divergencia entre os dois arquivos.

### 4. Adicionar configuracao minima do Prettier

Criar uma configuracao minima no repositorio, preferencialmente na raiz, por exemplo:

- `.prettierrc.json`
- opcionalmente `.prettierignore`

Objetivo:

- garantir previsibilidade no container;
- evitar que a formatacao dos gerados dependa apenas dos defaults da ferramenta;
- deixar clara a convencao adotada para futuros scripts de formatacao.

### 5. Validar novamente no container

Depois da mudanca:

```bash
docker compose exec frontend pnpm install --frozen-lockfile --config.confirmModulesPurge=false --config.package-import-method=copy
docker compose exec frontend pnpm --filter @abase/web exec prettier --version
docker compose exec frontend pnpm --filter @abase/web generate:api
```

Validar que:

- `prettier` fica disponivel no PATH do processo;
- o `generate:api` conclui sem `Prettier not found`;
- os arquivos em `apps/web/src/gen` sao gerados e formatados.

### 6. Registrar a pendencia como resolvida

Atualizar `docs/CHECKLIST_COMPLETO_ABASE_V2.md`:

- marcar `Formatacao automatica dos arquivos gerados pelo Kubb` como concluida;
- substituir a observacao atual por uma nota curta de que o formatter foi declarado e validado no container.

## Criterios de aceite

- `docker compose exec frontend pnpm --filter @abase/web exec prettier --version` retorna uma versao valida.
- `docker compose exec frontend pnpm --filter @abase/web generate:api` finaliza com sucesso no container.
- O log nao contem `Prettier not found`.
- Os arquivos em `apps/web/src/gen` permanecem sendo gerados e saem formatados.
- A checklist do projeto deixa de registrar essa pendencia.

## Riscos e observacoes

- Se o time nao quiser adotar Prettier no projeto, a alternativa tecnica e configurar `output.format: false` no Kubb. Isso remove o erro, mas mantem a pendencia original de formatacao automatica sem resolver o objetivo funcional.
- Neste workspace local, fora do container, `pnpm --filter @abase/web generate:api` atualmente falha antes por resolucao do binario do `kubb`. Essa falha e separada do problema descrito e nao deve substituir a validacao no container.
- Se a equipe decidir formatar apenas os arquivos gerados, vale limitar o escopo futuro dos scripts de Prettier para `apps/web/src/gen`.

## Resultado esperado

Ao final, o frontend passa a declarar explicitamente o formatter exigido pelo Kubb, o codegen continua funcionando no container e a pendencia de formatacao automatica deixa de ser um comportamento "acidental" para virar uma parte reproduzivel da configuracao do projeto.
