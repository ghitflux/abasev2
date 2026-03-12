<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Storage;
use App\Models\AgenteCadastro;
use App\Models\AgenteDocIssue;
use App\Models\AgenteDocReupload;
use App\Models\TesourariaPagamento;
use App\Models\AssociadoDoisCadastro;
use App\Models\AgenteCadastroAssumption;
use Carbon\Carbon;
use Illuminate\Support\Str;
use Illuminate\Support\Facades\Schema;
use App\Models\AppReupload;
use Illuminate\Support\Facades\Route;
use App\Models\AssociadoDoisDocReupload;

class AnalistaController extends Controller
{
    public function __construct()
    {
        $this->middleware(['auth', 'role:analista']);
    }

public function index(Request $r)
{
    $perPage   = (int) $r->input('pp', 20);
    $perPage   = max(1, min(200, $perPage));
    $rawSearch = trim((string) $r->input('q', ''));
    // ativos|todos|recebidos|recebida|reenvio|incompleta|pendente
    $statusIn  = strtolower(trim((string) $r->input('st', 'ativos')));
    $page      = max(1, (int) $r->input('page', 1));

    // ===== MODO DE BUSCA =====
    // Em "todos" buscamos APENAS por NOME; caso contrário, busca por CÓDIGO DE CONTRATO.
    $searchByName = ($statusIn === 'todos');

    // Normalização e validação de "código do contrato" — só usada quando NÃO estamos em "todos"
    $normalized     = strtoupper($rawSearch);
    $normalized     = preg_replace('/[^A-Z0-9\-]/', '', $normalized);
    $isContractCode = !$searchByName && $normalized !== '' && preg_match('/^[A-Z0-9]+(?:-[A-Z0-9]+)+$/', $normalized);
    $codeFilter     = $isContractCode ? $normalized : null;

    // Contador robusto de documentos (tabela web/Agente)
    $docsCountSql = "(
        CASE
          WHEN agente_cadastros.documents_json IS NULL
               OR TRIM(agente_cadastros.documents_json) = '' THEN 0
          WHEN JSON_VALID(agente_cadastros.documents_json) THEN COALESCE(JSON_LENGTH(agente_cadastros.documents_json), 0)
          ELSE 1
        END
    )";
    $hasDocsSql = "($docsCountSql > 0)";

    // ===== Flags de schema (evita quebrar quando coluna não existe ainda) =====
    $hasAssumptionsTable = \Schema::hasTable('agente_cadastro_assumptions');
    $hasA2AssumptionFk   = $hasAssumptionsTable && \Schema::hasColumn('agente_cadastro_assumptions', 'associadodois_cadastro_id');
    $hasHeartbeatCol     = $hasAssumptionsTable && \Schema::hasColumn('agente_cadastro_assumptions', 'heartbeat_at');
    $hasLiberadoCol      = $hasAssumptionsTable && \Schema::hasColumn('agente_cadastro_assumptions', 'liberado_em');

    // ===========================
    // ===== WEB / AGENTE ========
    // ===========================
    $webQb = \App\Models\AgenteCadastro::query()
        ->with([
            // ✅ assumption: select "dinâmico"
            'assumption' => function ($q) use ($hasHeartbeatCol, $hasLiberadoCol) {
                $cols = ['id', 'agente_cadastro_id', 'analista_id', 'status', 'assumido_em'];
                if ($hasHeartbeatCol) $cols[] = 'heartbeat_at';
                if ($hasLiberadoCol)  $cols[] = 'liberado_em';
                $q->select($cols);
            },

            'reuploads' => function ($q) {
                $q->select(
                    'id',
                    'agente_cadastro_id',
                    'status',
                    'uploaded_at',
                    'file_original_name',
                    'file_stored_name',
                    'file_relative_path',
                    'file_mime',
                    'file_size_bytes'
                )
                ->orderByDesc('uploaded_at')
                ->orderByDesc('id');
            },
        ])
        ->withCount([
            'issues as open_issues_count'      => fn ($q) => $q->where('status', 'incomplete'),
            'issues as resolved_issues_count'  => fn ($q) => $q->where('status', 'resolved'),
        ]);

    // BUSCA (web/Agente)
    if ($searchByName && $rawSearch !== '') {
        $webQb->where('full_name', 'like', '%' . $rawSearch . '%');
    }
    if (!$searchByName && $codeFilter !== null) {
        $webQb->where('contrato_codigo_contrato', 'like', "%{$codeFilter}%");
    }

    // ====== FILTROS ======
    if ($statusIn === 'ativos') {
        $webQb->where(function ($w) use ($hasDocsSql) {
            $w->whereHas('issues', fn ($i) => $i->where('status', 'incomplete'))
              ->orWhere(function ($w2) use ($hasDocsSql) {
                  $w2->whereRaw("NOT {$hasDocsSql}")
                     ->whereDoesntHave('reuploads');
              });
        });
    } elseif ($statusIn === 'todos') {
        // sem restrição
    } elseif ($statusIn === 'recebidos') {
        $webQb->whereRaw($hasDocsSql)
              ->whereDoesntHave('reuploads')
              ->whereDoesntHave('issues')
              ->whereRaw(
                  'NOT EXISTS (
                      SELECT 1
                        FROM tesouraria_pagamentos t
                       WHERE t.agente_cadastro_id = agente_cadastros.id
                  )'
              );
    } elseif ($statusIn === 'recebida') {
        $webQb->whereRaw($hasDocsSql)
              ->whereDoesntHave('reuploads', fn ($r2) => $r2->where('status', 'received'))
              ->whereDoesntHave('issues',    fn ($i2) => $i2->where('status', 'incomplete'))
              ->whereDoesntHave('issues',    fn ($i3) => $i3->where('status', 'resolved'));
    } elseif ($statusIn === 'reenvio') {
        $webQb->whereHas('reuploads', fn ($r3) => $r3->where('status', 'received'));
    } elseif ($statusIn === 'incompleta') {
        $webQb->whereHas('issues', fn ($i4) => $i4->where('status', 'incomplete'));
    } elseif ($statusIn === 'pendente') {
        $webQb->whereRaw("NOT {$hasDocsSql}")
              ->whereDoesntHave('reuploads');
    }

    // ===========================
    // ✅ REGRA DO "ASSUMIDO" (WEB) - ATUALIZADA (SQL NOT EXISTS)
    // - Se estiver "assumido" por OUTRO analista: some da lista
    // - Se estiver "assumido" por MIM: aparece
    // - Se não tiver assumption ou estiver "liberado": aparece
    // ===========================
    $me = auth()->id();

    if ($hasAssumptionsTable && $me) {
        $webTable = $webQb->getModel()->getTable(); // normalmente "agente_cadastros"

        $webQb->whereNotExists(function ($sub) use ($webTable, $me) {
            $sub->selectRaw('1')
                ->from('agente_cadastro_assumptions as a')
                ->whereColumn('a.agente_cadastro_id', $webTable . '.id')
                ->where('a.status', 'assumido')
                ->where('a.analista_id', '<>', $me);
        });
    }

    // Para unificar com APP, não paginamos aqui; puxamos "um pouco a mais" e mesclamos depois
    $webRows = $webQb
        ->orderByDesc('id')
        ->limit($perPage * 5)
        ->get()
        ->map(function ($w) {
            $w->setAttribute('is_app', false);
            $w->setAttribute('aceiteTermos', false);
            $w->setAttribute('aceite_termos', 0);
            return $w;
        });

    // ===========================
    // ======= APLICATIVO ========
    // ===========================
    $appRows  = collect();
    $wantsApp = in_array($statusIn, ['recebidos', 'incompleta'], true);

    // NOVO: mapa de IDs do APP que já estão na tesouraria
    $paidAppIdSet = [];
    if (\Schema::hasTable('tesouraria_pagamentos') && \Schema::hasColumn('tesouraria_pagamentos', 'associadodois_cadastro_id')) {
        $paid = \DB::table('tesouraria_pagamentos')
            ->whereNotNull('associadodois_cadastro_id')
            ->pluck('associadodois_cadastro_id')
            ->all();
        $paidAppIdSet = array_flip($paid);
    }

    if ($wantsApp) {

        $appsQ = \App\Models\AssociadoDoisCadastro::query();

        // ✅ Só aplica assumption do APP se a coluna existir
        if ($hasA2AssumptionFk) {
            $appsQ->with([
                'assumption' => function ($q) use ($hasHeartbeatCol, $hasLiberadoCol) {
                    $cols = ['id','associadodois_cadastro_id','analista_id','status','assumido_em'];
                    if ($hasHeartbeatCol) $cols[] = 'heartbeat_at';
                    if ($hasLiberadoCol)  $cols[] = 'liberado_em';
                    $q->select($cols);
                }
            ]);

            // ✅ REGRA DO "ASSUMIDO" (APP) - ATUALIZADA (SQL NOT EXISTS)
            // Esconde se estiver "assumido" por OUTRO analista
            if ($hasAssumptionsTable && $me) {
                $appTable = $appsQ->getModel()->getTable(); // ex: "associadodois_cadastros"

                $appsQ->whereNotExists(function ($sub) use ($appTable, $me) {
                    $sub->selectRaw('1')
                        ->from('agente_cadastro_assumptions as a')
                        ->whereColumn('a.associadodois_cadastro_id', $appTable . '.id')
                        ->where('a.status', 'assumido')
                        ->where('a.analista_id', '<>', $me);
                });
            }

        } else {
            // Não quebra primeira visita caso a migration ainda não tenha rodado nesse banco
            \Log::warning('[Analista.index] APP lock ignorado: coluna associadodois_cadastro_id ausente em agente_cadastro_assumptions', [
                'user_id' => $me,
                'st'      => $statusIn,
            ]);
        }

        // busca (APP)
        if ($searchByName && $rawSearch !== '') {
            $appsQ->where('full_name', 'like', '%' . $rawSearch . '%');
        }
        if (!$searchByName && $codeFilter !== null) {
            $appsQ->where('contrato_codigo_contrato', 'like', "%{$codeFilter}%");
        }

        $apps = $appsQ->orderByDesc('id')->limit($perPage * 5)->get();

        // Mapa de status de contato e (quando existir) flag aceite vindos de auxilio2_filiacoes
        $contactStatusMap = [];
        $contactAceiteMap = [];
        if ($apps->count() > 0 && \Schema::hasTable('auxilio2_filiacoes')) {
            $tb = 'auxilio2_filiacoes';
            $cadCol = \Schema::hasColumn($tb, 'associadodois_cadastro_id')
                ? 'associadodois_cadastro_id'
                : (\Schema::hasColumn($tb, 'cadastro_id') ? 'cadastro_id' : null);
            $statusCol = \Schema::hasColumn($tb, 'contato_status') ? 'contato_status' : null;
            $aceiteCol = \Schema::hasColumn($tb, 'aceite') ? 'aceite' : null;

            if ($cadCol) {
                $sel = [$cadCol.' as cad_id', 'id'];
                if ($statusCol) $sel[] = $statusCol.' as st';
                if ($aceiteCol) $sel[] = $aceiteCol.' as ac';

                $rows = \DB::table($tb)
                    ->select($sel)
                    ->whereIn($cadCol, $apps->pluck('id')->all())
                    ->orderBy($cadCol)
                    ->orderByDesc('id')
                    ->get();

                foreach ($rows as $row) {
                    if (!isset($contactStatusMap[$row->cad_id]) && property_exists($row, 'st')) {
                        $contactStatusMap[$row->cad_id] = $row->st;
                    }
                    if (!isset($contactAceiteMap[$row->cad_id]) && property_exists($row, 'ac')) {
                        $contactAceiteMap[$row->cad_id] = (int) $row->ac;
                    }
                }
            }
        }

        $appRows = $apps
            ->map(function ($r) use ($contactStatusMap, $paidAppIdSet) {
                $docsNorm  = $this->normalizeAppDocs($r->id, $r->documents_json, $r->created_at);
                $reupsNorm = $this->normalizeAppReuploads($r->id);

                $issues = \DB::table('associadodois_doc_issues')
                    ->where('associadodois_cadastro_id', $r->id)
                    ->pluck('status');

                $openSet     = ['open','waiting_user','received','rejected'];
                $resolvedSet = ['accepted','closed'];

                $openCnt     = $issues->filter(fn($s) => in_array($s, $openSet, true))->count();
                $resolvedCnt = $issues->filter(fn($s) => in_array($s, $resolvedSet, true))->count();

                // flags/app
                $r->setAttribute('is_app', true);
                $r->agente_responsavel    = 'Aplicativo';
                $r->documents_json        = array_values(array_merge($docsNorm, $reupsNorm));
                $r->open_issues_count     = $openCnt;
                $r->resolved_issues_count = $resolvedCnt;
                $r->setAttribute('app_reuploads_count', count($reupsNorm));

                // status de contato (chip)
                if (isset($contactStatusMap[$r->id]) && $contactStatusMap[$r->id] !== null && $contactStatusMap[$r->id] !== '') {
                    $r->setAttribute('contato_status', $contactStatusMap[$r->id]);
                }

                // ACEITE DE TERMOS (APP)
                $aceiteTermos = ((int)($r->aceite_termos ?? 0) === 1);
                $r->setAttribute('aceiteTermos', $aceiteTermos);
                $r->setAttribute('aceite_termos', $aceiteTermos ? 1 : 0);

                // já está na tesouraria?
                $r->setAttribute('tem_pagamento_tesouraria', isset($paidAppIdSet[$r->id]));

                return $r;
            })
            ->filter(function ($r) use ($statusIn) {
                $docsHasAny     = is_array($r->documents_json) && count($r->documents_json) > 0;
                $hasOpenIssue   = (int) ($r->open_issues_count ?? 0) > 0;
                $hasAnyReup     = (int) ($r->app_reuploads_count ?? 0) > 0;
                $jaNaTesouraria = (bool) ($r->tem_pagamento_tesouraria ?? false);

                if ($statusIn === 'recebidos') {
                    return $docsHasAny && !$hasOpenIssue && !$hasAnyReup && !$jaNaTesouraria;
                }
                if ($statusIn === 'incompleta') {
                    return $hasOpenIssue;
                }
                return false;
            })
            ->values();
    }

    // ===========================
    // ====== MESCLA + ORDEM =====
    // ===========================
    $merged = ($wantsApp ? $webRows->concat($appRows) : $webRows)->values();

    $ascByArrival = $merged->sort(function ($a, $b) {
        $aT = \Carbon\Carbon::parse($a->created_at);
        $bT = \Carbon\Carbon::parse($b->created_at);
        if ($aT->equalTo($bT)) {
            return ($a->id <=> $b->id);
        }
        return ($aT <=> $bT);
    })->values();

    $arrivalRank = [];
    foreach ($ascByArrival as $idx => $row) {
        $key = (($row->is_app ?? false) ? 'A' : 'W') . ':' . (int) $row->id;
        $arrivalRank[$key] = $idx + 1;
    }

    if ($statusIn === 'recebidos') {
        $sorted = $ascByArrival;
    } else {
        $sorted = $merged->sort(function ($a, $b) {
            return $b->id <=> $a->id;
        })->values();
    }

    foreach ($sorted as $row) {
        $key = (($row->is_app ?? false) ? 'A' : 'W') . ':' . (int) $row->id;
        $row->setAttribute('arrival_order', $arrivalRank[$key] ?? null);
    }

    $total   = $sorted->count();
    $offset  = ($page - 1) * $perPage;
    $items   = $sorted->slice($offset, $perPage)->values();

    // Quantidade de APPs nesta página (badge)
    $appCount = $items->filter(fn($r) => (bool)($r->is_app ?? false))->count();

    $contratos = new \Illuminate\Pagination\LengthAwarePaginator(
        $items,
        $total,
        $perPage,
        $page,
        [
            'path'  => $r->url(),
            'query' => $r->query(),
        ]
    );

    $reenviados = \App\Models\AgenteDocReupload::with(['cadastro', 'issue'])
        ->whereIn('status', ['received', 'accepted', 'rejected'])
        ->orderByRaw("FIELD(status, 'received','accepted','rejected')")
        ->orderByDesc('uploaded_at')
        ->orderByDesc('id')
        ->limit(200)
        ->get();

    $invalidSearch = (!$searchByName) && ($rawSearch !== '' && $codeFilter === null);

    return view('analista.dashboardanalista', [
        'contratos'      => $contratos,
        'search'         => $rawSearch,
        'perPage'        => $perPage,
        'reenviados'     => $reenviados,
        'onlyCode'       => !$searchByName,
        'invalidSearch'  => $invalidSearch,
        'codeFilter'     => $codeFilter,
        'statusFilter'   => $statusIn,
        'showConcluidos' => ($statusIn === 'todos'),
        'appCount'       => $appCount,
    ]);
}








    /**
     * Constrói a janela de competência **06→05** (fechamento no dia 05) para SQL (pagamentos).
     */
    private function competenciaSql(string $mesParam): array
    {
        $tz            = $this->tz();
        $fechamentoDia = (int) env('FECHAMENTO_DIA', 5);
        $diaInicio     = $fechamentoDia + 1; // 06 (se fechamento é 05)

        if (!preg_match('~^\d{4}-\d{2}$~', $mesParam)) {
            $mesParam = now($tz)->format('Y-m');
        }

        [$Y, $M]  = array_map('intval', explode('-', $mesParam));
        $inicio   = Carbon::create($Y, $M, $diaInicio, 0, 0, 0, $tz)->startOfDay();
        $exclusivo= $inicio->copy()->addMonth();
        $uiFim    = $exclusivo->copy()->subSecond();

        // Converte datas para a mesma zona da sessão MySQL
        $offsetMinutes = $inicio->offsetMinutes;
        $sign          = $offsetMinutes >= 0 ? '+' : '-';
        $h             = str_pad((string) floor(abs($offsetMinutes) / 60), 2, '0', STR_PAD_LEFT);
        $m             = str_pad((string) (abs($offsetMinutes) % 60), 2, '0', STR_PAD_LEFT);
        $TZ_SQL        = "{$sign}{$h}:{$m}";

        $TS_LOCAL = "CONVERT_TZ(COALESCE(p.paid_at, p.created_at), @@session.time_zone, ?)";
        $between  = "$TS_LOCAL >= ? AND $TS_LOCAL < ?";

        return [
            'tz'          => $tz,
            'mes'         => $mesParam,
            'start'       => $inicio,
            'end_excl'    => $exclusivo,
            'end_ui'      => $uiFim,
            'TZ_SQL'      => $TZ_SQL,
            'TS_LOCAL'    => $TS_LOCAL,
            'between'     => $between,
            'betweenArgs' => [$TZ_SQL, $inicio, $TZ_SQL, $exclusivo],
        ];
    }

    /**
     * LISTA + totais (mantido)
     */
    public function ajustesIndex(Request $r)
    {
        $perPage = (int) $r->input('pp', 50);
        $mes     = trim((string) $r->input('mes', now()->format('Y-m')));
        $q       = trim((string) $r->input('q', ''));

        $C = $this->competenciaSql($mes);

        $qb = DB::table('tesouraria_pagamentos as p')
            ->leftJoin('users as u', 'u.id', '=', 'p.created_by_user_id')
            ->select([
                'p.id',
                'p.agente_cadastro_id',
                'p.contrato_codigo_contrato',
                'p.contrato_valor_antecipacao',
                'p.cpf_cnpj',
                'p.full_name',
                'p.agente_responsavel',
                'p.status',
                'p.valor_pago',
                'p.paid_at',
                'p.created_at',
                'p.updated_at',
                DB::raw('COALESCE(u.name, "") as created_by_name'),
            ])
            ->selectRaw($C['TS_LOCAL'] . ' as paid_at_local', [$C['TZ_SQL']])
            ->whereRaw($C['between'], $C['betweenArgs']);

        if ($q !== '') {
            $digits = preg_replace('/\D+/', '', $q);
            $qb->where(function ($w) use ($q, $digits) {
                $w->where('p.full_name', 'like', "%{$q}%")
                  ->orWhere('p.contrato_codigo_contrato', 'like', "%{$q}%")
                  ->orWhere('p.agente_responsavel', 'like', "%{$q}%");
                if ($digits !== '') {
                    $w->orWhere('p.cpf_cnpj', 'like', "%{$digits}%");
                }
            });
        }

        $qb->orderByRaw($C['TS_LOCAL'] . ' asc', [$C['TZ_SQL']])
           ->orderBy('p.id', 'asc');

        $rows = $qb->paginate($perPage)->withQueryString();

        $totalPagina = collect($rows->items())->sum(fn ($row) => (float) ($row->valor_pago ?? 0));

        $cadPagosNaCompetencia = \App\Models\AgenteCadastro::query()
            ->join('tesouraria_pagamentos as t', 't.agente_cadastro_id', '=', 'agente_cadastros.id')
            ->where('t.status', 'pago')
            ->whereRaw(
                "CONVERT_TZ(COALESCE(t.paid_at, t.created_at), @@session.time_zone, ?) >= ?
                 AND CONVERT_TZ(COALESCE(t.paid_at, t.created_at), @@session.time_zone, ?) < ?",
                [$C['TZ_SQL'], $C['start'], $C['TZ_SQL'], $C['end_excl']]
            )
            ->select(
                'agente_cadastros.*',
                't.id as pagamento_id',
                't.paid_at',
                't.created_at as t_created_at',
                't.valor_pago',
                't.contrato_valor_antecipacao as t_valor_antecipacao',
                't.contrato_codigo_contrato as t_codigo'
            )
            ->get();

        $retornoEstimadoMes = 0.0;

        foreach ($cadPagosNaCompetencia as $c) {
            $raw = $c->anticipations_json
                ?? $c->contrato_antecipacoes
                ?? $c->contrato_antecipacoes_json
                ?? null;

            if ($raw instanceof \Illuminate\Support\Collection) {
                $items = $raw->toArray();
            } elseif (is_array($raw)) {
                $items = $raw;
            } elseif (is_string($raw) && trim($raw) !== '') {
                $items = (array) (json_decode($raw, true) ?: []);
            } else {
                $items = [];
            }

            $toFloat = function ($v) {
                if (is_numeric($v)) return (float) $v;
                $s = preg_replace('/[^\d,.\-]+/', '', (string) $v);
                $s = str_replace('.', '', $s);
                $s = str_replace(',', '.', $s);
                return (float) $s;
            };

            $somaAnt = 0.0;
            foreach ($items as $it) {
                $val = $it['valorAuxilio'] ?? $it['valor'] ?? $it['value'] ?? $it['amount'] ?? null;
                if ($val !== null && $val !== '') $somaAnt += $toFloat($val);
            }

            $mens  = (float) ($c->contrato_mensalidade ?? 0);
            $prazo = (int)   ($c->contrato_prazo_meses ?? 3);
            $x3pad = round($mens * ($prazo > 0 ? $prazo : 3), 2);
            $x3    = (float) ($c->t_valor_antecipacao ?? $c->contrato_valor_antecipacao ?? $x3pad);

            $retornoEstimadoMes += ($somaAnt > 0 ? $somaAnt : $x3);
        }

        return view('analista.dashboardanalistaajuste', [
            'rows'               => $rows,
            'search'             => $q,
            'perPage'            => $perPage,
            'mes'                => $C['mes'],
            'rangeStart'         => $C['start']->format('Y-m-d H:i:s'),
            'rangeEnd'           => $C['end_ui']->format('Y-m-d H:i:s'),
            'totalPagina'        => (float) $totalPagina,
            'retornoEstimadoMes' => (float) $retornoEstimadoMes,
        ]);
    }

    public function updatePagamentoDate(Request $r, int $pagamentoId)
    {
        $r->validate(['new_date' => ['required', 'string', 'max:25']]);

        $row = DB::table('tesouraria_pagamentos')->where('id', $pagamentoId)->first();
        if (!$row) {
            return response()->json(['error' => 'Pagamento não encontrado.'], 404);
        }
        if ($row->status !== 'pago') {
            return response()->json(['error' => 'Somente pagamentos com status "pago" podem ser ajustados.'], 422);
        }

        $raw = trim($r->input('new_date'));
        try {
            if (preg_match('~^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$~', $raw)) {
                $dt = Carbon::createFromFormat('Y-m-d\TH:i', $raw);
            } else {
                $dt = Carbon::createFromFormat('Y-m-d', $raw)->setTime(12, 0, 0);
            }
        } catch (\Throwable $e) {
            return response()->json(['error' => 'Formato de data inválido.'], 422);
        }

        DB::table('tesouraria_pagamentos')
            ->where('id', $pagamentoId)
            ->update([
                'paid_at'    => $dt,
                'updated_at' => now(),
                'notes'      => trim(((string) ($row->notes ?? '')) . "\n[Ajuste analista " . auth()->user()->name . " em " . now()->format('d/m/Y H:i') . " para {$dt->format('d/m/Y H:i')}]"),
            ]);

        return response()->json([
            'ok'          => true,
            'id'          => $pagamentoId,
            'paid_at_iso' => $dt->toIso8601String(),
            'paid_at_br'  => $dt->format('d/m/Y H:i'),
        ]);
    }

    /**
     * Marcar documentação como incompleta (web/Agente) — mantido
     */
    public function markIncomplete(Request $request, AgenteCadastro $cadastro)
    {
        $request->validate(['mensagem' => 'required|string|min:5|max:5000']);

        AgenteDocIssue::create([
            'agente_cadastro_id'       => $cadastro->id,
            'cpf_cnpj'                 => $cadastro->cpf_cnpj,
            'contrato_codigo_contrato' => $cadastro->contrato_codigo_contrato,
            'analista_id'              => $request->user()->id,
            'status'                   => 'incomplete',
            'mensagem'                 => $request->input('mensagem'),
            'documents_snapshot_json'  => $cadastro->documents_json ?: null,
        ]);

        Log::info('Analista marcou documentação como incompleta', ['cadastro_id' => $cadastro->id]);

        return back()->with('ok', 'Marcado como documentação incompleta e notificação registrada.');
    }

    /**
     * VALIDAR DOCUMENTAÇÃO (web/Agente) — mantido
     */
public function validateDocs(Request $request, AgenteCadastro $cadastro)
{
    DB::beginTransaction();

    try {
        // --- Pré-checagens robustas antes de "resolver" pendências ---
        // Há documentos?
        $docsRaw        = $cadastro->documents_json;
        $hasDocsInitial = is_array($docsRaw)
            ? (count($docsRaw) > 0)
            : (is_string($docsRaw) && trim($docsRaw) !== '' && count((array) json_decode($docsRaw, true)) > 0);

        $hasAnyReupload = AgenteDocReupload::where('agente_cadastro_id', $cadastro->id)->exists();
        $hasReupReceived= AgenteDocReupload::where('agente_cadastro_id', $cadastro->id)->where('status','received')->exists();
        $hasOpenIssue   = AgenteDocIssue::where('agente_cadastro_id', $cadastro->id)->where('status','incomplete')->exists();

        if (!$hasDocsInitial && !$hasAnyReupload) {
            DB::rollBack();
            return back()->withErrors([
                'validar' => 'Não há documentos anexados para validar.'
            ]);
        }

        // Se está "Incompleta" e não há reenvio recebido, não pode validar
        if ($hasOpenIssue && !$hasReupReceived) {
            DB::rollBack();
            return back()->withErrors([
                'validar' => 'Há pendências abertas e nenhum reenvio recebido. Aguarde o reenvio do associado para validar.'
            ]);
        }

        // --- Agora sim: fechar pendências e aceitar reenviados (quando existirem) ---
        AgenteDocIssue::where('agente_cadastro_id', $cadastro->id)
            ->where('status', 'incomplete')
            ->lockForUpdate()
            ->update([
                'status'     => 'resolved',
                'updated_at' => now(),
            ]);

        AgenteDocReupload::where('agente_cadastro_id', $cadastro->id)
            ->where('status', 'received')
            ->lockForUpdate()
            ->update([
                'status'     => 'accepted',
                'updated_at' => now(),
            ]);

        // Checagens finais
        $hasOpenIssueAfter = AgenteDocIssue::where('agente_cadastro_id', $cadastro->id)
            ->where('status', 'incomplete')
            ->exists();

        $hasAnyReupAfter = AgenteDocReupload::where('agente_cadastro_id', $cadastro->id)->exists();

        if (!$hasOpenIssueAfter && ($hasDocsInitial || $hasAnyReupAfter)) {
            $mens         = (float) ($cadastro->contrato_mensalidade ?? 0);
            $prazo        = (int)   ($cadastro->contrato_prazo_meses ?? 3);
            $valorAntecip = (float) ($cadastro->contrato_valor_antecipacao ?? round($mens * ($prazo > 0 ? $prazo : 3), 2));

            $tp = TesourariaPagamento::where('agente_cadastro_id', $cadastro->id)
                ->lockForUpdate()
                ->first();

            if ($tp) {
                $tp->contrato_codigo_contrato   = $cadastro->contrato_codigo_contrato;
                $tp->contrato_valor_antecipacao = $valorAntecip;
                $tp->cpf_cnpj                   = $cadastro->cpf_cnpj;
                $tp->full_name                  = $cadastro->full_name;
                $tp->agente_responsavel         = $cadastro->agente_responsavel;
                if ($tp->status !== 'pago') $tp->status = 'pendente';
                $tp->updated_at = now();
                $tp->save();

                Log::info('Analista: atualização de registro existente na Tesouraria', [
                    'tesouraria_id' => $tp->id,
                    'cadastro_id'   => $cadastro->id,
                    'status'        => $tp->status,
                ]);
            } else {
                $tp = TesourariaPagamento::create([
                    'agente_cadastro_id'         => $cadastro->id,
                    'created_by_user_id'         => null,
                    'contrato_codigo_contrato'   => $cadastro->contrato_codigo_contrato,
                    'contrato_valor_antecipacao' => $valorAntecip,
                    'cpf_cnpj'                   => $cadastro->cpf_cnpj,
                    'full_name'                  => $cadastro->full_name,
                    'agente_responsavel'         => $cadastro->agente_responsavel,
                    'status'                     => 'pendente',
                    'valor_pago'                 => null,
                    'paid_at'                    => null,
                    'forma_pagamento'            => null,
                    'comprovante_path'           => null,
                    'notes'                      => 'Gerado pelo Analista após validação.',
                ]);

                Log::info('Analista: criado registro na Tesouraria', [
                    'tesouraria_id' => $tp->id,
                    'cadastro_id'   => $cadastro->id,
                ]);
            }

            DB::commit();
            return back()->with('ok', 'Documentação validada e enviada à Tesouraria.');
        }

        DB::commit();
        return back()->with('ok', 'Documentação validada. (Sem envio à Tesouraria porque ainda existem restrições.)');

    } catch (\Throwable $e) {
        DB::rollBack();

        Log::error('Analista@validateDocs falhou', [
            'cadastro_id' => $cadastro->id,
            'err'         => $e->getMessage(),
        ]);

        return back()->withErrors([
            'validar' => 'Falha ao validar a documentação. ' . $e->getMessage(),
        ]);
    }
}


    public function validateContract(Request $request, AgenteCadastro $cadastro)
    {
        return $this->validateDocs($request, $cadastro);
    }
public function streamReupload(int $reupload)
{
    /** WEB: usa AgenteDocReupload (não existe App\Models\Reupload) */
    /** @var \App\Models\AgenteDocReupload $r */
    $r = \App\Models\AgenteDocReupload::query()->findOrFail($reupload);

    \Log::info('[Analista] Abrindo reupload WEB', [
        'id'   => $r->id,
        'user' => optional(auth()->user())->id,
        'ip'   => request()->ip(),
    ]);

    // Colunas dinâmicas
    $rawPath  = (string)(
          $r->file_relative_path
       ?? $r->path
       ?? $r->file_path
       ?? $r->filepath
       ?? $r->stored_path
       ?? $r->url
       ?? $r->file
       ?? ''
    );
    $original = (string)(
          $r->file_original_name
       ?? $r->original_name
       ?? $r->filename
       ?? $r->name
       ?? ''
    );
    $mimeHint = (string)($r->mime ?? $r->mimetype ?? $r->content_type ?? '');
    $sizeHint = isset($r->file_size_bytes) ? (int)$r->file_size_bytes
              : (isset($r->size) ? (int)$r->size : null);
    $download = request()->boolean('dl');

    if ($rawPath === '') abort(404, 'Arquivo não encontrado');

    // URL absoluta → redireciona
    if (preg_match('~^https?://~i', $rawPath)) {
        \Log::info('[Analista] Reupload WEB redirect', ['id' => $r->id, 'url' => $rawPath]);
        return redirect()->away($rawPath);
    }

    // Normaliza e evita path traversal
    $rel = $this->normalizeAppPath($rawPath);
    $rel = ltrim($rel, '/');
    if ($rel === '' || preg_match('~\.\.(?:/|\\\)~', $rel)) {
        \Log::warning('[Analista] Reupload WEB bloqueado (path inválido)', ['id' => $r->id, 'rel' => $rel]);
        abort(404, 'Arquivo inválido');
    }

    $disk = \Storage::disk('public');

    // Locais candidatos (ordem de preferência)
    $cands = [
        // /public/uploads/{rel}
        ['kind' => 'public_uploads', 'rel' => preg_match('~^uploads/~i', $rel) ? $rel : ('uploads/'.$rel),
         'abs' => public_path(preg_match('~^uploads/~i', $rel) ? $rel : ('uploads/'.$rel)), 'disk' => false],
        // storage/app/public/{rel}
        ['kind' => 'storage_public', 'rel' => $rel,
         'abs' => method_exists($disk, 'path') ? $disk->path($rel) : null, 'disk' => true],
        // storage/app/public/uploads/{rel}
        ['kind' => 'storage_public_uploads', 'rel' => 'uploads/'.$rel,
         'abs' => method_exists($disk, 'path') ? $disk->path('uploads/'.$rel) : null, 'disk' => true],
        // /public/{rel}
        ['kind' => 'public', 'rel' => ltrim(preg_replace('~^public/~i', '', $rel), '/'),
         'abs' => public_path(ltrim(preg_replace('~^public/~i', '', $rel), '/')), 'disk' => false],
        // /public/storage/{rel} (symlink)
        ['kind' => 'public_storage_symlink', 'rel' => 'storage/'.$rel,
         'abs' => public_path('storage/'.$rel), 'disk' => false],
    ];

    foreach ($cands as $c) {
        $exists = $c['disk'] ? $disk->exists($c['rel'])
                             : (is_string($c['abs']) && is_file($c['abs']));
        if (!$exists) continue;

        $mime = $mimeHint ?: (
            $c['disk']
                ? ($disk->mimeType($c['rel']) ?: $this->guessMimeFromExt($c['rel']))
                : (@mime_content_type($c['abs']) ?: $this->guessMimeFromExt($c['abs']))
        );
        $size = $sizeHint ?: ($c['disk'] ? (int)$disk->size($c['rel']) : (int)@filesize($c['abs']));

        $filename    = $original ?: (basename($c['abs'] ?: $rel) ?: 'arquivo');
        $disposition = $download ? 'attachment' : 'inline';

        $headers = array_filter([
            'Content-Type'        => $mime ?: 'application/octet-stream',
            'Content-Length'      => $size ?: null,
            'Content-Disposition' => $disposition.'; filename="'.$filename.'"',
            'Cache-Control'       => 'private, max-age=31536000',
        ], fn ($v) => $v !== null);

        \Log::info('[Analista] Reupload WEB serve', [
            'id' => $r->id, 'served' => $c['kind'], 'rel' => $c['rel'], 'abs' => $c['abs'],
            'mime' => $headers['Content-Type'] ?? null, 'size' => $size,
        ]);

        if ($c['disk']) {
            $stream = $disk->readStream($c['rel']);
            if (!$stream) break;

            return response()->stream(function () use ($stream) {
                fpassthru($stream);
            }, 200, $headers);
        }

        if ($download) {
            return response()->download($c['abs'], $filename, $headers);
        }
        return response()->file($c['abs'], $headers);
    }

    \Log::warning('[Analista] Reupload WEB 404', ['id' => $r->id, 'rel' => $rel]);
    abort(404, 'Arquivo não encontrado');
}





    
public function destroyPagamento(Request $r, int $pagamento)
{
    $row = DB::table('tesouraria_pagamentos')->where('id', $pagamento)->first();

    if (!$row) {
        return back()->withErrors(['excluir' => 'Registro não encontrado.']);
    }
    if (strtolower((string)($row->status ?? '')) === 'pago') {
        return back()->withErrors(['excluir' => 'Pagamentos com status "pago" não podem ser excluídos.']);
    }

    try {
        DB::transaction(function () use ($row, $pagamento) {
            $deletedAgenteById = 0;
            if (!empty($row->agente_cadastro_id)) {
                $deletedAgenteById = DB::table('agente_cadastros')
                    ->where('id', $row->agente_cadastro_id)
                    ->delete();
            }

            $deletedAgenteByContrato = 0;
            if ($deletedAgenteById === 0 && !empty($row->contrato_codigo_contrato)) {
                $deletedAgenteByContrato = DB::table('agente_cadastros')
                    ->where('contrato_codigo_contrato', $row->contrato_codigo_contrato)
                    ->delete();
            }

            DB::table('tesouraria_pagamentos')->where('id', $pagamento)->delete();

            Log::info('Analista excluiu pagamento e cadastro de agente', [
                'pagamento_id'               => $pagamento,
                'user_id'                    => optional(auth()->user())->id,
                'deleted_agente_by_id'       => $deletedAgenteById,
                'deleted_agente_by_contrato' => $deletedAgenteByContrato,
                'contrato_codigo_contrato'   => $row->contrato_codigo_contrato,
                'agente_cadastro_id'         => $row->agente_cadastro_id,
            ]);
        });
    } catch (\Throwable $e) {
        Log::error('Erro ao excluir pagamento/cadastro de agente', [
            'pagamento_id' => $pagamento,
            'error'        => $e->getMessage(),
        ]);
        return back()->withErrors(['excluir' => 'Falha ao excluir.']);
    }

    return back()->with('ok', 'Registro excluído com sucesso (tesouraria e cadastro do agente).');
}


    // =========================
    // ====== HELPERS APP ======
    // =========================

    /** --------- Helpers --------- */
    private function mergeAntecipacoesPost(Request $r, \App\Models\AssociadoDoisCadastro $cad, \Carbon\Carbon $now): array
    {
        $ants = $this->decodeJsonFlexible($cad->anticipations_json);
        if (!is_array($ants)) $ants = [];

        $post = (array) $r->input('ants', []);
        if ($post) {
            foreach ($post as $i => $row) {
                $ants[$i] = array_merge($ants[$i] ?? [], [
                    'numeroMensalidade' => (int) ($row['numeroMensalidade'] ?? ($i+1)),
                    'valorAuxilio'      => $this->toMoney($row['valorAuxilio'] ?? null) ?: 0.0,
                    'dataEnvio'         => $this->toDate($row['dataEnvio'] ?? null) ?: ($ants[$i]['dataEnvio'] ?? $now->toDateString()),
                    'status'            => $row['status'] ?? ($ants[$i]['status'] ?? 'Pendente'),
                    'observacao'        => $row['observacao'] ?? ($ants[$i]['observacao'] ?? null),
                ]);
            }
        }

        // Se mesmo assim ficou vazio, monte o padrão (usa suas regras)
        if (empty($ants)) {
            $mesAverb = $cad->contrato_mes_averbacao
                ? \Carbon\Carbon::parse($cad->contrato_mes_averbacao, $this->tz())->startOfMonth()
                : $this->calcMesAverbacaoFromApproval(
                    $cad->contrato_data_aprovacao
                        ? \Carbon\Carbon::parse($cad->contrato_data_aprovacao, $this->tz())
                        : $now
                );

            $primeira = $cad->contrato_data_envio_primeira
                ? \Carbon\Carbon::parse($cad->contrato_data_envio_primeira, $this->tz())
                : $this->calcPrimeiraMensalidadeFromMesAverbacao($mesAverb->copy());

            $prazo = (int) ($cad->contrato_prazo_meses ?? 3);
            $ants  = $this->montarAntecipacoesPadrao($primeira->copy(), max(1, min(3, $prazo ?: 3)));
        }

        return $ants;
    }

    private function persistirCalculoSeEnviado(Request $r, \App\Models\AssociadoDoisCadastro $cad): void
    {
        // Só atua se veio algum campo do cálculo
        if (!$r->hasAny([
            'contrato_mensalidade','contrato_taxa_antecipacao','contrato_margem_disponivel',
            'contrato_valor_antecipacao','contrato_data_aprovacao','contrato_data_envio_primeira',
            'contrato_status_contrato','contrato_mes_averbacao','contrato_doacao_associado',
            'calc_prazo_antecipacao'
        ])) return;

        $cad->contrato_mensalidade       = $this->toMoney($r->input('contrato_mensalidade'));
        $cad->contrato_taxa_antecipacao  = $this->toPercent($r->input('contrato_taxa_antecipacao'));
        $cad->contrato_margem_disponivel = $this->toMoney($r->input('contrato_margem_disponivel'));
        $cad->contrato_valor_antecipacao = $this->toMoney($r->input('contrato_valor_antecipacao'));
        $cad->contrato_data_aprovacao    = $this->toDate($r->input('contrato_data_aprovacao'));
        $cad->contrato_data_envio_primeira = $this->toDate($r->input('contrato_data_envio_primeira'));
        $cad->contrato_status_contrato   = $r->input('contrato_status_contrato') ?: $cad->contrato_status_contrato;
        $cad->contrato_mes_averbacao     = $r->input('contrato_mes_averbacao') ?: $cad->contrato_mes_averbacao;
        $cad->contrato_doacao_associado  = $this->toMoney($r->input('contrato_doacao_associado'));
        $cad->contrato_prazo_meses       = max(1, min(3, (int) $r->input('calc_prazo_antecipacao', $cad->contrato_prazo_meses ?: 3)));

        $cad->save();
    }

    // =========================
    // === HELPERS DE ARQUIVO ==
    // =========================

    /** Aceita array, JSON, ou JSON-duplo e devolve array sempre */
    private function decodeJsonFlexible($raw)
    {
        if (is_array($raw)) return $raw;
        $s = is_string($raw) ? trim($raw) : '';
        if ($s === '') return [];
        $once = json_decode($s, true);
        if (json_last_error() === JSON_ERROR_NONE) {
            if (is_array($once)) return $once;
            if (is_string($once)) {
                $twice = json_decode($once, true);
                return is_array($twice) ? $twice : [];
            }
        }
        return [];
    }

    /** Normaliza caminhos relativos do storage público (remove public/, storage/, barras extras) */
private function normalizeAppPath(string $path): string
{
    $p = trim($path ?? '');
    // remove possíveis prefixes redundantes
    $p = preg_replace('~^https?://[^/]+/~i', '', $p); // se vier com domínio
    $p = preg_replace('~^storage/~i', '', $p);        // ex: storage/uploads/...
    return ltrim($p, '/');
}

    /** Mime básico por extensão (fallback quando o Storage não sabe) */
private function guessMimeFromExt(string $name): string
{
    $ext = strtolower(pathinfo($name, PATHINFO_EXTENSION) ?: '');
    return match ($ext) {
        'jpg','jpeg' => 'image/jpeg',
        'png'        => 'image/png',
        'gif'        => 'image/gif',
        'webp'       => 'image/webp',
        'pdf'        => 'application/pdf',
        'txt','log'  => 'text/plain',
        'csv'        => 'text/csv',
        'doc'        => 'application/msword',
        'docx'       => 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xls'        => 'application/vnd.ms-excel',
        'xlsx'       => 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        default      => 'application/octet-stream',
    };
}

/**
 * Normaliza os documentos INICIAIS do APP (documents_json) para o modal/lista.
 * Agora identifica caminhos em public/uploads e gera URL correta (/uploads/...),
 * sem tentar usar o disk 'public'.
 */
	
private function relFromUploads(string $path): ?string
{
    $p = str_replace('\\', '/', trim($path));
    $p = ltrim(preg_replace('~^(?:public/|storage/)~i', '', $p), '/');
    $pos = stripos($p, 'uploads/');
    return $pos === false ? null : substr($p, $pos); // "uploads/..."
}
/**
 * APP — documentos iniciais (documents_json)
 * Agora tenta abrir em public/uploads/... (se existir),
 * senão cai para o disk('public') e, por fim, para /storage/...
 * Além disso, o "Abrir" passa por uma rota com LOG.
 */
private function normalizeAppDocs(int $cadastroId, $raw, $createdAt): array
{
    $data = $this->decodeJsonFlexible($raw);
    if (!is_array($data) || empty($data)) return [];

    // reindexa se vier numérico
    $assoc = array_keys($data) !== range(0, count($data) - 1)
        ? $data
        : collect($data)->mapWithKeys(fn ($p, $i) => ['arquivo_' . ($i + 1) => $p])->all();

    $out = [];
    $i = 1;

    foreach ($assoc as $key => $item) {
        $orig = is_array($item) ? ($item['original_name'] ?? $item['stored_name'] ?? null) : null;
        $mimeH= is_array($item) ? ($item['mime'] ?? $item['type'] ?? null) : null;
        $sizeH= is_array($item) ? ($item['size_bytes'] ?? $item['size'] ?? null) : null;
        $path = is_array($item) ? ($item['relative_path'] ?? $item['open_url'] ?? $item['path'] ?? $item['url'] ?? null) : $item;

        if (!is_string($path) || trim($path) === '') { $i++; continue; }

        // uploaded_at amigável
        $uploadedAt = null;
        if (is_array($item) && !empty($item['uploaded_at'])) {
            try { $uploadedAt = \Carbon\Carbon::parse($item['uploaded_at'])->format('d/m/Y H:i'); } catch (\Throwable $e) {}
        }
        if (!$uploadedAt && $createdAt) {
            try { $uploadedAt = \Carbon\Carbon::parse($createdAt)->format('d/m/Y H:i'); } catch (\Throwable $e) {}
        }

        // Resolução de caminho
        $resolvedUrl = '';      // para exibir (debug se precisar)
        $mime        = $mimeH ?: 'application/octet-stream';
        $sizeB       = $sizeH ? (int) $sizeH : null;
        $stored      = null;

        if (preg_match('~^https?://~i', $path)) {
            // URL absoluta
            $resolvedUrl = $path;
            $stored      = basename(parse_url($path, PHP_URL_PATH) ?? 'arquivo_'.$i);
            if (!$mimeH) $mime = $this->guessMimeFromExt($stored);
        } else {
            // relativo: normaliza e tenta em public/uploads primeiro
            $rel = $this->normalizeAppPath($path);               // ex.: "associados/467/arquivo.jpg"
            $rel = ltrim($rel, '/');
            $stored = basename($rel);

            // Tenta public/uploads/{rel}
            $candidate = preg_match('~^uploads/~i', $rel) ? $rel : ('uploads/'.$rel);
            $absUp = public_path($candidate);
            if (is_file($absUp)) {
                $resolvedUrl = asset($candidate);
                $sizeB       = $sizeB ?: (int) @filesize($absUp);
                $m           = @mime_content_type($absUp);
                if ($m) $mime = $m; else if (!$mimeH) $mime = $this->guessMimeFromExt($candidate);
            } else {
                // Tenta disk('public') => storage/app/public/{rel}
                $disk = \Storage::disk('public');
                if ($disk->exists($rel)) {
                    $resolvedUrl = $disk->url($rel);             // => /storage/{rel}
                    $mime        = $disk->mimeType($rel) ?: ($mimeH ?: $this->guessMimeFromExt($rel));
                    $sizeB       = $sizeB ?: (int) $disk->size($rel);
                } else {
                    // Fallback visual
                    $resolvedUrl = asset('storage/'.$rel);       // pode dar 404 se não existir — o proxy/rota cobre
                    $mime        = $mimeH ?: $this->guessMimeFromExt($rel);
                }
            }
        }

        // IMPORTANTE: o botão "Abrir" agora usa uma ROTA com LOG, não a URL direta
        $openUrl = route('analista.a2doc.open', ['cad' => $cadastroId, 'i' => $i]);

        $out[] = [
            'original_name' => $orig ?: (is_string($key) && $key !== '' ? strtoupper(str_replace(['_','-'],' ', $key)) : ('ARQUIVO_'.$i)),
            'stored_name'   => $stored,
            'mime'          => $mime,
            'size_bytes'    => $sizeB,
            'open_url'      => $openUrl,       // <<< botão "Abrir"
            'relative_path' => $resolvedUrl,   // URL resolvida (útil pra inspecionar)
            'uploaded_at'   => $uploadedAt,
            'is_reupload'   => false,
            'is_app_doc'    => true,
        ];
        $i++;
    }

    return $out;
}


/**
 * Solta o lock do cadastro (somente se estiver assumido por MIM).
 * Marca como liberado e zera heartbeat quando existir.
 */
private function liberarAssumido(int $cadastroId): void
{
    $me = auth()->id();
    if (!$me) return;

    // Cache simples pra não ficar consultando schema toda hora
    static $hasLiberadoEm = null;
    static $hasHeartbeat  = null;

    if ($hasLiberadoEm === null) {
        $hasLiberadoEm = \Schema::hasColumn('agente_cadastro_assumptions', 'liberado_em');
    }
    if ($hasHeartbeat === null) {
        $hasHeartbeat = \Schema::hasColumn('agente_cadastro_assumptions', 'heartbeat_at');
    }

    $upd = [
        'status'     => 'liberado',
        'updated_at' => now(),
    ];

    if ($hasLiberadoEm) {
        $upd['liberado_em'] = now();
    }
    if ($hasHeartbeat) {
        $upd['heartbeat_at'] = null;
    }

    \App\Models\AgenteCadastroAssumption::where('agente_cadastro_id', $cadastroId)
        ->where('status', 'assumido')
        ->where('analista_id', $me)
        ->update($upd);
}

private function liberarAssumidoApp(int $cadastroId): void
{
    $me = auth()->id();
    if (!$me) return;

    static $hasLiberadoEm = null;
    static $hasHeartbeat  = null;

    if ($hasLiberadoEm === null) {
        $hasLiberadoEm = \Schema::hasColumn('agente_cadastro_assumptions', 'liberado_em');
    }
    if ($hasHeartbeat === null) {
        $hasHeartbeat = \Schema::hasColumn('agente_cadastro_assumptions', 'heartbeat_at');
    }

    $upd = [
        'status'     => 'liberado',
        'updated_at' => now(),
    ];

    if ($hasLiberadoEm) $upd['liberado_em'] = now();
    if ($hasHeartbeat)  $upd['heartbeat_at'] = null;

    \App\Models\AgenteCadastroAssumption::where('associadodois_cadastro_id', $cadastroId)
        ->where('status', 'assumido')
        ->where('analista_id', $me)
        ->update($upd);
}

/**
 * Abre um documento INICIAL do APP (documents_json) com LOG.
 * Tenta na ordem: public/uploads/{rel} -> storage/app/public/{rel} -> redireciona se for URL absoluta.
 * Exibe 404 se não achar em lugar nenhum e LOGa o que tentou.
 *
 * GET /analista/a2/{cad}/doc/{i}?dl=1    (dl=download)
 */
public function openAppDoc(int $cad, int $i)
{
    $row = \DB::table('associadodois_cadastros')
        ->select('id','documents_json','created_at','full_name','contrato_codigo_contrato')
        ->where('id', $cad)
        ->first();

    if (!$row) abort(404);

    $docs = $this->decodeJsonFlexible($row->documents_json);
    if (empty($docs)) abort(404);

    // reindex igual ao normalizeAppDocs (1-based)
    if (array_keys($docs) === range(0, count($docs) - 1)) {
        $docs = collect($docs)->mapWithKeys(fn ($p, $idx) => ['arquivo_'.($idx+1) => $p])->all();
    }
    $keys = array_keys($docs);
    $key  = $keys[$i-1] ?? null;
    if ($key === null) abort(404);

    $item = $docs[$key];
    $path = is_array($item)
        ? ($item['relative_path'] ?? $item['open_url'] ?? $item['path'] ?? $item['url'] ?? '')
        : (string) $item;

    $original = is_array($item) ? ($item['original_name'] ?? null) : null;

    // Resolução
    $served  = null;  // 'public_uploads' | 'storage_public' | 'redirect'
    $absPath = null;
    $mime    = 'application/octet-stream';
    $dl      = request()->boolean('dl');

    if (preg_match('~^https?://~i', (string)$path)) {
        \Log::info('A2Doc OPEN redirect', [
            'cad'   => $row->id,
            'idx'   => $i,
            'path'  => $path,
            'user'  => optional(auth()->user())->id,
            'ip'    => request()->ip(),
        ]);
        return redirect()->away($path);
    }

    $rel    = $this->normalizeAppPath((string)$path);
    $rel    = ltrim($rel, '/');

    // 1) public/uploads/{rel}
    $candidate = preg_match('~^uploads/~i', $rel) ? $rel : ('uploads/'.$rel);
    $absUp     = public_path($candidate);
    if (is_file($absUp)) {
        $absPath = $absUp;
        $served  = 'public_uploads';
        $mime    = @mime_content_type($absUp) ?: $this->guessMimeFromExt($candidate);
    } else {
        // 2) storage/app/public/{rel}
        $disk = \Storage::disk('public');
        if ($rel !== '' && $disk->exists($rel)) {
            $absPath = $disk->path($rel);
            $served  = 'storage_public';
            $mime    = $disk->mimeType($rel) ?: $this->guessMimeFromExt($rel);
        }
    }

    if ($absPath && is_file($absPath)) {
        \Log::info('A2Doc OPEN file', [
            'cad'      => $row->id,
            'idx'      => $i,
            'served'   => $served,
            'rel'      => $rel,
            'abs'      => $absPath,
            'size'     => @filesize($absPath),
            'user'     => optional(auth()->user())->id,
            'ip'       => request()->ip(),
            'contrato' => $row->contrato_codigo_contrato,
            'nome'     => $row->full_name,
        ]);

        if ($dl) {
            return response()->download($absPath, ($original ?: basename($absPath)), ['Content-Type' => $mime]);
        }
        return response()->file($absPath, [
            'Content-Type'  => $mime,
            'Cache-Control' => 'private, max-age=31536000',
        ]);
    }

    // 404 com LOG detalhado
    \Log::warning('A2Doc OPEN 404', [
        'cad'      => $row->id,
        'idx'      => $i,
        'path_in'  => $path,
        'rel'      => $rel,
        'try_up'   => $candidate,
        'exists_up'=> is_file($absUp),
        'exists_st'=> \Storage::disk('public')->exists($rel),
        'user'     => optional(auth()->user())->id,
        'ip'       => request()->ip(),
    ]);

    abort(404);
}


/**
 * Normaliza a lista de arquivos do APP para o Analista.
 * - Junta documentos iniciais (documents_json) e reuploads (tabela dinâmica)
 * - Usa pushNormalizedFile() para reuploads, garantindo rota com log
 * - Para docs iniciais, usa rota analista.a2doc.open (com log)
 *
 * @param  object|array $cad  Cadastro (Eloquent ou stdClass)
 * @return array               Lista flat de arquivos normalizados
 */
private function normalizeAppReuploads($cad): array
{
    $out = [];

    // ==== 1) DOCUMENTOS INICIAIS (documents_json) COM ROTA (LOG) ====
    $cadId   = is_object($cad) ? ($cad->id ?? $cad->cadastro_id ?? $cad->cadastro ?? null)
                               : ($cad['id'] ?? $cad['cadastro_id'] ?? $cad['cadastro'] ?? null);

    // tenta várias chaves possíveis para o JSON
    $docsRaw = is_object($cad)
        ? ($cad->documents_json ?? $cad->a2_documents_json ?? $cad->docs_json ?? null)
        : ($cad['documents_json'] ?? $cad['a2_documents_json'] ?? $cad['docs_json'] ?? null);

    $docsArr = [];
    if (is_string($docsRaw)) {
        $tmp = json_decode($docsRaw, true);
        if (is_array($tmp)) $docsArr = $tmp;
    } elseif (is_array($docsRaw)) {
        $docsArr = $docsRaw;
    }

    // Normaliza para forma: [ ['name'=>..., 'path'=>...], ... ]
    $initialDocs = [];
    if ($docsArr) {
        $isList = array_is_list($docsArr);
        if ($isList) {
            foreach ($docsArr as $item) {
                if (!is_array($item)) continue;
                $path = (string)($item['path'] ?? $item['url'] ?? $item['file'] ?? '');
                if ($path === '') continue;
                $name = (string)($item['name'] ?? $item['key'] ?? basename($path));
                $initialDocs[] = ['name' => $name, 'path' => $path];
            }
        } else {
            // associativo: chave => caminho
            foreach ($docsArr as $k => $v) {
                $path = is_string($v) ? $v : (string)($v['path'] ?? $v['url'] ?? $v['file'] ?? '');
                if ($path === '') continue;
                $name = is_string($k) ? $k : (string)($v['name'] ?? basename($path));
                $initialDocs[] = ['name' => $name, 'path' => $path];
            }
        }
    }

    // Monta linhas dos documentos iniciais
    if (!empty($initialDocs)) {
        $routeName = 'analista.a2doc.open';
        $hasRoute  = Route::has($routeName);

        foreach (array_values($initialDocs) as $i => $doc) {
            $name = (string)($doc['name'] ?? 'documento');
            $path = (string)($doc['path'] ?? '');

            // Deriva uma URL "visual" (relative_path) semelhante ao pushNormalizedFile
            $url   = '';
            $mime  = 'application/octet-stream';
            $sizeB = null;
            $stored= null;

            if ($path !== '' && preg_match('~^https?://~i', $path)) {
                $url    = $path;
                $stored = basename(parse_url($path, PHP_URL_PATH) ?? 'arquivo');
                $mime   = $this->guessMimeFromExt($stored);
            } else {
                $rel = $this->normalizeAppPath($path);
                $relNoSlash = ltrim($rel, '/');
                $stored = basename($relNoSlash) ?: 'arquivo';

                // tenta disk('public') primeiro
                $disk = Storage::disk('public');
                if ($relNoSlash !== '' && $disk->exists($relNoSlash)) {
                    $url   = $disk->url($relNoSlash);
                    $mime  = $disk->mimeType($relNoSlash) ?: $this->guessMimeFromExt($relNoSlash);
                    $sizeB = (int)$disk->size($relNoSlash);
                } else {
                    // fallback: /public/uploads ou /storage
                    if ($relNoSlash !== '' && preg_match('~^(?:public/)?uploads/~i', $relNoSlash)) {
                        $publicRel = ltrim(preg_replace('~^public/~i', '', $relNoSlash), '/'); // "uploads/.."
                        $abs = public_path($publicRel);
                        if (is_file($abs)) {
                            $sizeB = (int)@filesize($abs);
                            $m = @mime_content_type($abs);
                            $mime = $m ?: $this->guessMimeFromExt($publicRel);
                        } else {
                            $mime = $this->guessMimeFromExt($publicRel);
                        }
                        $url = asset($publicRel);
                    } else {
                        $url  = $relNoSlash !== '' ? asset('storage/'.$relNoSlash) : '';
                        $mime = $this->guessMimeFromExt($relNoSlash ?: $stored);
                    }
                }
            }

            // Abre via ROTA (com log) se disponível
            $open = $url;
            if ($hasRoute && $cadId !== null) {
                try { $open = route($routeName, [$cadId, $i]); } catch (\Throwable $e) { /* mantém $open=$url */ }
            }

            $out[] = [
                'original_name' => $name ?: ($stored ?: 'arquivo'),
                'stored_name'   => $stored,
                'mime'          => $mime,
                'size_bytes'    => $sizeB,
                'open_url'      => $open,   // abre pelo controller (loga)
                'relative_path' => $url,    // url direto (fallback / inspeção)
                'uploaded_at'   => null,    // desconhecido para docs iniciais
                'is_reupload'   => false,   // importante para a view
            ];
        }
    }

    // ==== 2) REUPLOADS DO APP (TABELA DINÂMICA) ====
    $reups = AppReupload::query()
        ->forCadastro($cadId)
        ->orderByDesc('id')
        ->get();

    // Mapeia colunas dinâmicas só uma vez
    $pathCol     = AppReupload::pathColumn();
    $origCol     = AppReupload::firstExistingColumn(['original_name','filename','name']);
    $mimeCol     = AppReupload::firstExistingColumn(['mime','mimetype','content_type']);
    $sizeCol     = AppReupload::firstExistingColumn(['size','filesize','bytes']);
    $statusCol   = AppReupload::firstExistingColumn(['status','situacao']);
    $uploadedCol = AppReupload::firstExistingColumn(['uploaded_at','created_at','data_envio']);

    $streamRoute = 'analista.reuploads.a2.ver'; // rota de stream com log

    foreach ($reups as $r) {
        $this->pushNormalizedFile(
            $out,
            (string)($r->{$pathCol} ?? ''),
            (string)($origCol ? ($r->{$origCol} ?? '') : ''),
            $mimeCol ? ($r->{$mimeCol} ?? null) : null,
            $sizeCol ? ($r->{$sizeCol} ?? null) : null,
            $uploadedCol ? ($r->{$uploadedCol} ?? null) : null,
            $statusCol ? ($r->{$statusCol} ?? null) : null,
            (int)$r->id,
            $streamRoute
        );
    }

    return $out;
}




    /**
     * Normaliza REUPLOADS do WEB (tabela agente_doc_reuploads).
     * Também aceita bundle em extras.files.
     */
private function normalizeWebReuploads(int $cadastroId): array
{
    $list = \App\Models\AgenteDocReupload::query()
        ->where('agente_cadastro_id', $cadastroId)
        ->orderByDesc('id')
        ->get();

    $out = [];
    foreach ($list as $r) {
        $path = (string)(
              $r->file_relative_path
           ?? $r->path
           ?? $r->file_path
           ?? $r->filepath
           ?? $r->stored_path
           ?? $r->url
           ?? $r->file
           ?? ''
        );
        $orig = (string)(
              $r->file_original_name
           ?? $r->original_name
           ?? $r->filename
           ?? $r->name
           ?? 'arquivo'
        );
        $mime = $r->mime ?? $r->mimetype ?? $r->content_type ?? null;
        $size = isset($r->file_size_bytes) ? (int)$r->file_size_bytes
              : (isset($r->size) ? (int)$r->size : null);
        $upAt = $r->uploaded_at ?? $r->created_at;

        $this->pushNormalizedFile(
            $out,
            $path,
            $orig,
            $mime,
            $size,
            $upAt,
            $r->status ?? null,
            (int)$r->id,
            'analista.reuploads.ver' // rota WEB
        );
    }
    return $out;
}


// === EXATAMENTE COMO VOCÊ PEDIU ===
private function pushNormalizedFile(
    array &$out,
    string $path,
    string $originalName,
    ?string $mimeHint,
    ?int $sizeHint,
    $uploadedAtRaw,
    ?string $status = null,
    ?int $reuploadId = null,                // NOVO
    ?string $streamRouteName = null         // NOVO: ex. 'analista.reuploads.a2.ver' ou 'analista.reuploads.ver'
): void {
    $url   = '';                            // <- garante que SEMPRE existe
    $mime  = $mimeHint ?: 'application/octet-stream';
    $sizeB = $sizeHint ?: null;
    $stored= null;

    // uploaded_at formatado
    $uploadedBr = null;
    if (!empty($uploadedAtRaw)) {
        try { $uploadedBr = \Carbon\Carbon::parse($uploadedAtRaw)->format('d/m/Y H:i'); } catch (\Throwable $e) {}
    }

    if (preg_match('~^https?://~i', $path)) {
        $url    = $path;
        $stored = basename(parse_url($path, PHP_URL_PATH) ?? 'arquivo');
        if (!$mimeHint) $mime = $this->guessMimeFromExt($stored);

    } else {
        $rel = $this->normalizeAppPath($path);
        $relNoSlash = ltrim($rel, '/');
        $stored = $stored ?: basename($relNoSlash ?: 'arquivo');

        // 1) arquivos em public/uploads/...
        if ($relNoSlash !== '' && preg_match('~^(?:public/)?uploads/~i', $relNoSlash)) {
            $publicRel = ltrim(preg_replace('~^public/~i', '', $relNoSlash), '/'); // "uploads/..."
            $abs = public_path($publicRel);

            if (is_file($abs)) {
                $sizeB = $sizeB ?: (int) @filesize($abs);
                $m = @mime_content_type($abs);
                if ($m) $mime = $m; else if (!$mimeHint) $mime = $this->guessMimeFromExt($publicRel);
            } else {
                if (!$mimeHint) $mime = $this->guessMimeFromExt($publicRel);
            }

            $url = asset($publicRel); // https://site.com/uploads/...

        } else {
            // 2) disk('public') => /storage/{rel}
            $disk = \Storage::disk('public');

            if ($relNoSlash !== '' && $disk->exists($relNoSlash)) {
                $url   = $disk->url($relNoSlash);
                $mime  = $disk->mimeType($relNoSlash) ?: ($mimeHint ?: $this->guessMimeFromExt($relNoSlash));
                $sizeB = $sizeB ?: (int) $disk->size($relNoSlash);
            } else {
                // 3) fallback visual
                $url   = $relNoSlash !== '' ? asset('storage/'.$relNoSlash) : '';
                $mime  = $mimeHint ?: ($relNoSlash !== '' ? $this->guessMimeFromExt($relNoSlash) : 'application/octet-stream');
            }
        }
    }

    // Preferir abrir por ROTA (com LOG) quando possível
    $open = $url;
    if ($reuploadId && $streamRouteName && \Illuminate\Support\Facades\Route::has($streamRouteName)) {
        try { $open = route($streamRouteName, $reuploadId); } catch (\Throwable $e) { /* fallback $open=$url */ }
    }

    $row = [
        'original_name'   => $originalName ?: ($stored ?: 'arquivo'),
        'stored_name'     => $stored,
        'mime'            => $mime,
        'size_bytes'      => $sizeB,
        'open_url'        => $open,   // botão "Abrir" usa ROTA quando disponível
        'relative_path'   => $url,    // URL direto (fallback / inspeção)
        'uploaded_at'     => $uploadedBr,
        'is_reupload'     => true,
    ];
    if ($status !== null) $row['reupload_status'] = $status;

    $out[] = $row;
}



    private function calcMesAverbacaoFromApproval(Carbon $aprovacao): Carbon
    {
        // cutoff do próprio mês da aprovação (considera FECHAMENTO_OVERRIDES)
        $cutoff = $this->fechamentoDiaForMonth($aprovacao->copy()->startOfMonth());

        // 06+ => próximo mês
        if ($aprovacao->day >= ($cutoff + 1)) {
            $aprovacao = $aprovacao->copy()->addMonthNoOverflow();
        }

        return $aprovacao->copy()->startOfMonth();
    }

    // =========================
    // ====== REGRAS 06→05 =====
    // =========================

    /** Regra de competência 06→05 (05 ainda pertence ao mês; 06 já é do próximo) */
    private function competenciaWindow(?string $mesParam): array
    {
        $tz = $this->tz();
        $agora = Carbon::now($tz);

        if (!$mesParam || !preg_match('~^\d{4}-\d{2}$~', $mesParam)) {
            $base = $agora->copy();
            if ($base->day <= 5) $base->subMonthNoOverflow();
            $y = (int)$base->format('Y');
            $m = (int)$base->format('m');
        } else {
            [$y, $m] = array_map('intval', explode('-', $mesParam));
        }

        // Início: 06/mes 00:00 — Fim exclusivo: 06/(mes+1) 00:00
        $inicio = Carbon::create($y, $m, 6, 0, 0, 0, $tz)->startOfDay();
        $fim    = $inicio->copy()->addMonthNoOverflow();

        return [$inicio, $fim];
    }

    /** Mesma fórmula do Agente (base de cálculo da margem) */
    private function calcularMargem(?float $valorBruto, ?float $liqCc, ?float $mensalidade, int $prazo = 3): array
    {
        $vb   = (float) ($valorBruto ?? 0);
        $liq  = (float) ($liqCc ?? 0);
        $mens = (float) ($mensalidade ?? 0);
        $pz   = max($prazo, 0);

        $trintaBruto      = round($vb * 0.30, 2);
        $margem           = round($liq - $trintaBruto, 2);
        $valorAntecipacao = round($mens * $pz, 2);
        $doacaoFundo      = round($valorAntecipacao * 0.30, 2);

        return compact('trintaBruto','margem','valorAntecipacao','doacaoFundo') + [
            'pode_prosseguir' => ($margem > 0),
        ];
    }

    /** Competência p/ bloco de margem (lista/cálculo) */
    public function margemCompetencia(Request $r)
    {
        [$inicio, $fim] = $this->competenciaWindow($r->query('mes')); // "YYYY-MM" opcional

        // Buscamos os cadastros criados dentro da janela 06..05
        $cadastros = AgenteCadastro::query()
            ->select([
                'id','full_name','cpf_cnpj',
                'calc_valor_bruto','calc_liquido_cc',
                'contrato_mensalidade','contrato_prazo_meses',
                'created_at',
            ])
            ->where('created_at', '>=', $inicio)
            ->where('created_at', '<',  $fim)
            ->orderByDesc('id')
            ->get();

        // Enriquecemos cada linha com os derivados de margem (prazo: 3 meses)
        $prazoFixo = 3;
        $enriquecidos = $cadastros->map(function ($c) use ($prazoFixo) {
            $calc = $this->calcularMargem(
                $c->calc_valor_bruto,
                $c->calc_liquido_cc,
                $c->contrato_mensalidade,
                $prazoFixo
            );
            return (object) array_merge($c->toArray(), [
                'calc_trinta_bruto'       => $calc['trintaBruto'],
                'calc_margem'             => $calc['margem'],
                'calc_valor_antecipacao'  => $calc['valorAntecipacao'],
                'calc_doacao_fundo'       => $calc['doacaoFundo'],
                'calc_pode_prosseguir'    => $calc['pode_prosseguir'],
                'prazo_utilizado'         => $prazoFixo,
            ]);
        });

        // Totais do bloco
        $totais = [
            'qtde'                 => $enriquecidos->count(),
            'soma_valor_bruto'     => round($enriquecidos->sum('calc_valor_bruto'), 2),
            'soma_liquido_cc'      => round($enriquecidos->sum('calc_liquido_cc'), 2),
            'soma_mensalidade'     => round($enriquecidos->sum('contrato_mensalidade'), 2),
            'soma_trinta_bruto'    => round($enriquecidos->sum('calc_trinta_bruto'), 2),
            'soma_margem'          => round($enriquecidos->sum('calc_margem'), 2),
            'soma_antecipacao'     => round($enriquecidos->sum('calc_valor_antecipacao'), 2),
            'soma_doacao_fundo'    => round($enriquecidos->sum('calc_doacao_fundo'), 2),
        ];

        // Informações da competência para o cabeçalho do bloco
        $competencia = [
            'mes'        => $inicio->format('Y-m'),
            'intervalo'  => $inicio->format('d/m/Y') . ' 00:00 — ' . $fim->copy()->subSecond()->format('d/m/Y') . ' 23:59',
            'inicio_iso' => $inicio->toDateTimeString(),
            'fim_iso'    => $fim->toDateTimeString(),
            'cutoff'     => 5, // clareza na view
        ];

        // Se quiser consumir por AJAX, devolvemos JSON quando ?format=json
        if ($r->query('format') === 'json') {
            return response()->json([
                'competencia' => $competencia,
                'totais'      => $totais,
                'linhas'      => $enriquecidos,
            ]);
        }

        // Render normal (caso acesse sem ?format=json)
        return view('analista.dashboard', [
            'competencia_margem' => $competencia,
            'totais_margem'      => $totais,
            'linhas_margem'      => $enriquecidos,
        ]);
    }

    // === Helpers de parsing
    private function toMoney($s): ?float
    {
        if ($s === null || $s === '') return null;
        $s = str_replace(['R$', ' ', '.'], '', (string) $s);
        $s = str_replace(',', '.', $s);
        return (float) $s;
    }
    private function toPercent($s): ?float
    {
        if ($s === null || $s === '') return null;
        $s = str_replace(['%', ' '], '', (string) $s);
        $s = str_replace(',', '.', $s);
        return (float) $s;
    }
    private function toDate($s): ?string
    {
        if (!$s) return null;
        try {
            return \Carbon\Carbon::parse($s, $this->tz())->toDateString();
        } catch (\Throwable $e) {
            return null;
        }
    }
    private function toDateOrNull($v): ?\Carbon\Carbon {
        if (!$v) return null;
        try { return \Carbon\Carbon::parse($v, $this->tz()); } catch (\Throwable $e) { return null; }
    }
    /** Interpreta "AAAA-MM" como o dia 1 do mês; demais formatos caem no parse normal. */
    private function toMonthDateOrNull($v): ?\Carbon\Carbon {
        $s = trim((string)$v);
        if ($s === '') return null;
        if (preg_match('~^\d{4}-\d{2}$~', $s)) {
            [$y,$m] = array_map('intval', explode('-', $s));
            return \Carbon\Carbon::create($y, $m, 1, 0, 0, 0, $this->tz())->startOfDay();
        }
        return $this->toDateOrNull($s);
    }

    // =========================
    // ====== AUTO-PREENCH. ====
    // =========================

    /** Timezone padrão do projeto */
    private function tz(): string
    {
        return config('app.timezone') ?: (env('APP_TIMEZONE') ?: 'America/Sao_Paulo');
    }

    /** Lê overrides do env: FECHAMENTO_OVERRIDES="2026-01:7,2026-02:6" */
    private function fechamentoOverrideMap(): array
    {
        $raw = (string) env('FECHAMENTO_OVERRIDES', '');
        if (trim($raw) === '') return [];
        $map = [];
        foreach (explode(',', $raw) as $pair) {
            $pair = trim($pair);
            if ($pair === '' || strpos($pair, ':') === false) continue;
            [$ym, $d] = array_map('trim', explode(':', $pair, 2));
            if (preg_match('~^\d{4}-\d{2}$~', $ym) && ctype_digit($d) && (int)$d >= 1 && (int)$d <= 31) {
                $map[$ym] = (int)$d;
            }
        }
        return $map;
    }

    /** Retorna o dia de fechamento para um determinado mês (com override se existir) */
    private function fechamentoDiaForMonth(Carbon $monthDate): int
    {
        $def = (int) env('FECHAMENTO_DIA', 5);
        $ym  = $monthDate->format('Y-m');
        $map = $this->fechamentoOverrideMap();
        return (int) ($map[$ym] ?? $def);
    }

    /** Empurra sáb./dom. para segunda-feira */
    private function pushToMondayIfWeekend(Carbon $d): Carbon
    {
        $d = $d->copy();
        while ($d->isSaturday() || $d->isSunday()) {
            $d->addDay();
        }
        return $d;
    }

    /** Dado um "hoje", calcula mês de averbação conforme 06→05 */
    private function calcMesAverbacaoFromDate(Carbon $today): Carbon
    {
        $base = $today->copy();
        if ($base->day <= 5) $base->subMonthNoOverflow();
        return $base->copy()->startOfMonth();
    }

    /** A partir do mês de averbação, calcula a data da 1ª mensalidade (fechamento do mês seguinte, com empurrão) */
    private function calcPrimeiraMensalidadeFromMesAverbacao(Carbon $mesAverbacao): Carbon
    {
        $tz  = $this->tz();
        $mesSeguinte = $mesAverbacao->copy()->addMonthNoOverflow()->startOfMonth();
        $fechDia     = $this->fechamentoDiaForMonth($mesSeguinte);
        $first       = Carbon::create($mesSeguinte->year, $mesSeguinte->month, $fechDia, 0, 0, 0, $tz)->startOfDay();

        return $this->pushToMondayIfWeekend($first);
    }

    /** Monta N (até 3) antecipações a partir da primeira, só com vencimentos e R$ 0,00, status Pendente */
    private function montarAntecipacoesPadrao(Carbon $primeira, int $prazoMeses = 3): array
    {
        $prazoMeses = max(1, min(3, (int)$prazoMeses));
        $out = [];
        for ($i = 0; $i < $prazoMeses; $i++) {
            $mesRef  = $primeira->copy()->addMonthsNoOverflow($i);
            $fechDia = $this->fechamentoDiaForMonth($mesRef->copy()->startOfMonth());
            $data    = Carbon::create($mesRef->year, $mesRef->month, $fechDia, 0, 0, 0, $this->tz())->startOfDay();
            $data    = $this->pushToMondayIfWeekend($data);

            $out[] = [
                'numeroMensalidade' => $i + 1,
                'valorAuxilio'      => 0.00, // como no Agente (R$ 0,00 por linha)
                'dataEnvio'         => $data->toDateString(),
                'status'            => 'Pendente',
                'observacao'        => null,
            ];
        }
        return $out;
    }

    /**
     * Salvar cálculo/detalhes do contrato (ABA do cálculo no modal).
     * Rota: POST /analista/contrato/{id}/salvar-margem  (name: analista.contrato.salvar_margem)
     * >>> Apenas colunas existentes são atualizadas <<<
     * >>> Agora com preenchimentos padrões (espelha o Agente) quando campos não vierem <<<
     */
    public function salvarMargem(Request $r, int $id)
    {
        $cad = \App\Models\AssociadoDoisCadastro::findOrFail($id);
        $tz  = $this->tz();
        $agora = \Carbon\Carbon::now($tz);

        // ----- Inputs -----
        $calc_valor_bruto        = $this->toMoney($r->input('calc_valor_bruto'));
        $calc_liquido_cc         = $this->toMoney($r->input('calc_liquido_cc'));
        $calc_prazo_antecipacao  = (int) $r->input('calc_prazo_antecipacao', 3);

        $contrato_mensalidade        = $this->toMoney($r->input('contrato_mensalidade'));
        $contrato_taxa_antecipacao   = $this->toPercent($r->input('contrato_taxa_antecipacao'));
        $contrato_margem_disponivel  = $this->toMoney($r->input('contrato_margem_disponivel'));
        $contrato_valor_antecipacao  = $this->toMoney($r->input('contrato_valor_antecipacao'));
        $contrato_doacao_associado   = $this->toMoney($r->input('contrato_doacao_associado'));

        $contrato_data_aprovacao     = $this->toDateOrNull($r->input('contrato_data_aprovacao'));
        $contrato_data_primeira      = $this->toDateOrNull($r->input('contrato_data_envio_primeira'));
        $contrato_status_contrato    = (string) $r->input('contrato_status_contrato', 'Pendente');
        $contrato_mes_averbacao_raw  = trim((string) $r->input('contrato_mes_averbacao', ''));
        $contrato_mes_averbacao      = $this->toMonthDateOrNull($contrato_mes_averbacao_raw);

        // Antecipações (até 3)
        $antsIn  = (array) $r->input('ants', []);
        $antsOut = [];
        foreach ($antsIn as $row) {
            $num  = (int) ($row['numeroMensalidade'] ?? 0);
            $val  = $this->toMoney($row['valorAuxilio'] ?? null);
            $venc = $this->toDateOrNull($row['dataEnvio'] ?? null);
            $st   = trim((string) ($row['status'] ?? 'Pendente'));
            $obs  = trim((string) ($row['observacao'] ?? ''));
            if ($num || $val || $venc || $obs || $st) {
                $antsOut[] = [
                    'numeroMensalidade' => $num ?: null,
                    'valorAuxilio'      => $val ?: null,
                    'dataEnvio'         => $venc ? $venc->toDateString() : null,
                    'status'            => $st ?: null,
                    'observacao'        => $obs ?: null,
                ];
            }
        }

        // ----- Fallbacks (espelham o Agente) -----
        if (!$contrato_data_aprovacao) {
            $contrato_data_aprovacao = $agora->copy();
        }
        if (!$contrato_mes_averbacao) {
            $contrato_mes_averbacao = $this->calcMesAverbacaoFromApproval($contrato_data_aprovacao->copy());
        } else {
            $contrato_mes_averbacao = $contrato_mes_averbacao->copy()->startOfMonth();
        }
        if (!$contrato_data_primeira) {
            $contrato_data_primeira = $this->calcPrimeiraMensalidadeFromMesAverbacao($contrato_mes_averbacao->copy());
        }
        if (empty($antsOut)) {
            $antsOut = $this->montarAntecipacoesPadrao($contrato_data_primeira->copy(), max(1, min(3, $calc_prazo_antecipacao ?: 3)));
        }
        if ($contrato_taxa_antecipacao <= 0) {
            $contrato_taxa_antecipacao = 30.00;
        }

        $calc = $this->calcularMargem(
            $calc_valor_bruto,
            $calc_liquido_cc,
            $contrato_mensalidade,
            max($calc_prazo_antecipacao, 1)
        );
        if ($contrato_valor_antecipacao < 1)   $contrato_valor_antecipacao = $calc['valorAntecipacao'];
        if ($contrato_margem_disponivel === 0) $contrato_margem_disponivel = $calc['margem'];
        if ($contrato_doacao_associado  === 0) $contrato_doacao_associado  = $calc['doacaoFundo'];

        // ----- Persistência -----
        // Simulador
        $cad->calc_valor_bruto           = $calc_valor_bruto;
        $cad->calc_liquido_cc            = $calc_liquido_cc;
        $cad->calc_prazo_antecipacao     = $calc_prazo_antecipacao;

        // Detalhes do contrato
        $cad->contrato_mensalidade       = $contrato_mensalidade;
        $cad->contrato_prazo_meses       = $calc_prazo_antecipacao;
        $cad->contrato_taxa_antecipacao  = $contrato_taxa_antecipacao;
        $cad->contrato_margem_disponivel = $contrato_margem_disponivel;
        $cad->contrato_data_aprovacao    = $contrato_data_aprovacao?->toDateString();
        $cad->contrato_data_envio_primeira = $contrato_data_primeira?->toDateString();
        $cad->contrato_valor_antecipacao = $contrato_valor_antecipacao;
        $cad->contrato_status_contrato   = $contrato_status_contrato;
        $cad->contrato_mes_averbacao     = $contrato_mes_averbacao?->toDateString();
        $cad->contrato_doacao_associado  = $contrato_doacao_associado;

        // <<< ADIÇÕES ESPECÍFICAS QUE VOCÊ PEDIU >>>
        // 1) Espelhar calc_mensalidade_associativa, se a coluna existir
        if (\Schema::hasColumn($cad->getTable(), 'calc_mensalidade_associativa')) {
            $cad->calc_mensalidade_associativa = $contrato_mensalidade;
        }
        // 2) Preencher agente_responsavel = "Aplicativo" se estiver vazio (e a coluna existir)
        if (\Schema::hasColumn($cad->getTable(), 'agente_responsavel')) {
            $atual = trim((string) ($cad->agente_responsavel ?? ''));
            if ($atual === '') {
                $cad->agente_responsavel = 'Aplicativo';
            }
        }
        // 3) Preencher agente_filial = "Aplicativo" se estiver vazio (e a coluna existir)
        if (\Schema::hasColumn($cad->getTable(), 'agente_filial')) {
            $atualF = trim((string) ($cad->agente_filial ?? ''));
            if ($atualF === '') {
                $cad->agente_filial = 'Aplicativo';
            }
        }
        // <<< FIM DAS ADIÇÕES >>>

        // JSON de antecipações
        $cad->anticipations_json = !empty($antsOut)
            ? json_encode($antsOut, JSON_UNESCAPED_UNICODE)
            : null;

        $cad->save();

        return back()->with('ok', 'Cálculo e detalhes do contrato atualizados com sucesso.');
    }

    /**
     * Verifica pré-condições para liberar auxílio e, se falhar, devolve o motivo.
     */
    private function podeLiberarAuxilio(\App\Models\AssociadoDoisCadastro $cad, int $qual, ?string &$motivo = null): bool
    {
        $mensalidade = (float) ($cad->contrato_mensalidade ?? 0);
        $totalAnt    = (float) ($cad->contrato_valor_antecipacao ?? 0);
        $margem      = (float) ($cad->contrato_margem_disponivel ?? 0);

        if ($qual !== 1 && $qual !== 2) {
            $motivo = 'Parâmetro inválido: apenas 1 ou 2.'; return false;
        }
        if ($mensalidade <= 0) {
            $motivo = 'Mensalidade associativa precisa estar preenchida.'; return false;
        }
        if ($totalAnt <= 0) {
            $motivo = 'Valor total da antecipação precisa estar definido.'; return false;
        }
        if ($margem <= 0) {
            $motivo = 'Margem disponível deve ser maior que zero.'; return false;
        }
        return true;
    }

    /**
     * LIBERAR Auxílio Emergencial 1 ou 2 (APP)
     * Ex.: POST /analista/contrato/{id}/liberar-auxilio/1  ou /2
     */
    public function liberarAuxilio(Request $r, int $id, string $qual)
    {
        $now   = \Carbon\Carbon::now($this->tz());
        $qualN = (int) $qual;

        return \DB::transaction(function () use ($r, $id, $qualN, $now) {
            /** @var \App\Models\AssociadoDoisCadastro $cad */
            $cad = \App\Models\AssociadoDoisCadastro::query()
                ->where('id', $id)
                ->lockForUpdate()
                ->firstOrFail();

            // 1) Se o POST veio do mesmo form, persiste o cálculo antes de validar
            $this->persistirCalculoSeEnviado($r, $cad);

            // 2) Pré-condições (agora com dados atualizados)
            $motivo = null;
            if (!$this->podeLiberarAuxilio($cad, $qualN, $motivo)) {
                return back()->withErrors([
                    'liberar' => $motivo ?: 'Pré-condições não atendidas. Verifique Mensalidade / Valor total / Disponível.'
                ]);
            }

            // 3) Antecipações: usa as linhas do POST (se vieram), senão mantém/gera as atuais
            $ants = $this->mergeAntecipacoesPost($r, $cad, $now);

            // Garantir existência de pelo menos 2 linhas (auxílio 1 e 2)
            for ($i = 0; $i < 2; $i++) {
                if (!isset($ants[$i]) || !is_array($ants[$i])) {
                    $ants[$i] = [
                        'numeroMensalidade' => $i + 1,
                        'valorAuxilio'      => 0.00,
                        'dataEnvio'         => $now->toDateString(),
                        'status'            => 'Pendente',
                        'observacao'        => null,
                    ];
                } else {
                    if (empty($ants[$i]['numeroMensalidade'])) $ants[$i]['numeroMensalidade'] = $i + 1;
                    if (empty($ants[$i]['dataEnvio']))         $ants[$i]['dataEnvio']         = $now->toDateString();
                    if (!array_key_exists('observacao', $ants[$i])) $ants[$i]['observacao'] = null;
                }
            }

            // Índices: 1->0, 2->1
            $selIdx   = ($qualN === 2) ? 1 : 0;
            $otherIdx = $selIdx === 0 ? 1 : 0;

            // 4) Atualiza a linha selecionada: AUTORIZADO
            $obsSel = trim((string) ($ants[$selIdx]['observacao'] ?? ''));
            $tagSel = '[Autorizado pelo analista em ' . $now->format('d/m/Y H:i') . ']';
            $ants[$selIdx]['status']     = 'Autorizado';
            $ants[$selIdx]['observacao'] = $obsSel ? ($obsSel . ' ' . $tagSel) : $tagSel;

            // 5) Atualiza a outra linha: BLOQUEADO (regra de exclusividade)
            $obsOther = trim((string) ($ants[$otherIdx]['observacao'] ?? ''));
            $tagOther = '[Bloqueado pelo analista em ' . $now->format('d/m/Y H:i') . ']';
            $ants[$otherIdx]['status']     = 'Bloqueado';
            $ants[$otherIdx]['observacao'] = $obsOther ? ($obsOther . ' ' . $tagOther) : $tagOther;

            // 6) Flags do cadastro (sempre força exclusividade)
            if ($selIdx === 0) {
                $cad->auxilio1_status     = 'liberado';
                $cad->auxilio1_updated_at = $now;
                $cad->auxilio2_status     = 'bloqueado';
                $cad->auxilio2_updated_at = $now;
            } else {
                $cad->auxilio2_status     = 'liberado';
                $cad->auxilio2_updated_at = $now;
                $cad->auxilio1_status     = 'bloqueado';
                $cad->auxilio1_updated_at = $now;
            }

            // 7) Persiste tudo
            $cad->anticipations_json = json_encode($ants, JSON_UNESCAPED_UNICODE);
            $cad->save();

            \Log::info('Analista liberou auxílio com bloqueio do outro', [
                'cadastro_id' => $cad->id,
                'liberado'    => $selIdx + 1,
                'bloqueado'   => $otherIdx + 1,
                'user_id'     => optional(auth()->user())->id,
            ]);

            return back()->with('ok', "Auxílio emergencial " . ($selIdx + 1) . " liberado e o outro foi bloqueado.");
        });
    }

public function validateDocsA2(Request $r, int $id)
{
    \DB::beginTransaction();

    try {
        /** @var \App\Models\AssociadoDoisCadastro $cad */
        $cad = \App\Models\AssociadoDoisCadastro::query()
            ->where('id', $id)->lockForUpdate()->firstOrFail();

        // ======== REGRA NOVA: só valida com aceite_termos = 1 ========
        $aceiteTermos = (int)($cad->aceite_termos ?? 0) === 1;
        if (!$aceiteTermos) {
            \DB::rollBack();
            return back()->withErrors([
                'validar' => 'Só é possível validar após o ACEITE DOS TERMOS pelo associado no aplicativo.'
            ]);
        }
        // =============================================================

        // 1) Fechar pendências / aceitar reenvios
        \DB::table('associadodois_doc_issues')
            ->where('associadodois_cadastro_id', $cad->id)
            ->whereIn('status', ['open','waiting_user','received','rejected'])
            ->update(['status' => 'accepted', 'updated_at' => now()]);

        \DB::table('associadodois_doc_reuploads')
            ->where('associadodois_cadastro_id', $cad->id)
            ->where('status', 'received')
            ->update(['status' => 'accepted', 'updated_at' => now()]);

        $hasOpenIssue   = \DB::table('associadodois_doc_issues')
            ->where('associadodois_cadastro_id', $cad->id)
            ->whereIn('status', ['open','waiting_user','received','rejected'])
            ->exists();

        $docsArr        = is_array($cad->documents_json)
            ? $cad->documents_json
            : (json_decode($cad->documents_json ?? '[]', true) ?: []);
        $hasDocsInitial = !empty($docsArr);
        $hasAnyReupload = \DB::table('associadodois_doc_reuploads')
            ->where('associadodois_cadastro_id', $cad->id)->exists();

        // 2) Tesouraria
        if (!$hasOpenIssue && ($hasDocsInitial || $hasAnyReupload)) {
            $mens        = (float) ($cad->contrato_mensalidade ?? 0);
            $prazo       = (int)   ($cad->contrato_prazo_meses ?? 3);
            $valorAntecip= (float) ($cad->contrato_valor_antecipacao ?? round($mens * ($prazo > 0 ? $prazo : 3), 2));

            // checagem de nulabilidade de agente_cadastro_id
            $colInfo = \DB::selectOne("
                SELECT IS_NULLABLE
                  FROM INFORMATION_SCHEMA.COLUMNS
                 WHERE TABLE_SCHEMA = DATABASE()
                   AND TABLE_NAME  = 'tesouraria_pagamentos'
                   AND COLUMN_NAME = 'agente_cadastro_id'
            ");
            $isAgenteIdNullable = $colInfo && strtoupper((string)$colInfo->IS_NULLABLE) === 'YES';

            // mapeia possível agente vindo do APP
            $possibleAgenteId = null;
            if (\Illuminate\Support\Facades\Schema::hasColumn('associadodois_cadastros','agente_cadastro_id') && !empty($cad->agente_cadastro_id)) {
                $possibleAgenteId = (int) $cad->agente_cadastro_id;
            } elseif (\Illuminate\Support\Facades\Schema::hasColumn('associadodois_cadastros','agente_id') && !empty($cad->agente_id)) {
                $possibleAgenteId = (int) $cad->agente_id;
            }

            // se NOT NULL e sem mapeamento, cria/usa "Aplicativo (Default)"
            $mustProvideAgenteId = (\Illuminate\Support\Facades\Schema::hasColumn('tesouraria_pagamentos','agente_cadastro_id') && !$isAgenteIdNullable);
            if ($mustProvideAgenteId && $possibleAgenteId === null) {
                $agTable = 'agente_cadastros';

                $bySlug = \Illuminate\Support\Facades\Schema::hasColumn($agTable,'slug');
                $byNome = \Illuminate\Support\Facades\Schema::hasColumn($agTable,'nome');

                if ($bySlug) {
                    $possibleAgenteId = (int) \DB::table($agTable)->where('slug','app-default')->value('id');
                }
                if (!$possibleAgenteId && $byNome) {
                    $possibleAgenteId = (int) \DB::table($agTable)->where('nome','Aplicativo (Default)')->value('id');
                }

                if (!$possibleAgenteId) {
                    $insert = [];
                    if ($bySlug) $insert['slug'] = 'app-default';
                    if ($byNome) $insert['nome'] = 'Aplicativo (Default)';
                    if (\Illuminate\Support\Facades\Schema::hasColumn($agTable,'doc_type')) $insert['doc_type'] = 'app';
                    if (\Illuminate\Support\Facades\Schema::hasColumn($agTable,'ativo'))    $insert['ativo']    = 1;

                    $requiredCols = \DB::select("
                        SELECT COLUMN_NAME, DATA_TYPE
                          FROM INFORMATION_SCHEMA.COLUMNS
                         WHERE TABLE_SCHEMA = DATABASE()
                           AND TABLE_NAME = ?
                           AND IS_NULLABLE = 'NO'
                           AND COLUMN_KEY <> 'PRI'
                           AND EXTRA NOT LIKE '%auto_increment%'
                           AND COLUMN_DEFAULT IS NULL
                    ", [$agTable]);

                    foreach ($requiredCols as $c) {
                        $name = $c->COLUMN_NAME;
                        if (isset($insert[$name])) continue;

                        $type = strtolower($c->DATA_TYPE);
                        if (in_array($type, ['varchar','char','text','mediumtext','longtext','enum','set'])) {
                            $insert[$name] = ($name === 'doc_type') ? 'app'
                                              : (($name === 'status') ? 'ativo'
                                              : (($name === 'email') ? 'app@local' : ''));
                        } elseif (in_array($type, ['int','bigint','tinyint','smallint','mediumint'])) {
                            $insert[$name] = 0;
                        } elseif (in_array($type, ['decimal','numeric','float','double'])) {
                            $insert[$name] = 0;
                        } elseif ($type === 'date') {
                            $insert[$name] = now()->toDateString();
                        } elseif (in_array($type, ['datetime','timestamp'])) {
                            $insert[$name] = now();
                        } else {
                            $insert[$name] = '';
                        }
                    }

                    if (\Illuminate\Support\Facades\Schema::hasColumn($agTable,'created_at')) $insert['created_at'] = now();
                    if (\Illuminate\Support\Facades\Schema::hasColumn($agTable,'updated_at')) $insert['updated_at'] = now();

                    try {
                        $possibleAgenteId = \DB::table($agTable)->insertGetId($insert);
                    } catch (\Throwable $ie) {
                        \DB::commit();
                        return back()->withErrors([
                            'validar' => 'Não foi possível criar o agente padrão do APP. '
                                       . 'Vincule um agente ao cadastro OU torne agente_cadastro_id anulável.'
                        ]);
                    }
                }
            }

            // localizar pagamento existente
            $tpQuery = \App\Models\TesourariaPagamento::query()->lockForUpdate();
            if (\Illuminate\Support\Facades\Schema::hasColumn('tesouraria_pagamentos','associadodois_cadastro_id')) {
                $tpQuery->where('associadodois_cadastro_id', $cad->id);
            } else {
                $tpQuery->where('contrato_codigo_contrato', $cad->contrato_codigo_contrato);
            }
            $tp = $tpQuery->first();

            // payload
            $payloadBase = [
                'contrato_codigo_contrato'   => $cad->contrato_codigo_contrato,
                'contrato_valor_antecipacao' => $valorAntecip,
                'cpf_cnpj'                   => $cad->cpf_cnpj,
                'full_name'                  => $cad->full_name,
                'agente_responsavel'         => 'Aplicativo',
                'status'                     => 'pendente',
                'valor_pago'                 => null,
                'paid_at'                    => null,
                'forma_pagamento'            => null,
                'comprovante_path'           => null,
                'notes'                      => 'Gerado pelo Analista (APP) após validação (termos aceitos).',
            ];
            if (\Illuminate\Support\Facades\Schema::hasColumn('tesouraria_pagamentos','created_by_user_id')) {
                $payloadBase['created_by_user_id'] = optional($r->user())->id;
            }
            if (\Illuminate\Support\Facades\Schema::hasColumn('tesouraria_pagamentos','associadodois_cadastro_id')) {
                $payloadBase['associadodois_cadastro_id'] = $cad->id;
            }
            if (\Illuminate\Support\Facades\Schema::hasColumn('tesouraria_pagamentos','contrato_margem_disponivel')) {
                $payloadBase['contrato_margem_disponivel'] = $cad->contrato_margem_disponivel;
            }
            if (\Illuminate\Support\Facades\Schema::hasColumn('tesouraria_pagamentos','agente_cadastro_id')) {
                if ($possibleAgenteId !== null) {
                    $payloadBase['agente_cadastro_id'] = $possibleAgenteId;
                } elseif ($isAgenteIdNullable) {
                    $payloadBase['agente_cadastro_id'] = null;
                }
            }

            // upsert
            if ($tp) {
                $tp->fill($payloadBase);
                if ($tp->status !== 'pago') $tp->status = 'pendente';
                $tp->updated_at = now();
                $tp->save();
            } else {
                \App\Models\TesourariaPagamento::create($payloadBase);
            }

            \DB::commit();
            return back()->with('ok', 'Documentação validada (APP) e enviada à Tesouraria.');
        }

        \DB::commit();
        return back()->with('ok', 'Documentação validada, porém ainda há pendências ou ausência de documentos — não foi enviada à Tesouraria.');

    } catch (\Throwable $e) {
        \DB::rollBack();
        \Log::error('Analista@validateDocsA2 falhou', ['cadastro_id'=>$id,'err'=>$e->getMessage()]);
        return back()->withErrors(['validar' => 'Falha ao validar (APP). '.$e->getMessage()]);
    }
}


    /** Marcar documentação como incompleta — APP (AssociadoDois) */
    public function markIncompleteA2(Request $r, int $id)
    {
        // validação: mantemos "mensagem" como no seu front
        $r->validate([
            'mensagem'       => 'required|string|min:5|max:5000',
            'title'          => 'nullable|string|max:160',
            'required_docs'  => 'nullable', // pode vir array, json ou string
        ]);

        /** @var \App\Models\AssociadoDoisCadastro $cad */
        $cad = \App\Models\AssociadoDoisCadastro::findOrFail($id);

        // Normalizações
        $msg       = trim((string) $r->input('mensagem'));
        $title     = trim((string) ($r->input('title') ?? 'Documentação pendente'));
        $cpfCnpj   = preg_replace('/\D+/', '', (string) ($cad->cpf_cnpj ?? ''));
        $contrato  = (string) ($cad->contrato_codigo_contrato ?? null);

        // required_docs pode vir como array, json ou string separada por vírgulas/linhas
        $reqDocsRaw = $r->input('required_docs');
        $reqDocsArr = null;
        if (is_array($reqDocsRaw)) {
            $reqDocsArr = array_values(array_filter(array_map(fn($v)=>trim((string)$v), $reqDocsRaw), fn($v)=>$v!==''));
        } elseif (is_string($reqDocsRaw)) {
            $trim = trim($reqDocsRaw);
            if ($trim !== '') {
                $json = json_decode($trim, true);
                if (json_last_error() === JSON_ERROR_NONE && is_array($json)) {
                    $reqDocsArr = array_values(array_filter(array_map(fn($v)=>trim((string)$v), $json), fn($v)=>$v!==''));
                } else {
                    // quebra por vírgula/linha
                    $reqDocsArr = array_values(array_filter(array_map('trim', preg_split('/[\r\n,]+/', $trim)), fn($v)=>$v!==''));
                }
            }
        }

        // Monta linha respeitando colunas existentes
        $tbl  = 'associadodois_doc_issues';
        $cols = \Schema::getColumnListing($tbl);

        $row = [
            'associadodois_cadastro_id' => $cad->id,
            'status'                    => 'open',
            'opened_at'                 => now(),
            'title'                     => $title,
            'message'                   => $msg,
            'cpf_cnpj'                  => $cpfCnpj ?: null,
            'contrato_codigo_contrato'  => $contrato ?: null,
            'created_at'                => now(),
            'updated_at'                => now(),
        ];

        // created_by_user_id (se existir)
        if (in_array('created_by_user_id', $cols, true)) {
            $row['created_by_user_id'] = optional($r->user())->id;
        }

        // required_docs (se existir)
        if ($reqDocsArr !== null && in_array('required_docs', $cols, true)) {
            $row['required_docs'] = json_encode($reqDocsArr, JSON_UNESCAPED_UNICODE);
        }

        // extras: aproveitamos para snapshot dos documentos, caso a coluna exista
        if (in_array('extras', $cols, true)) {
            $snapshot = is_array($cad->documents_json)
                ? $cad->documents_json
                : (json_decode((string) ($cad->documents_json ?? '[]'), true) ?: []);
            $row['extras'] = json_encode([
                'source'               => 'analista-web',
                'documents_snapshot'   => $snapshot,
            ], JSON_UNESCAPED_UNICODE);
        }

        // filtra apenas colunas realmente existentes antes do insert
        $row = array_intersect_key($row, array_flip($cols));

        \DB::table($tbl)->insert($row);

        \Log::info('Analista marcou incompleta (APP)', [
            'cadastro_id' => $cad->id,
            'user_id'     => optional($r->user())->id,
            'required_docs_count' => is_array($reqDocsArr) ? count($reqDocsArr) : 0,
        ]);

        return back()->with('ok', 'Marcado como documentação incompleta (APP) e notificação registrada.');
    }

    /** ================= AJUSTE DE DADOS (somente NOME) ================= */
    public function dadosIndex(Request $r)
    {
        $perPage = (int) $r->input('pp', 20);
        if ($perPage <= 0)  $perPage = 20;
        if ($perPage > 200) $perPage = 200;

        $q = trim((string) $r->input('q', ''));

        // Busca por nome (full_name) OU CPF/CNPJ (somente dígitos)
        $cadastros = \App\Models\AgenteCadastro::query()
            ->when($q !== '', function ($qb) use ($q) {
                $digits = preg_replace('/\D+/', '', $q);
                $qb->where(function ($w) use ($q, $digits) {
                    $w->where('full_name', 'like', "%{$q}%");
                    if ($digits !== '') {
                        $w->orWhere('cpf_cnpj', 'like', "%{$digits}%");
                    }
                });
            })
            ->orderByDesc('id')
            ->paginate($perPage)
            ->withQueryString();

        // ÚNICA VIEW desta funcionalidade
        return view('analista.dados-index', [
            'rows'    => $cadastros,
            'search'  => $q,
            'perPage' => $perPage,
        ]);
    }

    public function dadosEdit(\App\Models\AgenteCadastro $cadastro)
    {
        // Não usamos tela separada; apenas redireciona para a lista filtrada
        $q = $cadastro->full_name ?: $cadastro->cpf_cnpj;
        return redirect()->route('analista.dados.index', ['q' => $q]);
    }

    public function dadosUpdate(Request $r, \App\Models\AgenteCadastro $cadastro)
    {
        $data = $r->validate([
            'full_name' => ['required','string','max:200'],
        ]);

        // força UPPERCASE no servidor também
        $nome = mb_strtoupper(trim($data['full_name']), 'UTF-8');
        $cadastro->full_name = $nome;
        $cadastro->save();

        \Log::info('Analista alterou NOME do associado (ajuste de dados)', [
            'cadastro_id' => $cadastro->id,
            'user_id'     => optional($r->user())->id,
            'full_name'   => $cadastro->full_name,
        ]);

        return redirect()
            ->route('analista.dados.index', ['q' => $cadastro->full_name])
            ->with('ok', 'Nome atualizado com sucesso.');
    }

    // ================== APP: envio dos Termos (upload de 0–2 arquivos) =========
public function enviarTermosA2(Request $r, int $id)
{
    /** @var \App\Models\AssociadoDoisCadastro $cad */
    $cad = AssociadoDoisCadastro::query()->findOrFail($id);

    // >>> BLOQUEIO 1: cálculo de margem ainda não concluído
    $motivo = null;
    if (!$this->podeLiberarAuxilio($cad, 1, $motivo)) {
        return back()->withErrors([
            'termos' => 'Envio de termos bloqueado até concluir o cálculo de margem. '
                      . ($motivo ?: 'Preencha Mensalidade, Valor total de antecipação e Disponível (todos > 0).')
        ]);
    }

    // >>> BLOQUEIO 2: contato ainda não ACEITO no app (usa apenas contato_status e sinônimos)
    $syn = ['aceito','accepted','ok','aprovado'];
    $contatoAceito = in_array(strtolower((string)($cad->contato_status ?? '')), $syn, true);

    // compat: aceitar flags antigas se existirem (sem depender de aceite_termos)
    if (!$contatoAceito) {
        if (isset($cad->contato_aceito) && (int)$cad->contato_aceito === 1) {
            $contatoAceito = true;
        } elseif (isset($cad->aceite_contato) && (int)$cad->aceite_contato === 1) {
            $contatoAceito = true;
        }
    }

    if (!$contatoAceito) {
        return back()->withErrors([
            'termos' => 'Envio de termos bloqueado até o ACEITE DE CONTATO pelo associado no aplicativo.'
        ]);
    }
    // <<< FIM DOS BLOQUEIOS

    // Validação (10 MB; PDF ou imagem)
    $r->validate([
        'termo_adesao' => [
            'nullable','file','max:10240',
            'mimetypes:application/pdf,image/jpeg,image/png,image/webp,image/heic'
        ],
        'termo_antecipacao' => [
            'nullable','file','max:10240',
            'mimetypes:application/pdf,image/jpeg,image/png,image/webp,image/heic'
        ],
    ], [], [
        'termo_adesao' => 'Termo de Adesão',
        'termo_antecipacao' => 'Termo de Antecipação',
    ]);

    if (!$r->hasFile('termo_adesao') && !$r->hasFile('termo_antecipacao')) {
        return back()->withErrors(['termos' => 'Selecione ao menos um arquivo (Adesão ou Antecipação).']);
    }

    $base = "associadodois/termos/{$cad->id}";
    $saved = [];

    foreach (['termo_adesao' => 'adesao', 'termo_antecipacao' => 'antecipacao'] as $input => $slug) {
        if ($r->hasFile($input)) {
            $f   = $r->file($input);
            $ext = strtolower($f->getClientOriginalExtension() ?: $f->extension() ?: 'bin');
            $name= now($this->tz())->format('Ymd_His')."_{$slug}_" . \Str::random(6) . ".{$ext}";
            $rel = $f->storeAs($base, $name, 'public'); // storage/app/public/...

            $saved[$input] = $rel;

            // colunas padrão *_path
            $col = $input.'_path';
            if (\Schema::hasColumn($cad->getTable(), $col)) {
                $cad->{$col} = $rel;
            }
            // compat: se existirem *_admin_path, preenche também
            $colAdmin = $input.'_admin_path';
            if (\Schema::hasColumn($cad->getTable(), $colAdmin)) {
                $cad->{$colAdmin} = $rel;
            }
        }
    }

    // fallback: se não há colunas individuais, usa JSON termos_paths_json
    if (!empty($saved)
        && !\Schema::hasColumn($cad->getTable(), 'termo_adesao_path')
        && !\Schema::hasColumn($cad->getTable(), 'termo_antecipacao_path')
        && \Schema::hasColumn($cad->getTable(), 'termos_paths_json')) {

        $map = is_array($cad->termos_paths_json ?? null)
            ? $cad->termos_paths_json
            : (json_decode((string)($cad->termos_paths_json ?? ''), true) ?: []);
        foreach ($saved as $k => $path) { $map[$k] = $path; }
        $cad->termos_paths_json = json_encode($map, JSON_UNESCAPED_UNICODE);
    }

    $cad->save();

    \Log::info('Analista(APP): termos enviados', [
        'cadastro_app_id' => $cad->id,
        'files'           => $saved,
        'user_id'         => optional($r->user())->id,
    ]);

    return back()->with('ok', 'Termo(s) enviado(s) com sucesso. O associado já pode visualizar na área dele.');
}




/**
 * Abre (stream/redirect) um reupload do APP com log.
 * Rota: analista.reuploads.a2.ver
 */
public function streamAssociadoDoisReupload(int $id)
{
    /** @var \App\Models\AppReupload $r */
    $r = AppReupload::query()->findOrFail($id);

    // Mapeia colunas dinâmicas do modelo
    $pathCol = AppReupload::pathColumn();
    $origCol = AppReupload::firstExistingColumn(['original_name','filename','name','file_original_name']);
    $mimeCol = AppReupload::firstExistingColumn(['mime','mimetype','content_type']);
    $sizeCol = AppReupload::firstExistingColumn(['size','filesize','bytes','file_size_bytes']);

    $rawPath  = (string)($r->{$pathCol} ?? '');
    $original = (string)($origCol ? ($r->{$origCol} ?? '') : '');
    $mimeHint = (string)($mimeCol ? ($r->{$mimeCol} ?? '') : '');
    $sizeHint = $sizeCol ? (int)($r->{$sizeCol} ?? 0) : null;
    $download = request()->boolean('dl'); // ?dl=1 força download

    \Log::info('A2Reupload OPEN begin', [
        'id'   => $r->id,
        'path' => $rawPath,
        'user' => optional(auth()->user())->id,
        'ip'   => request()->ip(),
    ]);

    if ($rawPath === '') {
        abort(404, 'Arquivo não encontrado');
    }

    // Se for URL absoluta, redireciona
    if (preg_match('~^https?://~i', $rawPath)) {
        \Log::info('A2Reupload OPEN redirect', ['id' => $r->id, 'url' => $rawPath]);
        return redirect()->away($rawPath);
    }

    // Normaliza relativo e bloqueia path traversal
    $rel = $this->normalizeAppPath($rawPath);
    $rel = ltrim($rel, '/');
    if ($rel === '' || preg_match('~\.\.(?:/|\\\)~', $rel)) {
        \Log::warning('A2Reupload OPEN blocked (path traversal?)', ['id' => $r->id, 'rel' => $rel]);
        abort(404, 'Arquivo inválido');
    }

    $disk = \Storage::disk('public');

    // Candidatos em ordem de preferência
    $candidates = [
        // 1) /public/uploads/{rel}
        [
            'kind'     => 'public_uploads',
            'rel'      => preg_match('~^uploads/~i', $rel) ? $rel : ('uploads/'.$rel),
            'abs'      => public_path(preg_match('~^uploads/~i', $rel) ? $rel : ('uploads/'.$rel)),
            'use_disk' => false,
        ],
        // 2) storage/app/public/{rel}
        [
            'kind'     => 'storage_public',
            'rel'      => $rel,
            'abs'      => method_exists($disk, 'path') ? $disk->path($rel) : null,
            'use_disk' => true,
        ],
        // 3) storage/app/public/uploads/{rel}
        [
            'kind'     => 'storage_public_uploads',
            'rel'      => 'uploads/'.$rel,
            'abs'      => method_exists($disk, 'path') ? $disk->path('uploads/'.$rel) : null,
            'use_disk' => true,
        ],
        // 4) /public/{rel} (casos legados)
        [
            'kind'     => 'public',
            'rel'      => ltrim(preg_replace('~^public/~i', '', $rel), '/'),
            'abs'      => public_path(ltrim(preg_replace('~^public/~i', '', $rel), '/')),
            'use_disk' => false,
        ],
        // 5) /public/storage/{rel} (symlink do Laravel)
        [
            'kind'     => 'public_storage_symlink',
            'rel'      => 'storage/'.$rel,
            'abs'      => public_path('storage/'.$rel),
            'use_disk' => false,
        ],
    ];

    foreach ($candidates as $cand) {
        $exists = $cand['use_disk']
            ? $disk->exists($cand['rel'])
            : (is_string($cand['abs']) && is_file($cand['abs']));

        if (!$exists) {
            continue;
        }

        // Metadados (MIME/size) com fallback
        $mime = $mimeHint ?: (
            $cand['use_disk']
                ? ($disk->mimeType($cand['rel']) ?: $this->guessMimeFromExt($cand['rel']))
                : (@mime_content_type($cand['abs']) ?: $this->guessMimeFromExt($cand['abs']))
        );
        $size = $sizeHint ?: ($cand['use_disk'] ? (int) $disk->size($cand['rel']) : (int) @filesize($cand['abs']));

        $filename    = $original ?: (basename($cand['abs'] ?: $rel) ?: 'arquivo');
        $disposition = $download ? 'attachment' : 'inline';

        $headers = array_filter([
            'Content-Type'        => $mime ?: 'application/octet-stream',
            'Content-Length'      => $size ?: null,
            'Content-Disposition' => $disposition . '; filename="'.$filename.'"',
            'Cache-Control'       => 'private, max-age=31536000',
        ], fn ($v) => $v !== null);

        \Log::info('A2Reupload OPEN serve', [
            'id'     => $r->id,
            'served' => $cand['kind'],
            'rel'    => $cand['rel'],
            'abs'    => $cand['abs'],
            'mime'   => $headers['Content-Type'] ?? null,
            'size'   => $size,
            'user'   => optional(auth()->user())->id,
            'ip'     => request()->ip(),
        ]);

        if ($cand['use_disk']) {
            $stream = $disk->readStream($cand['rel']);
            if (!$stream) break;

            return response()->stream(function () use ($stream) {
                fpassthru($stream);
            }, 200, $headers);
        }

        // Arquivo direto em /public
        if ($download) {
            return response()->download($cand['abs'], $filename, $headers);
        }
        return response()->file($cand['abs'], $headers);
    }

    \Log::warning('A2Reupload OPEN 404', [
        'id'    => $r->id,
        'rel'   => $rel,
        'cands' => collect($candidates)->pluck('abs', 'kind'),
        'user'  => optional(auth()->user())->id,
        'ip'    => request()->ip(),
    ]);

    abort(404, 'Arquivo não encontrado');
}

// ASSUMIR CADASTRO WEB
public function assumir($id)
{
    $analistaId = auth()->id();

    return DB::transaction(function () use ($id, $analistaId) {

        $cadastro = AgenteCadastro::whereKey($id)->lockForUpdate()->firstOrFail();

        $ass = AgenteCadastroAssumption::where('agente_cadastro_id', $id)
            ->lockForUpdate()
            ->first();

        if ($ass && $ass->status === 'assumido') {
            // idempotente: se já está assumido por mim, só retorna ok
            if ((int) $ass->analista_id === (int) $analistaId) {
                return response()->json(['ok' => true]);
            }

            return response()->json([
                'ok'      => false,
                'message' => 'Este cadastro já foi assumido por outro analista.',
            ], 409);
        }

        if (!$ass) {
            AgenteCadastroAssumption::create([
                'agente_cadastro_id' => $id,
                'analista_id'        => $analistaId,
                'status'             => 'assumido',
                'assumido_em'        => now(),   // ✅ primeira vez
                'heartbeat_at'       => now(),
            ]);
        } else {
            $ass->update([
                'analista_id'   => $analistaId,
                'status'        => 'assumido',
                'assumido_em'   => now(),       // ✅ registra o momento em que assumiu
                'liberado_em'   => null,
                'heartbeat_at'  => now(),
            ]);
        }

        return response()->json(['ok' => true]);
    });
}



// ASSUMIR CADASTRO APP
public function assumirApp($id)
{
    $analistaId = auth()->id();

    return DB::transaction(function () use ($id, $analistaId) {

        // trava o cadastro do APP (tabela certa)
        AssociadoDoisCadastro::whereKey($id)->lockForUpdate()->firstOrFail();

        // trava o assumption do APP (coluna certa)
        $ass = AgenteCadastroAssumption::where('associadodois_cadastro_id', $id)
            ->lockForUpdate()
            ->first();

        if ($ass && $ass->status === 'assumido') {
            if ((int) $ass->analista_id === (int) $analistaId) {
                return response()->json(['ok' => true]);
            }

            return response()->json([
                'ok'      => false,
                'message' => 'Este cadastro já foi assumido por outro analista.',
            ], 409);
        }

        if (!$ass) {
            AgenteCadastroAssumption::create([
                'agente_cadastro_id'        => null,
                'associadodois_cadastro_id' => $id,
                'analista_id'               => $analistaId,
                'status'                    => 'assumido',
                'assumido_em'               => now(),
                'liberado_em'               => null,
                'heartbeat_at'              => now(),
            ]);
        } else {
            $ass->update([
                'analista_id'   => $analistaId,
                'status'        => 'assumido',
                'assumido_em'   => now(),
                'liberado_em'   => null,
                'heartbeat_at'  => now(),
            ]);
        }

        return response()->json(['ok' => true]);
    });
}

public function streamA2Reupload(Request $request, AssociadoDoisDocReupload $reupload)
{
    $idx = $request->query('file');

    $extras = $reupload->extras ?? [];
    if (is_string($extras)) {
        $extras = json_decode($extras, true) ?: [];
    }

    if (is_array($extras) && is_array($extras['files'] ?? null) && $idx !== null) {
        $i = (int) $idx;
        $picked = $extras['files'][$i] ?? null;
        if (!$picked) abort(404);

        $path = $picked['disk_path'] ?? $picked['relative_path'] ?? $picked['public_url'] ?? null;
        $mime = $picked['mime'] ?? $reupload->file_mime ?? 'application/octet-stream';
        $name = $picked['original_name'] ?? $reupload->file_original_name ?? 'arquivo';
    } else {
        $path = $reupload->file_relative_path
            ?: ($reupload->file_stored_name
                ? ('associadodois/'.$reupload->cpf_cnpj.'/reuploads/'.$reupload->file_stored_name)
                : null);

        $mime = $reupload->file_mime ?? 'application/octet-stream';
        $name = $reupload->file_original_name ?? 'arquivo';
    }

    if (!$path) abort(404);

    $path = ltrim((string)$path, '/');
    $path = preg_replace('~^storage/~i', '', $path);
    $path = preg_replace('~^public/~i',  '', $path);
    $path = ltrim($path, '/');

    if (!Storage::disk('public')->exists($path)) abort(404);

    return response()->file(Storage::disk('public')->path($path), [
        'Content-Type' => $mime,
        'Content-Disposition' => 'inline; filename="'.$name.'"',
    ]);
}

}
