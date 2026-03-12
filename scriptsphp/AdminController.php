<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Illuminate\Support\Facades\Storage;
use Laravel\Fortify\Contracts\CreatesNewUsers;
use Laravel\Jetstream\Jetstream;
use Illuminate\Support\Facades\Schema;
use App\Models\User;
use App\Models\AgenteCadastro;
use App\Models\AgenteDocIssue;
use App\Models\TesourariaPagamento;
use App\Models\PagamentoMensalidade;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Validator;
use Illuminate\Validation\Rules\Password as PasswordRule;
use Illuminate\Support\Facades\Log;
use Carbon\Carbon;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Collection;
class AdminController extends Controller
{

        // Ajuste aqui se quiser mudar regra depois
    private const RETORNO_MENSALIDADE_MIN = 100.00;           // mensalidades = >= 100
    private const RETORNO_VALORES_3050    = [30.00, 50.00];   // “outra coisa” = 30 e 50

    public function __construct()
    {
        $this->middleware(['auth', 'role:admin']);
    }

public function index()
{
    $storeAgenteUrl = Route::has('admin.users.storeAgente') ? route('admin.users.storeAgente') : '#';
    $cadListUrl     = Route::has('admin.cadastros.list')   ? route('admin.cadastros.list')   : '#';
    $homeUrl        = url('/');
    $logoutUrl      = Route::has('logout') ? route('logout') : '#';

    // URLs de navegação (inclui Despesas)
    $relatoriosUrl = Route::has('admin.relatorios.index') ? route('admin.relatorios.index') : '#';
    $graficosUrl   = Route::has('admin.graficos.index')   ? route('admin.graficos.index')   : '#';
    $despesasUrl   = Route::has('admin.despesas.index')   ? route('admin.despesas.index')   : '#';

    // ===================== PERÍODO DO MÊS (sem regra 05/06) =====================
    $tz = config('app.timezone') ?: (env('APP_TIMEZONE') ?: 'America/Sao_Paulo');

    $mesParam = (string) request('mes', now($tz)->format('Y-m'));
    if (!preg_match('~^\d{4}-\d{2}$~', $mesParam)) {
        $mesParam = now($tz)->format('Y-m');
    }

    // Janela real do mês: [01/M 00:00, 01/(M+1) 00:00)
    $inicioCompetencia   = \Carbon\Carbon::createFromFormat('Y-m', $mesParam, $tz)->startOfMonth()->startOfDay();
    $fechamentoExclusivo = $inicioCompetencia->copy()->addMonth();

    // Para cards de retorno (1º/2º/3º) a partir do mês selecionado:
    // cards devem ser M+1, M+2, M+3
    $primeiroArquivoRef  = $inicioCompetencia->copy()->addMonthNoOverflow()->startOfMonth();

    // Offset local (para CONVERT_TZ)
    $TZ_SQL = $this->tzSqlFrom($inicioCompetencia);

    // Filtro padrão de datas para tesouraria (pago) usando CONVERT_TZ
    $betweenSql  = "CONVERT_TZ(COALESCE(t.paid_at, t.created_at), @@session.time_zone, ?) >= ?
                    AND CONVERT_TZ(COALESCE(t.paid_at, t.created_at), @@session.time_zone, ?) < ?";
    $betweenArgs = [$TZ_SQL, $inicioCompetencia, $TZ_SQL, $fechamentoExclusivo];

    // Labels e navegação de mês
    $fimInclusivoApenasUI = $fechamentoExclusivo->copy()->subSecond();
    $labelFaixa           = $inicioCompetencia->format('d/m/Y H:i') . ' - ' . $fimInclusivoApenasUI->format('d/m/Y H:i');

    \Carbon\Carbon::setLocale('pt_BR');
    $competenciaLabel = ucfirst($inicioCompetencia->translatedFormat('F')) . '/' . $inicioCompetencia->format('Y');

    $mesAnterior = $inicioCompetencia->copy()->subMonth()->format('Y-m');
    $mesSeguinte = $inicioCompetencia->copy()->addMonth()->format('Y-m');

    /* ===================== KPIs "HOJE" (dia corrente no fuso $tz) ===================== */
    $hojeInicio = now($tz)->startOfDay();
    $hojeFim    = $hojeInicio->copy()->addDay();

    // "HOJE" só vale quando o mês selecionado é o mês atual (no mesmo fuso)
    $isMesAtual = ($mesParam === $hojeInicio->format('Y-m'));

    // zera por padrão (evita "vazar" valores ao navegar meses)
    $cadastrosHoje = 0;
    $pendenciasHoje = 0;
    $pagPendentesHoje = 0;
    $pagConfirmadosHoje = 0;

    if ($isMesAtual) {
        $betweenArgsHoje = [$TZ_SQL, $hojeInicio, $TZ_SQL, $hojeFim];

        // 1) Cadastros criados hoje
        $cadastrosHoje = \App\Models\AgenteCadastro::whereBetween('created_at', [$hojeInicio, $hojeFim])->count();

        // 2) Pendências de documentos atualizadas hoje (status incompleto)
        $pendenciasHoje = DB::table('agente_doc_issues as i')
            ->where('i.status', 'incomplete')
            ->whereBetween('i.updated_at', [$hojeInicio, $hojeFim])
            ->count();

        // 3) Pagamentos pendentes "hoje" (distinct por cadastro, janela do dia)
        $pagPendentesHoje = DB::table('tesouraria_pagamentos as t')
            ->where('t.status', 'pendente')
            ->whereBetween(DB::raw('COALESCE(t.updated_at, t.created_at)'), [$hojeInicio, $hojeFim])
            ->whereNotNull('t.agente_cadastro_id')
            ->distinct()
            ->count('t.agente_cadastro_id');

        // 4) Pagamentos confirmados "hoje" (usa CONVERT_TZ)
        $pagConfirmadosHoje = DB::table('tesouraria_pagamentos as t')
            ->join('agente_cadastros as c','c.id','=','t.agente_cadastro_id')
            ->where('t.status','pago')
            ->whereRaw($betweenSql, $betweenArgsHoje)
            ->count();
    }
    /* =================== FIM KPIs "HOJE" =================== */

    // ===================== Cadastros (lista/paginação) =====================
    $q       = request('q', '');
    $perPage = 5;

    $qbCad = $this->buildCadastrosQuery($q);

    if ($q === '') {
        $qbCad->where('created_at', '>=', $inicioCompetencia)
              ->where('created_at', '<',  $fechamentoExclusivo);
    }

    $paginator = $qbCad
        ->orderByDesc('created_at')
        ->paginate($perPage, ['*'], 'cad_page');

    $cadMeta = [
        'current_page' => $paginator->currentPage(),
        'last_page'    => $paginator->lastPage(),
        'from'         => $paginator->firstItem() ?? 0,
        'to'           => $paginator->lastItem() ?? 0,
        'total'        => $paginator->total(),
        'page_name'    => 'cad_page',
    ];

    // ===================== Pendências de Documentos =====================
    $pendPerPage = (int) request('per_pend', 10);
    $pendPerPage = max(1, min(50, $pendPerPage));
    $pendPage    = (int) request('pend_page', 1);
    $pendQ       = trim((string) request('pend_q', ''));

    $issuesBase = \App\Models\AgenteDocIssue::query()
        ->with(['analista:id,name'])
        ->withCount('reuploads')
        ->when($pendQ !== '', function ($qry) use ($pendQ) {
            $qry->where(function ($w) use ($pendQ) {
                $w->where('cpf_cnpj', 'like', "%{$pendQ}%")
                  ->orWhere('contrato_codigo_contrato', 'like', "%{$pendQ}%")
                  ->orWhereHas('analista', fn($q2) => $q2->where('name', 'like', "%{$pendQ}%"));
            });
        });

    if ($pendQ === '') {
        $issuesBase->where('updated_at', '>=', $inicioCompetencia)
                   ->where('updated_at', '<',  $fechamentoExclusivo);
    }

    $docTotalsRow = DB::table('agente_doc_issues as i')
        ->when($pendQ !== '', function ($qry) use ($pendQ) {
            $qry->leftJoin('users as u', 'u.id', '=', 'i.analista_id')
                ->where(function ($w) use ($pendQ) {
                    $w->where('i.cpf_cnpj', 'like', "%{$pendQ}%")
                      ->orWhere('i.contrato_codigo_contrato', 'like', "%{$pendQ}%")
                      ->orWhere('u.name', 'like', "%{$pendQ}%");
                });
        }, function ($qry) use ($inicioCompetencia, $fechamentoExclusivo) {
            $qry->where('i.updated_at', '>=', $inicioCompetencia)
                ->where('i.updated_at', '<',  $fechamentoExclusivo);
        })
        ->selectRaw("SUM(i.status='incomplete') AS abertas,
                     SUM(i.status='resolved')   AS resolvidas,
                     COUNT(*)                   AS total")
        ->first();

    $docTotals = (object) [
        'abertas'    => (int) ($docTotalsRow->abertas    ?? 0),
        'resolvidas' => (int) ($docTotalsRow->resolvidas ?? 0),
        'total'      => (int) ($docTotalsRow->total      ?? 0),
    ];

    $docIssues = (clone $issuesBase)
        ->select(['id','cpf_cnpj','contrato_codigo_contrato','analista_id','status','mensagem','agent_uploads_json','created_at','updated_at'])
        ->orderByDesc('updated_at')
        ->paginate($pendPerPage, ['*'], 'pend_page', $pendPage);

    $analistas = \App\Models\User::whereIn('id', $docIssues->getCollection()->pluck('analista_id')->filter()->unique())
        ->pluck('name','id')->toArray();

    // ===================== TESOURARIA - Base no mês (pago) =====================
    $base = DB::table('tesouraria_pagamentos as t')
        ->join('agente_cadastros as c','c.id','=','t.agente_cadastro_id')
        ->where('t.status','pago')
        ->whereRaw($betweenSql, $betweenArgs);

    $pagConfirmados = (clone $base)->count();

    // ===================== KPI: Pagamentos Pendentes (mês) =====================
    $pagPendentes = DB::table('tesouraria_pagamentos as t')
        ->where('t.status', 'pendente')
        ->whereBetween(DB::raw('COALESCE(t.updated_at, t.created_at)'), [
            $inicioCompetencia, $fechamentoExclusivo
        ])
        ->whereNotNull('t.agente_cadastro_id')
        ->distinct()
        ->count('t.agente_cadastro_id');

    $totalMensalidadesTesouraria = (clone $base)->sum('t.valor_pago');

    // Auxílio do agente (pago no mês)
    $auxilioTotal = (clone $base)
        ->selectRaw("COALESCE(SUM(t.valor_pago * (COALESCE(c.auxilio_taxa,10)/100.0)),0) as s")
        ->value('s');

    // ===================== Contadores topo (mês) =====================
    $cadastrosCount = \App\Models\AgenteCadastro::where('created_at', '>=', $inicioCompetencia)
        ->where('created_at', '<',  $fechamentoExclusivo)
        ->count();

    $pendenciasDocumentos = DB::table('agente_doc_issues as i')
        ->where('i.status', 'incomplete')
        ->where('i.updated_at', '>=', $inicioCompetencia)
        ->where('i.updated_at', '<',  $fechamentoExclusivo)
        ->count();

    // ===================== Resumo Financeiro (somente pagos no mês) =====================
    $paidCadIds = DB::table('tesouraria_pagamentos as t')
        ->where('t.status','pago')
        ->whereRaw($betweenSql, $betweenArgs)
        ->pluck('t.agente_cadastro_id')
        ->filter()
        ->unique()
        ->values();

    $cadPagos = \App\Models\AgenteCadastro::whereIn('id', $paidCadIds)->get();

    $toFloat = function($v) {
        if (is_numeric($v)) return (float)$v;
        $s = preg_replace('/[^\d,.\-]+/','', (string)$v);
        $s = str_replace('.', '', $s);
        $s = str_replace(',', '.', $s);
        return (float)$s;
    };

    // 1) Valor Total de Auxílio (margem)
    $valorPago = (float) $cadPagos->sum(fn($c) => (float) ($c->contrato_margem_disponivel ?? 0));

    // 2) Doação Líquida
    $retornoRecebido = $cadPagos->sum(function($c) use ($toFloat) {
        $valorAnt = (float) ($c->contrato_valor_antecipacao   ?? 0);
        $margem   = (float) ($c->contrato_margem_disponivel   ?? 0);
        $perc     = is_null($c->auxilio_taxa) ? 10.0 : (float)$c->auxilio_taxa;
        $comissao = $margem * ($perc/100);
        $base     = $valorAnt - $margem - $comissao;

        $raw = $c->anticipations_json ?? $c->contrato_antecipacoes ?? $c->contrato_antecipacoes_json ?? $c->anticipations_json ?? null;
        if     ($raw instanceof \Illuminate\Support\Collection) $items = $raw->toArray();
        elseif (is_array($raw))                                  $items = $raw;
        elseif (is_string($raw) && trim($raw) !== '')            $items = (array) (json_decode($raw, true) ?: []);
        else                                                     $items = [];

        $sumConcluidas = 0.0;
        foreach ($items as $it) {
            $status   = strtolower((string)($it['status'] ?? $it['situacao'] ?? $it['state'] ?? ''));
            $paidFlag = $it['pago']   ?? $it['paid']   ?? null;

            $isConcluida =
                in_array($status, ['concluida','concluída','concluido','concluído','pago','paga','quitado','quitada','liquidado','liquidada'], true)
                || (is_bool($paidFlag) && $paidFlag === true)
                || (is_string($paidFlag) && in_array(strtolower($paidFlag), ['sim','true','1'], true));

            if ($isConcluida) {
                $valor = $it['valorAuxilio'] ?? $it['valor'] ?? $it['value'] ?? $it['amount'] ?? ($c->contrato_mensalidade ?? 0);
                $sumConcluidas += $toFloat($valor);
            }
        }
        return round($base + $sumConcluidas, 2);
    });

    // 3) Total de Mensalidades (pendentes estimadas)
    $retornoEstimado = $cadPagos->sum(function($c) use ($toFloat) {
        $raw = $c->anticipations_json ?? $c->contrato_antecipacoes ?? $c->contrato_antecipacoes_json ?? null;
        if     ($raw instanceof \Illuminate\Support\Collection) $items = $raw->toArray();
        elseif (is_array($raw))                                  $items = $raw;
        elseif (is_string($raw) && trim($raw) !== '')            $items = (array) (json_decode($raw, true) ?: []);
        else                                                     $items = [];

        $sum = 0.0;
        foreach ($items as $it) {
            $status   = strtolower((string)($it['status'] ?? $it['situacao'] ?? $it['state'] ?? ''));
            $paidFlag = $it['pago']   ?? $it['paid']   ?? null;

            $isPendente =
                in_array($status, ['pendente','pending','em aberto','aberto'], true)
                || (is_bool($paidFlag) && $paidFlag === false)
                || (is_string($paidFlag) && in_array(strtolower($paidFlag), ['nao','não','false','0'], true));

            if ($isPendente) {
                $valor = $it['valorAuxilio'] ?? $it['valor'] ?? $it['value'] ?? $it['amount'] ?? ($c->contrato_mensalidade ?? 0);
                $sum  += $toFloat($valor);
            }
        }
        return round($sum, 2);
    });

    // 4) Fundo de Doações
    $totalDoacoesAssociados = (float) $cadPagos->sum(fn($c) => (float) ($c->contrato_doacao_associado ?? 0));

    // ===================== BLOCO DOURADO - pagos dentro do mês =====================
    $cadPagosNaCompetencia = \App\Models\AgenteCadastro::query()
        ->join('tesouraria_pagamentos as t', 't.agente_cadastro_id', '=', 'agente_cadastros.id')
        ->where('t.status', 'pago')
        ->whereRaw($betweenSql, $betweenArgs)
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

    $retornoEstimadoDetalhes = [];
    $retornoEstimadoMes = 0.0;

    foreach ($cadPagosNaCompetencia as $c) {
        $raw = $c->anticipations_json ?? $c->contrato_antecipacoes ?? $c->contrato_antecipacoes_json ?? null;
        if     ($raw instanceof \Illuminate\Support\Collection) $items = $raw->toArray();
        elseif (is_array($raw))                                  $items = $raw;
        elseif (is_string($raw) && trim($raw) !== '')            $items = (array) (json_decode($raw, true) ?: []);
        else                                                     $items = [];

        $toFloatLocal = function($v) {
            if (is_numeric($v)) return (float)$v;
            $s = preg_replace('/[^\d,.\-]+/','', (string)$v);
            $s = str_replace('.', '', $s);
            $s = str_replace(',', '.', $s);
            return (float)$s;
        };

        $somaAnt = 0.0;
        foreach ($items as $it) {
            $val = $it['valorAuxilio'] ?? $it['valor'] ?? $it['value'] ?? $it['amount'] ?? null;
            if ($val !== null && $val !== '') $somaAnt += $toFloatLocal($val);
        }

        $mens  = (float) ($c->contrato_mensalidade ?? 0);
        $prazo = (int)   ($c->contrato_prazo_meses ?? 3);
        $x3pad = round($mens * ($prazo > 0 ? $prazo : 3), 2);

        $x3 = (float) ($c->t_valor_antecipacao ?? $c->contrato_valor_antecipacao ?? $x3pad);
        $considerado = $somaAnt > 0 ? $somaAnt : $x3;

        $dtRef  = \Carbon\Carbon::parse($c->paid_at ?? $c->t_created_at)->timezone($tz);
        $pagoEm = $dtRef->format('d/m/Y H:i');

        $retornoEstimadoDetalhes[] = [
            'cadastro_id'     => $c->id,
            'contrato_codigo' => $c->t_codigo ?: $c->contrato_codigo_contrato,
            'agente'          => $c->agente_responsavel ?: $c->agente_filial ?: '-',
            'associado'       => $c->full_name ?? '-',
            'mensalidade'     => (float) $mens,
            'x3'              => (float) $x3,
            'soma_antecip'    => (float) $somaAnt,
            'considerado'     => (float) $considerado,
            'pago_em'         => $pagoEm,
        ];

        $retornoEstimadoMes += (float) $considerado;
    }

    usort($retornoEstimadoDetalhes, function($a,$b){
        $cmp = strcasecmp($a['agente'] ?? '', $b['agente'] ?? '');
        return $cmp !== 0 ? $cmp : strcasecmp($a['associado'] ?? '', $b['associado'] ?? '');
    });

    $retornoEstimadoNota =
        'Estimativa do mês somando, para <strong>cada contrato com pagamento efetivado pela Tesouraria neste mês</strong>, '.
        'a <em>somatória das 3 linhas</em> de <em>Antecipações</em> (valorAuxilio). '.
        'Se o contrato não tiver linhas, utiliza-se o <em>Valor Total de Antecipação</em> (mensalidade × 3).';

    // ===================== Tesouraria - lista (somente pagos, mesmo mês) =====================
    $pagQ = trim((string) request('pag_q', ''));
    $pagamentos = \App\Models\TesourariaPagamento::query()
        ->from('tesouraria_pagamentos as t')
        ->select([
            't.id','t.agente_cadastro_id','t.created_by_user_id',
            't.contrato_codigo_contrato','t.contrato_valor_antecipacao',
            't.cpf_cnpj','t.full_name','t.agente_responsavel',
            't.status','t.valor_pago','t.paid_at','t.forma_pagamento',
            't.comprovante_path',
            't.comprovante_agente_path',
            't.comprovante_associado_path',
            't.created_at',
        ])
        ->where('t.status','pago')
        ->whereRaw($betweenSql, $betweenArgs)
        ->when($pagQ !== '', function ($qry) use ($pagQ) {
            $digits = preg_replace('/\D+/', '', $pagQ);
            $qry->where(function ($w) use ($pagQ, $digits) {
                $w->where('t.full_name', 'like', "%{$pagQ}%")
                  ->orWhere('t.contrato_codigo_contrato', 'like', "%{$pagQ}%");
                if ($digits !== '') $w->orWhere('t.cpf_cnpj', 'like', "%{$digits}%");
            });
        })
        ->orderByDesc(DB::raw('COALESCE(t.paid_at, t.created_at)'))
        ->get();

    // ===================== Snapshot mensalidades (opcional) =====================
    $mensalidadesMes = \App\Models\PagamentoMensalidade::query()
        ->whereMonth('referencia_month', $inicioCompetencia->month)
        ->whereYear('referencia_month',  $inicioCompetencia->year)
        ->count();

    /* =============== CARDS - Arquivos Retorno (dados) =============== */
    $retornoCards = [];
    for ($n = 1; $n <= 3; $n++) {
        $refMonth = $primeiroArquivoRef->copy()->addMonthsNoOverflow($n - 1)->startOfMonth();

        [$_rows, $totais] = $this->buildRetornoRowsAndTotals($refMonth);

        $esperado = $totais['esperado'] ?? 0.0;
        $recebido = $totais['recebido'] ?? 0.0;
        $total    = $totais['total']    ?? 0;
        $ok       = $totais['ok']       ?? 0;

        $pct = $esperado > 0
            ? max(0, min(100, ($recebido / $esperado) * 100))
            : 0.0;

        $retornoCards[] = [
            'n'              => $n,
            'title'          => "{$n}º arquivo retorno",
            'ref_fmt'        => $refMonth->format('m/Y'),
            'expected_total' => $esperado,
            'received_total' => $recebido,
            'expected_count' => $total,
            'received_count' => $ok,
            'pct'            => $pct,
        ];
    }

    /* ===== Fallback para não quebrar a view ===== */
    $porCategoria = $porCategoria ?? collect();

    // =================================================================
    // ================ GLOBAIS (TODOS OS PERÍODOS) ====================
    // =================================================================

    // Total de cadastros (site + app) deduplicado por CPF/CNPJ
    try {
        $hasAppTable = Schema::hasTable('associadodois_cadastros');

        $normA = "REPLACE(REPLACE(REPLACE(REPLACE(c.cpf_cnpj,'.',''),'-',''),'/',''),' ','')";
        $subA  = DB::table('agente_cadastros as c')
            ->selectRaw("$normA as doc")
            ->whereNotNull('c.cpf_cnpj')
            ->where('c.cpf_cnpj','!=','');

        if ($hasAppTable) {
            $normB = "REPLACE(REPLACE(REPLACE(REPLACE(a.cpf_cnpj,'.',''),'-',''),'/',''),' ','')";
            $subB  = DB::table('associadodois_cadastros as a')
                ->selectRaw("$normB as doc")
                ->whereNotNull('a.cpf_cnpj')
                ->where('a.cpf_cnpj','!=','');

            $union = $subA->union($subB);
            $totCadastrosAll = DB::query()
                ->fromSub($union, 'u')
                ->where('u.doc','!=','')
                ->distinct()
                ->count('u.doc');
        } else {
            $totCadastrosAll = (int) DB::table('agente_cadastros')->count();
        }
    } catch (\Throwable $e) {
        $totCadastrosAll = (int) DB::table('agente_cadastros')->count();
    }

    // Totais históricos de pagamentos
    $totPagAll = DB::table('tesouraria_pagamentos as p')
        ->leftJoin('agente_cadastros as c', 'c.id', '=', 'p.agente_cadastro_id')
        ->where('p.status','pago')
        ->selectRaw('
            COUNT(*) AS qtd_pagamentos,
            COALESCE(SUM(p.valor_pago),0) AS total_pago,
            COALESCE(SUM(p.valor_pago * COALESCE(c.auxilio_taxa,10)/100),0) AS total_auxilio
        ')
        ->first();

    // Totais do Aplicativo (pagos)
    $appAll = DB::table('tesouraria_pagamentos as t')
        ->selectRaw("
          COUNT(*) AS qtd_rows,
          COUNT(DISTINCT COALESCE(t.associadodois_cadastro_id, t.agente_cadastro_id, t.cpf_cnpj)) AS qtd_cadastros,
          COALESCE(SUM(t.valor_pago),0) AS total_pago
        ")
        ->where('t.status','pago')
        ->where(function($q2){
          $q2->whereRaw("LOWER(TRIM(t.agente_responsavel)) = 'aplicativo'")
             ->orWhere('t.agente_responsavel','like','Aplicativo%');
        })
        ->first();

    return view('admin.dashboardadmin', [
        'storeAgenteUrl'  => $storeAgenteUrl,
        'cadListUrl'      => $cadListUrl,
        'homeUrl'         => $homeUrl,
        'logoutUrl'       => $logoutUrl,

        // URLs usadas no drawer/navegação
        'relatoriosUrl'   => $relatoriosUrl,
        'graficosUrl'     => $graficosUrl,
        'despesasUrl'     => $despesasUrl,

        'cadastros'       => $paginator,
        'cadMeta'         => $cadMeta,
        'cadSearch'       => $q,
        'cadPerPage'      => $perPage,
        'cadPageName'     => $cadMeta['page_name'],

        'docIssues'       => $docIssues,
        'docTotals'       => $docTotals,
        'analistas'       => $analistas,

        'pagamentos'      => $pagamentos,

        'mes'                   => $mesParam,
        'mesAnterior'           => $mesAnterior,
        'mesSeguinte'           => $mesSeguinte,
        'mesLabel'              => $competenciaLabel,

        'periodo_inicio'        => $inicioCompetencia,
        'periodo_fim'           => $fimInclusivoApenasUI,
        'labelFaixa'            => $labelFaixa,
        'tz'                    => $tz,

        'cadastrosCount'        => $cadastrosCount,
        'pendenciasDocumentos'  => (int) $pendenciasDocumentos,
        'pagPendentes'          => $pagPendentes,
        'pagConfirmados'        => $pagConfirmados,
        'totalMensalidades'     => (float) $totalMensalidadesTesouraria,
        'auxilioTotal'          => (float) $auxilioTotal,

        'valorPago'               => (float) $valorPago,
        'retornoRecebido'         => (float) $retornoRecebido,
        'retornoEstimado'         => (float) $retornoEstimado,
        'totalDoacoesAssociados'  => (float) $totalDoacoesAssociados,

        'retornoEstimadoMes'      => (float) $retornoEstimadoMes,
        'retornoEstimadoNota'     => $retornoEstimadoNota,
        'retornoEstimadoDetalhes' => $retornoEstimadoDetalhes,
        'competenciaLabel'        => $competenciaLabel,

        'mensalidadesMes' => $mensalidadesMes,
        'retornoCards'    => $retornoCards,

        // KPIs DO DIA
        'cadastrosHoje'      => $cadastrosHoje,
        'pendenciasHoje'     => $pendenciasHoje,
        'pagPendentesHoje'   => $pagPendentesHoje,
        'pagConfirmadosHoje' => $pagConfirmadosHoje,

        'porCategoria'       => $porCategoria,

        // ===== Variáveis globais para o bloco "Comparativo Global" =====
        'totCadastrosAll' => (int) $totCadastrosAll,
        'totPagAll'       => $totPagAll,
        'appAll'          => $appAll,
    ]);
}

















    /**
     * Lista de cadastros (AJAX) para o painel do Admin.
     */
public function listCadastros(Request $request)
{
    $perPage  = max(1, min(50, (int) $request->input('per_page', 10)));
    $pageName = $request->input('page_name', 'cad_page');
    $page     = (int) $request->input($pageName, $request->input('page', 1));
    $q        = trim((string) $request->input('q', ''));

    // ============ MÊS REAL (01 -> último dia do mês) ============
    $tz       = config('app.timezone') ?: (env('APP_TIMEZONE') ?: 'America/Sao_Paulo');
    $mesParam = (string) $request->input('mes', now($tz)->format('Y-m'));

    if (!preg_match('~^\d{4}-\d{2}$~', $mesParam)) {
        $mesParam = now($tz)->format('Y-m');
    }

    $inicioPeriodo  = \Carbon\Carbon::createFromFormat('Y-m', $mesParam, $tz)->startOfMonth()->startOfDay();
    $fimExclusivo   = $inicioPeriodo->copy()->addMonth();

    // Offset local p/ usar no CONVERT_TZ
    $offsetMinutes = $inicioPeriodo->offsetMinutes;
    $sign = $offsetMinutes >= 0 ? '+' : '-';
    $h = str_pad((string) floor(abs($offsetMinutes) / 60), 2, '0', STR_PAD_LEFT);
    $m = str_pad((string) (abs($offsetMinutes) % 60), 2, '0', STR_PAD_LEFT);
    $TZ_SQL = "{$sign}{$h}:{$m}";

    // ============ Query base ============
    $qbCad = \App\Models\AgenteCadastro::query()
        ->select([
            'id','full_name','cpf_cnpj','matricula_servidor_publico','email',
            'orgao_publico','situacao_servidor',
            'contrato_codigo_contrato','contrato_prazo_meses','contrato_taxa_antecipacao',
            'contrato_mensalidade','contrato_valor_antecipacao','contrato_margem_disponivel',
            'contrato_status_contrato','agente_responsavel','observacoes',
            'created_at'
        ]);

    if ($q === '') {
        // 🔹 Sem busca => restringe ao MÊS REAL (convertendo created_at para TZ local)
        $qbCad->whereBetween(
            DB::raw("CONVERT_TZ(created_at, @@session.time_zone, ?)"),
            [$TZ_SQL, $inicioPeriodo, $fimExclusivo]
        );
    } else {
        // 🔹 Com busca => GLOBAL (sem filtro de data)
        $digits = preg_replace('/\D+/', '', $q);
        $tokens = preg_split('/\s+/', $q, -1, PREG_SPLIT_NO_EMPTY);

        $qbCad->where(function ($w) use ($tokens, $digits) {
            if ($digits !== '') {
                $w->orWhere('cpf_cnpj', 'like', "%{$digits}%")
                  ->orWhere('matricula_servidor_publico', 'like', "%{$digits}%")
                  ->orWhere('contrato_codigo_contrato', 'like', "%{$digits}%");
            }
            foreach ($tokens as $t) {
                $w->orWhere('full_name', 'like', "%{$t}%")
                  ->orWhere('email', 'like', "%{$t}%")
                  ->orWhere('orgao_publico', 'like', "%{$t}%")
                  ->orWhere('situacao_servidor', 'like', "%{$t}%")
                  ->orWhere('agente_responsavel', 'like', "%{$t}%");
            }
        });
    }

    $paginator = $qbCad
        ->orderByDesc('created_at')
        ->paginate($perPage, ['*'], $pageName, $page);

    $items = $paginator->getCollection()->map(function (\App\Models\AgenteCadastro $c) {
        return [
            'id'                         => $c->id,
            'full_name'                  => $c->full_name,
            'cpf_cnpj'                   => $c->cpf_cnpj,
            'matricula_servidor_publico' => $c->matricula_servidor_publico,
            'email'                      => $c->email,
            'orgao_publico'              => $c->orgao_publico,
            'situacao_servidor'          => $c->situacao_servidor,
            'contrato_codigo_contrato'   => $c->contrato_codigo_contrato,
            'contrato_prazo_meses'       => $c->contrato_prazo_meses,
            'contrato_taxa_antecipacao'  => $c->contrato_taxa_antecipacao,
            'contrato_mensalidade'       => $c->contrato_mensalidade,
            'contrato_valor_antecipacao' => $c->contrato_valor_antecipacao,
            'contrato_margem_disponivel' => $c->contrato_margem_disponivel,
            'contrato_status_contrato'   => $c->contrato_status_contrato,
            'agente_responsavel'         => $c->agente_responsavel,
            'observacoes'                => $c->observacoes,
            'status_norm'                => strtolower((string) ($c->contrato_status_contrato ?? 'pendente')),
        ];
    })->values();

    return response()->json([
        'data' => $items,
        'meta' => [
            'current_page' => $paginator->currentPage(),
            'last_page'    => $paginator->lastPage(),
            'from'         => $paginator->firstItem() ?? 0,
            'to'           => $paginator->lastItem() ?? 0,
            'total'        => $paginator->total(),
        ],
    ]);
}







    /**
     * Gera/mostra o PDF do cadastro (inline por padrão).
     * Use ?dl=1 para forçar download.
     * Se o DomPDF não estiver instalado, retorna a view HTML como fallback.
     */
    public function cadastroPdf($id)
    {
        $cad = \App\Models\AgenteCadastro::findOrFail($id);

        // Antecipações em array (se vier JSON/string)
        $anticipations = [];
        $raw = $cad->anticipations_json;
        if (is_string($raw)) { $raw = json_decode($raw, true) ?: []; }
        if (is_array($raw))  { $anticipations = array_values($raw); }

        // -> tenta em ordem: admin/, pdf/, raiz
        $view = collect([
            'admin.cadastro-agente',
            'pdf.cadastro-agente',
            'cadastro-agente',
        ])->first(fn ($v) => view()->exists($v));

        if (!$view) {
            abort(500, 'View do PDF não encontrada. Coloque em resources/views/pdf/cadastro-agente.blade.php ou admin/cadastro-agente.blade.php');
        }

        $now       = now();
        $filename  = 'cadastro-'.\Illuminate\Support\Str::slug($cad->full_name ?: 'associado').'-'.$cad->id.'.pdf';
        $download  = request()->boolean('dl'); // ?dl=1 para forçar download

        // Preferencial: barryvdh/laravel-dompdf
        if (class_exists(\Barryvdh\DomPDF\Facade\Pdf::class)) {
            $pdf = \Barryvdh\DomPDF\Facade\Pdf::loadView($view, compact('cad','anticipations','now'))
                ->setPaper('a4');
            return $download ? $pdf->download($filename) : $pdf->stream($filename);
        }

        // Fallback: wrapper registrado no container
        if (app()->bound('dompdf.wrapper')) {
            $pdf = app('dompdf.wrapper');
            $pdf->loadView($view, compact('cad','anticipations','now'))->setPaper('a4');
            return $download ? $pdf->download($filename) : $pdf->stream($filename);
        }

        // Último recurso: retorna o HTML (útil para debug)
        return response()->view($view, compact('cad','anticipations','now'));
    }

    // ===================== helpers =====================
    /**
 * Garante que o papel exista na tabela roles e retorna o ID.
 */
private function ensureRoleId(string $roleName): int
{
    $roleName = strtolower(trim($roleName));

    $roleId = (int) DB::table('roles')->where('name', $roleName)->value('id');
    if ($roleId > 0) return $roleId;

    return (int) DB::table('roles')->insertGetId([
        'name'       => $roleName,
        'created_at' => now(),
        'updated_at' => now(),
    ]);
}

/**
 * Upsert no pivot role_user (evita duplicar e mantém updated_at).
 */
private function upsertRoleUser(int $userId, int $roleId): void
{
    $now = now();

    $exists = DB::table('role_user')
        ->where('user_id', $userId)
        ->where('role_id', $roleId)
        ->exists();

    if ($exists) {
        DB::table('role_user')
            ->where('user_id', $userId)
            ->where('role_id', $roleId)
            ->update(['updated_at' => $now]);
    } else {
        DB::table('role_user')->insert([
            'user_id'    => $userId,
            'role_id'    => $roleId,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
    }
}

private function onlyDigits(?string $s): string {
    return preg_replace('/\D+/', '', (string) $s);
}

private function parseMoneyBr($v): float {
    if (is_numeric($v)) return (float)$v;
    $s = preg_replace('/[^\d,.\-]+/','', (string)$v);
    $s = str_replace('.', '', $s);
    $s = str_replace(',', '.', $s);
    return (float)$s;
}

protected function buildCadastrosQuery(string $q)
{
    $qb = AgenteCadastro::query()->select([
        'id','full_name','cpf_cnpj','email',
        'matricula_servidor_publico',
        'orgao_publico','situacao_servidor',
        'contrato_codigo_contrato','contrato_prazo_meses','contrato_taxa_antecipacao',
        'contrato_mensalidade','contrato_valor_antecipacao','contrato_margem_disponivel',
        'contrato_status_contrato','agente_responsavel','observacoes',
        'created_at'
    ]);

    if ($q !== '') {
        $digits = preg_replace('/\D+/', '', $q);
        $tokens = preg_split('/\s+/', $q, -1, PREG_SPLIT_NO_EMPTY);

        $qb->where(function ($w) use ($tokens, $digits) {
            if ($digits !== '') {
                $w->orWhere('cpf_cnpj', 'like', "%{$digits}%")
                  ->orWhere('matricula_servidor_publico', 'like', "%{$digits}%")
                  ->orWhere('contrato_codigo_contrato', 'like', "%{$digits}%");
            }
            foreach ($tokens as $t) {
                $w->orWhere('full_name', 'like', "%{$t}%")
                  ->orWhere('email', 'like', "%{$t}%")
                  ->orWhere('orgao_publico', 'like', "%{$t}%")
                  ->orWhere('situacao_servidor', 'like', "%{$t}%")
                  ->orWhere('agente_responsavel', 'like', "%{$t}%");
            }
        });
    }

    return $qb;
}


    private function normalizeTxt(string $raw): string
    {
        $enc = @mb_detect_encoding($raw, ['UTF-8','Windows-1252','ISO-8859-1'], true) ?: 'UTF-8';
        $txt = $enc !== 'UTF-8' ? @mb_convert_encoding($raw, 'UTF-8', $enc) : $raw;
        $txt = str_replace("\x0C", "\n", $txt);
        $txt = str_replace(["\r\n","\r"], "\n", $txt);
        $txt = preg_replace('/[ \t\x{00A0}\x{2007}\x{202F}]+/u', ' ', $txt);
        return $txt;
    }

    /**
     * Normaliza dígitos (remove tudo que não for 0-9).
     */
    private function normDigits(?string $s): string
    {
        return preg_replace('/\D+/', '', (string) $s);
    }

    /**
     * Normaliza texto (minúsculo, sem acentos, trim e espaço simples).
     */
    private function normText(?string $s): string
    {
        $t = \Illuminate\Support\Str::of((string)$s)
            ->lower()
            ->ascii()              // tira acentos
            ->replaceMatches('/\s+/', ' ')
            ->trim();
        return (string) $t;
    }

    /**
     * Tenta localizar o cadastro pela linha do arquivo (ordem: CPF -> Matrícula -> Nome+Órgão).
     * Retorna null se houver ambiguidade no match por nome.
     */
    private function findCadastroByRow(?string $cpf, ?string $matricula, ?string $nome, ?string $orgao): ?\App\Models\AgenteCadastro
    {
        // 1) CPF
        $cpfDigits = $this->normDigits($cpf);
        if ($cpfDigits !== '') {
            $cad = \App\Models\AgenteCadastro::whereRaw(
                "REPLACE(REPLACE(REPLACE(REPLACE(cpf_cnpj,'.',''),'-',''),'/',''),' ','') LIKE ?",
                ["%{$cpfDigits}%"]
            )->first();
            if ($cad) return $cad;
        }

        // 2) Matrícula
        $mat = $this->normDigits($matricula);
        if ($mat !== '') {
            $cad = \App\Models\AgenteCadastro::whereRaw(
                "REPLACE(REPLACE(REPLACE(REPLACE(matricula_servidor_publico,'.',''),'-',''),'/',''),' ','') = ?",
                [$mat]
            )->first();
            if ($cad) return $cad;
        }

        // 3) Nome + (opcional) Órgão — só aceita se houver match único
        $nomeTxt = trim((string)$nome);
        if ($nomeTxt !== '') {
            $qb = \App\Models\AgenteCadastro::query()
                ->where('full_name', 'like', "%{$nomeTxt}%");
            if ($orgao && trim($orgao) !== '') {
                $qb->where('orgao_publico', 'like', "%{$orgao}%");
            }
            $cands = $qb->limit(2)->get();
            if ($cands->count() === 1) return $cands->first();
        }

        return null;
    }

    private function parseDataPreferencial(?string $dataStr, string $fileBaseName): ?Carbon
{
    // 1) se vier no campo (dd/mm/aaaa ou aaaa-mm-dd)
    if ($dataStr) {
        $dataStr = trim($dataStr);
        $try = [
            'd/m/Y','d-m-Y','Y-m-d','Y/m/d','dmY','Ymd',
        ];
        foreach ($try as $fmt) {
            try { return Carbon::createFromFormat($fmt, $dataStr, 'America/Sao_Paulo'); } catch (\Throwable $e) {}
        }
    }
    // 2) tenta detectar AAAA-MM no nome do arquivo
    if (preg_match('/(20\d{2})[-_\.]?(0[1-9]|1[0-2])/', $fileBaseName, $m)) {
        return Carbon::createFromFormat('Y-m-d H:i:s', "{$m[1]}-{$m[2]}-01 00:00:00", 'America/Sao_Paulo');
    }
    // 3) fallback
    return now('America/Sao_Paulo');
}

private function parseCompetenciaArquivo(?string $comp): ?string
{
    if (!$comp) return null;
    $comp = trim($comp);
    // aceita AAAA-MM, AAAAMM, MM/AAAA, MMAAAA
    if (preg_match('/^(20\d{2})[-\/]?([01]\d)$/', $comp, $m)) {
        return sprintf('%04d-%02d', (int)$m[1], (int)$m[2]);
    }
    if (preg_match('/^([01]\d)[-\/]?(20\d{2})$/', $comp, $m)) {
        return sprintf('%04d-%02d', (int)$m[2], (int)$m[1]);
    }
    return null;
}

private function competenciaJanela0605(Carbon $data): string
{
    $cutoff = (int) env('FECHAMENTO_DIA', 5);
    $over  = trim((string) env('FECHAMENTO_OVERRIDES', '')); // "2025-11=6,2025-12=7"
    $map = [];
    if ($over !== '') {
        foreach (explode(',', $over) as $par) {
            [$k,$v] = array_pad(explode('=', $par), 2, null);
            if ($k && $v && preg_match('/^20\d{2}-[01]\d$/', $k)) $map[$k] = (int) $v;
        }
    }

    $y = (int) $data->format('Y');
    $m = (int) $data->format('m');
    $key = sprintf('%04d-%02d', $y, $m);
    $limite = $map[$key] ?? $cutoff;

    // '>' para manter a semântica que você fixou nos scripts
    if ((int)$data->format('d') > $limite) {
        // vira o próximo mês
        $data = $data->copy()->addMonthNoOverflow()->startOfMonth();
        return $data->format('Y-m');
    }
    // permanece no mês corrente
    return $key;
}
private function casarMensalidade(AgenteCadastro $cadastro, string $competencia, float $valor, ?string $contrato = null): ?PagamentoMensalidade
{
    // 1) casamento forte: cpf+competência+valor+contrato
    if ($contrato) {
        $m = PagamentoMensalidade::where('agente_cadastro_id', $cadastro->id)
            ->where('competencia', $competencia)
            ->where(function($q) use ($valor){
                $q->whereBetween('valor', [$valor-0.01, $valor+0.01])
                  ->orWhereBetween('valor_previsto', [$valor-0.01, $valor+0.01]);
            })
            ->where(function($q) use ($contrato){
                $q->where('contrato_codigo', $contrato)->orWhere('contrato', $contrato);
            })
            ->orderByDesc('id')
            ->first();
        if ($m) return $m;
    }

    // 2) cpf+competência+valor
    $m = PagamentoMensalidade::where('agente_cadastro_id', $cadastro->id)
        ->where('competencia', $competencia)
        ->where(function($q) use ($valor){
            $q->whereBetween('valor', [$valor-0.01, $valor+0.01])
              ->orWhereBetween('valor_previsto', [$valor-0.01, $valor+0.01]);
        })
        ->orderByDesc('id')
        ->first();
    if ($m) return $m;

    // 3) cpf+competência (única)
    $m = PagamentoMensalidade::where('agente_cadastro_id', $cadastro->id)
        ->where('competencia', $competencia)
        ->whereIn('status', ['pendente','3','5','6','S']) // pendentes/problemáticos
        ->orderByDesc('id')
        ->first();

    return $m;
}

// --- 3) Importa o arquivo e grava/atualiza pagamentos_mensalidades ---
public function baixaUpload(Request $r)
{
    $r->validate([
        'abase' => ['required','file','mimetypes:text/plain,text/csv,text/tab-separated-values'],
    ], ['abase.required' => 'Selecione o arquivo ABASE.txt.']);

    $user = $r->user();
    $file = $r->file('abase');

    // Guarda com carimbo
    $folder   = 'retornos/'.now('America/Sao_Paulo')->format('Ymd_His');
    $baseName = \Illuminate\Support\Str::slug(pathinfo($file->getClientOriginalName(), PATHINFO_FILENAME)).'.txt';
    $stored   = $file->storeAs($folder, $baseName);
    $absPath  = storage_path('app/'.$stored);

    // Lê (UTF-8)
    $raw   = file($absPath, FILE_IGNORE_NEW_LINES) ?: [];
    $lines = array_map(function($l){
        $enc = mb_detect_encoding($l, ['UTF-8','ISO-8859-1','Windows-1252'], true) ?: 'UTF-8';
        return $enc === 'UTF-8' ? $l : mb_convert_encoding($l, 'UTF-8', $enc);
    }, $raw);

    // Referência do cabeçalho (YYYY-MM-01)
    $headerText = implode("\n", array_slice($lines, 0, 40));
    $refYmd     = $this->parseAbaseReferencia($headerText) ?? now('America/Sao_Paulo')->format('Y-m-01');

    // Sumário para o drawer + contadores do toast
    $sum = [
        'arquivo'          => $stored,
        'referencia_month' => $refYmd,
        'total_linhas'     => count($lines),
        'criados'          => 0,
        'atualizados'      => 0, // mantemos, embora duplicados sejam "ignorados"
        'erros'            => 0,
        'por_status'       => [ '1'=>0,'2'=>0,'3'=>0,'4'=>0,'5'=>0,'6'=>0,'S'=>0 ],
        'total_valor'      => 0.0,
        'itens'            => [
            'ok'              => [],
            'duplicados'      => [],
            'migrados'        => [], // duplicado onde fizemos backfill do cadastro
            'nao_encontrados' => [], // criados sem vínculo
            'erros'           => [],
        ],
    ];

    // Contadores do toast
    $created = 0; $dups = 0; $vinculados = 0; $concluidos = 0; $novosCad = 0; // autocriação desativada

    $importUuid = (string) \Illuminate\Support\Str::uuid();
    $normDigits = fn($s) => preg_replace('/\D+/', '', (string)$s);

    DB::beginTransaction();
    try {
        foreach ($lines as $i => $line) {
            $row = $this->parseAbaseLinha($line);
            if (!$row) continue;

            try {
                $cpf       = $row['cpf'];
                $valor     = (float)$row['valor'];
                $status    = (string)$row['status_code'];
                $matricula = $row['matricula'] ?: null;
                $orgao     = $row['orgao_pagto'] ?: null;
                $nome      = $row['nome'] ?: null;

                // casamento inteligente (CPF -> Matrícula -> Nome+Órgão)
                $cad = $this->findCadastroByRow($cpf, $matricula, $nome, $orgao);

                // upsert por (cpf_cnpj, referencia_month)
                $existing = \App\Models\PagamentoMensalidade::where('cpf_cnpj',$cpf)
                    ->whereDate('referencia_month', $refYmd)
                    ->first();

                if ($existing) {
                    // Duplicado = mantém registro; apenas faz backfill do vínculo se não houver
                    $dups++;
                    if (!$existing->agente_cadastro_id && $cad) {
                        $existing->agente_cadastro_id = $cad->id;
                        $existing->save();
                        $vinculados++;
                        $sum['itens']['migrados'][] = [
                            'linha' => $i+1, 'cpf' => $cpf, 'nome' => $nome, 'valor' => $valor, 'status'=> $status
                        ];
                    } else {
                        $sum['itens']['duplicados'][] = [
                            'linha' => $i+1, 'cpf' => $cpf, 'nome' => $nome, 'valor' => $valor, 'status'=> $status
                        ];
                    }

                    // Mesmo em duplicado, atualiza resumo por status/valor
                    $sum['por_status'][$status] = ($sum['por_status'][$status] ?? 0) + 1;
                    $sum['total_valor']        += $valor;

                    // Checa conclusão (3 recebidos) se houver cadastro
                    if ($cad) {
                        $cntOk = \App\Models\PagamentoMensalidade::where('agente_cadastro_id', $cad->id)
                            ->whereIn('status_code', ['1','4'])
                            ->count();
                        if ($cntOk >= 3 && (strtolower((string)$cad->contrato_status_contrato) !== 'concluído')) {
                            $cad->update(['contrato_status_contrato' => 'Concluído']);
                            $concluidos++;
                        }
                    }
                    continue;
                }

                // novo lançamento
                $payload = [
                    'created_by_user_id' => $user?->id,
                    'import_uuid'        => $importUuid,
                    'referencia_month'   => $refYmd,
                    'status_code'        => $status,
                    'matricula'          => $matricula,
                    'orgao_pagto'        => $orgao,
                    'nome_relatorio'     => $nome,
                    'cpf_cnpj'           => $cpf,
                    'valor'              => $valor,
                    'source_file_path'   => $stored,
                    'agente_cadastro_id' => $cad?->id,
                ];

                \App\Models\PagamentoMensalidade::create($payload);
                $created++;
                if ($cad) {
                    $vinculados++;
                } else {
                    $sum['itens']['nao_encontrados'][] = [
                        'linha' => $i+1, 'cpf' => $cpf, 'nome' => $nome, 'valor' => $valor, 'status'=> $status
                    ];
                }

                $sum['por_status'][$status] = ($sum['por_status'][$status] ?? 0) + 1;
                $sum['total_valor']        += $valor;
                $sum['itens']['ok'][] = [
                    'linha' => $i+1, 'cpf' => $cpf, 'nome' => $nome, 'valor' => $valor, 'status'=> $status
                ];

                // Checa conclusão (3 recebidos) para o cadastro (se houver)
                if ($cad) {
                    $cntOk = \App\Models\PagamentoMensalidade::where('agente_cadastro_id', $cad->id)
                        ->whereIn('status_code', ['1','4'])
                        ->count();
                    if ($cntOk >= 3 && (strtolower((string)$cad->contrato_status_contrato) !== 'concluído')) {
                        $cad->update(['contrato_status_contrato' => 'Concluído']);
                        $concluidos++;
                    }
                }

            } catch (\Throwable $e) {
                $sum['erros']++;
                $sum['itens']['erros'][] = [
                    'linha'  => $i+1,
                    'raw'    => $line,
                    'motivo' => $e->getMessage(),
                ];
                \Log::warning('[RETORNO] erro na linha', ['line'=>$i+1,'err'=>$e->getMessage()]);
            }
        }

        DB::commit();
    } catch (\Throwable $e) {
        DB::rollBack();
        throw $e;
    }

    // guarda resumo 30 min (usado pelo drawer/detalhar)
    $token = \Illuminate\Support\Str::random(24);
    \Illuminate\Support\Facades\Cache::put("retorno:$token", $sum, now()->addMinutes(30));

    // ✅ Toast no topo (mensagem antiga que você quer)
    $toast = "Importação concluída: {$created} lançamentos, {$dups} duplicados ignorados, ".
             "{$vinculados} vinculados a cadastros, {$concluidos} contratos concluídos, ".
             "{$novosCad} cadastros criados (autocriação desativada).";

    return redirect()
        ->route('admin.dashboardadmin')
        ->with('ok', $toast) // <<< volta a mostrar o badge do topo
        ->with('retorno_token', $token)
        ->with('retorno_counts', [
            'arquivo'          => $sum['arquivo'],
            'referencia_month' => $sum['referencia_month'],
            'total_linhas'     => $sum['total_linhas'],
            'criados'          => $created,          // reflete o toast
            'atualizados'      => $sum['atualizados'],
            'duplicados'       => $dups,             // extra, caso queira exibir em algum lugar
            'vinculados'       => $vinculados,       // "
            'concluidos'       => $concluidos,       // "
            'erros'            => $sum['erros'],
            'por_status'       => $sum['por_status'],
            'total_valor'      => number_format($sum['total_valor'], 2, ',', '.'),
            'token'            => $token,
        ]);
}

// --- 1) Extrai "YYYY-MM-01" do cabeçalho (ex.: "Referência: 10/2025") ---
private function parseAbaseReferencia(string $txt): ?string
{
    // procura algo como "Referência: 10/2025" (com ou sem acento)
    if (preg_match('/Refer[eê]ncia:\s*(\d{2})\s*\/\s*(20\d{2})/iu', $txt, $m)) {
        $mm = (int)$m[1]; $yy = (int)$m[2];
        return sprintf('%04d-%02d-01', $yy, $mm);
    }
    // fallback: primeira ocorrência de mm/aaaa em qualquer linha
    if (preg_match('/\b([01]\d)\s*\/\s*(20\d{2})\b/u', $txt, $m)) {
        $mm = (int)$m[1]; $yy = (int)$m[2];
        return sprintf('%04d-%02d-01', $yy, $mm);
    }
    return null;
}


// --- 2) Interpreta UMA linha de lançamento do relatório ---
// Retorna array com: status_code, matricula, nome, valor, orgao_pagto, cpf
private function parseAbaseLinha(string $line): ?array
{
    $line = trim($line);
    if ($line === '') return null;

    // Linhas que NÃO são lançamentos
    $ignores = [
        'Governo do Estado', 'Empresa de Tecnologia', 'Relatório dos Lançamentos',
        'Entidade:', 'STATUS MATRICULA', '======', 'Órgão Pagamento:',
        'Legenda do Status', 'Total do Status:'
    ];
    foreach ($ignores as $kw) {
        if (stripos($line, $kw) !== false) return null;
    }

    // quebra por 2+ espaços (mantém tokens de colunas)
    $parts = preg_split('/\s{2,}/u', $line, -1, PREG_SPLIT_NO_EMPTY);
    if (!$parts || count($parts) < 6) return null;

    // CPF = último token (11 dígitos)
    $cpfTok = $parts[count($parts)-1] ?? '';
    if (!preg_match('/^\d{11}$/', $cpfTok)) return null;

    // ORGAO PAGTO = penúltimo token (geralmente "001","090","911" etc.)
    $orgaoTok = $parts[count($parts)-2] ?? '';

    // VALOR = antepenúltimo token (ex.: "100,00" / "275,46")
    $valorTok = $parts[count($parts)-3] ?? '';

    // STATUS = primeiro token (1,2,3,4,5,6,S)
    $statusTok = $parts[0] ?? '';
    if (!preg_match('/^[12-6S]$/', strtoupper($statusTok))) return null;
    $statusTok = strtoupper($statusTok);

    // MATRÍCULA = segundo token (ex.: "160863-X", "015270-6")
    $matTok = $parts[1] ?? '';

    // NOME = terceiro token (a coluna NOME vem inteira em um único token após split 2+ espaços)
    $nomeTok = $parts[2] ?? '';

    // normalizadores
    $normDigits = fn($s) => preg_replace('/\D+/', '', (string)$s);
    $parseMoney = function ($s) {
        $s = preg_replace('/[^\d,.\-]+/', '', (string)$s);
        $s = str_replace('.', '', $s);
        $s = str_replace(',', '.', $s);
        return is_numeric($s) ? (float)$s : null;
    };

    $valor = $parseMoney($valorTok);
    if ($valor === null) return null;

    return [
        'status_code' => $statusTok,
        'matricula'   => trim($matTok),
        'nome'        => trim($nomeTok),
        'valor'       => $valor,
        'orgao_pagto' => trim($orgaoTok),
        'cpf'         => $normDigits($cpfTok),
    ];
}


    /**
     * Stream do arquivo da mensalidade salvo em storage/app/public/baixas.
     * Aceita caminhos antigos iniciando por "storage/" ou "public/".
     */
    public function streamMensalidadeFile(PagamentoMensalidade $mensalidade)
    {
        $rel = (string) $mensalidade->source_file_path;
        if ($rel === '') abort(404);

        $rel = preg_replace('~^/?(?:storage/|public/)~', '', $rel);

        if (!Storage::disk('public')->exists($rel)) {
            abort(404);
        }

        $path = Storage::disk('public')->path($rel);
        $mime = Storage::disk('public')->mimeType($rel) ?: 'text/plain';

        return response()->file($path, [
            'Content-Type'  => $mime,
            'Cache-Control' => 'private, max-age=31536000',
        ]);
    }

/**
 * Cria um usuário via Fortify e atribui o papel selecionado (agente|analista).
 * A view envia: name, email, password, password_confirmation e role.
 */
public function storeAgente(Request $request, CreatesNewUsers $creator)
{
    // Papel vindo do select da view
    $role = strtolower(trim((string) $request->input('role', 'agente')));

    // trava de segurança: só aceita esses dois
    if (!in_array($role, ['agente', 'analista'], true)) {
        return back()
            ->withErrors(['role' => 'Papel inválido. Selecione "agente" ou "analista".'])
            ->withInput();
    }

    // Fortify/Jetstream normalmente já valida os campos,
    // mas garantimos que o role vai junto e termos = true quando necessário.
    $input = $request->only(['name', 'email', 'password', 'password_confirmation']);

    if (Jetstream::hasTermsAndPrivacyPolicyFeature()) {
        $input['terms'] = true;
    }

    $user = null;

    DB::transaction(function () use ($creator, $input, $role, &$user) {
        // cria usuário (Fortify cuida de validação/unique email/password rules)
        $user = $creator->create($input);

        // garante role e aplica no pivot
        $roleId = $this->ensureRoleId($role);
        $this->upsertRoleUser((int) $user->id, (int) $roleId);
    });

    $label = $role === 'analista' ? 'Analista' : 'Agente';

    return back()->with('ok', $label.' "'.$user->name.'" criado com sucesso!');
}

// ===================== EXPORT: CADASTROS (CSV) =====================
public function exportCadastrosCsv(Request $r)
{
    $q        = trim((string)$r->input('q',''));
    $status   = trim((string)$r->input('status',''));
    $dateFrom = $r->input('date_from');
    $dateTo   = $r->input('date_to');
    $all      = $r->boolean('all');
    $full     = $r->boolean('full', true);

    $qb = $full ? AgenteCadastro::query()
                : $this->buildCadastrosQuery($q);

    if ($q !== '' && $full) {
        $digits = preg_replace('/\D+/', '', $q);
        $qb->where(function ($w) use ($q, $digits) {
            $w->where('full_name', 'like', "%{$q}%")
              ->orWhere('email', 'like', "%{$q}%")
              ->orWhere('contrato_codigo_contrato', 'like', "%{$q}%");
            if ($digits !== '') $w->orWhere('cpf_cnpj', 'like', "%{$digits}%");
        });
    }

    if ($status !== '') { $qb->where('contrato_status_contrato', $status); }

    if (!$all && $dateFrom) { $qb->whereDate('created_at', '>=', $dateFrom); }
    if (!$all && $dateTo)   { $qb->whereDate('created_at', '<=', $dateTo); }

    $file = ($full ? 'cadastros-completo-' : 'cadastros-') . now()->format('Ymd_His') . '.csv';
    $headers = [
        'Content-Type'        => 'text/csv; charset=UTF-8',
        'Content-Disposition' => 'attachment; filename="'.$file.'"',
        'Cache-Control'       => 'private, max-age=0, no-cache',
    ];

    $columns = Schema::getColumnListing((new AgenteCadastro)->getTable());
    $hasBirth = in_array('birth_date', $columns, true);

    return response()->streamDownload(function() use ($qb, $columns, $hasBirth){
        $out = fopen('php://output', 'w');

        // BOM UTF-8
        echo chr(0xEF).chr(0xBB).chr(0xBF);

        // Cabeçalho: as colunas originais + "Idade"
        $headerRow = $columns;
        $headerRow[] = 'Idade';
        fputcsv($out, $headerRow, ';');

        foreach ($qb->orderBy('id')->cursor() as $row) {
            $vals = [];
            foreach ($columns as $col) {
                $v = $row->{$col};
                if ($v instanceof \Carbon\Carbon) {
                    $v = $v->toDateTimeString();
                } elseif (is_array($v) || is_object($v)) {
                    $v = json_encode($v, JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
                }
                $vals[] = $v;
            }

            // NOVO: Idade (derivada de birth_date, se existir)
            $idade = '';
            if ($hasBirth && !empty($row->birth_date)) {
                try {
                    $idade = \Carbon\Carbon::parse($row->birth_date)->age;
                } catch (\Throwable $e) { $idade = ''; }
            }
            $vals[] = $idade;

            fputcsv($out, $vals, ';');
        }
        fclose($out);
    }, $file, $headers);
}


// ===================== EXPORT: PAGAMENTOS (CSV) =====================
public function exportPagamentosCsv(Request $r)
{
    $status   = trim((string)$r->input('status',''));
    $forma    = trim((string)$r->input('forma',''));
    $dateFrom = $r->input('date_from');
    $dateTo   = $r->input('date_to');
    $mes      = $r->input('mes'); // opcional (janela 06→05)

    $qb = TesourariaPagamento::query()
        ->from('tesouraria_pagamentos as t')
        ->leftJoin('agente_cadastros as c', 'c.id', '=', 't.agente_cadastro_id') // NOVO: para birth_date
        ->select([
            't.id','t.full_name','t.cpf_cnpj','t.contrato_codigo_contrato',
            't.status','t.valor_pago','t.contrato_valor_antecipacao',
            't.paid_at','t.created_at','t.forma_pagamento','t.agente_responsavel',
            'c.birth_date as cad_birth_date', // NOVO
        ]);

    if ($status !== '') { $qb->where('t.status', $status); }
    if ($forma  !== '') { $qb->where('t.forma_pagamento','like',"%{$forma}%"); }

    if ($dateFrom || $dateTo) {
        if ($dateFrom) $qb->where(DB::raw('COALESCE(t.paid_at, t.created_at)'), '>=', $dateFrom);
        if ($dateTo)   $qb->where(DB::raw('COALESCE(t.paid_at, t.created_at)'), '<=', $dateTo);
    } elseif ($mes && preg_match('~^\d{4}-\d{2}$~', $mes)) {
        $tz = config('app.timezone') ?: (env('APP_TIMEZONE') ?: 'America/Sao_Paulo');
        $dia = (int) (config('app.fechamento_dia') ?? env('FECHAMENTO_DIA', 5));
        $base = \Carbon\Carbon::createFromFormat('Y-m', $mes, $tz)->startOfMonth()->day($dia)->startOfDay()->addDay(); // 06/M
        $end  = $base->copy()->addMonthNoOverflow(); // 06/(M+1)
        [$betweenSql, $betweenArgs] = $this->competenciaSql('t', $base, $end);
        $qb->whereRaw($betweenSql, $betweenArgs);
    }

    $rows = $qb->orderBy(DB::raw('COALESCE(t.paid_at, t.created_at)'))->get();

    $file = 'pagamentos-'.now()->format('Ymd_His').'.csv';
    $headers = [
        'Content-Type'        => 'text/csv; charset=UTF-8',
        'Content-Disposition' => 'attachment; filename="'.$file.'"',
    ];

    return response()->streamDownload(function() use ($rows){
        $out = fopen('php://output','w');
        echo chr(0xEF).chr(0xBB).chr(0xBF);

        // Cabeçalho original + Data Nasc. + Idade (APÊNDICE para não quebrar ordem existente)
        fputcsv($out, [
            'ID','Nome','CPF/CNPJ','Contrato','Status',
            'Valor Pago','Valor Base (Antecip.)','Pago em','Criado em',
            'Forma','Agente Responsável',
            'Data Nasc.','Idade' // NOVO
        ], ';');

        foreach ($rows as $p) {
            // NOVO: formatar Data Nasc. (se disponível no cadastro)
            $bdFmt = '';
            $idade = '';
            if (!empty($p->cad_birth_date)) {
                try {
                    $bd   = \Carbon\Carbon::parse($p->cad_birth_date);
                    $bdFmt = $bd->format('d/m/Y');
                    $idade = $bd->age;
                } catch (\Throwable $e) { $bdFmt = ''; $idade = ''; }
            }

            fputcsv($out, [
                $p->id,
                $p->full_name,
                $p->cpf_cnpj,
                $p->contrato_codigo_contrato,
                $p->status,
                number_format((float)$p->valor_pago, 2, ',', '.'),
                number_format((float)$p->contrato_valor_antecipacao, 2, ',', '.'),
                $p->paid_at ? \Illuminate\Support\Carbon::parse($p->paid_at)->format('d/m/Y H:i') : '',
                $p->created_at ? \Illuminate\Support\Carbon::parse($p->created_at)->format('d/m/Y H:i') : '',
                $p->forma_pagamento,
                $p->agente_responsavel,
                $bdFmt,   // NOVO
                $idade,   // NOVO
            ], ';');
        }
        fclose($out);
    }, $file, $headers);
}



// ===================== EXPORT: MENSALIDADES (CSV) =====================
public function exportMensalidadesCsv(Request $r)
{
    $status  = trim((string)$r->input('status',''));
    $orgao   = trim((string)$r->input('orgao',''));
    $refFrom = $r->input('ref_from');
    $refTo   = $r->input('ref_to');

    $qb = PagamentoMensalidade::query()
        ->with(['cadastro:id,full_name,birth_date']) // NOVO: birth_date
        ->select([
            'id','agente_cadastro_id','nome_relatorio','cpf_cnpj','referencia_month',
            'valor','status_code','orgao_pagto','created_at'
        ]);

    if ($status === 'ok') {
        $qb->whereIn('status_code', ['1','4']);
    } elseif ($status !== '') {
        $qb->where('status_code', $status);
    }

    if ($orgao !== '') { $qb->where('orgao_pagto','like', "%{$orgao}%"); }

    if ($refFrom) { $qb->whereDate('referencia_month', '>=', $refFrom.'-01'); }
    if ($refTo)   { $qb->whereDate('referencia_month', '<=', $refTo.'-28'); }

    $rows = $qb->orderBy('referencia_month')->get();

    $labels = [
        '1'=>'Efetivado','4'=>'Efetivado c/ diferença','2'=>'Sem margem (temp.)',
        '3'=>'Não lançado (outros)','5'=>'Problemas técnicos','6'=>'Com erros','S'=>'Compra dívida / Suspensão'
    ];

    $file = 'mensalidades-'.now()->format('Ymd_His').'.csv';
    $headers = [
        'Content-Type'        => 'text/csv; charset=UTF-8',
        'Content-Disposition' => 'attachment; filename="'.$file.'"',
    ];

    return response()->streamDownload(function() use ($rows, $labels){
        $out = fopen('php://output','w');
        echo chr(0xEF).chr(0xBB).chr(0xBF);

        // Cabeçalho original + Data Nasc. + Idade (apêndice)
        fputcsv($out, [
            'ID','Nome','CPF/CNPJ','Referência','Valor','Status','Órgão Pagto',
            'Cadastro ID','Criado em',
            'Data Nasc.','Idade' // NOVO
        ], ';');

        foreach ($rows as $m) {
            $nome = optional($m->cadastro)->full_name ?: $m->nome_relatorio;
            $ref  = $m->referencia_month ? \Illuminate\Support\Carbon::parse($m->referencia_month)->format('m/Y') : '';

            // NOVO: Data Nasc. e Idade (se houver cadastro vinculado)
            $bdFmt = '';
            $idade = '';
            $bdVal = optional($m->cadastro)->birth_date;
            if (!empty($bdVal)) {
                try {
                    $bd    = \Carbon\Carbon::parse($bdVal);
                    $bdFmt = $bd->format('d/m/Y');
                    $idade = $bd->age;
                } catch (\Throwable $e) { $bdFmt = ''; $idade = ''; }
            }

            fputcsv($out, [
                $m->id,
                $nome,
                $m->cpf_cnpj,
                $ref,
                number_format((float)$m->valor, 2, ',', '.'),
                $labels[$m->status_code] ?? $m->status_code,
                $m->orgao_pagto,
                $m->agente_cadastro_id,
                optional($m->created_at)->format('d/m/Y H:i'),
                $bdFmt, // NOVO
                $idade, // NOVO
            ], ';');
        }
        fclose($out);
    }, $file, $headers);
}


    public function agentesList(Request $r)
    {
        $q       = trim((string)$r->input('q',''));
        $perPage = max(1, min(50, (int)$r->input('per_page', 10)));
        $page    = max(1, (int)$r->input('page', 1));

        $roleId = DB::table('roles')->where('name','agente')->value('id');

        $qb = DB::table('users')
            ->select('users.id','users.name','users.email','users.created_at')
            ->join('role_user','role_user.user_id','=','users.id')
            ->where('role_user.role_id', $roleId);

        if ($q !== '') {
            $qb->where(function($w) use ($q){
                $w->where('users.name','like',"%{$q}%")
                  ->orWhere('users.email','like',"%{$q}%");
            });
        }

        $total = (clone $qb)->count();
        $rows  = (clone $qb)
            ->orderByDesc('users.id')
            ->forPage($page, $perPage)
            ->get();

        $data = $rows->map(function($u){
            return [
                'id'           => $u->id,
                'name'         => $u->name,
                'email'        => $u->email,
                'created_at'   => $u->created_at,
                'created_at_br'=> optional($u->created_at)->format('d/m/Y H:i'),
            ];
        });

        return response()->json([
            'data' => $data,
            'meta' => [
                'current_page' => $page,
                'last_page'    => (int) ceil($total / $perPage) ?: 1,
                'total'        => $total,
            ],
        ]);
    }

    public function agenteShow(User $user)
    {
        $roleNames = DB::table('roles')
            ->join('role_user','roles.id','=','role_user.role_id')
            ->where('role_user.user_id', $user->id)
            ->pluck('roles.name')
            ->values();

        return response()->json([
            'id'         => $user->id,
            'name'       => $user->name,
            'email'      => $user->email,
            'roles'      => $roleNames,
            'created_at' => optional($user->created_at)->toDateTimeString(),
        ]);
    }

    public function agenteSetPassword(Request $r, User $user)
    {
        if ($r->boolean('auto')) {
            $pwd = $this->generateStrongPassword();
        } else {
            $v = Validator::make($r->all(), [
                'password' => ['required','confirmed', PasswordRule::min(8)],
            ], [
                'password.required' => 'Informe a nova senha.',
                'password.confirmed'=> 'A confirmação não confere.',
                'password.min'      => 'A senha deve ter pelo menos :min caracteres.',
            ]);

            if ($v->fails()) {
                return response()->json(['error' => $v->errors()->first()], 422);
            }
            $pwd = (string) $r->input('password');
        }

        $user->password = Hash::make($pwd);
        $user->setRememberToken(Str::random(60));
        $user->save();

        $resp = ['message' => 'Senha atualizada com sucesso.'];
        if ($r->boolean('auto')) $resp['password'] = $pwd;

        return response()->json($resp);
    }

    public function agenteSuspender(User $user)
    {
        if ($user->id === auth()->id()) {
            return response()->json(['error' => 'Você não pode suspender a si mesmo.'], 422);
        }

        $agenteRoleId = DB::table('roles')->where('name','agente')->value('id');
        $userRoleId   = DB::table('roles')->where('name','user')->value('id');

        DB::table('role_user')->where([
            'user_id' => $user->id,
            'role_id' => $agenteRoleId,
        ])->delete();

        $existsUser = DB::table('role_user')->where([
            'user_id' => $user->id,
            'role_id' => $userRoleId,
        ])->exists();

        if (!$existsUser) {
            DB::table('role_user')->insert([
                'user_id'    => $user->id,
                'role_id'    => $userRoleId,
                'created_at' => now(),
                'updated_at' => now(),
            ]);
        }

        return response()->json(['message' => 'Agente suspenso com sucesso (papel alterado para "user").']);
    }

    private function generateStrongPassword(int $len = 14): string
    {
        $U='ABCDEFGHJKLMNPQRSTUVWXYZ'; $L='abcdefghijkmnopqrstuvwxyz'; $D='23456789'; $S='!@#$%^&*()-_=+[]{};:,.?';
        $all = $U.$L.$D.$S;
        $pick = function($pool,$n){ $s=''; for($i=0;$i<$n;$i++) $s.=$pool[random_int(0,strlen($pool)-1)]; return $s; };
        $pwd = $pick($U,2).$pick($L,4).$pick($D,3).$pick($S,2);
        while(strlen($pwd) < $len) $pwd .= $pick($all,1);
        return str_shuffle($pwd);
    }

    private function roleIdByName(array $candidateNames): ?int
    {
        $wanted = array_map('strtolower', $candidateNames);

        $all = DB::table('roles')->select('id', 'name')->get();
        Log::debug('roleIdByName: roles disponíveis', [
            'roles' => $all->map(fn($r) => ['id' => (int)$r->id, 'name' => $r->name])->toArray(),
        ]);

        $map = [];
        foreach ($all as $r) {
            $map[strtolower($r->name)] = (int) $r->id;
        }

        foreach ($wanted as $n) {
            if (isset($map[$n])) {
                Log::info('roleIdByName: encontrou papel', ['name' => $n, 'id' => $map[$n]]);
                return $map[$n];
            }
        }

        Log::warning('roleIdByName: papel NÃO encontrado', [
            'procurados' => $wanted,
            'disponiveis' => array_keys($map),
        ]);
        return null;
    }

    public function agentesSuspensosList(Request $r)
    {
        $q       = trim((string)$r->input('q',''));
        $perPage = max(1, min(50, (int)$r->input('per_page', 10)));
        $page    = max(1, (int)$r->input('page', 1));

        Log::info('agentesSuspensosList: início', compact('q','perPage','page'));

        $agenteRoleId = $this->roleIdByName(['agente']);
        $userRoleId   = $this->roleIdByName(['user']);

        Log::info('agentesSuspensosList: role IDs resolvidos', [
            'agenteRoleId' => $agenteRoleId,
            'userRoleId'   => $userRoleId,
        ]);

        if (!$agenteRoleId) {
            Log::error('agentesSuspensosList: papel "agente" não existe em roles');
            return response()->json([
                'data' => [],
                'meta' => ['current_page'=>$page,'last_page'=>1,'total'=>0],
                'error' => 'Papel "agente" não encontrado na tabela roles.',
            ], 200);
        }

        try {
            $qb = DB::table('users as u')
                ->whereNotExists(function($q) use ($agenteRoleId){
                    $q->select(DB::raw(1))
                      ->from('role_user as ru_ag')
                      ->whereColumn('ru_ag.user_id','u.id')
                      ->where('ru_ag.role_id', $agenteRoleId);
                });

            if ($userRoleId) {
                $qb->whereExists(function($q) use ($userRoleId){
                    $q->select(DB::raw(1))
                      ->from('role_user as ru_user')
                      ->whereColumn('ru_user.user_id','u.id')
                      ->where('ru_user.role_id', $userRoleId);
                });
            }

            if ($q !== '') {
                $qb->where(function($w) use ($q){
                    $w->where('u.name','like',"%{$q}%")
                      ->orWhere('u.email','like',"%{$q}%");
                });
            }

            Log::debug('agentesSuspensosList: SQL base', [
                'sql' => $qb->toSql(),
                'bindings' => $qb->getBindings(),
            ]);

            $total = (clone $qb)->distinct('u.id')->count('u.id');
            Log::info('agentesSuspensosList: total encontrados', ['total' => $total]);

            $rowsQb = (clone $qb)
                ->select(['u.id','u.name','u.email','u.created_at'])
                ->distinct('u.id')
                ->orderByDesc('u.id')
                ->forPage($page, $perPage);

            Log::debug('agentesSuspensosList: SQL de página', [
                'sql' => $rowsQb->toSql(),
                'bindings' => $rowsQb->getBindings(),
            ]);

            $rows = $rowsQb->get();

            Log::info('agentesSuspensosList: page result', [
                'page' => $page,
                'perPage' => $perPage,
                'count' => $rows->count(),
                'ids' => $rows->pluck('id')->all(),
            ]);

            $data = $rows->map(function($u){
                $created = $u->created_at instanceof \Carbon\Carbon
                    ? $u->created_at
                    : ($u->created_at ? Carbon::parse($u->created_at) : null);

                return [
                    'id'            => (int) $u->id,
                    'name'          => $u->name,
                    'email'         => $u->email,
                    'created_at_br' => $created?->format('d/m/Y H:i'),
                ];
            });

            return response()->json([
                'data' => $data,
                'meta' => [
                    'current_page' => $page,
                    'last_page'    => max(1, (int) ceil($total / $perPage)),
                    'total'        => $total,
                ],
            ]);
        } catch (\Throwable $e) {
            Log::error('agentesSuspensosList: exceção durante a consulta', [
                'message' => $e->getMessage(),
                'trace' => $e->getTraceAsString(),
            ]);
            return response()->json([
                'data' => [],
                'meta' => ['current_page'=>$page,'last_page'=>1,'total'=>0],
                'error' => 'Falha ao consultar usuários suspensos.',
            ], 500);
        }
    }

    public function agenteReativar(User $user)
    {
        Log::info('agenteReativar: início', ['user_id' => $user->id]);

        $agenteRoleId = $this->roleIdByName(['agente']);
        Log::info('agenteReativar: agenteRoleId', ['agenteRoleId' => $agenteRoleId]);

        if (!$agenteRoleId) {
            Log::error('agenteReativar: papel "agente" não encontrado em roles');
            return response()->json(['error' => 'Papel "agente" não encontrado.'], 422);
        }

        try {
            $exists = DB::table('role_user')->where([
                'user_id' => $user->id,
                'role_id' => $agenteRoleId,
            ])->exists();

            Log::info('agenteReativar: já possui papel agente?', ['exists' => $exists]);

            if (!$exists) {
                DB::table('role_user')->insert([
                    'user_id'    => $user->id,
                    'role_id'    => $agenteRoleId,
                    'created_at' => now(),
                    'updated_at' => now(),
                ]);
                Log::info('agenteReativar: papel agente inserido no pivot', [
                    'user_id' => $user->id, 'role_id' => $agenteRoleId
                ]);
            }

            return response()->json(['message' => 'Suspensão removida com sucesso.']);
        } catch (\Throwable $e) {
            Log::error('agenteReativar: exceção ao reativar', [
                'user_id' => $user->id,
                'message' => $e->getMessage(),
                'trace' => $e->getTraceAsString(),
            ]);
            return response()->json(['error' => 'Falha ao reativar usuário.'], 500);
        }
    }

    // EXCLUIR CONTRATOS
    public function contratosCanceladosList(Request $r)
    {
        $perPage = max(5, (int) $r->integer('per_page', 10));
        $page    = max(1, (int) $r->integer('page', 1));
        $q       = trim((string) $r->input('q', ''));

        $doc = preg_replace('/\D+/', '', $q);
        $normCol = function (string $col) {
            return "REPLACE(REPLACE(REPLACE(REPLACE($col,'.',''),'-',''),'/',''),' ','')";
        };

        $qb = TesourariaPagamento::query()
            ->from('tesouraria_pagamentos as p')
            ->join('agente_cadastros as c', 'c.id', '=', 'p.agente_cadastro_id')
            ->where('p.status', 'cancelado');

        if ($q !== '') {
            $qb->where(function ($w) use ($q, $doc, $normCol) {
                if ($doc !== '') {
                    $w->orWhereRaw($normCol('c.cpf_cnpj') . ' LIKE ?', ["%{$doc}%"]);
                    $w->orWhereRaw($normCol('p.cpf_cnpj') . ' LIKE ?', ["%{$doc}%"]);
                }
                $w->orWhere('c.cpf_cnpj', 'like', "%{$q}%")
                  ->orWhere('p.cpf_cnpj', 'like', "%{$q}%")
                  ->orWhere('p.contrato_codigo_contrato', 'like', "%{$q}%")
                  ->orWhere('c.full_name', 'like', "%{$q}%");
            });
        }

        $qb->orderByDesc('p.updated_at');

        $paginator = $qb->paginate(
            $perPage,
            [
                'c.id as cadastro_id',
                'c.full_name',
                'c.cpf_cnpj',
                'c.contrato_status_contrato',
                'p.id as pagamento_id',
                'p.contrato_codigo_contrato',
                'p.valor_pago',
                'p.paid_at',
                'p.updated_at',
            ],
            'page',
            $page
        );

        $data = collect($paginator->items())->map(function ($row) {
            return [
                'id'            => (int) $row->cadastro_id,
                'name'          => (string) $row->full_name,
                'cpf_cnpj'      => (string) $row->cpf_cnpj,
                'contrato'      => (string) ($row->contrato_codigo_contrato ?? ''),
                'status'        => (string) ($row->contrato_status_contrato ?? '—'),
                'valor_pago'    => $row->valor_pago !== null ? (float) $row->valor_pago : null,
                'paid_at'       => $row->paid_at ? Carbon::parse($row->paid_at)->format('d/m/Y H:i') : null,
                'updated_at_br' => Carbon::parse($row->updated_at)->format('d/m/Y H:i'),
                'can_delete'    => true,
            ];
        });

        return response()->json([
            'data' => $data,
            'meta' => [
                'current_page' => $paginator->currentPage(),
                'last_page'    => $paginator->lastPage(),
                'from'         => $paginator->firstItem(),
                'to'           => $paginator->lastItem(),
                'total'        => $paginator->total(),
            ],
        ]);
    }

    public function contratoShow(int $cadastroId)
    {
        $cad = AgenteCadastro::query()
            ->select([
                'id','full_name','cpf_cnpj','email','orgao_publico','situacao_servidor',
                'contrato_codigo_contrato','contrato_status_contrato','contrato_valor_antecipacao',
                'contrato_mensalidade','contrato_margem_disponivel','agente_responsavel',
                'created_at','updated_at'
            ])
            ->find($cadastroId);

        if (!$cad) {
            return response()->json(['error' => 'Cadastro não encontrado.'], 404);
        }

        $pagCancelado = TesourariaPagamento::where('agente_cadastro_id', $cadastroId)
            ->where('status','cancelado')
            ->latest('updated_at')
            ->first();

        if (!$pagCancelado) {
            return response()->json(['error' => 'Este cadastro não possui pagamento cancelado.'], 409);
        }

        return response()->json([
            'id'       => $cad->id,
            'name'     => $cad->full_name,
            'cpf_cnpj' => $cad->cpf_cnpj,
            'email'    => $cad->email,
            'contrato' => $cad->contrato_codigo_contrato,
            'status'   => $cad->contrato_status_contrato,
            'valores'  => [
                'auxilio'      => $cad->contrato_valor_antecipacao,
                'mensalidade'  => $cad->contrato_mensalidade,
                'margem'       => $cad->contrato_margem_disponivel,
            ],
            'agente_responsavel' => $cad->agente_responsavel,
            'created_at_br'      => Carbon::parse($cad->created_at)->format('d/m/Y H:i'),
            'can_delete'         => true,
            'pagamento_cancelado'=> [
                'id'        => $pagCancelado->id,
                'valor'     => $pagCancelado->valor_pago,
                'paid_at'   => $pagCancelado->paid_at ? Carbon::parse($pagCancelado->paid_at)->format('d/m/Y H:i') : null,
                'forma'     => $pagCancelado->forma_pagamento,
                'contrato'  => $pagCancelado->contrato_codigo_contrato,
                'updated_at'=> Carbon::parse($pagCancelado->updated_at)->format('d/m/Y H:i'),
            ],
        ]);
    }

    public function contratoDestroy(int $cadastroId)
    {
        $cad = AgenteCadastro::find($cadastroId);
        if (!$cad) {
            return response()->json(['error' => 'Cadastro não encontrado.'], 404);
        }

        $temCancelado = TesourariaPagamento::where('agente_cadastro_id', $cadastroId)
            ->where('status','cancelado')
            ->exists();

        if (!$temCancelado) {
            return response()->json([
                'error' => 'Só é permitido excluir contratos que estejam CANCELADOS pelo Tesoureiro.'
            ], 409);
        }

        DB::transaction(function () use ($cad) {
            $cad->delete();
        });

        return response()->json([
            'message'    => 'Contrato excluído com sucesso. Todos os vínculos diretos foram limpos.',
            'deleted_id' => $cadastroId,
        ]);
    }


/* =============== HELPERS: janela da competência (ancorada em FECHAMENTO_DIA e no ?mes=YYYY-MM) — Início =============== */
/**
 * Retorna [inicio, fimExclusivo, refPrimeiroArquivoMonth]
 * - inicio: dia FECHAMENTO_DIA do mês selecionado em ?mes=YYYY-MM
 * - fimExclusivo: inicio + 1 mês
 * - refPrimeiroArquivoMonth: 1º dia do mês da competência seguinte (mês de fimExclusivo - 1 dia)
 */
private function competenciaWindow(): array
{
    $tz       = config('app.timezone') ?: (env('APP_TIMEZONE') ?: 'America/Sao_Paulo');
    $dia      = (int) (config('app.fechamento_dia') ?? env('FECHAMENTO_DIA', 5));
    $mesParam = request('mes', now($tz)->format('Y-m'));
    if (!preg_match('~^\d{4}-\d{2}$~', (string)$mesParam)) {
        $mesParam = now($tz)->format('Y-m');
    }

    // ancora em 05/M 00:00 e desloca +1 dia => início real 06/M 00:00
    $start = \Carbon\Carbon::createFromFormat('Y-m', $mesParam, $tz)
        ->startOfMonth()->day($dia)->startOfDay()
        ->addDay();                               // <<< NOVO (06/M 00:00)

    $end   = $start->copy()->addMonthNoOverflow(); // 06/(M+1) 00:00 (exclusivo)

    // 1º arquivo retorno continua sendo o mês de (end - 1 dia) => 05/(M+1), mês (M+1)
    $firstRefMonth = $end->copy()->subDay()->startOfMonth();

    return [$start, $end, $firstRefMonth];
}
/* =============== HELPERS: janela da competência — Fim =============== */


/** Retorna offset SQL do fuso do momento de referência (ex.: "-03:00"). */
private function tzSqlFrom(Carbon $ref): string
{
    $min  = $ref->offsetMinutes;
    $sign = $min >= 0 ? '+' : '-';
    $h    = str_pad((string) floor(abs($min) / 60), 2, '0', STR_PAD_LEFT);
    $m    = str_pad((string) (abs($min) % 60), 2, '0', STR_PAD_LEFT);
    return "{$sign}{$h}:{$m}";
}

/**
 * Monta a **mesma** expressão que você já usa:
 * CONVERT_TZ(COALESCE(alias.paid_at, alias.created_at), @@session.time_zone, ?) BETWEEN [ini,fim)
 * Retorna [ $whereSql, $bindings ].
 */
private function competenciaSql(string $alias, Carbon $ini, Carbon $fim): array
{
    $tz = $this->tzSqlFrom($ini);
    $expr = "CONVERT_TZ(COALESCE({$alias}.paid_at, {$alias}.created_at), @@session.time_zone, ?)";
    $sql  = "{$expr} >= ? AND {$expr} < ?";
    return [$sql, [$tz, $ini, $tz, $fim]];
}

/** "Setembro/2025" (fallback para "09/2025" se não houver locale PT). */
private function competenciaLabelMes(Carbon $ini): string
{
    try {
        return ucfirst($ini->locale('pt_BR')->translatedFormat('F/Y'));
    } catch (\Throwable $e) {
        return $ini->format('m/Y');
    }
}


/* =============== NOVO: cálculo dos 3 cards de "Arquivos Retorno" — Início =============== */
/**
 * Retorna um array com 3 cards (1º/2º/3º arquivo retorno) para a coorte da competência atual.
 * Coorte = contratos que tiveram **tesouraria_pagamentos.status='pago'** dentro da janela da competência.
 * Valores esperados por contrato:
 *  - se existir anticipations_json[n].valorAuxilio => usa esse valor
 *  - senão => usa contrato_mensalidade
 * Recebidos (por card) = soma de pagamentos_mensalidades (status 1/4) da **referencia_month** do card.
 */
// ======== CARDS: usa só o arquivo retorno (comportamento antigo) ========
private function buildRetornoCardsData(): array
{
    [$winStart, $winEnd, $firstRef] = $this->competenciaWindow();
    $tblMens = (new \App\Models\PagamentoMensalidade)->getTable(); // ex.: pagamentos_mensalidades

    $cards = [];
    for ($n = 1; $n <= 3; $n++) {
        $refMonth = $firstRef->copy()->addMonths($n - 1);
        $refDate  = $refMonth->format('Y-m-01');

        // Tudo que veio no arquivo dessa referência
        $rowsAll = \DB::table($tblMens.' as p')
            ->select('p.agente_cadastro_id','p.cpf_cnpj','p.valor','p.status_code')
            ->whereDate('p.referencia_month', $refDate)
            ->get();

        // Esperado = soma de TODOS os valores do arquivo
        $expectedTotal = (float) $rowsAll->sum(fn($r) => (float) ($r->valor ?? 0));

        // Recebido = soma status 1/4
        $okRows        = $rowsAll->whereIn('status_code', ['1','4']);
        $receivedTotal = (float) $okRows->sum(fn($r) => (float) ($r->valor ?? 0));

        // Contagem por contrato/CPF (se não tiver id)
        $keyAll = $rowsAll->map(fn($r) =>
            $r->agente_cadastro_id ?: preg_replace('/\D+/', '', (string) $r->cpf_cnpj)
        )->unique()->count();

        $keyOk  = $okRows->map(fn($r) =>
            $r->agente_cadastro_id ?: preg_replace('/\D+/', '', (string) $r->cpf_cnpj)
        )->unique()->count();

        $cards[] = [
            'n'               => $n,
            'title'           => "{$n}º arquivo retorno",
            'ref'             => $refDate,
            'ref_fmt'         => $refMonth->format('m/Y'),
            'expected_total'  => round($expectedTotal, 2),
            'received_total'  => round($receivedTotal, 2),
            'expected_count'  => $keyAll,
            'received_count'  => $keyOk,
            'pct'             => $expectedTotal > 0 ? round(($receivedTotal / $expectedTotal) * 100, 1) : 0.0,
        ];
    }

    return $cards;
}


/* =============== NOVO: cálculo dos 3 cards de "Arquivos Retorno" — Fim =============== */


/* =============== NOVO: Detalhar um card (lista de nomes + status do arquivo) — Início =============== */
// ======== MODAL: usa só o arquivo retorno (comportamento antigo) ========
public function retornoDetalhar(\Illuminate\Http\Request $r, int $n)
{
    // TRACE
    $trace = 'RETORNO#DETALHAR#' . now('UTC')->format('Ymd-His-v') . '-' . Str::upper(Str::random(4));

    Log::info("[$trace] retornoDetalhar: início", [
        'n'        => $n,
        'user_id'  => auth()->id(),
        'ip'       => $r->ip(),
        'query'    => $r->query(),
        'path'     => $r->path(),
    ]);

    if ($n < 1 || $n > 3) {
        Log::warning("[$trace] retornoDetalhar: parâmetro n fora do intervalo permitido (1..3)", [
            'n' => $n,
        ]);
        abort(404);
    }

    // ====== CORREÇÃO AQUI: usa o "mes" selecionado para calcular M+1..M+3 ======
    $tz = config('app.timezone') ?: (env('APP_TIMEZONE') ?: 'America/Sao_Paulo');

    $mesParam = (string) $r->query('mes', now($tz)->format('Y-m'));
    if (!preg_match('~^\d{4}-\d{2}$~', $mesParam)) {
        $mesParam = now($tz)->format('Y-m');
    }

    $base = \Carbon\Carbon::createFromFormat('Y-m', $mesParam, $tz)->startOfMonth();

    // cards devem ser M+1, M+2, M+3 (n=1..3)
    $firstRef = $base->copy()->addMonthNoOverflow()->startOfMonth();          // M+1
    $refMonth = $firstRef->copy()->addMonthsNoOverflow($n - 1)->startOfMonth(); // M+1..M+3
    $refDate  = $refMonth->format('Y-m-01');

    // (opcional) janela do mês selecionado só para log/debug
    $winStart = $base->copy()->startOfDay();
    $winEnd   = $base->copy()->addMonth();

    Log::info("[$trace] retornoDetalhar: competência calculada (M+1..M+3)", [
        'mes_param' => $mesParam,
        'base'      => $base->format('Y-m'),
        'firstRef'  => $firstRef->format('Y-m'),
        'n'         => $n,
        'mesISO'    => $refMonth->format('Y-m'),
        'refDate'   => $refDate,
        'winStart'  => (string) $winStart,
        'winEnd'    => (string) $winEnd,
    ]);

    // SQL trace opcional
    if (config('app.debug') && $r->boolean('trace_sql', false)) {
        DB::listen(function ($q) use ($trace) {
            Log::debug("[$trace] SQL", [
                'sql'      => $q->sql,
                'time_ms'  => $q->time,
                'bindings' => $q->bindings,
            ]);
        });
    }

    // Usa o helper para montar linhas + totais
    // (mantém seu contrato: buildRetornoRowsAndTotals($refMonth, $trace))
    [$rows, $totais] = $this->buildRetornoRowsAndTotals($refMonth, $trace);

    Log::info("[$trace] retornoDetalhar: saída final", [
        'n'       => $n,
        'refFmt'  => $refMonth->format('m/Y'),
        'refDate' => $refDate,
        'totais'  => $totais,
        'sample'  => array_slice($rows, 0, 3),
    ]);

    return response()->json([
        'n'      => $n,
        'refFmt' => $refMonth->format('m/Y'),
        'ref'    => $refDate,
        'totais' => $totais,
        'rows'   => $rows,
        'trace'  => $trace, // útil pra bater com log quando der ruim
    ]);
}



/**
 * Converte uma linha de pagamentos_mensalidades em array usado no front,
 * aplicando a mesma regra de "OK / Cancelado / No arquivo" e valores.
 *
 * @param  object $r      Linha retornada pelo DB (stdClass)
 * @param  array  $labels Mapa de status_code => label
 * @return array
 */
protected function mapMensRowToRetornoArray($r, array $labels): array
{
    $statusCode  = (string) ($r->status_code ?? '');
    $statusLabel = $labels[$statusCode] ?? $statusCode;

    $manualStatusRaw = $r->manual_status ?? null;
    $manualStatus    = is_null($manualStatusRaw) ? null : trim((string) $manualStatusRaw);
    $manualStatusLc  = $manualStatus ? mb_strtolower($manualStatus) : '';

    // Do arquivo retorno (status 1 ou 4)
    $okArquivo = in_array($statusCode, ['1', '4'], true);

    // Manual marcado como pago
    $okManual = in_array($manualStatusLc, ['pago', 'ok', 'concluido', 'concluído'], true);
    $canceladoManual = in_array($manualStatusLc, ['cancelado', 'cancelada'], true);

    // Regra final: qualquer OK (arquivo ou manual)
    $ok = $okManual || $okArquivo;

    // Valor esperado: sempre o do arquivo
    $esperado = (float) ($r->valor ?? 0);

    // Valor recebido:
    if ($okManual) {
        // Se manual "pago": usa recebido_manual se tiver, senão cai pro esperado
        $recebido = (float) ($r->recebido_manual ?? $esperado);
    } elseif ($okArquivo) {
        // Só arquivo OK: usa o valor do arquivo
        $recebido = $esperado;
    } else {
        $recebido = 0.0;
    }

    $situacaoCode  = $ok ? 'ok' : ($canceladoManual ? 'bad' : 'warn');
    $situacaoLabel = $ok ? 'Concluído' : ($canceladoManual ? 'Cancelado' : 'No arquivo');

    return [
        // id usado no front para botão de comprovante (usa agente se existir)
        'id'        => (int) ($r->agente_cadastro_id ?: $r->id),
        'source_id' => (int) $r->id, // id real da linha

        'nome' => $r->nome_relatorio ?: '-',
        'cpf'  => $r->cpf_cnpj ?: '-',

        // valores
        'valor'    => $esperado,   // base
        'esperado' => $esperado,
        'recebido' => $recebido,

        'status_code'    => $statusCode,
        'status_label'   => $statusLabel,
        'ok'             => $ok,
        'tem_linha'      => true,
        'situacao_code'  => $situacaoCode,
        'situacao_label' => $situacaoLabel,

        'orgao'     => $r->orgao_pagto,
        'relatorio' => $r->nome_relatorio,

        // campos manuais expostos para o front (aba "Revisados")
        'manual_status'           => $manualStatus ?: null,
        'manual_valor'            => $r->recebido_manual !== null ? (float) $r->recebido_manual : null,
        'manual_forma_pagamento'  => $r->manual_forma_pagamento ?? null,
        'manual_paid_at'          => $r->manual_paid_at ?? null,
        'manual_comprovante_path' => $r->manual_comprovante_path ?? null,
    ];
}


/**
 * Monta linhas + totais do arquivo retorno de um mês específico.
 *
 * @param  \Carbon\Carbon $refMonth  Mês de referência (primeiro dia do mês)
 * @param  string|null    $trace     Opcional, para logs
 * @return array [array $rows, array $totais]
 */
protected function buildRetornoRowsAndTotals(Carbon $refMonth, ?string $trace = null): array
{
    $refDate = $refMonth->format('Y-m-01');
    $tblMens = (new PagamentoMensalidade)->getTable();

    $labels = [
        '1' => 'Efetivado',
        '4' => 'Efetivado c/ diferença',
        '2' => 'Sem margem (temp.)',
        '3' => 'Não lançado (outros)',
        '5' => 'Problemas técnicos',
        '6' => 'Com erros',
        'S' => 'Compra dívida / Suspensão',
    ];

    if ($trace) {
        Log::info("[$trace] buildRetornoRowsAndTotals: buscando registros", [
            'refDate' => $refDate,
            'table'   => $tblMens,
        ]);
    }

    $pRows = DB::table($tblMens . ' as p')
        ->select([
            'p.id',
            'p.agente_cadastro_id',
            'p.nome_relatorio',
            'p.cpf_cnpj',
            'p.valor',
            'p.status_code',
            'p.orgao_pagto',

            // Campos manuais (revisados)
            'p.manual_status',
            'p.manual_forma_pagamento',
            'p.manual_paid_at',
            'p.manual_comprovante_path',
            'p.recebido_manual',
        ])
        ->whereDate('p.referencia_month', '=', $refDate)
        ->orderBy('p.nome_relatorio', 'asc')
        ->get();

    if ($trace) {
        Log::info("[$trace] buildRetornoRowsAndTotals: linhas retornadas", [
            'rows_count' => $pRows->count(),
            'sample'     => $pRows->take(3)->toArray(),
        ]);
    }

    // Monta as linhas usando a mesma regra do front
    $rows = [];
    foreach ($pRows as $r) {
        $rows[] = $this->mapMensRowToRetornoArray($r, $labels);
    }

    // Totais (sempre considerando manual + arquivo)
    $totais = [
        'esperado' => round((float) array_sum(array_column($rows, 'esperado')), 2),
        'recebido' => round((float) array_sum(array_column($rows, 'recebido')), 2),
        'ok'       => collect($rows)->where('ok', true)->count(),
        'total'    => count($rows),
    ];

    if ($trace) {
        Log::info("[$trace] buildRetornoRowsAndTotals: totais calculados", [
            'refFmt'  => $refMonth->format('m/Y'),
            'refDate' => $refDate,
            'totais'  => $totais,
        ]);
    }

    return [$rows, $totais];
}

// ============ Marcar manualmente uma linha (chip laranja) ============
public function retornoMarcar(Request $r)
{
    $acao = $r->input('acao');
    $ids  = (array) $r->input('ids', []);

    if (!in_array($acao, ['estornar','ignorar','manual'])) {
        return response()->json(['ok'=>false,'msg'=>'Ação inválida'], 422);
    }

    $q = PagamentoMensalidade::whereIn('id', $ids);
    $count = 0;

    foreach ($q->get() as $m) {
        if ($acao === 'estornar') {
            $m->status  = 'pendente';
            $m->paid_at = null;
        } elseif ($acao === 'ignorar') {
            // não muda status do seu funil — só marca anotação, se houver coluna
            if (property_exists($m, 'observacao')) {
                $m->observacao = trim(($m->observacao ?? '').' | ignorado no retorno');
            }
        } else { // manual
            $m->status = 'ok';
            $m->paid_at = $m->paid_at ?: now('America/Sao_Paulo');
        }
        $m->save();
        $count++;
    }

    return response()->json(['ok'=>true,'acao'=>$acao,'afetados'=>$count]);
}
/**
 * JSON para o painel "Visão de Meses (−1 / Atual / +1 / +2)".
 * Lê pagamentos_mensalidades por referencia_month e calcula recebidos (status 1|4).
 * Se ?mes=YYYY-MM vier, usa como base. Caso contrário, usa o mês de calendário
 * em APP_TIMEZONE. O ponteiro/progresso usa FECHAMENTO_DIA + FECHAMENTO_OVERRIDES.
 */
public function retornoMapaMeses(\Illuminate\Http\Request $r)
{
    $tz  = config('app.timezone', env('APP_TIMEZONE', 'America/Sao_Paulo'));
    $now = \Carbon\Carbon::now($tz);

    $cutoffDefault = (int) env('FECHAMENTO_DIA', 5);
    $ovRaw = (string) env('FECHAMENTO_OVERRIDES', '');
    $ovMap = [];
    if ($ovRaw !== '') {
        foreach (explode(',', $ovRaw) as $pair) {
            [$ym, $d] = array_map('trim', array_pad(explode(':', $pair, 2), 2, ''));
            if (preg_match('/^\d{4}-\d{2}$/', $ym) && ctype_digit($d)) $ovMap[$ym] = (int) $d;
        }
    }
    $cutoffFor = function (\Carbon\Carbon $d) use ($cutoffDefault, $ovMap) {
        $ym = $d->format('Y-m');
        return $ovMap[$ym] ?? $cutoffDefault;
    };

    $mesParam = trim((string) $r->query('mes', ''));
    $base = $mesParam && preg_match('/^\d{4}-\d{2}$/', $mesParam)
        ? \Carbon\Carbon::createFromFormat('Y-m', $mesParam, $tz)->startOfMonth()
        : $now->copy()->startOfMonth();

    $months = [
        $base->copy()->subMonthNoOverflow(),
        $base->copy(),
        $base->copy()->addMonthNoOverflow(),
        $base->copy()->addMonthsNoOverflow(2),
    ];

    $pt = [1=>'janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro'];

    $model = new \App\Models\PagamentoMensalidade();
    $table = $model->getTable(); // ex.: pagamentos_mensalidades

    $seqCol = null;
    foreach (['arquivo_seq','retorno_seq','retorno_arquivo_seq','arquivo_ordem','batch_seq','lote_seq'] as $c) {
        if (\Illuminate\Support\Facades\Schema::hasColumn($table, $c)) { $seqCol = $c; break; }
    }

    // chave “contrato” para DISTINCT: agente_cadastro_id OU CPF normalizado
    $docKey = "COALESCE(CAST(p.agente_cadastro_id AS CHAR), REPLACE(REPLACE(REPLACE(REPLACE(p.cpf_cnpj,'.',''),'-',''),'/',''),' ',''))";

    $items = [];
    foreach ($months as $m) {
        $isoMonth = $m->format('Y-m');
        $isoRef   = $m->format('Y-m-01');

        // BASE: sempre por referencia_month
        $qAll = \DB::table($table.' as p')->whereDate('p.referencia_month', $isoRef);
        $qOk  = \DB::table($table.' as p')->whereDate('p.referencia_month', $isoRef)->whereIn('p.status_code', ['1','4']);

        // totais em R$
        $expectedTotal = (float) (clone $qAll)->sum('p.valor');
        $receivedTotal = (float) (clone $qOk)->sum('p.valor');

        // CONTAGEM DISTINTA por contrato
        $expectedCount = (int) (clone $qAll)->selectRaw("COUNT(DISTINCT {$docKey}) AS c")->value('c');
        $receivedCount = (int) (clone $qOk)->selectRaw("COUNT(DISTINCT {$docKey}) AS c")->value('c');

        // SEGMENTOS (1º/2º/3º arquivo) – incrementais
        $inc1 = 0.0; $inc2 = 0.0; $inc3 = 0.0;
        if ($expectedTotal > 0.0) {
            if ($seqCol) {
                $sum1 = (float) (clone $qOk)->where("p.$seqCol", 1)->sum('p.valor');
                $sum2 = (float) (clone $qOk)->where("p.$seqCol", 2)->sum('p.valor');
                $sum3 = (float) (clone $qOk)->where("p.$seqCol", '>=', 3)->sum('p.valor');
                $inc1 = $sum1; $inc2 = $sum2; $inc3 = $sum3;
            } else {
                // fallback por “ondas” cronológicas no mesmo mês
                $dates = (clone $qOk)->orderBy('p.created_at')->pluck('p.created_at');
                $n = $dates->count();
                if ($n > 0) {
                    $i1 = max(0, (int) floor($n/3) - 1);
                    $i2 = max(0, (int) floor(2*$n/3) - 1);
                    $t1 = $dates[$i1]; $t2 = $dates[$i2];
                    $s1 = (float) (clone $qOk)->where('p.created_at','<=',$t1)->sum('p.valor');
                    $s2 = (float) (clone $qOk)->where('p.created_at','<=',$t2)->sum('p.valor');
                    $s3 = (float) (clone $qOk)->sum('p.valor');
                    $inc1 = $s1;
                    $inc2 = max(0.0, $s2 - $s1);
                    $inc3 = max(0.0, $s3 - $s2);
                }
            }
        }

        $p1 = $expectedTotal > 0 ? round(100 * $inc1 / $expectedTotal, 1) : 0.0;
        $p2 = $expectedTotal > 0 ? round(100 * $inc2 / $expectedTotal, 1) : 0.0;
        $p3 = $expectedTotal > 0 ? round(100 * $inc3 / $expectedTotal, 1) : 0.0;
        $sumPct = $p1 + $p2 + $p3;
        if ($sumPct > 100) { $p3 = max(0.0, round($p3 - ($sumPct - 100), 1)); }

        $segments = [
            ['n'=>1,'ref'=>$isoMonth,'ref_fmt'=>$m->format('m/Y'),'expected_total'=>round($expectedTotal,2),'received_total'=>round($inc1,2),'pct'=>$p1],
            ['n'=>2,'ref'=>$isoMonth,'ref_fmt'=>$m->format('m/Y'),'expected_total'=>round($expectedTotal,2),'received_total'=>round($inc2,2),'pct'=>$p2],
            ['n'=>3,'ref'=>$isoMonth,'ref_fmt'=>$m->format('m/Y'),'expected_total'=>round($expectedTotal,2),'received_total'=>round($inc3,2),'pct'=>$p3],
        ];

        // ponteiro visual até o dia de corte
        $progress = 0.0;
        if      ($m->lt($base)) { $progress = 100.0; }
        elseif  ($m->isSameMonth($now)) {
            $daysIn  = $m->daysInMonth;
            $cutoff  = max(1, (int) $cutoffFor($m));
            $endDay  = max(1, min($daysIn, $cutoff));
            $dayNow  = max(1, min($endDay, (int) $now->day));
            $progress = ($endDay > 1) ? round(100 * ($dayNow - 1) / ($endDay - 1), 2) : 100.0;
        }

        $items[] = [
            'iso'            => $isoMonth,
            'label'          => ($pt[(int)$m->format('n')] ?? $m->format('F')) . ' de ' . $m->format('Y'),
            'expected_total' => $expectedTotal,
            'expected_count' => $expectedCount,   // ← agora DISTINTO
            'received_total' => $receivedTotal,
            'received_count' => $receivedCount,   // ← agora DISTINTO
            'arrecadado_fmt' => 'R$ ' . number_format($receivedTotal, 2, ',', '.'),
            'contratos_text' => sprintf('%d/%d', $receivedCount, $expectedCount),
            'progress_pct'   => $progress,
            'segments'       => $segments,
        ];
    }

    return response()->json([
        'base'    => $base->format('Y-m'),
        'current' => $now->format('Y-m'), // ajuda o “Atual” no front
        'months'  => $items,
        'tz'      => $tz,
        'cutoff'  => ['default' => $cutoffDefault, 'overrides' => $ovMap],
    ]);
}



// Helper: janela da competência e 1º ref. do arquivo (mantido)
private function competenciaWindowForMonth(string $ym, string $tz): array
{
    if (!preg_match('~^\d{4}-\d{2}$~', $ym)) {
        $ym = now($tz)->format('Y-m');
    }
    $dia = (int) (config('app.fechamento_dia') ?? env('FECHAMENTO_DIA', 5));

    // ancora em 05/M 00:00 e desloca +1 dia => início real 06/M 00:00
    $start = \Carbon\Carbon::createFromFormat('Y-m', $ym, $tz)
        ->startOfMonth()->day($dia)->startOfDay()
        ->addDay();                               // 06/M 00:00
    $end   = $start->copy()->addMonthNoOverflow(); // 06/(M+1) 00:00 (exclusivo)

    // 1º arquivo retorno = mês de (end - 1 dia) → início do mês (M+1)
    $firstRefMonth = $end->copy()->subDay()->startOfMonth();

    return [$start, $end, $firstRefMonth];
}

// === ROTAS (garanta que exista uma com este name usado no JS) ===
// Route::patch('/admin/retorno/{item}/valor', [TesoureiroController::class, 'retornoUpdateValor'])
//     ->name('admin.retorno.valor.update');

// PATCH admin/retorno/{item}/valor  (field: 'esperado' | 'recebido', valor: string/number BRL)
public function retornoUpdateValor(Request $r, PagamentoMensalidade $item)
{
    $r->validate([
        'field' => 'required|in:esperado,recebido',
        'valor' => 'required'
    ]);

    $valor = $this->parseMoney((string)$r->input('valor'));

    if ($r->input('field') === 'esperado') {
        $item->esperado_manual = $valor;
    } else {
        $item->recebido_manual = $valor;

        // Se recebeu manual > 0, marcar como "pago"
        if ($valor > 0 && $item->manual_status !== 'pago') {
            $item->manual_status     = 'pago';
            $item->manual_paid_at    = now();
            $item->manual_by_user_id = auth()->id();
        }
    }

    $item->save();
    $item->refresh(); // garante accessors / casts atualizados

    // Fallback caso o model não tenha accessors *_efetivo
    $esperadoEfetivo = $item->esperado_efetivo
        ?? ($item->esperado_manual ?? ($item->valor ?? 0));
    $recebidoEfetivo = $item->recebido_efetivo
        ?? ($item->recebido_manual ?? ($item->recebido ?? 0));

    return response()->json([
        'ok'       => true,
        'esperado' => number_format((float)$esperadoEfetivo, 2, ',', '.'),
        'recebido' => number_format((float)$recebidoEfetivo, 2, ',', '.'),
        'status'   => $item->manual_status,
    ]);
}

// POST admin/retorno/{item}/comprovante (multipart: file 'comprovante', valor_pago?, forma_pagamento, status=pago|cancelado)
public function retornoUploadComprovante(Request $r, PagamentoMensalidade $item)
{
    $rid = (string) Str::uuid();

    $safeInputs = $r->except(['comprovante']);
    $fileMeta = null;
    try {
        if ($r->hasFile('comprovante')) {
            $fx = $r->file('comprovante');
            $fileMeta = [
                'is_valid'  => $fx->isValid(),
                'orig_name' => $fx->getClientOriginalName(),
                'mime'      => $fx->getClientMimeType(),
                'size'      => $fx->getSize(),
                'ext'       => $fx->getClientOriginalExtension(),
            ];
        }
    } catch (\Throwable $e) {}

    Log::warning('[retornoUploadComprovante] START', [
        'rid'    => $rid,
        'route'  => optional($r->route())->getName(),
        'method' => $r->method(),
        'url'    => $r->fullUrl(),
        'ip'     => $r->ip(),
        'ua'     => substr((string) $r->userAgent(), 0, 180),
        'item_id'=> $item->id,
        'inputs' => $safeInputs,
        'has_file' => $r->hasFile('comprovante'),
        'file_meta'=> $fileMeta,
    ]);

    // validação com log (sem mudar teu fluxo)
    try {
        $r->validate([
            'status'          => 'required|in:pago,cancelado',
            'forma_pagamento' => 'nullable|string|max:40',
            'valor_pago'      => 'nullable',
            'comprovante'     => 'nullable|file|max:8192|mimes:png,jpg,jpeg,pdf',
        ]);
    } catch (ValidationException $e) {
        Log::warning('[retornoUploadComprovante] VALIDATION_FAIL', [
            'rid'=>$rid,
            'item_id'=>$item->id,
            'errors'=>$e->errors(),
            'inputs'=>$safeInputs,
            'file_meta'=>$fileMeta,
        ]);
        throw $e;
    }

    // BEFORE snapshot
    Log::info('[retornoUploadComprovante] MODEL_BEFORE', [
        'rid'=>$rid,
        'item_id'=>$item->id,
        'before'=>$item->toArray(),
    ]);

    // upload (opcional)
    if ($r->hasFile('comprovante')) {
        $dir  = 'retornos/' . now()->format('Y/m');
        $path = $r->file('comprovante')->store($dir, 'public');

        Log::warning('[retornoUploadComprovante] FILE_STORED', [
            'rid'=>$rid,
            'dir'=>$dir,
            'new_path'=>$path,
            'old_path'=>$item->manual_comprovante_path,
            'disk'=>'public',
        ]);

        $item->manual_comprovante_path = $path;
    }

    $valorPago = $r->filled('valor_pago') ? $this->parseMoney((string)$r->input('valor_pago')) : null;

    Log::info('[retornoUploadComprovante] MONEY_PARSE', [
        'rid'=>$rid,
        'valor_pago_in'=>$r->input('valor_pago'),
        'valor_pago_num'=>$valorPago,
    ]);

    $status = (string) $r->input('status');

    // status/infos manuais
    $item->manual_status          = $status;
    $item->manual_forma_pagamento = $r->input('forma_pagamento');
    $item->manual_paid_at         = $status === 'pago' ? now() : null;
    $item->manual_by_user_id      = auth()->id();

    if (!is_null($valorPago)) {
        $item->recebido_manual = $valorPago;
    }

    // O que de fato vai pro banco
    $dirty = $item->getDirty();
    Log::warning('[retornoUploadComprovante] MODEL_DIRTY_BEFORE_SAVE', [
        'rid'=>$rid,
        'item_id'=>$item->id,
        'dirty'=>$dirty,
    ]);

    $item->save();
    $item->refresh();

    Log::warning('[retornoUploadComprovante] MODEL_AFTER_SAVE', [
        'rid'=>$rid,
        'item_id'=>$item->id,
        'after'=>$item->toArray(),
    ]);

    // registro contábil (logado)
    try {
        if ($status === 'pago' && $item->agente_cadastro_id) {
            $tp = TesourariaPagamento::create([
                'agente_cadastro_id'         => $item->agente_cadastro_id,
                'created_by_user_id'         => auth()->id(),
                'contrato_codigo_contrato'   => null,
                'contrato_valor_antecipacao' => null,
                'cpf_cnpj'                   => $item->cpf_cnpj,
                'full_name'                  => '',
                'agente_responsavel'         => null,
                'status'                     => 'pago',
                'valor_pago'                 => $item->recebido_manual ?? $item->valor,
                'paid_at'                    => now(),
                'forma_pagamento'            => $item->manual_forma_pagamento,
                'comprovante_path'           => $item->manual_comprovante_path,
                'notes'                      => 'Registro manual a partir do arquivo retorno',
            ]);

            Log::warning('[retornoUploadComprovante] TESOURARIA_CREATED', [
                'rid'=>$rid,
                'tesouraria_id'=>$tp->id ?? null,
                'item_id'=>$item->id,
                'valor_pago'=>$tp->valor_pago ?? null,
                'comprovante_path'=>$tp->comprovante_path ?? null,
            ]);
        } else {
            Log::info('[retornoUploadComprovante] TESOURARIA_SKIPPED', [
                'rid'=>$rid,
                'status'=>$status,
                'agente_cadastro_id'=>$item->agente_cadastro_id,
            ]);
        }
    } catch (\Throwable $e) {
        Log::error('[retornoUploadComprovante] TESOURARIA_FAIL', [
            'rid'=>$rid,
            'item_id'=>$item->id,
            'err'=>$e->getMessage(),
        ]);
        // mantém silencioso como você já queria
    }

    $recebidoEfetivo = $item->recebido_efetivo
        ?? ($item->recebido_manual ?? ($item->recebido ?? 0));

    $viewUrl = $item->manual_comprovante_path
        ? route('admin.retorno.comprovante.ver', $item->id)
        : null;

    Log::warning('[retornoUploadComprovante] END_OK', [
        'rid'=>$rid,
        'item_id'=>$item->id,
        'status'=>$item->manual_status,
        'recebidoEfetivo'=>$recebidoEfetivo,
        'view_url'=>$viewUrl,
    ]);

    return response()->json([
        'ok'       => true,
        'status'   => $item->manual_status,
        'recebido' => number_format((float)$recebidoEfetivo, 2, ',', '.'),
        'view_url' => $viewUrl,
        'rid'      => $rid,
    ]);
}

// GET admin/retorno/{item}/comprovante
public function retornoVerComprovante(PagamentoMensalidade $item)
{
    abort_unless(
        $item->manual_comprovante_path &&
        \Illuminate\Support\Facades\Storage::disk('public')->exists($item->manual_comprovante_path),
        404
    );

    return response()->file(
        \Illuminate\Support\Facades\Storage::disk('public')->path($item->manual_comprovante_path)
    );
}

// Utilitário: parse de dinheiro BR/US
private function parseMoney(string $v): float
{
    $v = trim($v);
    $v = str_replace(['R$', ' '], '', $v);
    if (preg_match('/,/', $v) && preg_match('/\./', $v)) {
        $v = str_replace('.', '', $v);
        $v = str_replace(',', '.', $v);
    } elseif (preg_match('/,/', $v) && !preg_match('/\./', $v)) {
        $v = str_replace(',', '.', $v);
    }
    return (float) $v;
}

//REFINANCIAMENTO
public function retornoRefinAptos(Request $r)
{
    $ref1 = $r->query('ref1');
    $ref2 = $r->query('ref2');
    $ref3 = $r->query('ref3');

    if (!$ref1 || !$ref2 || !$ref3) {
        $mesISO = $this->rfResolveMesISO($r);
        [$ref1C, $ref2C, $ref3C] = $this->rfRefsFromMes($mesISO);
        $ref1 = $ref1C->toDateString();
        $ref2 = $ref2C->toDateString();
        $ref3 = $ref3C->toDateString();
    }

    try {
        $ref1Iso = Carbon::parse($ref1)->startOfMonth()->toDateString();
        $ref2Iso = Carbon::parse($ref2)->startOfMonth()->toDateString();
        $ref3Iso = Carbon::parse($ref3)->startOfMonth()->toDateString();
    } catch (\Throwable $e) {
        return response()->json(['ok'=>false,'message'=>'Refs inválidas.'], 422);
    }

    $normDoc = fn($v) => $this->rfNormDoc($v);

    $hasManualStatus = Schema::hasColumn('pagamentos_mensalidades', 'manual_status');

    // 2) pega linhas dos 3 meses (isso continua por mês, porque o 1/3 2/3 3/3 depende disso)
    $rows = DB::table('pagamentos_mensalidades')
        ->select([
            'id',
            'cpf_cnpj',
            'agente_cadastro_id',
            'referencia_month',
            'status_code',
            'nome_relatorio',
        ])
        ->when($hasManualStatus, fn($q) => $q->addSelect('manual_status'))
        ->where(function ($q) use ($ref1Iso, $ref2Iso, $ref3Iso) {
            $q->whereDate('referencia_month', $ref1Iso)
              ->orWhereDate('referencia_month', $ref2Iso)
              ->orWhereDate('referencia_month', $ref3Iso);
        })
        ->get();

    // =========================
    // NOVO: sets de exclusão SEM depender de mês/cycle
    // Basta existir na tabela -> remove da view
    // (filtra só pelos CPFs que aparecem nesse ciclo, para não varrer o banco inteiro)
    // =========================
    $cpfCandidates = $rows
        ->map(fn($x) => $normDoc($x->cpf_cnpj ?? ''))
        ->filter()
        ->unique()
        ->values()
        ->all();

    $refinSet = [];
    $solSet   = [];

    $normExpr = function (string $col): string {
        // normalize "só dígitos" no SQL (MySQL)
        return "REPLACE(REPLACE(REPLACE(REPLACE($col,'.',''),'-',''),'/',''),' ','')";
    };

    // 1) CPFs já refinanciados (QUALQUER ciclo)
    if (!empty($cpfCandidates) && Schema::hasTable('refinanciamentos')) {
        $t = 'refinanciamentos';
        $cpfCol = Schema::hasColumn($t, 'cpf_cnpj') ? 'cpf_cnpj'
               : (Schema::hasColumn($t, 'cpf') ? 'cpf' : null);

        if ($cpfCol) {
            $docs = DB::table($t)
                ->select($cpfCol)
                ->whereIn(DB::raw($normExpr($cpfCol)), $cpfCandidates)
                ->pluck($cpfCol)
                ->all();

            foreach ($docs as $doc) {
                $d = $normDoc($doc);
                if ($d !== '') $refinSet[$d] = true;
            }
        }
    }

    if (!empty($cpfCandidates) && Schema::hasTable('retorno_refinanciamentos')) {
        $t = 'retorno_refinanciamentos';
        $cpfCol = Schema::hasColumn($t, 'cpf_cnpj') ? 'cpf_cnpj'
               : (Schema::hasColumn($t, 'cpf') ? 'cpf' : null);

        if ($cpfCol) {
            $docs = DB::table($t)
                ->select($cpfCol)
                ->whereIn(DB::raw($normExpr($cpfCol)), $cpfCandidates)
                ->pluck($cpfCol)
                ->all();

            foreach ($docs as $doc) {
                $d = $normDoc($doc);
                if ($d !== '') $refinSet[$d] = true;
            }
        }
    }

    // 1B) CPFs que já possuem SOLICITAÇÃO (QUALQUER ciclo)
    // Se tiver coluna status, aplica bloqueio por status; se não tiver, só existir já bloqueia.
    if (!empty($cpfCandidates) && Schema::hasTable('refinanciamento_solicitacoes')) {
        $tSol = 'refinanciamento_solicitacoes';

        $cpfCol = Schema::hasColumn($tSol, 'cpf_cnpj') ? 'cpf_cnpj'
                : (Schema::hasColumn($tSol, 'cpf') ? 'cpf' : null);

        $hasStatus = Schema::hasColumn($tSol, 'status');

        if ($cpfCol) {
            $qSol = DB::table($tSol)->select($cpfCol)
                ->whereIn(DB::raw($normExpr($cpfCol)), $cpfCandidates);

            if ($hasStatus) {
                $block = [
                    'pending','pendente','in_progress','processing',
                    'approved','aprovado','done','ok',
                    'concluido','concluído','suspended','suspenso'
                ];

                $qSol->whereIn(DB::raw("LOWER(TRIM(COALESCE(status,'')))"), $block);
            }

            foreach ($qSol->pluck($cpfCol)->all() as $doc) {
                $d = $normDoc($doc);
                if ($d !== '') $solSet[$d] = true;
            }
        }
    }

    // =========================
    // Monta por CPF (já excluindo pelo refinSet/solSet sem mês)
    // =========================
    $byCpf = [];

    $findCadastroIdByCpf = function (string $cpfDigits): ?int {
        if ($cpfDigits === '') return null;
        $cad = AgenteCadastro::whereRaw(
            "REPLACE(REPLACE(REPLACE(REPLACE(cpf_cnpj,'.',''),'-',''),'/',''),' ','') = ?",
            [$cpfDigits]
        )->select('id')->first();
        return $cad ? (int)$cad->id : null;
    };

    foreach ($rows as $row) {
        $cpfNorm = $normDoc($row->cpf_cnpj ?? '');
        if ($cpfNorm === '') continue;

        // ✅ agora bloqueia se existir em refinanciamentos/retorno_refinanciamentos/solicitações (sem depender de mês)
        if (isset($refinSet[$cpfNorm]) || isset($solSet[$cpfNorm])) continue;

        if (!isset($byCpf[$cpfNorm])) {
            $cadId = $row->agente_cadastro_id ? (int)$row->agente_cadastro_id : null;
            if (!$cadId) $cadId = $findCadastroIdByCpf($cpfNorm);

            $byCpf[$cpfNorm] = [
                'cpf'         => $cpfNorm,
                'nome'        => (string)($row->nome_relatorio ?? ''),
                'cadastro_id' => $cadId,
                'parcelas'    => [
                    1 => ['present'=>false, 'ok'=>false, 'pm_id'=>null, 'used'=>false],
                    2 => ['present'=>false, 'ok'=>false, 'pm_id'=>null, 'used'=>false],
                    3 => ['present'=>false, 'ok'=>false, 'pm_id'=>null, 'used'=>false],
                ],
            ];
        }

        if ($byCpf[$cpfNorm]['nome'] === '' && !empty($row->nome_relatorio)) {
            $byCpf[$cpfNorm]['nome'] = (string)$row->nome_relatorio;
        }

        if (!$byCpf[$cpfNorm]['cadastro_id'] && $row->agente_cadastro_id) {
            $byCpf[$cpfNorm]['cadastro_id'] = (int)$row->agente_cadastro_id;
        }

        $rm = Carbon::parse($row->referencia_month)->startOfMonth()->toDateString();
        $n = null;
        if ($rm === $ref1Iso) $n = 1;
        elseif ($rm === $ref2Iso) $n = 2;
        elseif ($rm === $ref3Iso) $n = 3;
        if (!$n) continue;

        $byCpf[$cpfNorm]['parcelas'][$n]['present'] = true;
        $byCpf[$cpfNorm]['parcelas'][$n]['ok']      = $this->pmIsOk($row, $hasManualStatus);
        $byCpf[$cpfNorm]['parcelas'][$n]['pm_id']   = (int)$row->id;
    }

    // 3) “zerar ciclo”: pagamentos já consumidos em itens
    $pmIds = [];
    foreach ($byCpf as $it) {
        foreach ([1,2,3] as $n) {
            if (!empty($it['parcelas'][$n]['pm_id'])) $pmIds[] = (int)$it['parcelas'][$n]['pm_id'];
        }
    }
    $pmIds = array_values(array_unique($pmIds));

    $usedMap = [];
    if (!empty($pmIds) && Schema::hasTable('refinanciamento_itens')) {
        $col = null;
        if (Schema::hasColumn('refinanciamento_itens', 'pagamento_mensalidade_id')) {
            $col = 'pagamento_mensalidade_id';
        } elseif (Schema::hasColumn('refinanciamento_itens', 'pagamentos_mensalidade_id')) {
            $col = 'pagamentos_mensalidade_id';
        }

        if ($col) {
            $used = DB::table('refinanciamento_itens')
                ->whereIn($col, $pmIds)
                ->pluck($col)
                ->all();

            foreach ($used as $id) $usedMap[(int)$id] = true;
        }
    }

    foreach ($byCpf as &$item) {
        foreach ([1,2,3] as $n) {
            $pmId = (int)($item['parcelas'][$n]['pm_id'] ?? 0);
            if ($pmId && isset($usedMap[$pmId])) {
                $item['parcelas'][$n]['used'] = true;
            }
        }
    }
    unset($item);

    // 4) lista final
    $final = [];
    foreach ($byCpf as $item) {
        $hasUsed = (bool)$item['parcelas'][1]['used']
            || (bool)$item['parcelas'][2]['used']
            || (bool)$item['parcelas'][3]['used'];

        if ($hasUsed) continue;

        $ok1 = (bool)$item['parcelas'][1]['ok'];
        $ok2 = (bool)$item['parcelas'][2]['ok'];
        $ok3 = (bool)$item['parcelas'][3]['ok'];
        $parcelasOk = (int)$ok1 + (int)$ok2 + (int)$ok3;

        $can = ($parcelasOk === 3) && !empty($item['cadastro_id']);

        $final[] = [
            'cpf'           => $item['cpf'],
            'nome'          => $item['nome'] ?: '-',
            'cadastro_id'   => $item['cadastro_id'],
            'parcelas'      => [
                '1' => $item['parcelas'][1],
                '2' => $item['parcelas'][2],
                '3' => $item['parcelas'][3],
            ],
            'parcelas_ok'   => $parcelasOk,
            'can_refinance' => $can,
        ];
    }

    usort($final, function($a,$b){
        if ((int)$b['can_refinance'] !== (int)$a['can_refinance']) {
            return (int)$b['can_refinance'] <=> (int)$a['can_refinance'];
        }
        if ((int)$b['parcelas_ok'] !== (int)$a['parcelas_ok']) {
            return (int)$b['parcelas_ok'] <=> (int)$a['parcelas_ok'];
        }
        return strcmp((string)$a['nome'], (string)$b['nome']);
    });

    $aptos = 0;
    foreach ($final as $it) if (!empty($it['can_refinance'])) $aptos++;

    return response()->json([
        'ok' => true,
        'refs' => [
            'ref1' => ['iso'=>$ref1Iso, 'fmt'=>substr($ref1Iso,5,2).'/'.substr($ref1Iso,0,4)],
            'ref2' => ['iso'=>$ref2Iso, 'fmt'=>substr($ref2Iso,5,2).'/'.substr($ref2Iso,0,4)],
            'ref3' => ['iso'=>$ref3Iso, 'fmt'=>substr($ref3Iso,5,2).'/'.substr($ref3Iso,0,4)],
        ],
        'total' => count($final),
        'aptos' => $aptos,
        'rows'  => $final,
    ]);
}



/**
 * EXECUTA o refinanciamento do cadastro (fluxo AGENTE).
 * Correção aplicada: NÃO insere mais colunas que não existem em refinanciamento_itens
 * (manual_status / ok / parcela_n). Agora insere somente o que sua migration tem.
 */
public function retornoRefinExecutar(Request $r, int $cadastro)
{
    $trace = 'REFI#EXEC#' . now('UTC')->format('Ymd-His-v') . '-' . Str::upper(Str::random(4));

    $ref1 = $r->input('ref1');
    $ref2 = $r->input('ref2');
    $ref3 = $r->input('ref3');

    if (!$ref1 || !$ref2 || !$ref3) {
        Log::warning("[REFI][exec][$trace] refs_missing", [
            'user_id' => auth()->id(),
            'cadastro_id' => $cadastro,
        ]);
        return response()->json(['ok' => false, 'message' => 'Refs (ref1/ref2/ref3) ausentes.'], 422);
    }

    try {
        $ref1Iso = Carbon::parse($ref1)->startOfMonth()->toDateString();
        $ref2Iso = Carbon::parse($ref2)->startOfMonth()->toDateString();
        $ref3Iso = Carbon::parse($ref3)->startOfMonth()->toDateString();
    } catch (\Throwable $e) {
        Log::warning("[REFI][exec][$trace] refs_invalid", [
            'user_id' => auth()->id(),
            'cadastro_id' => $cadastro,
            'ref1' => $ref1, 'ref2' => $ref2, 'ref3' => $ref3,
        ]);
        return response()->json(['ok' => false, 'message' => 'Refs inválidas.'], 422);
    }

    $cad = AgenteCadastro::find($cadastro);
    if (!$cad) {
        return response()->json(['ok'=>false,'message'=>'Cadastro não encontrado.'], 404);
    }

    $hasManualStatus = Schema::hasColumn('pagamentos_mensalidades', 'manual_status');
    $hasValor        = Schema::hasColumn('pagamentos_mensalidades', 'valor');

    // CPF pode estar vazio no cadastro - busca fallback no retorno
    $cpfDigits = $this->rfNormDoc($cad->cpf_cnpj ?? '');

    if ($cpfDigits === '') {
        $cpfFromPm = DB::table('pagamentos_mensalidades')
            ->where('agente_cadastro_id', $cadastro)
            ->where(function ($q) use ($ref1Iso, $ref2Iso, $ref3Iso) {
                $q->whereDate('referencia_month', $ref1Iso)
                  ->orWhereDate('referencia_month', $ref2Iso)
                  ->orWhereDate('referencia_month', $ref3Iso);
            })
            ->orderByDesc('id')
            ->value('cpf_cnpj');

        $cpfDigits = $this->rfNormDoc($cpfFromPm);
    }

    if ($cpfDigits === '') {
        Log::warning("[REFI][exec][$trace] cpf_missing", [
            'user_id' => auth()->id(),
            'cadastro_id' => $cadastro,
            'refs' => [$ref1Iso, $ref2Iso, $ref3Iso],
        ]);
        return response()->json(['ok'=>false,'message'=>'CPF do cadastro está vazio e não foi possível inferir pelo retorno.'], 422);
    }

    // Backfill do CPF no cadastro (isso elimina cpf_missing na aprovação)
    $this->rfBackfillCadastroCpf($cadastro, $cpfDigits);

    // Evita duplicar o mesmo ciclo para o mesmo cadastro/CPF
    if (Schema::hasTable('refinanciamentos')) {
        $dup = DB::table('refinanciamentos')
            ->where('cadastro_id', $cadastro)
            ->whereDate('ref1', $ref1Iso)
            ->whereDate('ref2', $ref2Iso)
            ->whereDate('ref3', $ref3Iso)
            ->whereIn('status', ['pending','pendente','in_progress','processing','approved','aprovado','done','concluido','concluído','ok'])
            ->exists();

        if ($dup) {
            return response()->json([
                'ok' => false,
                'message' => 'Já existe refinanciamento criado para esse cadastro nesse ciclo.',
            ], 409);
        }
    }

    return DB::transaction(function () use (
        $trace, $r, $cad, $cadastro, $cpfDigits,
        $ref1Iso, $ref2Iso, $ref3Iso,
        $hasManualStatus, $hasValor
    ) {
        // Busca as 3 linhas do retorno do ciclo:
        // preferencial: agente_cadastro_id; fallback: cpf normalizado
        $cpfNorm = $cpfDigits;

        $rows = DB::table('pagamentos_mensalidades as p')
            ->select([
                'p.id',
                'p.cpf_cnpj',
                'p.agente_cadastro_id',
                'p.referencia_month',
                'p.status_code',
                'p.nome_relatorio',
            ])
            ->when($hasManualStatus, fn($q) => $q->addSelect('p.manual_status'))
            ->when($hasValor, fn($q) => $q->addSelect('p.valor'))
            ->where(function ($w) use ($cadastro, $cpfNorm) {
                $w->where('p.agente_cadastro_id', $cadastro)
                  ->orWhereRaw("REPLACE(REPLACE(REPLACE(REPLACE(p.cpf_cnpj,'.',''),'-',''),'/',''),' ','') = ?", [$cpfNorm]);
            })
            ->where(function ($q) use ($ref1Iso, $ref2Iso, $ref3Iso) {
                $q->whereDate('p.referencia_month', $ref1Iso)
                  ->orWhereDate('p.referencia_month', $ref2Iso)
                  ->orWhereDate('p.referencia_month', $ref3Iso);
            })
            ->orderByDesc('p.id')
            ->get();

        // Escolhe 1 linha por mês (se houver duplicadas):
        // regra: prefere OK; senão pega a mais recente.
        $pickFor = function (string $refIso) use ($rows, $hasManualStatus) {
            $bucket = $rows->filter(function($x) use ($refIso) {
                return Carbon::parse($x->referencia_month)->startOfMonth()->toDateString() === $refIso;
            });

            if ($bucket->isEmpty()) return null;

            $ok = $bucket->first(fn($x) => $this->pmIsOk($x, $hasManualStatus));
            return $ok ?: $bucket->first();
        };

        $r1 = $pickFor($ref1Iso);
        $r2 = $pickFor($ref2Iso);
        $r3 = $pickFor($ref3Iso);

        if (!$r1 || !$r2 || !$r3) {
            Log::warning("[REFI][exec][$trace] missing_month_rows", [
                'cadastro_id' => $cadastro,
                'cpf' => $cpfDigits,
                'have' => [
                    'ref1' => (bool)$r1,
                    'ref2' => (bool)$r2,
                    'ref3' => (bool)$r3,
                ],
                'refs' => [$ref1Iso,$ref2Iso,$ref3Iso],
            ]);
            return response()->json([
                'ok' => false,
                'message' => 'Não encontrei as 3 parcelas no retorno para esse ciclo.',
            ], 422);
        }

        // valida OK nas 3 parcelas
        $ok1 = $this->pmIsOk($r1, $hasManualStatus);
        $ok2 = $this->pmIsOk($r2, $hasManualStatus);
        $ok3 = $this->pmIsOk($r3, $hasManualStatus);

        if (!(($ok1 ? 1 : 0) + ($ok2 ? 1 : 0) + ($ok3 ? 1 : 0) === 3)) {
            return response()->json([
                'ok' => false,
                'message' => 'As 3 parcelas precisam estar OK (status 1/4 ou manual pago).',
                'debug' => [
                    'ok1' => $ok1, 'ok2' => $ok2, 'ok3' => $ok3,
                    'pm_ids' => [(int)$r1->id,(int)$r2->id,(int)$r3->id],
                ]
            ], 422);
        }

        $pmIds = [(int)$r1->id, (int)$r2->id, (int)$r3->id];

        // Bloqueia se qualquer pm_id já foi consumido em refinanciamento_itens
        if (Schema::hasTable('refinanciamento_itens') && Schema::hasColumn('refinanciamento_itens', 'pagamento_mensalidade_id')) {
            $used = DB::table('refinanciamento_itens')
                ->whereIn('pagamento_mensalidade_id', $pmIds)
                ->exists();

            if ($used) {
                return response()->json([
                    'ok' => false,
                    'message' => 'Este ciclo já foi consumido (há mensalidades já usadas em refinanciamento_itens).',
                ], 409);
            }
        }

        // Monta ciclo_key compatível com seu padrão
        $cycleKey = substr($ref1Iso, 0, 7) . '|' . substr($ref2Iso, 0, 7) . '|' . substr($ref3Iso, 0, 7);

        $nomeSnapshot   = (string)($cad->full_name ?? ($r1->nome_relatorio ?? ''));
        $agenteSnapshot = (string)($cad->agente_responsavel ?? 'Agente');
        $filialSnapshot = (string)($cad->agente_filial ?? ($cad->agente_filial_snapshot ?? ($cad->agente_responsavel ?? '')));

        $parcelasJson = [
            '1' => ['present'=>true,'ok'=>true,'pm_id'=>(int)$r1->id],
            '2' => ['present'=>true,'ok'=>true,'pm_id'=>(int)$r2->id],
            '3' => ['present'=>true,'ok'=>true,'pm_id'=>(int)$r3->id],
        ];

        // Cria registro principal em refinanciamentos
        if (!Schema::hasTable('refinanciamentos')) {
            return response()->json(['ok'=>false,'message'=>'Tabela refinanciamentos não existe.'], 500);
        }

        $refiId = DB::table('refinanciamentos')->insertGetId([
            'cadastro_id'         => $cadastro,
            'cpf_cnpj'            => $cpfDigits,
            'nome_snapshot'       => $nomeSnapshot ?: '-',
            'agente_snapshot'     => $agenteSnapshot ?: '-',
            'filial_snapshot'     => $filialSnapshot ?: '-',
            'cycle_key'           => $cycleKey,
            'ref1'                => $ref1Iso,
            'ref2'                => $ref2Iso,
            'ref3'                => $ref3Iso,
            'parcelas_ok'         => 3,
            'parcelas_json'       => json_encode($parcelasJson, JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES),
            'status'              => 'pending',
            'created_by_user_id'  => auth()->id(),
            'reviewed_by_user_id' => null,
            'reviewed_at'         => null,
            'refinanciamento_id'  => null,
            'analista_note'       => null,
            'coordenador_note'    => null,
            'created_at'          => now(),
            'updated_at'          => now(),
        ]);

        // Cria itens (somente colunas existentes na tabela)
        if (Schema::hasTable('refinanciamento_itens')) {
            $cols = Schema::getColumnListing('refinanciamento_itens');
            $hasCol = fn($c) => in_array($c, $cols, true);

            $mkItem = function($pmRow, string $refIso) use ($refiId, $hasCol) {
                $payload = [
                    'refinanciamento_id' => $refiId,
                ];

                if ($hasCol('pagamento_mensalidade_id')) $payload['pagamento_mensalidade_id'] = (int)$pmRow->id;

                // mês do ciclo
                if ($hasCol('mes_ref')) $payload['mes_ref'] = $refIso;

                // valor (se existir no retorno)
                if ($hasCol('valor')) {
                    $payload['valor'] = isset($pmRow->valor) ? (float)$pmRow->valor : 0.0;
                }

                if ($hasCol('status_code')) $payload['status_code'] = (string)($pmRow->status_code ?? null);

                if ($hasCol('created_at')) $payload['created_at'] = now();
                if ($hasCol('updated_at')) $payload['updated_at'] = now();

                return $payload;
            };

            DB::table('refinanciamento_itens')->insert([
                $mkItem($r1, $ref1Iso),
                $mkItem($r2, $ref2Iso),
                $mkItem($r3, $ref3Iso),
            ]);
        }

        // Opcional: se essas mensalidades não tinham vínculo, vincula (ajuda o sistema todo)
        DB::table('pagamentos_mensalidades')
            ->whereIn('id', $pmIds)
            ->whereNull('agente_cadastro_id')
            ->update(['agente_cadastro_id' => $cadastro]);

        Log::info("[REFI][exec][$trace] created", [
            'refin_id' => $refiId,
            'cadastro_id' => $cadastro,
            'cpf' => $cpfDigits,
            'cycle' => [$ref1Iso,$ref2Iso,$ref3Iso],
        ]);

        return response()->json([
            'ok' => true,
            'refin_id' => $refiId,
            'cadastro_id' => $cadastro,
            'cpf' => $cpfDigits,
            'cycle_key' => $cycleKey,
        ]);
    });
}



private function pmIsOk($row, bool $hasManualStatus): bool
{
    $st = strtoupper(trim((string)($row->status_code ?? '')));
    $okArquivo = in_array($st, ['1', '4'], true);

    if (!$hasManualStatus) return $okArquivo;

    $manual = mb_strtolower(trim((string)($row->manual_status ?? '')));
    $okManual = in_array($manual, ['pago', 'ok', 'concluido', 'concluído', 'done'], true);

    return $okArquivo || $okManual;
}

private function rfNormDoc(?string $v): string
{
    return preg_replace('/\D+/', '', (string)$v);
}
/**
 * Se o cadastro estiver sem CPF, tenta preencher usando um CPF encontrado no retorno.
 * Isso elimina o cpf_missing na aprovação quando o fluxo usa o cadastro como fonte.
 */
private function rfBackfillCadastroCpf(int $cadastroId, string $cpfDigits): void
{
    if ($cadastroId <= 0) return;
    $cpfDigits = $this->rfNormDoc($cpfDigits);
    if ($cpfDigits === '') return;

    try {
        $cad = AgenteCadastro::find($cadastroId);
        if (!$cad) return;

        $curr = $this->rfNormDoc($cad->cpf_cnpj ?? '');
        if ($curr === '') {
            $cad->cpf_cnpj = $cpfDigits; // salva limpo mesmo
            $cad->save();
        }
    } catch (\Throwable $e) {
        // silencioso
    }
}
/* ===================== helpers ===================== */

private function rfResolveMesISO(Request $r): string
{
    $tz = config('app.timezone') ?: (env('APP_TIMEZONE') ?: 'America/Sao_Paulo');

    $mes = trim((string)($r->query('mes') ?? $r->input('mes') ?? ''));
    if ($mes !== '' && preg_match('~^\d{4}-\d{2}$~', $mes)) {
        return $mes;
    }

    // fallback: tenta ref1
    $ref1 = trim((string)($r->query('ref1') ?? $r->input('ref1') ?? ''));
    if ($ref1 !== '') {
        try {
            return Carbon::parse($ref1, $tz)->format('Y-m');
        } catch (\Throwable $e) {
            // ignora
        }
    }

    return now($tz)->format('Y-m');
}

private function rfRefsFromMes(string $mesISO): array
{
    $tz = config('app.timezone') ?: (env('APP_TIMEZONE') ?: 'America/Sao_Paulo');

    if (!preg_match('~^\d{4}-\d{2}$~', $mesISO)) {
        $mesISO = now($tz)->format('Y-m');
    }

    $base = Carbon::createFromFormat('Y-m', $mesISO, $tz)->startOfMonth();

    // 3 meses consecutivos
    $ref1 = $base->copy();
    $ref2 = $base->copy()->addMonthNoOverflow();
    $ref3 = $base->copy()->addMonthsNoOverflow(2);

    return [$ref1, $ref2, $ref3];
}


// =====================================================
// EDITAR DADOS CADASTRAIS — agente_cadastros
// Autocomplete -> Modal -> Update
// =====================================================

public function cadastroEditSearch(Request $request)
{
    if (!Schema::hasTable('agente_cadastros')) {
        return response()->json(['ok' => false, 'items' => [], 'message' => 'Tabela agente_cadastros não existe.'], 422);
    }

    $q = trim((string) $request->query('q', ''));
    if ($q === '') {
        return response()->json(['ok' => true, 'items' => []]);
    }

    $digits = preg_replace('/\D+/', '', $q);

    $rows = DB::table('agente_cadastros')
        ->select('id', 'cpf_cnpj', 'full_name', 'email', 'cellphone', 'city', 'uf')
        ->where(function ($w) use ($q, $digits) {
            // busca por CPF/CNPJ (prefixo)
            if ($digits !== '') {
                $w->orWhere('cpf_cnpj', 'like', $digits . '%');
            }
            // busca por nome (contém)
            $w->orWhere('full_name', 'like', '%' . $q . '%');
        })
        ->orderBy('full_name')
        ->limit(12)
        ->get();

    $items = $rows->map(function ($r) {
        $cpf = (string)($r->cpf_cnpj ?? '');
        $nome = (string)($r->full_name ?? '');
        $label = trim($cpf . ' • ' . $nome);
        return [
            'id' => (int) $r->id,
            'cpf_cnpj' => $cpf,
            'full_name' => $nome,
            'label' => $label,
            'meta' => trim(($r->city ?? '') . '/' . ($r->uf ?? '')),
        ];
    });

    return response()->json(['ok' => true, 'items' => $items]);
}

public function cadastroEditShow($id)
{
    if (!Schema::hasTable('agente_cadastros')) {
        return response()->json(['ok' => false, 'message' => 'Tabela agente_cadastros não existe.'], 422);
    }

    $row = DB::table('agente_cadastros')->where('id', (int)$id)->first();
    if (!$row) {
        return response()->json(['ok' => false, 'message' => 'Cadastro não encontrado.'], 404);
    }

    // JSON fields -> string bonitinha no textarea
    foreach (['anticipations_json', 'documents_json'] as $col) {
        if (isset($row->$col) && $row->$col !== null && $row->$col !== '') {
            $decoded = is_string($row->$col) ? json_decode($row->$col, true) : $row->$col;
            if (json_last_error() === JSON_ERROR_NONE) {
                $row->$col = json_encode($decoded, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
            }
        }
    }

    return response()->json(['ok' => true, 'data' => $row]);
}

public function cadastroEditUpdate(Request $request, $id)
{
    if (!Schema::hasTable('agente_cadastros')) {
        return response()->json(['ok' => false, 'message' => 'Tabela agente_cadastros não existe.'], 422);
    }

    $id = (int) $id;

    // Regras alinhadas com sua migration
    $rules = [
        'doc_type' => 'nullable|string|max:10',
        'cpf_cnpj' => 'nullable|string|max:20',
        'rg' => 'nullable|string|max:30',
        'orgao_expedidor' => 'nullable|string|max:80',
        'full_name' => 'required|string|max:200',
        'birth_date' => 'nullable|date',
        'profession' => 'nullable|string|max:120',
        'marital_status' => 'nullable|string|max:40',

        'cep' => 'nullable|string|max:12',
        'address' => 'nullable|string|max:200',
        'address_number' => 'nullable|string|max:20',
        'complement' => 'nullable|string|max:120',
        'neighborhood' => 'nullable|string|max:120',
        'city' => 'nullable|string|max:120',
        'uf' => 'nullable|string|size:2',

        'cellphone' => 'nullable|string|max:30',
        'orgao_publico' => 'nullable|string|max:160',
        'situacao_servidor' => 'nullable|string|max:60',
        'matricula_servidor_publico' => 'nullable|string|max:60',
        'email' => 'nullable|email|max:160',

        'bank_name' => 'nullable|string|max:120',
        'bank_agency' => 'nullable|string|max:40',
        'bank_account' => 'nullable|string|max:60',
        'account_type' => 'nullable|in:corrente,poupanca',
        'pix_key' => 'nullable|string|max:160',

        'contrato_mensalidade' => 'nullable|numeric',
        'contrato_prazo_meses' => 'nullable|integer',
        'contrato_taxa_antecipacao' => 'nullable|numeric',
        'contrato_margem_disponivel' => 'nullable|numeric',
        'contrato_data_aprovacao' => 'nullable|date',
        'contrato_data_envio_primeira' => 'nullable|date',
        'contrato_valor_antecipacao' => 'nullable|numeric',
        'contrato_status_contrato' => 'nullable|string|max:60',
        'contrato_mes_averbacao' => 'nullable|date',
        'contrato_codigo_contrato' => 'nullable|string|max:80',
        'contrato_doacao_associado' => 'nullable|numeric',

        'calc_valor_bruto' => 'nullable|numeric',
        'calc_liquido_cc' => 'nullable|numeric',
        'calc_prazo_antecipacao' => 'nullable|integer',
        'calc_mensalidade_associativa' => 'nullable|numeric',

        'anticipations_json' => 'nullable|string',
        'agente_responsavel' => 'nullable|string|max:160',
        'agente_filial' => 'nullable|string|max:160',
        'observacoes' => 'nullable|string',

        'auxilio_taxa' => 'nullable|numeric',
        'auxilio_data_envio' => 'nullable|date',
        'auxilio_status' => 'nullable|string|max:80',

        'documents_json' => 'nullable|string',
    ];

    $v = Validator::make($request->all(), $rules);
    if ($v->fails()) {
        return response()->json(['ok' => false, 'message' => 'Validação falhou.', 'errors' => $v->errors()], 422);
    }

    $data = $v->validated();

    // Normalizações úteis
    if (array_key_exists('cpf_cnpj', $data)) {
        $cpf = preg_replace('/\D+/', '', (string)$data['cpf_cnpj']);
        $data['cpf_cnpj'] = $cpf !== '' ? $cpf : null;
    }

    if (array_key_exists('doc_type', $data) && $data['doc_type'] !== null) {
        $data['doc_type'] = strtoupper(trim((string)$data['doc_type']));
    }

    if (array_key_exists('uf', $data) && $data['uf'] !== null) {
        $data['uf'] = strtoupper(trim((string)$data['uf']));
    }

    // JSON fields: validar JSON se vier preenchido
    foreach (['anticipations_json', 'documents_json'] as $col) {
        if (array_key_exists($col, $data)) {
            $val = trim((string)($data[$col] ?? ''));
            if ($val === '') {
                $data[$col] = null;
                continue;
            }
            $decoded = json_decode($val, true);
            if (json_last_error() !== JSON_ERROR_NONE) {
                return response()->json([
                    'ok' => false,
                    'message' => "Campo {$col} não é um JSON válido.",
                    'errors' => [$col => ['JSON inválido. Verifique vírgulas, aspas e chaves.']]
                ], 422);
            }
            $data[$col] = json_encode($decoded, JSON_UNESCAPED_UNICODE);
        }
    }

    $exists = DB::table('agente_cadastros')->where('id', $id)->exists();
    if (!$exists) {
        return response()->json(['ok' => false, 'message' => 'Cadastro não encontrado.'], 404);
    }

    $data['updated_at'] = now();

    DB::table('agente_cadastros')->where('id', $id)->update($data);

    return response()->json(['ok' => true, 'message' => 'Dados atualizados com sucesso.']);
}


//EDITAR VALOR REFINANCIAMENTO 


// =====================
// ADMIN: PENDENTES REFINANCIAMENTO
// =====================

private function normDoc(?string $v): string
{
    $v = (string)($v ?? '');
    $v = preg_replace('/\D+/', '', $v);
    return $v ?: '';
}
private function cpfNormExpr(string $col): string
{
    return "REPLACE(REPLACE(REPLACE(REPLACE({$col},'.',''),'-',''),'/',''),' ','')";
}

/**
 * Regra "pago" igual Tesouraria:
 * - APP: existe comprovante kind/tipo = 'app'
 * - WEB: existe 'associado' E existe 'agente'
 */
private function refiPaidSql(): ?string
{
    if (!\Schema::hasTable('refinanciamento_comprovantes')) return null;

    $kindCol = null;
    if (\Schema::hasColumn('refinanciamento_comprovantes', 'kind')) $kindCol = 'kind';
    elseif (\Schema::hasColumn('refinanciamento_comprovantes', 'tipo')) $kindCol = 'tipo';

    if ($kindCol) {
        return "
          (
            EXISTS (
              SELECT 1 FROM refinanciamento_comprovantes rc
              WHERE rc.refinanciamento_id = r.id
                AND LOWER(TRIM(COALESCE(rc.{$kindCol},''))) = 'app'
            )
            OR
            (
              EXISTS (
                SELECT 1 FROM refinanciamento_comprovantes rc
                WHERE rc.refinanciamento_id = r.id
                  AND LOWER(TRIM(COALESCE(rc.{$kindCol},''))) = 'associado'
              )
              AND
              EXISTS (
                SELECT 1 FROM refinanciamento_comprovantes rc
                WHERE rc.refinanciamento_id = r.id
                  AND LOWER(TRIM(COALESCE(rc.{$kindCol},''))) = 'agente'
              )
            )
          )
        ";
    }

    // fallback antigo: qualquer comprovante já conta como "pago"
    return "EXISTS (SELECT 1 FROM refinanciamento_comprovantes rc WHERE rc.refinanciamento_id = r.id)";
}

/**
 * GET admin/refi/pendentes/list (JSON paginado)
 */
public function refiPendentesList(\Illuminate\Http\Request $request)
{
    if (!\Schema::hasTable('refinanciamentos')) {
        return response()->json([
            'data' => [],
            'meta' => ['current_page'=>1,'last_page'=>1,'total'=>0],
            'error' => 'Tabela refinanciamentos não existe.',
        ], 422);
    }

    $perPage = (int)($request->query('per_page', 12));
    $perPage = max(1, min(200, $perPage));
    $page    = (int)($request->query('page', 1));
    $q       = trim((string)$request->query('q', ''));
    $origem  = strtolower(trim((string)$request->query('origem', ''))); // app|web|''

    $cpfNormR = $this->cpfNormExpr('r.cpf_cnpj');

    // join leve para resolver nome/agente por CPF (WEB)
    $hasAg = \Schema::hasTable('agente_cadastros');

    $qb = \DB::table('refinanciamentos as r');

    if ($hasAg) {
        $acx = \DB::table('agente_cadastros')
            ->select([
                \DB::raw($this->cpfNormExpr('cpf_cnpj') . ' as cpf_norm'),
                \DB::raw('MAX(id) as id'),
            ])
            ->groupBy(\DB::raw($this->cpfNormExpr('cpf_cnpj')));

        $qb->leftJoinSub($acx, 'acx', function ($j) use ($cpfNormR) {
            $j->on(\DB::raw($cpfNormR), '=', 'acx.cpf_norm');
        });

        $qb->leftJoin('agente_cadastros as ac', 'ac.id', '=', 'acx.id');
    }

    // pendente = NOT (paidSql)
    $paidSql = $this->refiPaidSql();
    if ($paidSql) {
        $qb->whereRaw("NOT ({$paidSql})");
    }

    // filtro origem (heurística defensiva)
    if ($origem === 'app') {
        $qb->where(function($w){
            if (\Schema::hasColumn('refinanciamentos','associadodois_cadastro_id')) {
                $w->whereNotNull('r.associadodois_cadastro_id');
            } else {
                $w->whereRaw("LOWER(TRIM(COALESCE(r.origem,''))) = 'app'");
            }
        });
    } elseif ($origem === 'web') {
        $qb->where(function($w){
            if (\Schema::hasColumn('refinanciamentos','associadodois_cadastro_id')) {
                $w->whereNull('r.associadodois_cadastro_id');
            } else {
                $w->whereRaw("LOWER(TRIM(COALESCE(r.origem,''))) <> 'app'");
            }
        });
    }

    // busca
    if ($q !== '') {
        $qDoc = $this->normDoc($q);

        $qb->where(function ($w) use ($q, $qDoc, $hasAg) {
            if ($qDoc !== '') {
                $w->orWhereRaw($this->cpfNormExpr('r.cpf_cnpj') . " LIKE ?", ["%{$qDoc}%"]);
            }

            if (\Schema::hasColumn('refinanciamentos','nome_snapshot')) {
                $w->orWhere('r.nome_snapshot', 'like', "%{$q}%");
            }

            if ($hasAg) {
                $w->orWhere('ac.full_name', 'like', "%{$q}%");
                if (\Schema::hasColumn('agente_cadastros','agente_responsavel')) {
                    $w->orWhere('ac.agente_responsavel', 'like', "%{$q}%");
                }
            }
        });
    }

    // selects
    $nomeExpr = \Schema::hasColumn('refinanciamentos','nome_snapshot')
        ? "COALESCE(NULLIF(TRIM(r.nome_snapshot),''), NULLIF(TRIM(ac.full_name),''))"
        : "NULLIF(TRIM(ac.full_name),'')";

    $agExpr = (\Schema::hasColumn('agente_cadastros','agente_responsavel') ? "NULLIF(TRIM(ac.agente_responsavel),'')" : "NULL");

    $valorExpr = \Schema::hasColumn('refinanciamentos','valor_refinanciamento')
        ? "COALESCE(r.valor_refinanciamento, r.valor_total, 0)"
        : (\Schema::hasColumn('refinanciamentos','valor_total') ? "COALESCE(r.valor_total,0)" : "0");

    $origExpr = \Schema::hasColumn('refinanciamentos','origem')
        ? "LOWER(TRIM(COALESCE(r.origem,'')))"
        : (\Schema::hasColumn('refinanciamentos','associadodois_cadastro_id')
            ? "CASE WHEN r.associadodois_cadastro_id IS NULL THEN 'web' ELSE 'app' END"
            : "'-'"
        );

    $qb->select([
        'r.id',
        \DB::raw("NULLIF(TRIM(r.cpf_cnpj),'') as cpf_cnpj"),
        \DB::raw("{$origExpr} as origem"),
        \DB::raw("{$nomeExpr} as nome"),
        \DB::raw("COALESCE({$agExpr}, NULLIF(TRIM(ac.full_name),'')) as agente_responsavel"),
        \DB::raw("{$valorExpr} as valor_atual"),
        \DB::raw("DATE_FORMAT(r.created_at, '%d/%m/%Y %H:%i') as created_at_br"),
    ]);

    $qb->orderByDesc('r.id');

    $rows = $qb->paginate($perPage, ['*'], 'page', $page);

    // formata cpf (apenas visual)
    $data = collect($rows->items())->map(function($it){
        $doc = preg_replace('/\D+/', '', (string)($it->cpf_cnpj ?? ''));
        $it->cpf_cnpj_fmt = $doc !== '' ? $doc : null;
        return $it;
    })->values();

    return response()->json([
        'data' => $data,
        'meta' => [
            'current_page' => $rows->currentPage(),
            'last_page'    => $rows->lastPage(),
            'total'        => $rows->total(),
        ],
    ]);
}

/**
 * GET admin/refi/pendentes/{refinanciamento} (JSON detalhado)
 */
public function refiPendentesShow(\Illuminate\Http\Request $request, int $refinanciamento)
{
    if (!\Schema::hasTable('refinanciamentos')) {
        return response()->json(['error' => 'Tabela refinanciamentos não existe.'], 422);
    }

    $r = \DB::table('refinanciamentos as r')->where('r.id', $refinanciamento)->first();
    if (!$r) return response()->json(['error' => 'Refinanciamento não encontrado.'], 404);

    // pendente?
    $paidSql = $this->refiPaidSql();
    $isPago = false;
    if ($paidSql) {
        $isPago = (bool)\DB::table('refinanciamentos as r')
            ->where('r.id', $refinanciamento)
            ->whereRaw($paidSql)
            ->exists();
    }
    $isPendente = !$isPago;

    // resolve cpf (digits)
    $cpfDigits = $this->normDoc((string)($r->cpf_cnpj ?? ''));

    // ---------------------------------------------
    // ✅ Calcula margens sem GROUP BY (evita 1055)
    // Prioridade do valor:
    // 1) tp_margem (tesouraria_pagamentos.contrato_margem_disponivel)
    // 2) ac_margem (agente_cadastros.contrato_margem_disponivel)
    // 3) r.valor_refinanciamento
    // 4) r.valor_total
    // ---------------------------------------------
    $tp_margem = null;
    $ac_margem = null;

    $hasTP = \Schema::hasTable('tesouraria_pagamentos')
        && \Schema::hasColumn('tesouraria_pagamentos', 'cpf_cnpj')
        && \Schema::hasColumn('tesouraria_pagamentos', 'contrato_margem_disponivel');

    if ($hasTP && $cpfDigits !== '') {
        $tp_margem = \DB::table('tesouraria_pagamentos as tp')
            ->whereRaw($this->cpfNormExpr('tp.cpf_cnpj') . ' = ?', [$cpfDigits])
            ->max('tp.contrato_margem_disponivel');
        $tp_margem = is_null($tp_margem) ? null : (float)$tp_margem;
    }

    $hasAC = \Schema::hasTable('agente_cadastros')
        && \Schema::hasColumn('agente_cadastros', 'cpf_cnpj')
        && \Schema::hasColumn('agente_cadastros', 'contrato_margem_disponivel');

    if ($hasAC && $cpfDigits !== '') {
        $ac_margem = \DB::table('agente_cadastros as ac')
            ->whereRaw($this->cpfNormExpr('ac.cpf_cnpj') . ' = ?', [$cpfDigits])
            ->max('ac.contrato_margem_disponivel');
        $ac_margem = is_null($ac_margem) ? null : (float)$ac_margem;
    }

    $r_valor_ref = \Schema::hasColumn('refinanciamentos','valor_refinanciamento') ? ($r->valor_refinanciamento ?? null) : null;
    $r_valor_total = \Schema::hasColumn('refinanciamentos','valor_total') ? ($r->valor_total ?? null) : null;

    $valorAtual = 0.0;
    if (!is_null($tp_margem)) {
        $valorAtual = (float)$tp_margem;
    } elseif (!is_null($ac_margem)) {
        $valorAtual = (float)$ac_margem;
    } elseif (!is_null($r_valor_ref)) {
        $valorAtual = (float)$r_valor_ref;
    } elseif (!is_null($r_valor_total)) {
        $valorAtual = (float)$r_valor_total;
    }

    // resolve nome/agente por CPF (WEB primeiro)
    $nome = null;
    if (\Schema::hasColumn('refinanciamentos','nome_snapshot')) {
        $nome = trim((string)($r->nome_snapshot ?? '')) ?: null;
    }

    $agenteResp = null;

    if (\Schema::hasTable('agente_cadastros') && $cpfDigits !== '') {
        $ag = \DB::table('agente_cadastros')
            ->whereRaw($this->cpfNormExpr('cpf_cnpj') . ' = ?', [$cpfDigits])
            ->orderByDesc('id')
            ->first();

        if ($ag) {
            $agenteResp = trim((string)($ag->agente_responsavel ?? '')) ?: trim((string)($ag->full_name ?? '')) ?: null;
            if (!$nome) $nome = trim((string)($ag->full_name ?? '')) ?: null;
        }
    }

    // APP fallback
    if (!$agenteResp && \Schema::hasTable('associadodois_cadastros') && $cpfDigits !== '') {
        $ap = \DB::table('associadodois_cadastros')
            ->whereRaw($this->cpfNormExpr('cpf_cnpj') . ' = ?', [$cpfDigits])
            ->orderByDesc('id')
            ->first();

        if ($ap) {
            $agenteResp = trim((string)($ap->agente_responsavel ?? '')) ?: trim((string)($ap->full_name ?? '')) ?: null;
            if (!$nome) $nome = trim((string)($ap->full_name ?? '')) ?: null;
        }
    }

    // qual coluna será atualizada?
    $updateCol = \Schema::hasColumn('refinanciamentos','valor_refinanciamento')
        ? 'valor_refinanciamento'
        : (\Schema::hasColumn('refinanciamentos','valor_total') ? 'valor_total' : null);

    return response()->json([
        'id' => (int)$r->id,
        'cpf_cnpj' => $cpfDigits ?: null,
        'cpf_cnpj_fmt' => $cpfDigits ?: null,
        'nome' => $nome,
        'agente_responsavel' => $agenteResp,
        'origem' => \Schema::hasColumn('refinanciamentos','associadodois_cadastro_id')
            ? (empty($r->associadodois_cadastro_id) ? 'web' : 'app')
            : (strtolower(trim((string)($r->origem ?? ''))) ?: '-'),
        'is_pendente' => $isPendente,
        'valor_atual' => (float)$valorAtual,
        'update_col'  => $updateCol,

        // debug
        'tp_margem' => $tp_margem,
        'ac_margem' => $ac_margem,
        'r_valor_ref' => $r_valor_ref,
        'r_valor_total'=> $r_valor_total,
    ]);
}


/**
 * PATCH admin/refi/pendentes/{refinanciamento}/valor
 * ✅ Atualiza:
 *   - agente_cadastros.contrato_margem_disponivel (registro mais recente do CPF)
 *   - tesouraria_pagamentos.contrato_margem_disponivel (registro mais recente do CPF)  ✅ para refletir "valor atual" (tp_margem)
 * ✅ Cria snapshot em refinanciamento_ajustes_valor (com valores ANTES da atualização)
 * ❗ Não altera valor_refinanciamento/valor_total (mantém sua versão estável)
 */
public function refiPendentesUpdateValor(\Illuminate\Http\Request $request, int $refinanciamento)
{
    $rid = 'REFI_PEND_UPDVAL_' . now()->format('Ymd-His') . '-' . substr((string)\Illuminate\Support\Str::uuid(), 0, 8);
    $uid = (int) (auth()->id() ?? 0);

    try {
        if (!\Schema::hasTable('refinanciamentos')) {
            return response()->json(['error' => 'Tabela refinanciamentos não existe.'], 422);
        }

        if (!\Schema::hasTable('refinanciamento_ajustes_valor')) {
            return response()->json(['error' => 'Tabela refinanciamento_ajustes_valor não existe. Rode a migration.'], 422);
        }

        // precisa existir agente_cadastros pois o update é lá
        if (!\Schema::hasTable('agente_cadastros') || !\Schema::hasColumn('agente_cadastros', 'contrato_margem_disponivel')) {
            return response()->json(['error' => 'Tabela agente_cadastros ou coluna contrato_margem_disponivel não existe.'], 422);
        }

        $valor = (float) $request->input('valor', 0);
        if (!is_finite($valor) || $valor <= 0) {
            return response()->json(['error' => 'Valor inválido.'], 422);
        }

        $motivo = trim((string)$request->input('motivo', '')) ?: null;

        $row = \DB::table('refinanciamentos')->where('id', $refinanciamento)->first();
        if (!$row) return response()->json(['error' => 'Refinanciamento não encontrado.'], 404);

        // só permite se ainda for pendente
        $paidSql = $this->refiPaidSql();
        if ($paidSql) {
            $isPago = (bool)\DB::table('refinanciamentos as r')
                ->where('r.id', $refinanciamento)
                ->whereRaw($paidSql)
                ->exists();

            if ($isPago) {
                return response()->json(['error' => 'Este refinanciamento já parece finalizado (comprovantes completos). Edição bloqueada.'], 422);
            }
        }

        $cpfDigits = $this->normDoc((string)($row->cpf_cnpj ?? ''));
        if ($cpfDigits === '') {
            return response()->json(['error' => 'CPF/CNPJ inválido no refinanciamento.'], 422);
        }

        // origem
        $origem = \Schema::hasColumn('refinanciamentos','associadodois_cadastro_id')
            ? (empty($row->associadodois_cadastro_id) ? 'web' : 'app')
            : (strtolower(trim((string)($row->origem ?? ''))) ?: '-');

        // -----------------------------
        // Captura valores ANTES (para snapshot/debug)
        // -----------------------------
        $tp_margem = null;
        $ac_margem = null;
        $a2_margem = null;

        // (1) TP (tesouraria) - pegamos o valor atual e também o ID mais recente (pra atualizar)
        $tpId = null;
        $hasTP = \Schema::hasTable('tesouraria_pagamentos')
            && \Schema::hasColumn('tesouraria_pagamentos', 'cpf_cnpj')
            && \Schema::hasColumn('tesouraria_pagamentos', 'contrato_margem_disponivel');

        if ($hasTP) {
            $tpRow = \DB::table('tesouraria_pagamentos as tp')
                ->select(['tp.id', 'tp.contrato_margem_disponivel'])
                ->whereRaw($this->cpfNormExpr('tp.cpf_cnpj') . ' = ?', [$cpfDigits])
                ->orderByDesc('tp.id')
                ->first();

            if ($tpRow) {
                $tpId = (int)$tpRow->id;
                $tp_margem = $tpRow->contrato_margem_disponivel !== null ? (float)$tpRow->contrato_margem_disponivel : null;
            }
        }

        // (2) Agente (registro mais recente do CPF) - é nele que vamos atualizar
        $ag = \DB::table('agente_cadastros as ac')
            ->whereRaw($this->cpfNormExpr('ac.cpf_cnpj') . ' = ?', [$cpfDigits])
            ->orderByDesc('ac.id')
            ->first();

        if (!$ag) {
            return response()->json(['error' => 'Nenhum cadastro de agente encontrado para este CPF/CNPJ.'], 422);
        }

        $agId = (int)$ag->id;
        $ac_margem = isset($ag->contrato_margem_disponivel) && $ag->contrato_margem_disponivel !== null
            ? (float)$ag->contrato_margem_disponivel
            : null;

        // (3) A2 (opcional, só debug)
        $hasA2 = \Schema::hasTable('associadodois_cadastros')
            && \Schema::hasColumn('associadodois_cadastros', 'cpf_cnpj')
            && \Schema::hasColumn('associadodois_cadastros', 'contrato_margem_disponivel');

        if ($hasA2) {
            $a2_margem = \DB::table('associadodois_cadastros as a2')
                ->whereRaw($this->cpfNormExpr('a2.cpf_cnpj') . ' = ?', [$cpfDigits])
                ->max('a2.contrato_margem_disponivel');
            $a2_margem = is_null($a2_margem) ? null : (float)$a2_margem;
        }

        // --------------------------------------------
        // Snapshot deve refletir como estava ANTES
        // Base = valor do agente ANTES (como você quer)
        // --------------------------------------------
        $valorBase = $ac_margem;
        $fonteBase = 'ac';

        $last = \DB::table('refinanciamento_ajustes_valor')
            ->where('refinanciamento_id', $refinanciamento)
            ->orderByDesc('id')
            ->first();

        // se nunca ajustou, antigo = valor do agente antes
        $valorAntigo = $last ? (float)$last->valor_novo : $ac_margem;

        // --------------------------------------------
        // ✅ Transação: atualiza AGENTE (+ TP p/ refletir) + grava snapshot
        // --------------------------------------------
        $snapshotId = null;

        \DB::transaction(function () use (
            $request, $uid, $rid,
            $refinanciamento, $cpfDigits, $origem,
            $agId, $tpId, $hasTP,
            $valor, $motivo,
            $fonteBase, $valorBase, $valorAntigo,
            $tp_margem, $ac_margem, $a2_margem,
            &$snapshotId
        ) {
            // 1) Atualiza agente (onde o Tesoureiro costuma buscar no WEB)
            \DB::table('agente_cadastros')
                ->where('id', $agId)
                ->update([
                    'contrato_margem_disponivel' => $valor,
                    'updated_at' => now(),
                ]);

            // 2) ✅ Atualiza também tesouraria_pagamentos (pra "Valor atual" refletir, já que sua tela prioriza tp_margem)
            if ($hasTP && $tpId) {
                \DB::table('tesouraria_pagamentos')
                    ->where('id', $tpId)
                    ->update([
                        'contrato_margem_disponivel' => $valor,
                        'updated_at' => now(),
                    ]);
            }

            // 3) Snapshot (com valores ANTES da atualização)
            $snapshotId = \DB::table('refinanciamento_ajustes_valor')->insertGetId([
                'refinanciamento_id' => $refinanciamento,
                'cpf_cnpj' => $cpfDigits ?: null,
                'origem' => $origem,

                'fonte_base' => $fonteBase,
                'valor_base' => $valorBase,      // ✅ agente antes
                'valor_antigo' => $valorAntigo,  // ✅ último ajuste ou agente antes
                'valor_novo' => $valor,

                'tp_margem' => $tp_margem, // valores ANTES (debug)
                'ac_margem' => $ac_margem,
                'a2_margem' => $a2_margem,

                'created_by_user_id' => $uid ?: null,
                'ip' => (string) $request->ip(),
                'user_agent' => substr((string)$request->userAgent(), 0, 255),
                'motivo' => $motivo,
                'meta' => json_encode([
                    'rid' => $rid,
                    'agente_cadastro_id' => $agId,
                    'tesouraria_pagamento_id' => $tpId,
                    'request_valor_raw' => $request->input('valor'),
                ], JSON_UNESCAPED_UNICODE),

                'created_at' => now(),
                'updated_at' => now(),
            ]);
        });

        \Log::info('[ADMIN][refiPendentesUpdateValor] atualizado', [
            'rid' => $rid,
            'uid' => $uid,
            'refinanciamento_id' => $refinanciamento,
            'cpf' => $cpfDigits,
            'agente_cadastro_id' => $agId,
            'tesouraria_pagamento_id' => $tpId,
            'agente_valor_antigo' => $ac_margem,
            'tp_valor_antigo' => $tp_margem,
            'valor_novo' => $valor,
            'snapshot_id' => (int)$snapshotId,
        ]);

        return response()->json([
            'ok' => true,
            'message' => 'Valor atualizado no AGENTE (e Tesouraria) e snapshot criado.',
            'snapshot_id' => (int)$snapshotId,

            'refinanciamento_id' => (int)$refinanciamento,
            'cpf_cnpj' => $cpfDigits ?: null,
            'origem' => $origem,

            // confirmações (antes/depois)
            'agente_cadastro_id' => $agId,
            'agente_valor_antigo' => $ac_margem,
            'agente_valor_novo' => $valor,

            'tesouraria_pagamento_id' => $tpId,
            'tp_valor_antigo' => $tp_margem,
            'tp_valor_novo' => $tpId ? $valor : null,

            // snapshot
            'fonte_base' => $fonteBase,
            'valor_base' => $valorBase,
            'valor_antigo' => $valorAntigo,
            'valor_novo' => $valor,

            // debug antes
            'tp_margem' => $tp_margem,
            'ac_margem' => $ac_margem,
            'a2_margem' => $a2_margem,
        ]);
    } catch (\Throwable $e) {
        \Log::error('[ADMIN][refiPendentesUpdateValor] exception', [
            'rid' => $rid,
            'uid' => $uid,
            'refinanciamento_id' => $refinanciamento,
            'err' => $e->getMessage(),
        ]);

        return response()->json(['error' => 'Erro ao salvar ajuste.'], 500);
    }
}






public function associadosAgenteList(\Illuminate\Http\Request $r)
{
    $rid = (string) \Illuminate\Support\Str::uuid();
    $tz  = config('app.timezone', 'America/Sao_Paulo');
    $t   = 'agente_cadastros';

    // ✅ LOG EXTRA: se isso não aparecer, o frontend nem está chamando a rota
    \Illuminate\Support\Facades\Log::info('[associadosAgenteList] HIT', [
        'rid' => $rid,
        'path' => $r->path(),
        'full' => $r->fullUrl(),
        'user_id' => optional(auth()->user())->id,
    ]);

    \Illuminate\Support\Facades\Log::info('[associadosAgenteList] START', [
        'rid' => $rid,
        'url' => $r->fullUrl(),
        'ip'  => $r->ip(),
        'query' => $r->query(),
        'accept' => $r->header('accept'),
        'xhr' => $r->header('x-requested-with'),
        'user_id' => optional(auth()->user())->id,
    ]);

    try {
        $hasTable = \Illuminate\Support\Facades\Schema::hasTable($t);
        \Illuminate\Support\Facades\Log::info('[associadosAgenteList] HAS_TABLE', [
            'rid' => $rid,
            'table' => $t,
            'has' => $hasTable,
        ]);

        if (!$hasTable) {
            \Illuminate\Support\Facades\Log::error('[associadosAgenteList] NO_TABLE', [
                'rid' => $rid,
                'table' => $t,
            ]);
            return response()->json(['ok'=>false,'message'=>"Tabela {$t} não existe.", 'rid'=>$rid], 422);
        }

        $page = max(1, (int) $r->query('page', 1));
        $per  = (int) $r->query('per_page', 10);
        $per  = ($per < 1) ? 10 : min($per, 50);

        $q = trim((string) $r->query('q', ''));
        $qDigits = $q !== '' ? preg_replace('/\D+/', '', $q) : '';

        \Illuminate\Support\Facades\Log::info('[associadosAgenteList] PARAMS', [
            'rid' => $rid,
            'page' => $page,
            'per_page' => $per,
            'q_raw' => $q,
            'q_digits' => $qDigits,
        ]);

        // regra mínima
        $lenQ = mb_strlen($q);
        $lenDigits = strlen($qDigits);

        $shouldSearch =
            ($lenDigits >= 2) ||
            ($lenDigits === 0 && $lenQ >= 3);

        if (!$shouldSearch) {
            return response()->json([
                'ok' => true,
                'rid' => $rid,
                'data' => [],
                'meta' => [
                    'current_page' => 1,
                    'last_page' => 1,
                    'per_page' => $per,
                    'total' => 0,
                ],
                'hint' => 'Digite ao menos 3 letras do nome ou 2 dígitos do CPF/CNPJ.',
            ]);
        }

        $query = \Illuminate\Support\Facades\DB::table($t)->select([
            'id','cpf_cnpj','full_name','agente_responsavel','updated_at',
        ]);

        $query->where(function($w) use ($q, $qDigits) {
            if ($qDigits !== '') {
                $w->orWhere('cpf_cnpj', 'like', "%{$qDigits}%");
            }
            $w->orWhere('full_name', 'like', "%{$q}%");
        });

        \Illuminate\Support\Facades\Log::info('[associadosAgenteList] SQL', [
            'rid' => $rid,
            'sql' => $query->toSql(),
            'bindings' => $query->getBindings(),
        ]);

        $p = $query->orderByDesc('updated_at')->paginate($per, ['*'], 'page', $page);

        \Illuminate\Support\Facades\Log::info('[associadosAgenteList] PAGINATE', [
            'rid' => $rid,
            'total' => $p->total(),
            'current_page' => $p->currentPage(),
            'last_page' => $p->lastPage(),
            'count_items' => count($p->items()),
        ]);

        $data = collect($p->items())->map(function($it) use ($tz) {
            $updated = $it->updated_at
                ? \Carbon\Carbon::parse($it->updated_at)->timezone($tz)->format('d/m/Y H:i')
                : null;

            return [
                'id' => (int)$it->id,
                'cpf_cnpj' => (string)$it->cpf_cnpj,
                'name' => (string)$it->full_name,
                'agente_responsavel' => $it->agente_responsavel,
                'updated_at_br' => $updated,
            ];
        })->values();

        return response()->json([
            'ok' => true,
            'rid' => $rid,
            'data' => $data,
            'meta' => [
                'current_page' => $p->currentPage(),
                'last_page' => $p->lastPage(),
                'per_page' => $p->perPage(),
                'total' => $p->total(),
            ],
        ]);
    } catch (\Throwable $e) {
        \Illuminate\Support\Facades\Log::error('[associadosAgenteList] EXCEPTION', [
            'rid' => $rid,
            'msg' => $e->getMessage(),
            'line' => $e->getLine(),
            'file' => $e->getFile(),
        ]);
        return response()->json(['ok'=>false,'error'=>'Erro interno ao listar.', 'rid'=>$rid], 500);
    }
}

public function associadoAgenteShow(\Illuminate\Http\Request $r, int $cadastro)
{
    $rid = (string) \Illuminate\Support\Str::uuid();
    $tz  = config('app.timezone', 'America/Sao_Paulo');
    $t   = 'agente_cadastros';

    \Illuminate\Support\Facades\Log::info('[associadoAgenteShow] START', [
        'rid' => $rid,
        'cadastro' => $cadastro,
        'url' => $r->fullUrl(),
        'ip'  => $r->ip(),
        'user_id' => optional(auth()->user())->id,
    ]);

    try {
        if (!\Illuminate\Support\Facades\Schema::hasTable($t)) {
            \Illuminate\Support\Facades\Log::error('[associadoAgenteShow] NO_TABLE', [
                'rid' => $rid,
                'table' => $t,
            ]);
            return response()->json(['ok'=>false,'message'=>"Tabela {$t} não existe.", 'rid'=>$rid], 422);
        }

        $row = \Illuminate\Support\Facades\DB::table($t)->where('id', $cadastro)->first();

        \Illuminate\Support\Facades\Log::info('[associadoAgenteShow] FOUND', [
            'rid' => $rid,
            'found' => (bool)$row,
        ]);

        if (!$row) {
            return response()->json(['ok'=>false,'message'=>'Cadastro não encontrado.', 'rid'=>$rid], 404);
        }

        $updated = $row->updated_at
            ? \Carbon\Carbon::parse($row->updated_at)->timezone($tz)->format('d/m/Y H:i')
            : null;

        return response()->json([
            'ok' => true,
            'rid' => $rid,
            'id' => (int)$row->id,
            'cpf_cnpj' => (string)$row->cpf_cnpj,
            'name' => (string)$row->full_name,
            'email' => $row->email ?? null,
            'agente_responsavel' => $row->agente_responsavel ?? null,
            'agente_filial' => $row->agente_filial ?? null,
            'updated_at_br' => $updated,
        ]);
    } catch (\Throwable $e) {
        \Illuminate\Support\Facades\Log::error('[associadoAgenteShow] EXCEPTION', [
            'rid' => $rid,
            'msg' => $e->getMessage(),
            'line' => $e->getLine(),
            'file' => $e->getFile(),
        ]);
        return response()->json(['ok'=>false,'error'=>'Erro interno ao carregar detalhe.', 'rid'=>$rid], 500);
    }
}

public function associadoAgenteUpdate(\Illuminate\Http\Request $r, int $cadastro)
{
    $rid = (string) \Illuminate\Support\Str::uuid();
    $t   = 'agente_cadastros';

    \Illuminate\Support\Facades\Log::info('[associadoAgenteUpdate] START', [
        'rid' => $rid,
        'cadastro' => $cadastro,
        'url' => $r->fullUrl(),
        'ip'  => $r->ip(),
        'user_id' => optional(auth()->user())->id,
        'payload_raw' => $r->all(),
    ]);

    try {
        if (!\Illuminate\Support\Facades\Schema::hasTable($t)) {
            return response()->json(['ok'=>false,'error'=>"Tabela {$t} não existe.", 'rid'=>$rid], 422);
        }

        $row = \Illuminate\Support\Facades\DB::table($t)->where('id', $cadastro)->first();
        if (!$row) {
            return response()->json(['ok'=>false,'error'=>'Cadastro não encontrado.', 'rid'=>$rid], 404);
        }

        // ✅ recebe apenas 1 campo e aplica em 2 colunas
        $novoAgente = trim((string) $r->input('agente_responsavel', ''));

        if ($novoAgente === '') {
            return response()->json(['ok'=>false,'error'=>'Informe o novo agente.', 'rid'=>$rid], 422);
        }

        $payload = [
            'agente_responsavel' => $novoAgente,
            'agente_filial'      => $novoAgente,   // ✅ automático
            'updated_at'         => now(),
        ];

        \Illuminate\Support\Facades\Log::info('[associadoAgenteUpdate] PAYLOAD', [
            'rid' => $rid,
            'payload' => $payload,
        ]);

        $affected = \Illuminate\Support\Facades\DB::table($t)->where('id', $cadastro)->update($payload);

        \Illuminate\Support\Facades\Log::info('[associadoAgenteUpdate] UPDATED', [
            'rid' => $rid,
            'affected' => $affected,
        ]);

        return response()->json([
            'ok' => true,
            'rid' => $rid,
            'message' => 'Agente atualizado com sucesso.',
        ]);
    } catch (\Throwable $e) {
        \Illuminate\Support\Facades\Log::error('[associadoAgenteUpdate] EXCEPTION', [
            'rid' => $rid,
            'msg' => $e->getMessage(),
            'line' => $e->getLine(),
            'file' => $e->getFile(),
        ]);
        return response()->json(['ok'=>false,'error'=>'Erro interno ao atualizar.', 'rid'=>$rid], 500);
    }
}

public function associadosAgenteOptions(\Illuminate\Http\Request $r)
{
    $rid = (string) \Illuminate\Support\Str::uuid();
    $t   = 'agente_cadastros';

    \Illuminate\Support\Facades\Log::info('[associadosAgenteOptions] START', [
        'rid' => $rid,
        'url' => $r->fullUrl(),
        'user_id' => optional(auth()->user())->id,
    ]);

    try {
        if (!\Illuminate\Support\Facades\Schema::hasTable($t)) {
            return response()->json(['ok'=>false,'rid'=>$rid,'responsaveis'=>[],'filiais'=>[]], 200);
        }

        $responsaveis = \Illuminate\Support\Facades\DB::table($t)
            ->select('agente_responsavel')
            ->whereNotNull('agente_responsavel')
            ->where('agente_responsavel', '<>', '')
            ->distinct()
            ->orderBy('agente_responsavel')
            ->limit(300)
            ->pluck('agente_responsavel')
            ->values();

        $filiais = \Illuminate\Support\Facades\DB::table($t)
            ->select('agente_filial')
            ->whereNotNull('agente_filial')
            ->where('agente_filial', '<>', '')
            ->distinct()
            ->orderBy('agente_filial')
            ->limit(300)
            ->pluck('agente_filial')
            ->values();

        \Illuminate\Support\Facades\Log::info('[associadosAgenteOptions] END_OK', [
            'rid' => $rid,
            'count_responsaveis' => $responsaveis->count(),
            'count_filiais' => $filiais->count(),
        ]);

        return response()->json([
            'ok' => true,
            'rid' => $rid,
            'responsaveis' => $responsaveis,
            'filiais' => $filiais,
        ]);
    } catch (\Throwable $e) {
        \Illuminate\Support\Facades\Log::error('[associadosAgenteOptions] EXCEPTION', [
            'rid' => $rid,
            'msg' => $e->getMessage(),
            'line' => $e->getLine(),
            'file' => $e->getFile(),
        ]);
        return response()->json(['ok'=>false,'rid'=>$rid,'responsaveis'=>[],'filiais'=>[]], 500);
    }
}


// =========================
// INÍCIO: Métodos Admin - Atualizar Porcentagem do Agente (COM agente_margens)
// - LIST/SHOW lê de agente_margens (vigente)
// - UPDATE escreve em agente_margens + historico + snapshots
// - Mantém o JSON do frontend: auxilio_taxa_val / auxilio_taxa_txt
// =========================

public function agenteMargemList(\Illuminate\Http\Request $r)
{
    $rid = (string) \Illuminate\Support\Str::uuid();

    \Illuminate\Support\Facades\Log::info('[agenteMargemList] HIT', [
        'rid' => $rid,
        'path' => $r->path(),
        'full' => $r->fullUrl(),
        'user_id' => optional(auth()->user())->id,
        'query' => $r->query(),
    ]);

    try {
        foreach (['users','roles','role_user','agente_margens'] as $tb) {
            if (!\Illuminate\Support\Facades\Schema::hasTable($tb)) {
                return response()->json(['ok'=>false,'message'=>"Tabela {$tb} não existe.", 'rid'=>$rid], 422);
            }
        }

        $page = max(1, (int) $r->query('page', 1));
        $per  = (int) $r->query('per_page', 10);
        $per  = ($per < 1) ? 10 : min($per, 50);

        $q = trim((string) $r->query('q', ''));
        $qDigits = $q !== '' ? preg_replace('/\D+/', '', $q) : '';

        $lenQ = mb_strlen($q);
        $lenDigits = strlen($qDigits);
        $shouldSearch = ($lenDigits >= 2) || ($lenDigits === 0 && $lenQ >= 3);

        if (!$shouldSearch) {
            return response()->json([
                'ok' => true,
                'rid' => $rid,
                'data' => [],
                'meta' => [
                    'current_page' => 1,
                    'last_page' => 1,
                    'per_page' => $per,
                    'total' => 0,
                ],
                'hint' => 'Digite ao menos 3 letras do nome ou 2 dígitos.',
            ]);
        }

        // subquery: margem vigente por agente_user_id (última por vigente_desde)
        $vig = \Illuminate\Support\Facades\DB::table('agente_margens as am')
            ->selectRaw('am.agente_user_id, MAX(am.vigente_desde) as max_desde')
            ->whereNull('am.vigente_ate')
            ->groupBy('am.agente_user_id');

        $qb = \Illuminate\Support\Facades\DB::table('users as u')
            ->join('role_user as ru', 'ru.user_id', '=', 'u.id')
            ->join('roles as ro', 'ro.id', '=', 'ru.role_id')
            ->whereRaw("LOWER(TRIM(ro.name)) = 'agente'")
            ->where(function($w) use ($q, $qDigits) {
                if ($qDigits !== '') {
                    $w->orWhere('u.email', 'like', "%{$qDigits}%");
                }
                $w->orWhere('u.name', 'like', "%{$q}%")
                  ->orWhere('u.email', 'like', "%{$q}%");
            })
            ->leftJoinSub($vig, 'vig', function($j){
                $j->on('vig.agente_user_id','=','u.id');
            })
            ->leftJoin('agente_margens as amv', function($j){
                $j->on('amv.agente_user_id','=','u.id')
                  ->on('amv.vigente_desde','=','vig.max_desde')
                  ->whereNull('amv.vigente_ate');
            })
            ->addSelect([
                'u.id','u.name','u.email',
                \Illuminate\Support\Facades\DB::raw('amv.percentual as percentual'),
            ]);

        $p = $qb->orderBy('u.name')->paginate($per, ['*'], 'page', $page);

        $data = collect($p->items())->map(function($it) {
            $perc = isset($it->percentual) ? (is_null($it->percentual) ? null : (float)$it->percentual) : null;
            $txt  = is_null($perc) ? '—' : (rtrim(rtrim(number_format($perc, 2, ',', '.'), '0'), ',') . '%');

            return [
                'id' => (int)$it->id,                       // users.id (agente)
                'cpf_cnpj' => (string)($it->email ?? '—'), // mantém layout
                'name' => (string)($it->name ?? '—'),
                // frontend espera auxilio_taxa_*
                'auxilio_taxa_val' => $perc,
                'auxilio_taxa_txt' => $txt,
            ];
        })->values();

        return response()->json([
            'ok' => true,
            'rid' => $rid,
            'data' => $data,
            'meta' => [
                'current_page' => $p->currentPage(),
                'last_page' => $p->lastPage(),
                'per_page' => $p->perPage(),
                'total' => $p->total(),
            ],
        ]);

    } catch (\Throwable $e) {
        \Illuminate\Support\Facades\Log::error('[agenteMargemList] EXCEPTION', [
            'rid' => $rid,
            'msg' => $e->getMessage(),
            'line' => $e->getLine(),
            'file' => $e->getFile(),
        ]);
        return response()->json(['ok'=>false,'error'=>'Erro interno ao listar.', 'rid'=>$rid], 500);
    }
}

public function agenteMargemShow(\Illuminate\Http\Request $r, int $cadastro)
{
    // $cadastro = users.id do agente
    $rid = (string) \Illuminate\Support\Str::uuid();
    $tz  = config('app.timezone', 'America/Sao_Paulo');

    \Illuminate\Support\Facades\Log::info('[agenteMargemShow] START', [
        'rid' => $rid,
        'agente_user_id' => $cadastro,
        'url' => $r->fullUrl(),
        'ip'  => $r->ip(),
        'user_id' => optional(auth()->user())->id,
    ]);

    try {
        foreach (['users','roles','role_user','agente_margens'] as $tb) {
            if (!\Illuminate\Support\Facades\Schema::hasTable($tb)) {
                return response()->json(['ok'=>false,'message'=>"Tabela {$tb} não existe.", 'rid'=>$rid], 422);
            }
        }

        // confirma agente
        $u = \Illuminate\Support\Facades\DB::table('users as u')
            ->join('role_user as ru', 'ru.user_id', '=', 'u.id')
            ->join('roles as ro', 'ro.id', '=', 'ru.role_id')
            ->whereRaw("LOWER(TRIM(ro.name)) = 'agente'")
            ->where('u.id', $cadastro)
            ->select('u.id','u.name','u.email','u.updated_at')
            ->first();

        if (!$u) {
            return response()->json(['ok'=>false,'message'=>'Usuário não encontrado (ou não é agente).', 'rid'=>$rid], 404);
        }

        // margem vigente
        $m = \Illuminate\Support\Facades\DB::table('agente_margens')
            ->where('agente_user_id', $cadastro)
            ->whereNull('vigente_ate')
            ->orderByDesc('vigente_desde')
            ->first();

        $perc = $m ? (float)$m->percentual : null;
        $txt  = is_null($perc) ? '—' : (rtrim(rtrim(number_format($perc, 2, ',', '.'), '0'), ',') . '%');

        $updated = $u->updated_at
            ? \Carbon\Carbon::parse($u->updated_at)->timezone($tz)->format('d/m/Y H:i')
            : null;

        return response()->json([
            'ok' => true,
            'rid' => $rid,
            'id' => (int)$u->id,
            'cpf_cnpj' => (string)($u->email ?? '—'),
            'name' => (string)$u->name,
            'auxilio_taxa_val' => $perc,
            'auxilio_taxa_txt' => $txt,
            'updated_at_br' => $updated,
        ]);

    } catch (\Throwable $e) {
        \Illuminate\Support\Facades\Log::error('[agenteMargemShow] EXCEPTION', [
            'rid' => $rid,
            'msg' => $e->getMessage(),
            'line' => $e->getLine(),
            'file' => $e->getFile(),
        ]);
        return response()->json(['ok'=>false,'error'=>'Erro interno ao carregar detalhe.', 'rid'=>$rid], 500);
    }
}

public function agenteMargemUpdate(\Illuminate\Http\Request $r, int $cadastro)
{
    // $cadastro = users.id do agente
    $rid = (string) \Illuminate\Support\Str::uuid();
    $tz  = config('app.timezone', 'America/Sao_Paulo');

    \Illuminate\Support\Facades\Log::info('[agenteMargemUpdate] START', [
        'rid' => $rid,
        'agente_user_id' => $cadastro,
        'url' => $r->fullUrl(),
        'ip'  => $r->ip(),
        'user_id' => optional(auth()->user())->id,
        'payload_raw' => $r->all(),
    ]);

    try {
        foreach (['users','roles','role_user','agente_margens','agente_margem_historicos','agente_margem_snapshots','agente_cadastros'] as $tb) {
            if (!\Illuminate\Support\Facades\Schema::hasTable($tb)) {
                return response()->json(['ok'=>false,'error'=>"Tabela {$tb} não existe.", 'rid'=>$rid], 422);
            }
        }

        // confirma agente
        $isAgente = \Illuminate\Support\Facades\DB::table('users as u')
            ->join('role_user as ru', 'ru.user_id', '=', 'u.id')
            ->join('roles as ro', 'ro.id', '=', 'ru.role_id')
            ->whereRaw("LOWER(TRIM(ro.name)) = 'agente'")
            ->where('u.id', $cadastro)
            ->exists();

        if (!$isAgente) {
            return response()->json(['ok'=>false,'error'=>'Usuário não encontrado (ou não é agente).', 'rid'=>$rid], 404);
        }

        // valida %
        $val = $r->input('auxilio_taxa', null); // frontend manda assim
        if (!is_numeric($val)) {
            return response()->json(['ok'=>false,'error'=>'Informe um número válido para a porcentagem.', 'rid'=>$rid], 422);
        }
        $val = (float)$val;
        if ($val < 0 || $val > 100) {
            return response()->json(['ok'=>false,'error'=>'A porcentagem deve ficar entre 0 e 100.', 'rid'=>$rid], 422);
        }

        $changedBy = optional(auth()->user())->id;
        $motivo = trim((string)$r->input('motivo', '')) ?: null;

        // descobrir colunas do cadastro para snapshot (defensivo como seu método contratos)
        $cadTbl = 'agente_cadastros';

        $pick = function(array $cands) use ($cadTbl) {
            foreach ($cands as $c) if (\Illuminate\Support\Facades\Schema::hasColumn($cadTbl, $c)) return $c;
            return null;
        };

        $COL_MENSAL = $pick(['contrato_mensalidade','valor_mensalidade','mensalidade']);
        $COL_MARGEM = $pick(['contrato_margem_disponivel','margem_disponivel','margemDisponivel','contrato_margem']);

        // como ligar cadastros ao agente
        $cadLinkCol = null;
        foreach (['agente_user_id','user_id'] as $cand) {
            if (\Illuminate\Support\Facades\Schema::hasColumn($cadTbl, $cand)) { $cadLinkCol = $cand; break; }
        }

        // nome do agente (para fallback)
        $agenteName = \Illuminate\Support\Facades\DB::table('users')->where('id', $cadastro)->value('name');
        $hasResp = \Illuminate\Support\Facades\Schema::hasColumn($cadTbl, 'agente_responsavel');
        $hasFil  = \Illuminate\Support\Facades\Schema::hasColumn($cadTbl, 'agente_filial');

        // percentual anterior (vigente atual)
        $cur = \Illuminate\Support\Facades\DB::table('agente_margens')
            ->where('agente_user_id', $cadastro)
            ->whereNull('vigente_ate')
            ->orderByDesc('vigente_desde')
            ->first();

        $oldPerc = $cur ? (float)$cur->percentual : null;

        // tudo em transação
        $result = \Illuminate\Support\Facades\DB::transaction(function() use (
            $cadastro, $val, $oldPerc, $changedBy, $motivo, $cadTbl, $cadLinkCol, $agenteName, $hasResp, $hasFil, $COL_MENSAL, $COL_MARGEM, $rid
        ){
            // encerra atual (se existir)
            if ($oldPerc !== null) {
                \Illuminate\Support\Facades\DB::table('agente_margens')
                    ->where('agente_user_id', $cadastro)
                    ->whereNull('vigente_ate')
                    ->update([
                        'vigente_ate' => now(),
                        'updated_by_user_id' => $changedBy,
                        'motivo' => $motivo,
                        'updated_at' => now(),
                    ]);
            }

            // cria novo vigente
            \Illuminate\Support\Facades\DB::table('agente_margens')->insert([
                'agente_user_id' => $cadastro,
                'percentual' => $val,
                'vigente_desde' => now(),
                'vigente_ate' => null,
                'updated_by_user_id' => $changedBy,
                'motivo' => $motivo,
                'created_at' => now(),
                'updated_at' => now(),
            ]);

            // histórico
            \Illuminate\Support\Facades\DB::table('agente_margem_historicos')->insert([
                'agente_user_id' => $cadastro,
                'percentual_anterior' => $oldPerc,
                'percentual_novo' => $val,
                'changed_by_user_id' => $changedBy,
                'motivo' => $motivo,
                'meta' => json_encode(['rid'=>$rid]),
                'created_at' => now(),
                'updated_at' => now(),
            ]);

            // selecionar cadastros afetados
            $qCad = \Illuminate\Support\Facades\DB::table($cadTbl.' as c')
                ->select('c.id');

            if ($COL_MENSAL) $qCad->addSelect(\Illuminate\Support\Facades\DB::raw("c.$COL_MENSAL as mensalidade"));
            else $qCad->addSelect(\Illuminate\Support\Facades\DB::raw("NULL as mensalidade"));

            if ($COL_MARGEM) $qCad->addSelect(\Illuminate\Support\Facades\DB::raw("c.$COL_MARGEM as margem_disponivel"));
            else $qCad->addSelect(\Illuminate\Support\Facades\DB::raw("NULL as margem_disponivel"));

            if ($cadLinkCol) {
                $qCad->where("c.$cadLinkCol", $cadastro);
            } else {
                // fallback por nome
                $qCad->where(function($w) use ($agenteName, $hasResp, $hasFil){
                    if ($hasResp) $w->orWhere('c.agente_responsavel', $agenteName);
                    if ($hasFil)  $w->orWhere('c.agente_filial', $agenteName);
                });
            }

            // snapshots por lote (chunk)
            $inserted = 0;
            $qCad->orderBy('c.id')->chunk(500, function($rows) use ($cadastro, $oldPerc, $val, &$inserted, $changedBy, $motivo){
                $now = now();
                $batch = [];

                foreach ($rows as $row) {
                    $mensal = isset($row->mensalidade) ? (is_null($row->mensalidade) ? null : (float)$row->mensalidade) : null;
                    $margem = isset($row->margem_disponivel) ? (is_null($row->margem_disponivel) ? null : (float)$row->margem_disponivel) : null;

                    $auxOld = null;
                    if (!is_null($margem) && !is_null($oldPerc)) {
                        $auxOld = round($margem * ($oldPerc/100), 2);
                    }

                    $auxNew = null;
                    if (!is_null($margem)) {
                        $auxNew = round($margem * ($val/100), 2);
                    }

                    $batch[] = [
                        'agente_cadastro_id' => (int)$row->id,
                        'agente_user_id' => (int)$cadastro,
                        'percentual_anterior' => $oldPerc,
                        'percentual_novo' => $val,
                        'mensalidade' => $mensal,
                        'margem_disponivel' => $margem,
                        'auxilio_valor_anterior' => $auxOld,
                        'auxilio_valor_novo' => $auxNew,
                        'changed_by_user_id' => $changedBy,
                        'motivo' => $motivo,
                        'created_at' => $now,
                        'updated_at' => $now,
                    ];
                }

                if (!empty($batch)) {
                    \Illuminate\Support\Facades\DB::table('agente_margem_snapshots')->insert($batch);
                    $inserted += count($batch);
                }
            });

            return [
                'snapshots' => $inserted,
            ];
        });

        $txt = rtrim(rtrim(number_format($val, 2, ',', '.'), '0'), ',') . '%';

        return response()->json([
            'ok' => true,
            'rid' => $rid,
            'message' => 'Porcentagem atualizada com sucesso.',
            // mantém contrato do frontend
            'auxilio_taxa_val' => $val,
            'auxilio_taxa_txt' => $txt,
            // extras úteis p/ debug
            'snapshots' => $result['snapshots'] ?? 0,
        ]);

    } catch (\Throwable $e) {
        \Illuminate\Support\Facades\Log::error('[agenteMargemUpdate] EXCEPTION', [
            'rid' => $rid,
            'msg' => $e->getMessage(),
            'line' => $e->getLine(),
            'file' => $e->getFile(),
        ]);
        return response()->json(['ok'=>false,'error'=>'Erro interno ao atualizar.', 'rid'=>$rid], 500);
    }
}

// =========================
// FIM: Métodos Admin - Atualizar Porcentagem do Agente (COM agente_margens)
// =========================
}
