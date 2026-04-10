# Deploy: Modal de Detalhes do Associado em Filas e Dashboard

## Escopo
- Adiciona `Ver detalhes do associado` na aba `Aptos a renovar`.
- Troca a navegação para rota de associado por modal expandido no `Dashboard Executivo`.
- Mantém o usuário na mesma página e no mesmo contexto de paginação/filtro.

## Rotas afetadas
- `/agentes/refinanciados`
  - aba `Aptos a renovar`
- `/dashboard`
  - modal de detalhamento dos indicadores
  - tabela mensal de `Novos associados`

## Comportamento entregue
- `Aptos a renovar`
  - cada linha agora expõe botão `Ver detalhes do associado`
  - o botão abre modal expandido com cadastro, contratos, ciclos e parcelas
  - o modal respeita o nível de acesso já existente da rota
- `Dashboard Executivo`
  - qualquer linha detalhada que antes levava para `/associados/[id]` agora abre modal expandido
  - a tabela mensal de `Novos associados` também ganhou ação direta de detalhe
  - o segundo modal abre por cima do detalhamento atual, sem perder o contexto

## Arquivos alterados
- [page.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/agentes/refinanciados/page.tsx)
- [page.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/dashboard/page.tsx)

## Reuso de componente existente
- O modal expandido reutiliza [associado-details-dialog.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/components/associados/associado-details-dialog.tsx)
- Nenhum endpoint novo foi criado

## Validação executada
- `src/app/(dashboard)/agentes/refinanciados/page.test.tsx`: `OK`
- `src/app/(dashboard)/dashboard/page.test.tsx`: `OK`
- `frontend` reiniciado após ajuste

## Deploy
```bash
docker restart abase-v2-frontend-1
```

## Conferência manual pós-deploy
- Em `Aptos a renovar`, clicar em `Ver detalhes do associado` e validar abertura do modal sem sair da fila
- No `Dashboard Executivo`, abrir um detalhamento e validar que o botão de detalhe abre o segundo modal
- Fechar o modal do associado e confirmar que o usuário volta ao detalhamento anterior, sem perder filtro nem página
