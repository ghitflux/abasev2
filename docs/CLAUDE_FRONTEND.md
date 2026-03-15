# CLAUDE.md — ABASE v2 Frontend

> Contexto operacional para Claude Code na instância frontend do monorepo ABASE v2.

## Identidade do Projeto

Frontend do ABASE v2 dentro de um monorepo gerenciado por pnpm workspaces. O workspace deste app é `@abase/web` (em `apps/web/`). Aplicação Next.js 16 com App Router para cinco tipos de usuário (AGENTE, ANALISTA, COORDENADOR, TESOUREIRO, ADMIN). Tema dark com acentos em laranja/verde/rosa. TODOS os 50 componentes shadcn/ui estão pré-instalados, além de 14 componentes customizados compostos.

## Stack Técnica

- Next.js 16 com Turbopack (default, nunca Webpack)
- React 19.2 (Server Components, Suspense, View Transitions)
- TypeScript estrito
- Tailwind CSS 4 (nunca CSS modules ou styled-components)
- shadcn/ui + Radix UI — TODOS os 50 componentes instalados
- shadcn charts via `src/components/ui/chart.tsx` + Recharts primitives para dashboards e analytics
- TanStack Query v5 (React Query)
- Zod para validação
- Zustand para state global (apenas auth)
- Kubb para code generation a partir de OpenAPI
- proxy.ts (Next.js 16) para interceptação de auth
- pnpm como package manager (NUNCA npm ou yarn)
- date-fns com locale pt-BR para formatação de datas
- react-dropzone para upload de arquivos (arquivo retorno)

## Monorepo com pnpm

Este projeto vive em `apps/web/` dentro do monorepo. O package.json é `@abase/web`. Dependências internas usam protocolo `workspace:*`.

```bash
# Instalar dependência neste workspace
pnpm --filter @abase/web add pacote

# Rodar dev
pnpm --filter @abase/web dev

# Rodar qualquer script
pnpm --filter @abase/web generate:api
```

Packages compartilhados disponíveis:
- `@abase/tsconfig` — TSConfig base (extends em apps/web/tsconfig.json)
- `@abase/eslint-config` — ESLint config compartilhado
- `@abase/shared-types` — Enums e constants usados em front e back

## shadcn/ui — TODOS os 50 Componentes Instalados

Os seguintes componentes já estão em `src/components/ui/` e NÃO precisam ser instalados novamente: accordion, alert, alert-dialog, aspect-ratio, avatar, badge, breadcrumb, button, button-group, calendar, card, carousel, chart, checkbox, collapsible, command, context-menu, dialog, drawer, dropdown-menu, empty, field, hover-card, input, input-group, input-otp, item, kbd, label, menubar, native-select, navigation-menu, pagination, popover, progress, radio-group, resizable, scroll-area, select, separator, sheet, sidebar, skeleton, slider, sonner, spinner, switch, table, tabs, textarea, toggle, toggle-group, tooltip, typography.

Comando que foi usado para instalar tudo de uma vez:
```bash
pnpm dlx shadcn@latest add accordion alert alert-dialog aspect-ratio avatar badge breadcrumb button button-group calendar card carousel chart checkbox collapsible command context-menu dialog drawer dropdown-menu empty field hover-card input input-group input-otp item kbd label menubar native-select navigation-menu pagination popover progress radio-group resizable scroll-area select separator sheet sidebar skeleton slider sonner spinner switch table tabs textarea toggle toggle-group tooltip typography
```

## 14 Componentes Customizados — src/components/custom/

### date-picker.tsx
Combina Popover + Calendar + date-fns (locale pt-BR). Aceita `value: Date`, `onChange: (date: Date) => void`, `placeholder`, `disabled`. Formata exibição como "11 de mar. de 2026".

### date-range-picker.tsx
Dois calendários lado a lado para seleção de período. Props: `value: DateRange`, `onChange`, `numberOfMonths: 2`.

### time-picker.tsx
Input com máscara HH:MM. Valida 00:00-23:59. Permite digitação direta ou incremento com setas.

### date-time-picker.tsx
Composição de DatePicker + TimePicker. Retorna ISO string completa.

### searchable-select.tsx
Command + Popover (combobox). Props: `options: Array<{value, label}>`, `value`, `onChange`, `placeholder`, `searchPlaceholder`. Filtra opções enquanto digita. Usado para: selecionar órgão público, selecionar agente, selecionar associado.

### multi-select.tsx
Command + Badge tags. Permite selecionar múltiplos valores. Cada seleção aparece como Badge removível. Usado para: filtros avançados, seleção de competências múltiplas.

### input-currency.tsx
Input com máscara automática R$ X.XXX,XX. Aceita apenas números. Formata em tempo real enquanto digita. Armazena valor como number (centavos internamente). Usado para: mensalidade, valor bruto, margem.

### input-cpf-cnpj.tsx
Input com máscara dinâmica. Detecta automaticamente se é CPF (XXX.XXX.XXX-XX, 11 dígitos) ou CNPJ (XX.XXX.XXX/XXXX-XX, 14 dígitos). Valida dígitos verificadores.

### input-phone.tsx
Input com máscara (XX) XXXXX-XXXX. Aceita 10 ou 11 dígitos (fixo ou celular).

### input-cep.tsx
Input com máscara XXXXX-XXX. Ao completar 8 dígitos, faz fetch automático para API ViaCEP e preenche endereço, bairro, cidade, UF.

### dropdown-actions.tsx
DropdownMenu padronizado para coluna "Ações" de tabelas. Props: `items: Array<{label, icon, onClick, variant?, disabled?}>`. Abre com botão de 3 pontos (MoreHorizontal).

### file-upload-dropzone.tsx
Baseado em react-dropzone. Área de drag-and-drop com ícone de upload. Props: `accept: {csv, xlsx}`, `maxSize`, `onUpload`, `isProcessing`. Mostra preview do nome do arquivo selecionado. Usado na tela de Importação do Arquivo Retorno.

### calendar-competencia.tsx
MonthPicker para seleção de competência (mês/ano). Exibe grid de meses dentro de um Popover. Permite navegar entre anos. Retorna Date (primeiro dia do mês). Usado na tela de Confirmações do Tesoureiro.

### status-badge.tsx
Badge com cores mapeadas por status do sistema. Props: `status: string`, `variant?: string`. Mapeamento:
- Verde: ativo, ciclo_renovado, concluido, descontado, efetivado, baixa_efetuada
- Amarelo: em_aberto, pendente, aguardando, em_andamento, futuro
- Vermelho: inadimplente, nao_descontado, rejeitado, erro, cancelado
- Cinza: inativo, suspenso
- Azul: apto_a_renovar, ciclo_aberto

## Design System — Tema Dark

```css
:root {
  --background: 220 15% 8%;
  --foreground: 0 0% 95%;
  --card: 220 15% 12%;
  --primary: 25 95% 53%;          /* Laranja ABASE */
  --secondary: 220 15% 18%;
  --accent: 142 71% 45%;          /* Verde */
  --destructive: 0 84% 60%;       /* Vermelho */
  --warning: 38 92% 50%;          /* Amarelo */
  --border: 220 10% 20%;
  --ring: 25 95% 53%;
  --sidebar: 220 15% 10%;
  --sidebar-active: 25 95% 53%;
}
```

## proxy.ts — Next.js 16 Auth

```typescript
// src/app/proxy.ts — substitui middleware.ts no Next.js 16
export default function proxy(request: NextRequest) {
  const token = request.cookies.get('access_token')?.value
  const isAuthPage = request.nextUrl.pathname.startsWith('/login')
  const isApiRoute = request.nextUrl.pathname.startsWith('/api')

  if (!token && !isAuthPage && !isApiRoute)
    return NextResponse.redirect(new URL('/login', request.url))

  if (token && isAuthPage)
    return NextResponse.redirect(new URL('/dashboard', request.url))

  if (isApiRoute && token) {
    const headers = new Headers(request.headers)
    headers.set('Authorization', `Bearer ${token}`)
    return NextResponse.next({ request: { headers } })
  }
  return NextResponse.next()
}
```

## Navegação por Role

ADMIN: Todos os itens. AGENTE: Meus Contratos, Esteira, Renovações, Pagamentos, Refinanciados. ANALISTA: Dashboard Análise, Refinanciamento. COORDENADOR: Refinanciados, Refinanciamento. TESOUREIRO: Dashboard Contratos, Confirmações, Refinanciamentos.

## Padrão Universal de Tabelas

Todas as tabelas do sistema devem seguir este padrão consistente, tendo como referência o módulo **Meus Contratos** (`agentes/meus-contratos/page.tsx`).

### Componente CopySnippet

**SEMPRE usar o componente compartilhado** `src/components/shared/copy-snippet.tsx`. **NUNCA duplicar** uma versão local do componente.

```tsx
import CopySnippet from "@/components/shared/copy-snippet";

// Modo padrão (pill com label + valor + ícone de cópia)
<CopySnippet label="CPF" value={row.cpf_cnpj} mono />
<CopySnippet label="Matrícula do Servidor" value={row.matricula_orgao} mono />
<CopySnippet label="Contrato" value={row.contrato_codigo} mono />

// Modo inline (só o valor, sem pill — para células de texto corrido)
<CopySnippet label="Nome" value={row.nome_completo} inline />
```

### Regras para campos de CPF e Matrícula

- **CPF**: sempre renderizar via `<CopySnippet label="CPF" value={row.cpf_cnpj} mono />`. Nunca usar `maskCPFCNPJ()` diretamente em células de tabela.
- **Matrícula do Servidor**: campo correto é `matricula_orgao` (preenchido manualmente no cadastro). O campo `matricula` é um ID interno auto-gerado (`MAT-XXXXX`) e **não deve ser exibido** como matrícula do servidor.
  - Sempre usar: `<CopySnippet label="Matrícula do Servidor" value={row.matricula_orgao || row.matricula} mono />`
  - Cabeçalho da coluna: **"Matrícula do Servidor"** (não "Matrícula")

### Expandir/Colapsar linhas

Usar o `renderExpanded` prop do `DataTable`. O chevron de expansão fica na primeira coluna e usa o seletor `group-data-[expanded=true]:rotate-90` do Tailwind:

```tsx
{
  id: "expand",
  header: "",
  headerClassName: "w-8 px-3",
  cellClassName: "w-8 px-3",
  cell: () => (
    <ChevronRightIcon className="size-4 text-muted-foreground transition-transform duration-200 group-data-[expanded=true]:rotate-90" />
  ),
},
```

O `DataTable` já aplica `className="group"` e `data-expanded="true/false"` em cada `TableRow`, portanto o seletor funciona automaticamente.

### Skeleton loading

- Usar `<Skeleton>` (shadcn/ui) enquanto os dados carregam — nunca `<Spinner>` isolado na tabela.
- Para navegação por linha (ex: ir para detalhes do associado), usar `navigatingId` state para mostrar skeletons inline nas células enquanto o `router.push()` está em voo.

```tsx
const [navigatingId, setNavigatingId] = React.useState<number | null>(null);

// Na coluna:
cell: (row) =>
  navigatingId === row.id ? (
    <Skeleton className="h-4 w-40" />
  ) : (
    <p>{row.nome}</p>
  ),
```

### Ações por linha

- Botões de ação primária (criar, confirmar, dar baixa): `variant="success"`
- Botões secundários (ver, abrir): `variant="outline"`
- Sempre chamar `e.stopPropagation()` em onClick de botões dentro de linhas expansíveis

### Sub-tabela expandida

Quando a linha expandida contém uma tabela interna (ex: parcelas), usar `<table>` nativa com estas classes:

```tsx
<div className="overflow-hidden rounded-xl border border-border/60">
  <table className="w-full text-sm">
    <thead>
      <tr className="border-b border-border/60 bg-muted/20">
        <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Coluna
        </th>
      </tr>
    </thead>
    <tbody>
      <tr className="border-b border-border/40 last:border-0 hover:bg-white/3">
        <td className="px-4 py-3">...</td>
      </tr>
    </tbody>
  </table>
</div>
```

## Convenções

- Componentes: PascalCase, export default, um por arquivo
- Server Components por padrão ("use client" só quando necessário)
- Formulários: React Hook Form + Zod (schemas do gen/zod/)
- Tokens em httpOnly cookies (proxy.ts gerencia)
- Formatação: Intl.NumberFormat('pt-BR', {style:'currency', currency:'BRL'})
- Datas: date-fns com locale pt-BR para display, ISO para API
- NUNCA localStorage para tokens
- Endpoints cobertos pelo schema: preferir tipos, query params e hooks do Kubb em `src/gen/models`, `src/gen/hooks` e `src/gen/zod`
- `apiFetch` em `src/lib/api/client.ts` continua válido para fluxos já existentes, uploads com progresso e integrações ainda não migradas para hooks gerados
- Clientes/hooks gerados pelo Kubb usam o proxy local `src/app/api/v1/[...path]/route.ts`; `apiFetch` usa `src/app/api/backend/[...path]/route.ts`
- Dashboard executivo admin: rota `/dashboard` exclusiva de `ADMIN`, protegida em navegação e com `RoleGuard`
- Para dashboards e analytics, usar apenas os componentes shadcn charts de `src/components/ui/chart.tsx` e os primitives do Recharts que já sustentam esse wrapper

## Comandos

```bash
pnpm --filter @abase/web dev          # Dev com Turbopack
pnpm --filter @abase/web build        # Build prod
pnpm --filter @abase/web generate:api # Kubb code gen
pnpm --filter @abase/web type-check   # TSC
pnpm dlx shadcn@latest add [comp]     # Adicionar componente shadcn
```
