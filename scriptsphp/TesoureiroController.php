<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Facades\Route;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Validator;
use Illuminate\Validation\ValidationException;
use Illuminate\Database\Eloquent\ModelNotFoundException;
use Illuminate\Support\Str;
use Illuminate\Database\QueryException;
use Illuminate\Support\Facades\File;
use Illuminate\Validation\Rule;
use Throwable;
use Carbon\Carbon;
use App\Models\TesourariaConfirmacao;
use App\Models\AgenteCadastro;
use App\Models\AgenteDocReupload;
use App\Models\TesourariaPagamento;
use App\Models\User;
use App\Models\AssociadoDoisCadastro;

use Barryvdh\DomPDF\Facade\Pdf;

class TesoureiroController extends Controller
{
    public function __construct()
    {
        // permite que admin também visualize comprovantes se necessário
        $this->middleware(['auth', 'role:tesoureiro'])->except(['streamComprovante']);
    }

    /* ============================================================================================
     |  COMPETÊNCIA (janela com fechamento no dia FECHAMENTO_DIA)
     |  - Usa fuso horário local para montar a janela (ex.: 05→05)
     |  - Retorna também expressão TS_LOCAL para usar com CONVERT_TZ no MySQL
     * ============================================================================================ */
    public static function parseCompetencia(Request $request): array
    {
        $tz            = config('app.timezone') ?: (env('APP_TIMEZONE') ?: 'America/Sao_Paulo');
        $fechamentoDia = (int) env('FECHAMENTO_DIA', 5);

        // mes=YYYY-MM (se vier vazio ou inválido, usa mês atual no fuso escolhido)
        $mesISO = $request->query('mes');
        if (!$mesISO || !preg_match('~^\d{4}-\d{2}$~', $mesISO)) {
            $mesISO = now($tz)->format('Y-m');
        }

        $competencia         = Carbon::createFromFormat('Y-m', $mesISO, $tz)->startOfMonth();
        $inicioCompetencia   = $competencia->copy()->day($fechamentoDia)->startOfDay();             // ex.: 05/mes 00:00
        $fechamentoExclusivo = $competencia->copy()->addMonth()->day($fechamentoDia)->startOfDay(); // ex.: 05/mes+1 00:00
        $fimInclusivoUI      = $fechamentoExclusivo->copy()->subSecond();                           // pra exibir na tela

        // Offset para CONVERT_TZ (pega o offset real do fuso, ex.: -03:00)
        $offsetMinutes = $inicioCompetencia->offsetMinutes;
        $sign  = $offsetMinutes >= 0 ? '+' : '-';
        $h     = str_pad((string) floor(abs($offsetMinutes) / 60), 2, '0', STR_PAD_LEFT);
        $m     = str_pad((string) (abs($offsetMinutes) % 60), 2, '0', STR_PAD_LEFT);
        $TZ_OFF = "{$sign}{$h}:{$m}";

        // Timestamp local baseado em paid_at/created_at (alias p)
        $TS_LOCAL   = "CONVERT_TZ(COALESCE(p.paid_at, p.created_at), @@session.time_zone, '{$TZ_OFF}')";
        $betweenSql = "$TS_LOCAL >= ? AND $TS_LOCAL < ?";
        $betweenArgs = [
            $inicioCompetencia->format('Y-m-d H:i:s'),
            $fechamentoExclusivo->format('Y-m-d H:i:s'),
        ];

        return [
            $mesISO,            // 0
            $inicioCompetencia, // 1 - início (local)
            $fechamentoExclusivo, // 2 - fim exclusivo (local)
            $fimInclusivoUI,    // 3 - fim inclusivo p/ exibir
            $TZ_OFF,            // 4
            $TS_LOCAL,          // 5
            $betweenSql,        // 6
            $betweenArgs,       // 7
        ];
    }

    /** Helper de formatação de CPF/CNPJ */
    public static function maskDoc($doc): string
    {
        $d = preg_replace('/\D+/', '', (string) $doc);
        if (strlen($d) === 11) {
            return substr($d, 0, 3) . '.' . substr($d, 3, 3) . '.' . substr($d, 6, 3) . '-' . substr($d, 9, 2);
        }
        if (strlen($d) === 14) {
            return substr($d, 0, 2) . '.' . substr($d, 2, 3) . '.' . substr($d, 5, 3) . '/' . substr($d, 8, 4) . '-' . substr($d, 12, 2);
        }
        return (string) $doc;
    }

/** ---------------- Dashboard (principal) ---------------- */
public function index(Request $r)
{
    // ===== trace para agrupar os logs desta requisição
    $trace = 'TESOUREIRO#' . now('UTC')->format('Ymd-His-v') . '-' . Str::upper(Str::random(4));

    if (config('app.debug') && $r->boolean('trace_sql', false)) {
        DB::listen(function ($q) use ($trace) {
            Log::debug('[' . $trace . '] SQL', [
                'sql'      => $q->sql,
                'time_ms'  => $q->time,
                'bindings' => $q->bindings,
            ]);
        });
    }

    // ======================================================================
    // ✅ MÊS NATURAL (calendário):
    // - mês selecionado = Y-m
    // - janela do mês: 01 00:00:00 até 1º do próximo mês 00:00:00 (exclusivo)
    // - comparação no banco em UTC
    // ======================================================================
    $tzDisplay = config('app.display_tz') ?: (config('app.timezone') ?: 'America/Sao_Paulo');

    $mesISO = (string) $r->input('mes', now($tzDisplay)->format('Y-m'));
    try {
        $compLocal = Carbon::createFromFormat('Y-m', $mesISO, $tzDisplay)->startOfMonth();
    } catch (\Throwable $e) {
        $mesISO = now($tzDisplay)->format('Y-m');
        $compLocal = Carbon::createFromFormat('Y-m', $mesISO, $tzDisplay)->startOfMonth();
    }

    $iniLocal   = $compLocal->copy()->startOfMonth()->startOfDay();     // dia 01 00:00:00
    $fimExLocal = $compLocal->copy()->addMonth()->startOfMonth();       // exclusivo

    $iniUtc   = $iniLocal->copy()->tz('UTC');
    $fimExUtc = $fimExLocal->copy()->tz('UTC');

    Log::info('[' . $trace . '] Mês calendário (natural)', [
        'mesISO'     => $mesISO,
        'iniLocal'   => $iniLocal->format('Y-m-d H:i:s'),
        'fimExLocal' => $fimExLocal->format('Y-m-d H:i:s'),
        'iniUtc'     => $iniUtc->format('Y-m-d H:i:s'),
        'fimExUtc'   => $fimExUtc->format('Y-m-d H:i:s'),
    ]);

    // ======================================================================
    // ✅ filtros do request (status / busca / período)
    // ======================================================================
    $payFilter = strtolower(trim((string) $r->query('pay_status', 'all'))); // all|pendente|pago|cancelado
    if (!in_array($payFilter, ['all','pendente','pago','cancelado'], true)) $payFilter = 'all';

    $q = trim((string) $r->query('q', ''));

    $from = trim((string) $r->query('from', ''));
    $to   = trim((string) $r->query('to', ''));

    $hasPeriodo = (bool)(
        preg_match('/^\d{4}\-\d{2}\-\d{2}$/', $from) ||
        preg_match('/^\d{4}\-\d{2}\-\d{2}$/', $to)
    );

    $pIniUtc = null;
    $pFimExUtc = null;

    if ($hasPeriodo) {
        if (!preg_match('/^\d{4}\-\d{2}\-\d{2}$/', $from)) {
            $from = now($tzDisplay)->subDays(7)->toDateString();
        }
        if (!preg_match('/^\d{4}\-\d{2}\-\d{2}$/', $to)) {
            $to = now($tzDisplay)->toDateString();
        }

        try { $dIni = Carbon::parse($from, $tzDisplay)->startOfDay(); }
        catch (\Throwable $e) { $dIni = now($tzDisplay)->subDays(7)->startOfDay(); }

        try { $dFim = Carbon::parse($to, $tzDisplay)->endOfDay(); }
        catch (\Throwable $e) { $dFim = now($tzDisplay)->endOfDay(); }

        if ($dIni->gt($dFim)) {
            [$dIni, $dFim] = [$dFim->copy()->startOfDay(), $dIni->copy()->endOfDay()];
            [$from, $to]   = [$to, $from];
        }

        // período em UTC (fim exclusivo = +1s do endOfDay, ou usa <= endOfDay via whereBetween)
        $pIniUtc = $dIni->copy()->tz('UTC');
        $pFimExUtc = $dFim->copy()->tz('UTC');

        Log::info('['.$trace.'] Filtro período', [
            'from' => $from,
            'to'   => $to,
            'iniUtc' => $pIniUtc->format('Y-m-d H:i:s'),
            'fimUtc' => $pFimExUtc->format('Y-m-d H:i:s'),
            'pay_status' => $payFilter,
            'q' => $q,
        ]);
    }

    // ===== helper para resolver a chave PIX (1º campo não-vazio)
    $resolvePix = function ($row, $pay = null) {
        $cands = [
            data_get($row, 'pix_key'),
            data_get($row, 'pix'),
            data_get($row, 'chave_pix'),
            data_get($row, 'bank_pix'),
            data_get($row, 'pixKey'),
            data_get($row, 'pix_chave'),
            data_get($row, 'key_pix'),
            data_get($row, 'pixcode'),
            data_get($pay, 'pix_key'),
            data_get($pay, 'chave_pix'),
            data_get($pay, 'pix'),
            data_get($pay, 'bank_pix'),
        ];
        foreach ($cands as $v) {
            if (is_string($v)) $v = trim($v);
            if (!is_null($v) && $v !== '') return $v;
        }
        return null;
    };

    // ===== helper para horário local (dia + hora) usado na "ordem de chegada"
    $resolveLocalDt = function ($model) use ($tzDisplay) {
        try {
            $pay = $model->relationLoaded('pagamentoTesouraria')
                ? $model->pagamentoTesouraria
                : (property_exists($model, 'pagamentoTesouraria') ? $model->pagamentoTesouraria : null);
        } catch (\Throwable $e) {
            $pay = null;
        }

        // Regra: paid_at > created_at do pagamento > created_at do cadastro
        $ts = null;
        if ($pay && $pay->paid_at) $ts = $pay->paid_at;
        elseif ($pay && $pay->created_at) $ts = $pay->created_at;
        elseif (isset($model->created_at)) $ts = $model->created_at;

        if (!$ts) return [null, null];

        if (!$ts instanceof \Carbon\Carbon && !$ts instanceof \Carbon\CarbonImmutable) {
            try { $ts = Carbon::parse($ts, config('app.timezone') ?: 'UTC'); }
            catch (\Throwable $e) { return [null, null]; }
        }

        $local = $ts->copy()->setTimezone($tzDisplay);
        return [$local, $local->getTimestamp()];
    };

    // ===== colunas dinâmicas do pagamento
    $wantedPay = [
        'agente_cadastro_id',
        'associadodois_cadastro_id',
        'status',
        'created_at',
        'updated_at',
        'valor_pago',
        'paid_at',
        'comprovante_associado_path',
        'comprovante_agente_path',
        'comprovante_path',
        'contrato_margem_disponivel',
        'chave_pix',
        'pix_key',
        'pix',
        'bank_pix',
        'bank_name',
        'bank_agency',
        'bank_account',
        'account_type',
        'agente_responsavel',
        'contrato_codigo_contrato',
        'cpf_cnpj',
        'full_name',
        'nome_associado',
        'created_by_user_id',
        'forma_pagamento',
    ];

    $payCols = ['id'];
    foreach ($wantedPay as $c) {
        if (Schema::hasColumn('tesouraria_pagamentos', $c)) $payCols[] = $c;
    }
    $paySelect = implode(',', $payCols);

    // ======================================================================
    // ✅ Regras de status:
    // - PAGO: status='pago' e paid_at NOT NULL  (data real de pagamento)
    // - CANCELADO: status='cancelado'
    // - PENDENTE: todo o resto (inclui null) + status='pago' com paid_at NULL (tratado como pendente)
    // ======================================================================
    $isPago = function($p){
        $p->where('status', 'pago')->whereNotNull('paid_at');
    };

    $isCancelado = function($p){
        $p->where('status', 'cancelado');
    };

    $isPendente = function($p){
        $p->where(function($w){
            $w->whereNull('status')
              ->orWhereNotIn('status', ['pago','cancelado'])
              ->orWhere(function($x){
                  // se alguém marcou 'pago' mas não tem paid_at, consideramos pendente
                  $x->where('status','pago')->whereNull('paid_at');
              });
        });
    };

    // ======================================================================
    // ✅ REGRA DE VISIBILIDADE POR MÊS (mantém como está hoje):
    // - Pendentes: SEMPRE aparecem (qualquer mês/ano)
    // - Pago/Cancelado: só aparecem se dentro do MÊS SELECIONADO
    //    - Pago: paid_at dentro do mês
    //    - Cancelado: created_at dentro do mês (não tem paid_at geralmente)
    // ======================================================================
    $paidInMonth = function($p) use ($iniUtc, $fimExUtc, $isPago){
        $isPago($p);
        $p->where('paid_at','>=',$iniUtc->format('Y-m-d H:i:s'))
          ->where('paid_at','<', $fimExUtc->format('Y-m-d H:i:s'));
    };

    $canceladoInMonth = function($p) use ($iniUtc, $fimExUtc, $isCancelado){
        $isCancelado($p);
        $p->where('created_at','>=',$iniUtc->format('Y-m-d H:i:s'))
          ->where('created_at','<', $fimExUtc->format('Y-m-d H:i:s'));
    };

    $pendingAnytime = function($p) use ($isPendente){
        $isPendente($p);
    };

    // ======================================================================
    // ✅ Filtro de PERÍODO (from/to) com regra por status:
    // - pago: paid_at
    // - pendente/cancelado: created_at
    // - all: (pago -> paid_at) OR (não-pago -> created_at)
    // ======================================================================
    $periodFilter = null;
    if ($hasPeriodo && $pIniUtc && $pFimExUtc) {
        $pIniStr = $pIniUtc->format('Y-m-d H:i:s');
        $pFimStr = $pFimExUtc->format('Y-m-d H:i:s');

        $periodFilter = function($p) use ($payFilter, $pIniStr, $pFimStr, $isPago, $isCancelado, $isPendente){
            if ($payFilter === 'pago') {
                $isPago($p);
                $p->whereBetween('paid_at', [$pIniStr, $pFimStr]);
                return;
            }
            if ($payFilter === 'cancelado') {
                $isCancelado($p);
                $p->whereBetween('created_at', [$pIniStr, $pFimStr]);
                return;
            }
            if ($payFilter === 'pendente') {
                $isPendente($p);
                $p->whereBetween('created_at', [$pIniStr, $pFimStr]);
                return;
            }

            // all:
            $p->where(function($w) use ($pIniStr, $pFimStr){
                $w->where(function($a) use ($pIniStr, $pFimStr){
                    $a->where('status','pago')->whereNotNull('paid_at')
                      ->whereBetween('paid_at', [$pIniStr, $pFimStr]);
                })->orWhere(function($b) use ($pIniStr, $pFimStr){
                    $b->where(function($x){
                        $x->whereNull('status')
                          ->orWhereNotIn('status', ['pago','cancelado'])
                          ->orWhere(function($y){
                              $y->where('status','pago')->whereNull('paid_at');
                          })
                          ->orWhere('status','cancelado');
                    })->whereBetween('created_at', [$pIniStr, $pFimStr]);
                });
            });
        };
    }

    // ======================================================================
    // ✅ whereHas final: (pendentes sempre) OU (pago no mês) OU (cancelado no mês)
    // + aplica filtro de período se existir
    // + aplica busca q se existir (no pagamento)
    // ======================================================================
    $payWindowOrPending = function($p) use (
        $pendingAnytime, $paidInMonth, $canceladoInMonth,
        $periodFilter, $q
    ){
        $p->where(function($w) use ($pendingAnytime, $paidInMonth, $canceladoInMonth){
            $w->where(function($a) use ($pendingAnytime){ $pendingAnytime($a); })
              ->orWhere(function($b) use ($paidInMonth){ $paidInMonth($b); })
              ->orWhere(function($c) use ($canceladoInMonth){ $canceladoInMonth($c); });
        });

        // período (opcional)
        if ($periodFilter) {
            $p->where(function($w) use ($periodFilter){
                $periodFilter($w);
            });
        }

        // busca (opcional) direto no pagamento: cpf / nome / código
        if ($q !== '') {
            $qDigits = preg_replace('/\D+/', '', $q);

            $p->where(function($w) use ($q, $qDigits){
                $w->orWhere('full_name','like','%'.$q.'%')
                  ->orWhere('contrato_codigo_contrato','like','%'.$q.'%')
                  ->orWhere('cpf_cnpj','like','%'.$q.'%');

                if ($qDigits !== '') {
                    $w->orWhereRaw(
                        "REPLACE(REPLACE(REPLACE(REPLACE(cpf_cnpj,'.',''),'-',''),'/',''),' ','') LIKE ?",
                        ['%'.$qDigits.'%']
                    );
                }
            });
        }
    };

    /* -------------------------------------------------------------
     | 1) WEB (agente_cadastros)
     * -------------------------------------------------------------*/
    $concluidosAgente = AgenteCadastro::query()
        ->with(["pagamentoTesouraria:{$paySelect}"])
        ->whereHas('pagamentoTesouraria', $payWindowOrPending)
        ->orderByDesc('id')
        ->get()
        ->map(function ($c) use ($resolvePix, $resolveLocalDt) {
            $pay = $c->relationLoaded('pagamentoTesouraria') ? $c->pagamentoTesouraria : null;

            $c->setAttribute('is_app', false);
            if (empty($c->agente_responsavel) && $pay) {
                $c->agente_responsavel = $pay->agente_responsavel ?: 'Agente';
            }

            $c->setAttribute('pix_resolved', $resolvePix($c, $pay));
            [$dtLocal, $tsLocal] = $resolveLocalDt($c);
            $c->setAttribute('fila_dt', $dtLocal);
            $c->setAttribute('fila_dt_str', $dtLocal ? $dtLocal->format('d/m/Y H:i') : null);
            $c->setAttribute('fila_ts', $tsLocal);
            return $c;
        });

    /* -------------------------------------------------------------
     | 2) APP (associadodois_cadastros)
     * -------------------------------------------------------------*/
    $concluidosApp = collect();
    if (class_exists(\App\Models\AssociadoDoisCadastro::class)) {
        try {
            $appCols = ['id'];
            foreach ([
                'full_name','cpf_cnpj','email','created_at','pix_key','pix','chave_pix','bank_pix',
                'pixKey','pix_chave','key_pix','pixcode','bank_name','bank_agency','bank_account',
                'account_type','contrato_codigo_contrato','contrato_margem_disponivel','agente_responsavel',
            ] as $c) {
                if (Schema::hasColumn('associadodois_cadastros', $c)) $appCols[] = $c;
            }

            $concluidosApp = AssociadoDoisCadastro::query()
                ->select($appCols)
                ->with(["pagamentoTesouraria:{$paySelect}"])
                ->whereHas('pagamentoTesouraria', $payWindowOrPending)
                ->orderByDesc('id')
                ->get()
                ->map(function ($c) use ($resolvePix, $resolveLocalDt) {
                    $c->setAttribute('is_app', true);
                    if (empty($c->agente_responsavel)) $c->agente_responsavel = 'Aplicativo';

                    $pay = $c->relationLoaded('pagamentoTesouraria') ? $c->pagamentoTesouraria : null;
                    $c->setAttribute('pix_resolved', $resolvePix($c, $pay));

                    [$dtLocal, $tsLocal] = $resolveLocalDt($c);
                    $c->setAttribute('fila_dt', $dtLocal);
                    $c->setAttribute('fila_dt_str', $dtLocal ? $dtLocal->format('d/m/Y H:i') : null);
                    $c->setAttribute('fila_ts', $tsLocal);
                    return $c;
                });
        } catch (\Throwable $e) {
            Log::warning('[INDEX] Falha ao carregar bloco APP', ['err' => $e->getMessage()]);
        }
    }

    /* -------------------------------------------------------------
     | 3) DEDUP (contrato → cpf → id) e ordena (mantido)
     * -------------------------------------------------------------*/
    $all = $concluidosAgente->concat($concluidosApp)->values();

    $scoreFn = function ($x) {
        $pay    = optional($x->pagamentoTesouraria);
        $pixOk  = filled($x->getAttribute('pix_resolved')) ? 1 : 0;
        $isApp  = (bool) $x->getAttribute('is_app');
        $hasEm  = (string) ($x->email ?? '') !== '' ? 1 : 0;
        $paidTs = optional($pay->paid_at)->timestamp ?? 0;
        $crtTs  = optional($x->created_at)->timestamp ?? 0;
        $idNum  = is_numeric($x->id) ? (int) $x->id : 0;
        return [$pixOk, $isApp ? 1 : 0, $hasEm, $paidTs, $crtTs, $idNum];
    };

    $best = [];
    foreach ($all as $c) {
        $pay = optional($c->pagamentoTesouraria);
        $key = strtoupper((string)(
            $c->contrato_codigo_contrato
            ?? optional($pay)->contrato_codigo_contrato
            ?? $c->cpf_cnpj
            ?? optional($pay)->cpf_cnpj
            ?? 'ID-' . $c->id
        ));

        $cur = $best[$key] ?? null;
        if (!$cur) { $best[$key] = $c; continue; }
        if ($scoreFn($c) > $scoreFn($cur)) $best[$key] = $c;
    }

    $concluidos = collect(array_values($best))
        ->map(function ($c) use ($resolveLocalDt) {
            if (!$c->getAttribute('fila_dt')) {
                [$dtLocal, $tsLocal] = $resolveLocalDt($c);
                $c->setAttribute('fila_dt', $dtLocal);
                $c->setAttribute('fila_dt_str', $dtLocal ? $dtLocal->format('d/m/Y H:i') : null);
                $c->setAttribute('fila_ts', $tsLocal);
            }
            return $c;
        })
        ->values();

    // ======================================================================
    // ✅ guarda anti-vazamento consistente com as regras:
    // - pendente: sempre fica
    // - pago: só fica se status='pago' e paid_at no mês
    // - cancelado: só fica se created_at no mês
    // ======================================================================
    $concluidos = $concluidos->filter(function ($c) use ($iniUtc, $fimExUtc) {
        $pay = null;
        try { $pay = $c->pagamentoTesouraria ?? null; } catch (\Throwable $e) { $pay = null; }
        if (!$pay) return false;

        $st = (string) ($pay->status ?? '');

        // pago só se paid_at existir e dentro do mês
        if ($st === 'pago') {
            if (!$pay->paid_at) return true; // tratado como pendente visual
            $ts = ($pay->paid_at instanceof \Carbon\Carbon) ? $pay->paid_at : \Carbon\Carbon::parse($pay->paid_at, 'UTC');
            return $ts->gte($iniUtc) && $ts->lt($fimExUtc);
        }

        // cancelado só se created_at dentro do mês
        if ($st === 'cancelado') {
            if (!$pay->created_at) return false;
            $ts = ($pay->created_at instanceof \Carbon\Carbon) ? $pay->created_at : \Carbon\Carbon::parse($pay->created_at, 'UTC');
            return $ts->gte($iniUtc) && $ts->lt($fimExUtc);
        }

        // pendente/qualquer outro: sempre fica
        return true;
    })->values();

    // ===== separa PENDENTES x outros e ordena (mantido)
    $payStatusOf = function ($cad) {
        $pay = null;
        try { $pay = $cad->pagamentoTesouraria ?? null; } catch (\Throwable $e) { $pay = null; }

        $s = (string) (optional($pay)->status ?? '');
        if ($s === 'pago' && !empty(optional($pay)->paid_at)) return 'pago';
        if ($s === 'cancelado') return 'cancelado';
        return 'pendente';
    };

    $pendentes = $concluidos->filter(fn($c) => $payStatusOf($c) === 'pendente')->values();
    $outros    = $concluidos->reject(fn($c) => $payStatusOf($c) === 'pendente')->values();

    $sortKey = function ($c) {
        $ts = $c->getAttribute('fila_ts');
        if ($ts !== null) return $ts;

        $pay = null;
        try { $pay = $c->pagamentoTesouraria ?? null; } catch (\Throwable $e) { $pay = null; }

        if ($pay && $pay->paid_at instanceof \Carbon\Carbon) return $pay->paid_at->getTimestamp();
        if ($pay && $pay->paid_at) return strtotime((string) $pay->paid_at);
        if (isset($c->created_at) && $c->created_at instanceof \Carbon\Carbon) return $c->created_at->getTimestamp();
        if (isset($c->created_at) && $c->created_at) return strtotime((string) $c->created_at);

        return is_numeric($c->id) ? (int) $c->id : 0;
    };

    // Pendentes: mais antigos primeiro
    $pendentes = $pendentes->sortBy($sortKey)->values();
    // Outros (pago/cancelado): mais recentes primeiro
    $outros    = $outros->sortByDesc($sortKey)->values();

    $ordem = 1;
    foreach ($pendentes as $c) { $c->setAttribute('fila_ordem', $ordem++); }
    foreach ($outros as $c)    { $c->setAttribute('fila_ordem', null); }

    $concluidos = $pendentes->concat($outros)->values();

    // ===== payloads usuais da view (mantidos)
    $metrics   = ['receitas_mes' => '—', 'despesas_mes' => '—', 'saldo' => '—', 'pendencias' => '0'];
    $reuploads = collect();
    $pendentesColl = collect();
    $recebidos = collect();

    $ajustesUrl = Route::has('tesoureiro.ajustes.index')
        ? route('tesoureiro.ajustes.index')
        : null;

    $contratosUrl = Route::has('tesoureiro.dashboardtesoureiro')
        ? route('tesoureiro.dashboardtesoureiro')
        : (Route::has('tesoureiro.dashboard') ? route('tesoureiro.dashboard') : url()->current());

    $mesSel = $mesISO;

    // ✅ pendências por dia: isso hoje ainda usa “janela fechamento” no seu controller.
    // Como você pediu backend primeiro, deixei como está para não quebrar seu badge.
    // Quando vier o frontend, a gente ajusta o buildPendenciasResumoCal para mês natural também.
    $pendResumo = $this->buildPendenciasResumoCal($mesISO);
    $pendentesTotal = (int) ($pendResumo['total'] ?? 0);
    $pendentesPorDia = (array) ($pendResumo['days'] ?? []);

    return view('tesoureiro.dashboardtesoureiro', compact(
        'concluidos',
        'metrics',
        'reuploads',
        'pendentesColl',
        'recebidos',
        'ajustesUrl',
        'contratosUrl',
        'mesSel',
        'pendentesTotal',
        'pendentesPorDia'
    ));
}



    /** ---------------- PDF do cadastro (único) ---------------- */
    public function cadastroPdf($id)
    {
        // Sanitiza o ID (evita "462 " virar false e cair como 1)
        $rawId = is_scalar($id) ? trim((string) $id) : '';
        if (!preg_match('/^\d+$/', $rawId)) {
            abort(404, 'ID inválido.');
        }
        $id = (int) $rawId;

        Log::info('[TESOURARIA] cadastroPdf:in', ['raw_id' => $id, 'route' => optional(request()->route())->getName()]);

        $cad   = null;
        $isApp = false;
        $from  = 'direct';

        // 1) Tenta ID direto em AssociadoDois (APP)
        try {
            $cad   = AssociadoDoisCadastro::findOrFail($id);
            $isApp = true;
            $from  = 'associadodois:id';
        } catch (ModelNotFoundException $e1) {

            // 2) Tenta ID direto em AgenteCadastro (WEB)
            try {
                $cad   = AgenteCadastro::findOrFail($id);
                $isApp = false;
                $from  = 'agente:id';
            } catch (ModelNotFoundException $e2) {

                // 3) Trata como ID de TesourariaPagamento e resolve o vínculo
                try {
                    $pay = TesourariaPagamento::findOrFail($id);
                    $from = 'pagamento:id';

                    // Prioriza vínculo do APP
                    $cadIdApp = $pay->associadodois_cadastro_id
                             ?? $pay->associado_cadastro_id
                             ?? null;

                    if ($cadIdApp) {
                        $cad = AssociadoDoisCadastro::find($cadIdApp);
                        if ($cad) {
                            $isApp = true;
                            $from  = 'pagamento:associado';
                        }
                    }

                    // Fallback: vínculo WEB
                    if (!$cad) {
                        $cadIdWeb = $pay->agente_cadastro_id
                                ?? $pay->cadastro_id
                                ?? null;
                        if ($cadIdWeb) {
                            $cad = AgenteCadastro::find($cadIdWeb);
                            if ($cad) {
                                $isApp = false;
                                $from  = 'pagamento:agente';
                            }
                        }
                    }

                    if (!$cad) {
                        Log::warning('[TESOURARIA] cadastroPdf:pay-without-cadastro', [
                            'pay_id' => $pay->id,
                            'checked' => ['associadodois_cadastro_id','associado_cadastro_id','agente_cadastro_id','cadastro_id'],
                        ]);
                        abort(404, 'Pagamento sem vínculo de cadastro.');
                    }
                } catch (ModelNotFoundException $e3) {
                    Log::warning('[TESOURARIA] cadastroPdf:not-found', ['id' => $id]);
                    abort(404, 'Cadastro não encontrado.');
                }
            }
        }

        // Normaliza "antecipações"
        $anticipations = [];
        $raw = null;
        foreach (['antecipacoes_json','anticipations_json'] as $key) {
            $raw = data_get($cad, $key);
            if (!is_null($raw)) break;
        }
        if (is_string($raw)) {
            $raw = json_decode($raw, true) ?: [];
        }
        if (is_array($raw)) {
            $anticipations = array_values($raw);
        }

        // Escolha de view conforme origem
        $views = $isApp
            ? ['pdf.cadastro-app','pdf.cadastro-associadodois','pdf.cadastro-associado','cadastro-associado']
            : ['pdf.cadastro-tesoureiro','admin.cadastro-agente','pdf.cadastro-agente','cadastro-agente'];

        $view = collect($views)->first(fn($v) => view()->exists($v));
        if (!$view) {
            Log::error('[TESOURARIA] cadastroPdf:view-missing', ['isApp' => $isApp, 'tried' => $views]);
            abort(500, 'View do PDF não encontrada.');
        }

        $nomeBase = $cad->full_name ?? $cad->nome ?? $cad->name ?? 'associado';
        $filename = ($isApp ? 'cadastro-app-' : 'cadastro-') . Str::slug($nomeBase) . '-' . $cad->id . '.pdf';
        $download = request()->boolean('dl'); // ?dl=1

        // Log pra depurar de onde veio
        Log::info('[TESOURARIA] cadastroPdf:resolved', [
            'is_app' => $isApp,
            'cad_id' => $cad->id,
            'from'   => $from,
            'view'   => $view,
        ]);

        if (class_exists(\Barryvdh\DomPDF\Facade\Pdf::class)) {
            $pdf = Pdf::loadView($view, compact('cad','anticipations'))->setPaper('a4');
            return $download ? $pdf->download($filename) : $pdf->stream($filename);
        }
        if (app()->bound('dompdf.wrapper')) {
            $pdf = app('dompdf.wrapper');
            $pdf->loadView($view, compact('cad','anticipations'))->setPaper('a4');
            return $download ? $pdf->download($filename) : $pdf->stream($filename);
        }

        return response()->view($view, compact('cad','anticipations'));
    }

    /** ---------------- Upload duplo (tela principal / AGENTE) ---------------- */
    public function pagamentosUploadComprovante(Request $request, AgenteCadastro $cadastro)
    {
        $debugId = (string) Str::uuid();
        Log::info("pagamentosUploadComprovante:init debug_id={$debugId}", [
            'cadastro_id' => $cadastro->id,
            'user_id'     => Auth::id(),
        ]);

        try {
            $v = Validator::make($request->all(), [
                'comprovantes'   => ['required','array','size:2'],
                'comprovantes.*' => ['file','mimes:jpg,jpeg,png,webp,pdf','max:5120'],
            ]);
            if ($v->fails()) {
                Log::warning("pagamentosUploadComprovante:validation_failed debug_id={$debugId}", [
                    'errors' => $v->errors()->toArray(),
                ]);
                if ($request->wantsJson()) {
                    return response()->json(['ok'=>false,'errors'=>$v->errors(),'debug_id'=>$debugId], 422);
                }
                throw new ValidationException($v);
            }

            /** @var \Illuminate\Http\UploadedFile[] $files */
            $files = $request->file('comprovantes');

            Log::info("pagamentosUploadComprovante:files_received debug_id={$debugId}", [
                'count' => count($files),
                'f0'    => $files[0]?->getClientOriginalName(),
                'f1'    => $files[1]?->getClientOriginalName(),
                'sizes' => [ $files[0]?->getSize(), $files[1]?->getSize() ],
            ]);

            $dir   = 'tesouraria/comprovantes/'.$cadastro->id;
            $paths = [];

            foreach ($files as $idx => $file) {
                $ext        = strtolower($file->getClientOriginalExtension() ?: 'bin');
                $storedName = now()->format('Ymd_His')."_{$idx}_".Str::random(8).'.'.$ext;
                $paths[]    = $file->storeAs($dir, $storedName, 'public');
            }

            if (count($paths) !== 2) {
                Log::error("pagamentosUploadComprovante:paths_count_mismatch debug_id={$debugId}", ['paths'=>$paths]);
                return back()->withErrors(['comprovantes' => 'Falha ao enviar os dois comprovantes.'])->with('debug_id',$debugId);
            }

            $pay = TesourariaPagamento::firstOrNew(['agente_cadastro_id' => $cadastro->id]);
            if (!$pay->exists) {
                $pay->fill([
                    'cpf_cnpj'                   => $cadastro->cpf_cnpj,
                    'full_name'                  => $cadastro->full_name,
                    'agente_responsavel'         => $cadastro->agente_responsavel,
                    'contrato_codigo_contrato'   => $cadastro->contrato_codigo_contrato,
                    'contrato_margem_disponivel' => $cadastro->contrato_margem_disponivel,
                    'status'                     => 'pendente',
                    'created_by_user_id'         => Auth::id(),
                ]);
            }

            $oldAssoc  = $pay->comprovante_associado_path;
            $oldAgente = $pay->comprovante_agente_path;

            $pay->comprovante_associado_path = $paths[0];
            $pay->comprovante_agente_path    = $paths[1];
            $pay->save();

            $this->deleteIfExistsPublic($oldAssoc, $paths[0]);
            $this->deleteIfExistsPublic($oldAgente, $paths[1]);

            Log::info("pagamentosUploadComprovante:done debug_id={$debugId}", [
                'pay_id' => $pay->id, 'assoc'=>$paths[0], 'agente'=>$paths[1]
            ]);

            if ($request->wantsJson()) {
                return response()->json(['ok'=>true,'debug_id'=>$debugId,'pay_id'=>$pay->id], 200);
            }

            return back()->with('ok', 'Comprovantes enviados com sucesso.')->with('debug_id',$debugId);

        } catch (ValidationException $e) {
            throw $e;
        } catch (Throwable $e) {
            Log::error("pagamentosUploadComprovante:exception debug_id={$debugId} ".$e->getMessage(), [
                'trace' => $e->getTraceAsString(),
            ]);
            if ($request->wantsJson()) {
                return response()->json(['ok'=>false,'message'=>'Erro inesperado ao enviar.','debug_id'=>$debugId], 500);
            }
            return back()->withErrors(['comprovantes'=>'Erro inesperado ao enviar.'])->with('debug_id',$debugId);
        }
    }

    /** ---------------- Upload único (APP - AssociadoDois) com espelhamento no legado ---------------- */
    public function pagamentosUploadComprovanteApp(Request $request, AssociadoDoisCadastro $associadodois_cadastro)
    {
        $debugId = (string) Str::uuid();

        // Descobre o arquivo (aceita várias chaves)
        $keys = ['comprovante','arquivo','file','upload','file_app','doc'];
        $file = null; $foundKey = null;
        foreach ($keys as $k) {
            if ($request->hasFile($k)) { $file = $request->file($k); $foundKey = $k; break; }
        }
        if (!$file && $request->hasFile('comprovantes')) {
            $arr = $request->file('comprovantes');
            if (is_array($arr) && count($arr) > 0) { $file = $arr[0]; $foundKey = 'comprovantes[0]'; }
        }

        if (!$file) {
            Log::warning("pagamentosUploadComprovanteApp:no_file debug_id={$debugId}");
            return $request->wantsJson()
                ? response()->json(['ok'=>false,'message'=>'Envie um arquivo de comprovante.','debug_id'=>$debugId], 422)
                : back()->withErrors(['comprovante_app'=>'Envie um arquivo de comprovante.'])->with('debug_id',$debugId);
        }

        // Validação
        $v = Validator::make(
            ['comprovante_unico' => $file],
            ['comprovante_unico' => ['required','file','mimes:jpg,jpeg,png,webp,pdf','max:5120']]
        );
        if ($v->fails()) {
            Log::warning("pagamentosUploadComprovanteApp:validation_failed debug_id={$debugId}", ['errors'=>$v->errors()->toArray(),'key'=>$foundKey]);
            return $request->wantsJson()
                ? response()->json(['ok'=>false,'errors'=>$v->errors(),'debug_id'=>$debugId], 422)
                : back()->withErrors($v->errors())->with('debug_id',$debugId);
        }

        try {
            // Diretório por ID do cadastro APP
            $dir = 'tesouraria/comprovantes/'.$associadodois_cadastro->id;
            $ext        = strtolower($file->getClientOriginalExtension() ?: 'bin');
            $storedName = now()->format('Ymd_His')."_app_".Str::random(8).'.'.$ext;
            $path       = $file->storeAs($dir, $storedName, 'public');

            // Localiza/cria o pagamento do APP
            $pay = TesourariaPagamento::firstOrNew(['associadodois_cadastro_id' => $associadodois_cadastro->id]);
            if (!$pay->exists) {
                $pay->fill([
                    'cpf_cnpj'                   => $associadodois_cadastro->cpf_cnpj ?? null,
                    'full_name'                  => $associadodois_cadastro->full_name ?? 'Associado',
                    'agente_responsavel'         => $associadodois_cadastro->agente_responsavel ?? 'Aplicativo',
                    'contrato_codigo_contrato'   => $associadodois_cadastro->contrato_codigo_contrato ?? null,
                    'contrato_margem_disponivel' => $associadodois_cadastro->contrato_margem_disponivel ?? null,
                    'status'                     => 'pendente',
                    'created_by_user_id'         => Auth::id(),
                ]);
                $pay->associadodois_cadastro_id = $associadodois_cadastro->id;
            }

            // salva associado e espelha no legado se vazio
            $oldAssoc  = $pay->comprovante_associado_path;
            $oldLegacy = $pay->comprovante_path;

            $pay->comprovante_associado_path = $path;

            if (empty($pay->comprovante_path)) {
                $pay->comprovante_path = $path;
            }

            $pay->save();

            // apaga só o arquivo associado antigo (NÃO apagar o legado)
            $this->deleteIfExistsPublic($oldAssoc, $pay->comprovante_associado_path);

            $base      = route('tesoureiro.comprovantes.ver', $pay->id);
            $verAssoc  = $this->versionToken($pay->comprovante_associado_path ?? '');
            $viewAssoc = $this->versionedUrl($base, 1, $verAssoc);

            Log::info("pagamentosUploadComprovanteApp:done debug_id={$debugId}", [
                'pay_id'   => $pay->id,
                'cad_app'  => $associadodois_cadastro->id,
                'stored'   => $path,
                'view_url' => $viewAssoc,
                'mirrored' => (empty($oldLegacy) ? 'yes' : 'no'),
            ]);

            if ($request->wantsJson()) {
                return response()->json([
                    'ok'         => true,
                    'debug_id'   => $debugId,
                    'pay_id'     => $pay->id,
                    'view_assoc' => $viewAssoc,
                ], 200);
            }

            return back()->with('ok', 'Comprovante (aplicativo) enviado com sucesso.')->with('debug_id', $debugId);

        } catch (Throwable $e) {
            Log::error("pagamentosUploadComprovanteApp:exception debug_id={$debugId} ".$e->getMessage(), [
                'trace' => $e->getTraceAsString(),
            ]);
            return $request->wantsJson()
                ? response()->json(['ok'=>false,'message'=>'Erro inesperado ao enviar.','debug_id'=>$debugId], 500)
                : back()->withErrors(['comprovante_app'=>'Erro inesperado ao enviar.'])->with('debug_id',$debugId);
        }
    }

    /** ---------------- Exibir comprovante (rota nomeada para tesoureiro/admin) ---------------- */
    public function streamComprovante(\App\Models\TesourariaPagamento $pagamento, ?string $qual = null)
    {
        $debugId = (string) Str::uuid();

        // Permissão
        $user = auth()->user();
        if (!($user && ($user->hasRole('admin') || $user->hasRole('tesoureiro')))) {
            Log::warning("streamComprovante:forbidden debug_id={$debugId}", ['user_id'=>$user?->id, 'pay_id'=>$pagamento->id]);
            abort(403);
        }

        // Resolve a coluna desejada
        $col = null;
        $q = strtolower(trim((string) $qual));
        if (in_array($q, ['associado','assoc','cliente'], true))       $col = 'comprovante_associado_path';
        elseif (in_array($q, ['agente','agent'], true))                 $col = 'comprovante_agente_path';
        elseif (in_array($q, ['app','mobile','legado','padrao','padrão','path','default'], true))
                                                                       $col = 'comprovante_path';

        if (!$col && request()->has('i')) {
            $i = (int) request('i');
            $col = [0=>'comprovante_path', 1=>'comprovante_associado_path', 2=>'comprovante_agente_path'][$i] ?? null;
        }

        // Ordem de tentativa: pedido explícito -> associado -> agente -> legado
        $candidatos = [];
        if ($col) $candidatos[] = (string) $pagamento->{$col};
        $candidatos[] = (string) $pagamento->comprovante_associado_path;
        $candidatos[] = (string) $pagamento->comprovante_agente_path;
        $candidatos[] = (string) $pagamento->comprovante_path;

        foreach ($candidatos as $path) {
            $path = trim($path ?? '');
            if ($path === '') continue;

            // URL absoluta (S3 público/CDN) -> redireciona
            if (preg_match('~^https?://~i', $path)) {
                return redirect()->away($path);
            }

            // Suporta "disk:relative/path"
            $disk = null; $rel = $path;
            if (preg_match('/^([a-z0-9_]+):(.*)$/i', $path, $m)) {
                $disk = $m[1];
                $rel  = ltrim($m[2], '/');
            }
            $rel = ltrim($rel, '/');

            // Preferência: disco public com ETag
            $tryDisk = $disk ?: 'public';
            try {
                if (Storage::disk($tryDisk)->exists($rel)) {
                    if ($tryDisk === 'public') {
                        $mtime = Storage::disk($tryDisk)->lastModified($rel);
                        $size  = Storage::disk($tryDisk)->size($rel);
                        $etag  = md5($rel.'|'.$mtime.'|'.$size);

                        Log::info("streamComprovante:hit debug_id={$debugId}", [
                            'pay_id'=>$pagamento->id, 'qual'=>$qual, 'rel'=>$path, 'disk'=>$tryDisk, 'etag'=>$etag
                        ]);

                        $ifNoneMatch = request()->header('If-None-Match');
                        if ($etag && $ifNoneMatch && trim($ifNoneMatch,'"') === $etag) {
                            return response('', 304, ['ETag' => '"'.$etag.'"', 'X-Debug-Id'=>$debugId]);
                        }

                        $abs  = Storage::disk($tryDisk)->path($rel);
                        $mime = Storage::disk($tryDisk)->mimeType($rel) ?: 'application/octet-stream';

                        $headers = [
                            'Content-Type' => $mime,
                            'ETag'         => '"'.$etag.'"',
                            'X-Debug-Id'   => $debugId,
                        ];
                        if (request()->has('v')) $headers['Cache-Control'] = 'private, max-age=31536000, immutable';
                        else { $headers['Cache-Control']='no-store, no-cache, must-revalidate, max-age=0'; $headers['Pragma']='no-cache'; $headers['Expires']='0'; }

                        return response()->file($abs, $headers);
                    }

                    // Outros discos (local, s3, etc.)
                    return Storage::disk($tryDisk)->response($rel);
                }
            } catch (\Throwable $e) {
                // segue tentando outras opções
            }

            // Tenta em discos comuns se não foi especificado
            if (!$disk) {
                foreach (['local','s3'] as $d) {
                    try {
                        if (Storage::disk($d)->exists($rel)) return Storage::disk($d)->response($rel);
                    } catch (\Throwable $e) {}
                }
            }

            // Caminho absoluto no filesystem
            foreach ([storage_path('app/'.$rel), storage_path('app/public/'.$rel), public_path($rel)] as $abs) {
                if (is_file($abs)) {
                    $mime = File::mimeType($abs) ?: 'application/octet-stream';
                    return response()->file($abs, ['Content-Type'=>$mime]);
                }
            }
        }

        Log::warning('Comprovante não encontrado', [
            'pagamento_id' => $pagamento->id,
            'qual' => $qual,
            'assoc'  => $pagamento->comprovante_associado_path,
            'agente' => $pagamento->comprovante_agente_path,
            'legado' => $pagamento->comprovante_path,
            'debug_id' => $debugId,
        ]);

        abort(404, 'Comprovante não encontrado');
    }

    /** ---------------- Efetivar pagamento (tela principal) ---------------- */
    public function pagamentosEfetuar(Request $request, AgenteCadastro $cadastro)
    {
        $debugId = (string) Str::uuid();
        Log::info("pagamentosEfetuar:init debug_id={$debugId}", [
            'cadastro_id'=>$cadastro->id, 'user_id'=>Auth::id(), 'payload'=>$request->all()
        ]);

        $data = $request->validate([
            'valor_pago'      => ['nullable','numeric','min:0'],
            'valor_base'      => ['nullable','numeric','min:0'],
            'valor_agente'    => ['nullable','numeric','min:0'],
            'forma_pagamento' => ['nullable','string','max:40'],
            'notes'           => ['nullable','string','max:2000'],
        ]);

        $valorBase   = $data['valor_base'] ?? $data['valor_pago'] ?? $cadastro->contrato_margem_disponivel;
        $valorAgente = $data['valor_agente'] ?? null;

        $msgExtra = '';

        DB::transaction(function () use ($cadastro, $valorBase, $valorAgente, $data, &$msgExtra, $debugId) {
            $notes = trim(($data['notes'] ?? '')
                . ($valorAgente !== null ? ("\nAuxílio do agente: R$ ".number_format((float)$valorAgente, 2, ',', '.')) : '')
            );

            $pay = TesourariaPagamento::updateOrCreate(
                ['agente_cadastro_id' => $cadastro->id],
                [
                    'cpf_cnpj'                   => $cadastro->cpf_cnpj,
                    'full_name'                  => $cadastro->full_name,
                    'agente_responsavel'         => $cadastro->agente_responsavel,
                    'contrato_codigo_contrato'   => $cadastro->contrato_codigo_contrato,
                    'contrato_margem_disponivel' => $cadastro->contrato_margem_disponivel,
                    'valor_pago'         => $valorBase,
                    'status'             => 'pago',
                    'paid_at'            => now(),
                    'created_by_user_id' => Auth::id(),
                    'forma_pagamento'    => $data['forma_pagamento'] ?? null,
                    'notes'              => ($notes !== '' ? $notes : null),
                ]
            );

            Log::info("pagamentosEfetuar:updated debug_id={$debugId}", ['pay_id'=>$pay->id, 'valor_base'=>$valorBase]);

            $result = $this->ensureAssociadoAccount($cadastro);

            if ($result['status'] === 'created') {
                $msgExtra = " Conta do associado criada. Login: CPF (somente dígitos). Senha: matrícula do servidor público.";
                if (!empty($result['generated_temp'])) {
                    $msgExtra .= " Observação: matrícula ausente; senha temporária foi gerada.";
                }
            } elseif ($result['status'] === 'attached') {
                $msgExtra = " Associado já existia; papel garantido.";
            } elseif ($result['status'] === 'missing_cpf') {
                $msgExtra = " Atenção: cadastro sem CPF/CNPJ válido — não foi possível criar a conta do associado.";
            }

            Log::info("pagamentosEfetuar:ensure_associado debug_id={$debugId}", ['result'=>$result['status']]);
        });

        return back()->with('ok', 'Pagamento marcado como concluído.' . $msgExtra)->with('debug_id',$debugId);
    }

    public function reuploadPagamentoEfetivado(AgenteDocReupload $reupload)
    {
        $reupload->update(['status' => 'accepted']);
        return back()->with('ok', 'Reenvio marcado como concluído.');
    }

    /** ---------------- Criar/atualizar lançamento pendente (principal) ---------------- */
    public function pagamentosGerar(Request $request, AgenteCadastro $cadastro)
    {
        $valor = $request->input('valor_pago', $cadastro->contrato_margem_disponivel);

        TesourariaPagamento::updateOrCreate(
            ['agente_cadastro_id' => $cadastro->id],
            [
                'cpf_cnpj'                   => $cadastro->cpf_cnpj,
                'full_name'                  => $cadastro->full_name,
                'agente_responsavel'         => $cadastro->agente_responsavel,
                'contrato_codigo_contrato'   => $cadastro->contrato_codigo_contrato,
                'contrato_margem_disponivel' => $cadastro->contrato_margem_disponivel,
                'status'             => 'pendente',
                'valor_pago'         => $valor,
                'paid_at'            => null,
                'created_by_user_id' => Auth::id(),
            ]
        );

        return back()->with('ok', 'Lançamento criado com sucesso.');
    }

    /** ---------------- Usuário associado ---------------- */
    protected function ensureAssociadoAccount(AgenteCadastro $cadastro): array
    {
        $cpf = preg_replace('/\D+/', '', (string)($cadastro->cpf_cnpj ?? ''));
        if ($cpf === '') {
            return ['status' => 'missing_cpf'];
        }

        $matriculaDigits = preg_replace('/\D+/', '', (string)($cadastro->matricula_servidor_publico ?? ''));
        $generatedTemp   = false;

        if ($matriculaDigits === '') {
            $matriculaDigits = Str::random(10);
            $generatedTemp = true;
        }

        $emailFromCadastro = trim((string)($cadastro->email ?? ''));
        $emailFromCadastro = $emailFromCadastro !== '' ? $emailFromCadastro : null;

        $user = null;
        if (Schema::hasColumn('users', 'username')) {
            $user = User::where('username', $cpf)->first();
        }
        if (!$user && Schema::hasColumn('users', 'email')) {
            $emailsProbe = array_values(array_unique(array_filter([
                $emailFromCadastro,
                $cpf, // legado
            ])));
            if (!empty($emailsProbe)) {
                $user = User::whereIn('email', $emailsProbe)->first();
            }
        }

        if ($user) {
            $this->attachAssociadoRole($user);
            return ['status' => 'attached', 'user' => $user];
        }

        $payload = [
            'name'     => $cadastro->full_name ?: 'Associado',
            'password' => Hash::make($matriculaDigits),
        ];

        if (Schema::hasColumn('users', 'email')) {
            $payload['email'] = $emailFromCadastro ?: $cpf;
        }
        if (Schema::hasColumn('users', 'username')) {
            $payload['username'] = $cpf;
        }
        if (Schema::hasColumn('users', 'must_set_password')) {
            $payload['must_set_password'] = false;
        }

        $user = new User();
        $user->forceFill($payload)->save();

        $this->attachAssociadoRole($user);

        return [
            'status'         => 'created',
            'user'           => $user,
            'generated_temp' => $generatedTemp,
        ];
    }

    protected function attachAssociadoRole(User $user): void
    {
        $roleName = 'associado';

        if (method_exists($user, 'assignRole') && class_exists(\Spatie\Permission\Models\Role::class)) {
            \Spatie\Permission\Models\Role::findOrCreate($roleName, 'web');
            if (!$user->hasRole($roleName)) {
                $user->assignRole($roleName);
            }
            return;
        }

        if (Schema::hasTable('role_user') && Schema::hasTable('roles')) {
            $roleId = DB::table('roles')->where('name', $roleName)->value('id');
            if (!$roleId) {
                $roleId = DB::table('roles')->insertGetId([
                    'name'       => $roleName,
                    'guard_name' => 'web',
                    'created_at' => now(),
                    'updated_at' => now(),
                ]);
            }

            DB::table('role_user')->updateOrInsert(
                ['role_id' => $roleId, 'user_id' => $user->id],
                ['created_at' => now(), 'updated_at' => now()]
            );
        }
    }

    /** ---------------- Cancelar/limpar (principal) — CIRÚRGICO (não toca no legado) ---------------- */
    public function pagamentosCongelar(Request $request, AgenteCadastro $cadastro)
    {
        TesourariaPagamento::updateOrCreate(
            ['agente_cadastro_id' => $cadastro->id],
            [
                'cpf_cnpj'                   => $cadastro->cpf_cnpj,
                'full_name'                  => $cadastro->full_name,
                'agente_responsavel'         => $cadastro->agente_responsavel,
                'contrato_codigo_contrato'   => $cadastro->contrato_codigo_contrato,
                'contrato_margem_disponivel' => $cadastro->contrato_margem_disponivel,
                'status'             => 'cancelado',
                'valor_pago'         => $cadastro->contrato_margem_disponivel,
                'paid_at'            => null,
                'created_by_user_id' => Auth::id(),
            ]
        );

        return back()->with('ok', 'Contrato congelado. Você ainda pode enviar o comprovante e efetivar o pagamento quando quiser.');
    }

    public function pagamentosLimpar(Request $request, AgenteCadastro $cadastro)
    {
        $debugId = (string) Str::uuid();

        $pay = TesourariaPagamento::where('agente_cadastro_id', $cadastro->id)->first();

        if (!$pay) {
            Log::info("pagamentosLimpar:nothing debug_id={$debugId}", ['cadastro_id'=>$cadastro->id]);
            return back()->with('ok', 'Nada para limpar para este contrato.')->with('debug_id',$debugId);
        }

        $toDelete = array_filter([
            (string) $pay->comprovante_associado_path,
            (string) $pay->comprovante_agente_path,
        ]);

        foreach ($toDelete as $rel) {
            $rel = $this->normalizePublicPath($rel);
            if (Storage::disk('public')->exists($rel)) {
                Storage::disk('public')->delete($rel);
            }
        }

        $pay->forceFill([
            'comprovante_associado_path' => null,
            'comprovante_agente_path'    => null,
            'status'                     => 'pendente',
            'paid_at'                    => null,
        ])->save();

        Log::info("pagamentosLimpar:done debug_id={$debugId}", [
            'cadastro_id'=>$cadastro->id,
            'pay_id'=>$pay->id,
            'legacy_preserved' => (bool) $pay->comprovante_path,
        ]);

        return back()->with('ok', 'Comprovantes do associado e do agente removidos. O legado foi preservado.')->with('debug_id',$debugId);
    }

    // ========================= APP (AssociadoDois) — Efetuar / Congelar / Limpar =========================

    public function pagamentosEfetuarApp(Request $request, \App\Models\AssociadoDoisCadastro $associadodois_cadastro)
    {
        $debugId = (string) \Illuminate\Support\Str::uuid();
        \Illuminate\Support\Facades\Log::info("pagamentosEfetuarApp:init debug_id={$debugId}", [
            'cad_app_id' => $associadodois_cadastro->id,
            'user_id'    => \Illuminate\Support\Facades\Auth::id(),
            'payload'    => $request->all(),
        ]);

        $data = $request->validate([
            'valor_pago'      => ['nullable','numeric','min:0'],
            'valor_base'      => ['nullable','numeric','min:0'],
            'forma_pagamento' => ['nullable','string','max:40'],
            'notes'           => ['nullable','string','max:2000'],
        ]);

        $valorBase = $data['valor_base']
                  ?? $data['valor_pago']
                  ?? $associadodois_cadastro->contrato_margem_disponivel;

        \Illuminate\Support\Facades\DB::transaction(function () use ($associadodois_cadastro, $valorBase, $data, $debugId) {
            $notes = trim($data['notes'] ?? '');

            $pay = \App\Models\TesourariaPagamento::updateOrCreate(
                ['associadodois_cadastro_id' => $associadodois_cadastro->id],
                [
                    'cpf_cnpj'                   => $associadodois_cadastro->cpf_cnpj,
                    'full_name'                  => $associadodois_cadastro->full_name ?? 'Associado',
                    // força o rótulo "Aplicativo" para refletir corretamente na view
                    'agente_responsavel'         => 'Aplicativo',
                    'contrato_codigo_contrato'   => $associadodois_cadastro->contrato_codigo_contrato,
                    'contrato_margem_disponivel' => $associadodois_cadastro->contrato_margem_disponivel,
                    'valor_pago'                 => $valorBase,
                    'status'                     => 'pago',
                    'paid_at'                    => now(),
                    'created_by_user_id'         => \Illuminate\Support\Facades\Auth::id(),
                    'forma_pagamento'            => $data['forma_pagamento'] ?? null,
                    'notes'                      => ($notes !== '' ? $notes : null),
                ]
            );

            \Illuminate\Support\Facades\Log::info("pagamentosEfetuarApp:updated debug_id={$debugId}", [
                'pay_id'     => $pay->id,
                'valor_base' => $valorBase,
            ]);
        });

        return back()
            ->with('ok','Pagamento (App) marcado como concluído.')
            ->with('debug_id', $debugId);
    }

    public function pagamentosCongelarApp(Request $request, \App\Models\AssociadoDoisCadastro $associadodois_cadastro)
    {
        \App\Models\TesourariaPagamento::updateOrCreate(
            ['associadodois_cadastro_id' => $associadodois_cadastro->id],
            [
                'cpf_cnpj'                   => $associadodois_cadastro->cpf_cnpj,
                'full_name'                  => $associadodois_cadastro->full_name ?? 'Associado',
                'agente_responsavel'         => $associadodois_cadastro->agente_responsavel ?? 'Aplicativo',
                'contrato_codigo_contrato'   => $associadodois_cadastro->contrato_codigo_contrato,
                'contrato_margem_disponivel' => $associadodois_cadastro->contrato_margem_disponivel,
                'status'             => 'cancelado',
                'valor_pago'         => $associadodois_cadastro->contrato_margem_disponivel,
                'paid_at'            => null,
                'created_by_user_id' => \Illuminate\Support\Facades\Auth::id(),
            ]
        );

        return back()->with('ok','Contrato do App congelado.');
    }

    public function pagamentosLimparApp(Request $request, \App\Models\AssociadoDoisCadastro $associadodois_cadastro)
    {
        $debugId = (string) \Illuminate\Support\Str::uuid();

        $pay = \App\Models\TesourariaPagamento::where('associadodois_cadastro_id', $associadodois_cadastro->id)->first();
        if (!$pay) {
            return back()->with('ok','Nada para limpar para este contrato.')->with('debug_id',$debugId);
        }

        $toDelete = array_filter([
            (string) $pay->comprovante_associado_path,
            (string) $pay->comprovante_path, // se você espelhou acima
        ]);

        foreach ($toDelete as $rel) {
            $rel = $this->normalizePublicPath($rel);
            if (\Storage::disk('public')->exists($rel)) {
                \Storage::disk('public')->delete($rel);
            }
        }

        $pay->forceFill([
            'comprovante_associado_path' => null,
            'comprovante_path'           => null,
            'status'                     => 'pendente',
            'paid_at'                    => null,
        ])->save();

        return back()->with('ok','Comprovante do App limpo.')->with('debug_id',$debugId);
    }

    // ========================= AJUSTES =========================

    /**
     * Lista apenas pagamentos PAGO dentro da competência (ajustes não efetivam pagamentos).
     */
public function ajustesIndex(Request $r)
{
    // Competência vira apenas CONTEXTO para UI (não filtra mais a lista)
    [$mesISO, $ini, $fimEx, $fimUI, $_off, $TS_LOCAL, $betweenSql, $betweenArgs] = self::parseCompetencia($r);

    $q = trim((string)$r->input('q', ''));
    $PER_PAGE = 10;

    // ==========================
    // 1) WEB (agente_cadastros)
    // ==========================
    $web = DB::table('tesouraria_pagamentos as p')
        ->leftJoin('agente_cadastros as c', 'c.id', '=', 'p.agente_cadastro_id')
        ->whereNotNull('p.agente_cadastro_id')
        ->where('p.status', '=', 'pago') // <- traz TODOS os pagos (sem filtrar por competência)
        ->selectRaw("
            'web' as origem,
            p.id as pag_id,
            p.status,
            p.created_at,
            p.updated_at,
            p.comprovante_path as path_legacy,
            p.comprovante_associado_path as path_assoc,
            p.comprovante_agente_path as path_agente,
            p.notes,

            c.id as cad_id,
            c.full_name as cad_full_name,
            c.cpf_cnpj as cad_cpf_cnpj,
            c.contrato_codigo_contrato as cad_codigo,
            c.contrato_margem_disponivel as cad_margem,
            c.agente_responsavel as cad_agente,

            COALESCE(c.full_name, p.full_name, '') as nome,
            COALESCE(c.cpf_cnpj, p.cpf_cnpj, '') as cpf,
            COALESCE(c.contrato_codigo_contrato, p.contrato_codigo_contrato, '') as codigo,
            COALESCE(c.contrato_margem_disponivel, p.contrato_margem_disponivel) as margem,
            COALESCE(c.agente_responsavel, p.agente_responsavel, '') as agente
        ");

    // ==========================
    // 2) APP (associadodois_cadastros)
    // ==========================
    $app = DB::table('tesouraria_pagamentos as p')
        ->leftJoin('associadodois_cadastros as a', 'a.id', '=', 'p.associadodois_cadastro_id')
        ->whereNotNull('p.associadodois_cadastro_id')
        ->where('p.status', '=', 'pago') // <- traz TODOS os pagos (sem filtrar por competência)
        ->selectRaw("
            'app' as origem,
            p.id as pag_id,
            p.status,
            p.created_at,
            p.updated_at,
            p.comprovante_path as path_legacy,
            p.comprovante_associado_path as path_assoc,
            p.comprovante_agente_path as path_agente,
            p.notes,

            a.id as cad_id,
            a.full_name as cad_full_name,
            a.cpf_cnpj as cad_cpf_cnpj,
            a.contrato_codigo_contrato as cad_codigo,
            a.contrato_margem_disponivel as cad_margem,
            a.agente_responsavel as cad_agente,

            COALESCE(a.full_name, p.full_name, '') as nome,
            COALESCE(a.cpf_cnpj, p.cpf_cnpj, '') as cpf,
            COALESCE(a.contrato_codigo_contrato, p.contrato_codigo_contrato, '') as codigo,
            COALESCE(a.contrato_margem_disponivel, p.contrato_margem_disponivel) as margem,
            COALESCE(a.agente_responsavel, p.agente_responsavel, '') as agente
        ");

    // ==========================
    // 3) Fallback (pagamento sem vínculo)
    // ==========================
    $solo = DB::table('tesouraria_pagamentos as p')
        ->whereNull('p.agente_cadastro_id')
        ->whereNull('p.associadodois_cadastro_id')
        ->where('p.status', '=', 'pago') // <- traz TODOS os pagos (sem filtrar por competência)
        ->selectRaw("
            'pagamento' as origem,
            p.id as pag_id,
            p.status,
            p.created_at,
            p.updated_at,
            p.comprovante_path as path_legacy,
            p.comprovante_associado_path as path_assoc,
            p.comprovante_agente_path as path_agente,
            p.notes,

            NULL as cad_id,
            NULL as cad_full_name,
            NULL as cad_cpf_cnpj,
            NULL as cad_codigo,
            NULL as cad_margem,
            NULL as cad_agente,

            COALESCE(p.full_name, '') as nome,
            COALESCE(p.cpf_cnpj, '') as cpf,
            COALESCE(p.contrato_codigo_contrato, '') as codigo,
            p.contrato_margem_disponivel as margem,
            COALESCE(p.agente_responsavel, '') as agente
        ");

    // UNION dos 3 mundos (web + app + solo)
    $union = $web->unionAll($app)->unionAll($solo);

    // Consulta final (com busca + paginação no banco)
    $query = DB::query()->fromSub($union, 'x');

    if ($q !== '') {
        $qDigits = preg_replace('/\D+/', '', $q);

        $query->where(function ($w) use ($q, $qDigits) {
            $w->where('x.nome', 'like', '%' . $q . '%')
              ->orWhere('x.codigo', 'like', '%' . $q . '%')
              ->orWhere('x.cpf', 'like', '%' . $q . '%');

            // busca por CPF/CNPJ só com dígitos (funciona mesmo com máscara)
            if ($qDigits !== '') {
                $w->orWhereRaw(
                    "REPLACE(REPLACE(REPLACE(REPLACE(x.cpf,'.',''),'-',''),'/',''),' ','') LIKE ?",
                    ['%' . $qDigits . '%']
                );
            }
        });
    }

    $p = $query
        ->orderByDesc('x.pag_id')
        ->paginate($PER_PAGE)
        ->appends($r->query());

    $rows = collect($p->items())->map(function ($row) use ($mesISO, $q) {
        // mantém o “cadastro” (mesmo que a view não use diretamente)
        $cadastro = (object)[
            'id'                         => (int)($row->cad_id ?? 0),
            'full_name'                  => (string)($row->cad_full_name ?? $row->nome ?? ''),
            'cpf_cnpj'                   => (string)($row->cad_cpf_cnpj ?? $row->cpf ?? ''),
            'contrato_codigo_contrato'   => (string)($row->cad_codigo ?? $row->codigo ?? ''),
            'contrato_margem_disponivel' => $row->cad_margem ?? $row->margem,
            'agente_responsavel'         => (string)($row->cad_agente ?? $row->agente ?? ''),
        ];

        $base = !empty($row->pag_id) ? route('tesoureiro.comprovantes.ver', $row->pag_id) : null;

        $verAssoc  = $this->versionToken($row->path_assoc ?? '');
        $verAgente = $this->versionToken($row->path_agente ?? '');
        $verLegado = $this->versionToken($row->path_legacy ?? '');

        $row->source   = 'pagamento';
        $row->origem   = $row->origem ?? null;
        $row->pag_id   = (int)($row->pag_id ?? 0);
        $row->cad_id   = (int)($row->cad_id ?? 0);
        $row->cadastro = $cadastro;

        $row->status = (string)($row->status ?? 'pendente');
        $row->nome   = (string)($row->nome ?? '');
        $row->cpf    = (string)($row->cpf ?? '');
        $row->codigo = (string)($row->codigo ?? '');
        $row->margem = $row->margem ?? null;
        $row->agente = (string)($row->agente ?? '');

        $row->view_assoc  = ($base && !empty($row->path_assoc))  ? $this->versionedUrl($base, 1, $verAssoc)  : null;
        $row->view_agente = ($base && !empty($row->path_agente)) ? $this->versionedUrl($base, 2, $verAgente) : null;
        $row->view_legado = ($base && !empty($row->path_legacy)) ? $this->versionedUrl($base, 0, $verLegado) : null;

        $row->upload_pair_url = route('tesoureiro.ajustes.pagamentos.upload_pair', $row->pag_id);
        $row->efetuar_url     = null; // (mantido como estava)
        $row->clear_url       = route('tesoureiro.ajustes.pagamentos.limpar', $row->pag_id);

        return $row;
    });

    return view('tesoureiro.dashboardtesoureiroajuste', [
        'rows'        => $rows,
        'total'       => (int)$p->total(),
        'from'        => (int)($p->firstItem() ?? 0),
        'to'          => (int)($p->lastItem() ?? 0),
        'currentPage' => (int)$p->currentPage(),
        'lastPage'    => (int)$p->lastPage(),
        'mesSel'      => $mesISO, // contexto
        'rIni'        => $ini,
        'rFim'        => $fimUI,
    ]);
}


    /* ===================== helpers para upload/cache ===================== */

    protected static function phpUploadErrorName($code): ?string
    {
        if ($code === null) return null;
        return match ($code) {
            UPLOAD_ERR_OK         => 'UPLOAD_ERR_OK',
            UPLOAD_ERR_INI_SIZE   => 'UPLOAD_ERR_INI_SIZE',
            UPLOAD_ERR_FORM_SIZE  => 'UPLOAD_ERR_FORM_SIZE',
            UPLOAD_ERR_PARTIAL    => 'UPLOAD_ERR_PARTIAL',
            UPLOAD_ERR_NO_FILE    => 'UPLOAD_ERR_NO_FILE',
            UPLOAD_ERR_NO_TMP_DIR => 'UPLOAD_ERR_NO_TMP_DIR',
            UPLOAD_ERR_CANT_WRITE => 'UPLOAD_ERR_CANT_WRITE',
            UPLOAD_ERR_EXTENSION  => 'UPLOAD_ERR_EXTENSION',
            default               => 'UPLOAD_ERR_'.$code,
        };
    }

    protected function normalizePublicPath(?string $rel): string
    {
        $rel = (string) $rel;
        return preg_replace('~^/?(?:storage/|public/)~', '', $rel);
    }

    protected function versionToken(?string $rel): ?string
    {
        if (!$rel) return null;
        $rel = $this->normalizePublicPath($rel);
        $disk = Storage::disk('public');
        if (!$disk->exists($rel)) return null;
        $mtime = $disk->lastModified($rel);
        $size  = $disk->size($rel);
        $token = $mtime.'-'.$size;
        Log::info('versionToken', ['rel'=>$rel, 'mtime'=>$mtime, 'size'=>$size, 'token'=>$token]);
        return $token;
    }

    protected function versionedUrl(string $base, int $i, ?string $ver): string
    {
        $url = $base.'?i='.$i;
        if ($ver) $url .= '&v='.$ver;
        return $url;
    }

    protected function deleteIfExistsPublic(?string $old, ?string $new = null): void
    {
        $old = $this->normalizePublicPath((string)$old);
        $new = $this->normalizePublicPath((string)$new);
        if ($old && $old !== $new && Storage::disk('public')->exists($old)) {
            Storage::disk('public')->delete($old);
            Log::info('deleteIfExistsPublic:deleted_old', ['old'=>$old]);
        }
    }

    /** ---------------- AJUSTES: upload (pagamento existente, APENAS pagos) ---------------- */
    public function ajustesUploadComprovantesPair(Request $request, TesourariaPagamento $pagamento)
    {
        $debugId = (string) Str::uuid();
        Log::info("ajustesUpload:init debug_id={$debugId}", [
            'pay_id'  => $pagamento->id,
            'status'  => $pagamento->status,
            'user_id' => auth()->id(),
        ]);

        $iniProbe = [
            'upload_max_filesize' => ini_get('upload_max_filesize'),
            'post_max_size'       => ini_get('post_max_size'),
            'max_file_uploads'    => ini_get('max_file_uploads'),
            'file_uploads'        => ini_get('file_uploads'),
            'memory_limit'        => ini_get('memory_limit'),
            'upload_tmp_dir'      => ini_get('upload_tmp_dir') ?: sys_get_temp_dir(),
        ];

        $filesProbe = [];
        foreach (['comprovante_assoc','comprovante_agente'] as $key) {
            $f = $request->file($key);
            if ($f) {
                $filesProbe[$key] = [
                    'name'       => $f->getClientOriginalName(),
                    'size'       => $f->getSize(),
                    'mime'       => $f->getClientMimeType(),
                    'error'      => $f->getError(),
                    'error_name' => self::phpUploadErrorName($f->getError()),
                    'is_valid'   => $f->isValid(),
                ];
            } elseif (isset($_FILES[$key])) {
                $err = $_FILES[$key]['error'] ?? null;
                $filesProbe[$key] = [
                    'name'       => $_FILES[$key]['name']  ?? null,
                    'size'       => $_FILES[$key]['size']  ?? null,
                    'error'      => $err,
                    'error_name' => self::phpUploadErrorName($err),
                ];
            } else {
                $filesProbe[$key] = null;
            }
        }
        Log::info("ajustesUpload:probe debug_id={$debugId}", ['ini' => $iniProbe, 'files' => $filesProbe]);

        if ($pagamento->status !== 'pago') {
            Log::warning("ajustesUpload:forbidden_status debug_id={$debugId}");
            return response()->json([
                'ok'       => false,
                'debug_id' => $debugId,
                'message'  => 'Ajustes só permitem atualizar comprovantes de pagamentos já pagos.',
            ], 403);
        }

        try {
            $v = Validator::make($request->all(), [
                'comprovante_assoc'  => ['nullable','file','mimes:jpg,jpeg,png,webp,pdf','max:10240'],
                'comprovante_agente' => ['nullable','file','mimes:jpg,jpeg,png,webp,pdf','max:10240'],
                'mes'                => ['nullable','string'],
                'from_status'        => ['nullable','string'],
                'q'                  => ['nullable','string'],
            ]);

            if ($v->fails()) {
                Log::warning("ajustesUpload:validation_failed debug_id={$debugId}", [
                    'errors' => $v->errors()->toArray()
                ]);
                return response()->json([
                    'ok'       => false,
                    'debug_id' => $debugId,
                    'message'  => 'Falha na validação do upload.',
                    'errors'   => $v->errors(),
                ], 422);
            }

            if (!$request->hasFile('comprovante_assoc') && !$request->hasFile('comprovante_agente')) {
                Log::warning("ajustesUpload:no_files debug_id={$debugId}");
                return response()->json([
                    'ok'       => false,
                    'debug_id' => $debugId,
                    'message'  => 'Envie pelo menos um arquivo (associado ou agente).',
                ], 422);
            }

            $cad = $pagamento->cadastro;
            if (!$cad) {
                Log::error("ajustesUpload:no_cadastro debug_id={$debugId}", ['pay_id'=>$pagamento->id]);
                return response()->json([
                    'ok'       => false,
                    'debug_id' => $debugId,
                    'message'  => 'Cadastro vinculado não encontrado.',
                ], 404);
            }

            $dir = 'tesouraria/comprovantes/'.$cad->id;

            $oldAssoc  = $pagamento->comprovante_associado_path;
            $oldAgente = $pagamento->comprovante_agente_path;

            if ($request->hasFile('comprovante_assoc')) {
                $file = $request->file('comprovante_assoc');
                $ext  = strtolower($file->getClientOriginalExtension() ?: 'bin');
                $storedName = now()->format('Ymd_His')."_assoc_".Str::random(8).'.'.$ext;
                $path = $file->storeAs($dir, $storedName, 'public');
                $pagamento->comprovante_associado_path = $path;
                Log::info("ajustesUpload:saved_assoc debug_id={$debugId}", ['path'=>$path]);
            }

            if ($request->hasFile('comprovante_agente')) {
                $file = $request->file('comprovante_agente');
                $ext  = strtolower($file->getClientOriginalExtension() ?: 'bin');
                $storedName = now()->format('Ymd_His')."_agente_".Str::random(8).'.'.$ext;
                $path = $file->storeAs($dir, $storedName, 'public');
                $pagamento->comprovante_agente_path = $path;
                Log::info("ajustesUpload:saved_agente debug_id={$debugId}", ['path'=>$path]);
            }

            $pagamento->save();

            $this->deleteIfExistsPublic($oldAssoc,  $pagamento->comprovante_associado_path);
            $this->deleteIfExistsPublic($oldAgente, $pagamento->comprovante_agente_path);

            $base      = route('tesoureiro.comprovantes.ver', $pagamento->id);
            $hasAssoc  = !empty($pagamento->comprovante_associado_path);
            $hasAgente = !empty($pagamento->comprovante_agente_path);
            $hasLegacy = !empty($pagamento->comprovante_path);

            $verAssoc  = $this->versionToken($pagamento->comprovante_associado_path ?? '');
            $verAgente = $this->versionToken($pagamento->comprovante_agente_path ?? '');
            $verLegado = $this->versionToken($pagamento->comprovante_path ?? '');

            $viewAssoc  = $hasAssoc  ? $this->versionedUrl($base, 1, $verAssoc)   : null;
            $viewAgente = $hasAgente ? $this->versionedUrl($base, 2, $verAgente) : null;
            $viewLegado = $hasLegacy ? $this->versionedUrl($base, 0, $verLegado) : null;

            Log::info("ajustesUpload:done debug_id={$debugId}", [
                'pay_id'     => $pagamento->id,
                'assoc_path' => $pagamento->comprovante_associado_path,
                'agente_path'=> $pagamento->comprovante_agente_path,
                'legacy_path'=> $pagamento->comprovante_path,
                'ver_assoc'  => $verAssoc,
                'ver_agente' => $verAgente,
                'ver_legado' => $verLegado,
                'view_assoc' => $viewAssoc,
                'view_agente'=> $viewAgente,
                'view_legado'=> $viewLegado,
            ]);

            return response()->json([
                'ok'                 => true,
                'debug_id'           => $debugId,
                'message'            => 'Comprovante(s) atualizado(s).',
                'pag_id'             => $pagamento->id,
                'view_assoc'         => $viewAssoc,
                'view_agente'        => $viewAgente,
                'view_legado'        => $viewLegado,
                'need_assoc'         => !$hasAssoc,
                'need_agente'        => !$hasAgente,
                'replace_upload_url' => route('tesoureiro.ajustes.pagamentos.upload_pair', $pagamento->id),
                'efetuar_url'        => null,
                'clear_url'          => route('tesoureiro.ajustes.pagamentos.limpar', $pagamento->id),
                'valor_base'         => $pagamento->contrato_margem_disponivel,
            ]);

        } catch (Throwable $e) {
            Log::error("ajustesUpload:exception debug_id={$debugId} ".$e->getMessage(), [
                'trace' => $e->getTraceAsString(),
            ]);
            return response()->json([
                'ok'       => false,
                'debug_id' => $debugId,
                'message'  => 'Erro inesperado ao enviar.',
            ], 500);
        }
    }

    /** ---------------- AJUSTES: upload (cadastro sem pagamento) — BLOQUEADO ---------------- */
    public function ajustesUploadComprovantesPairCadastro(Request $request, AgenteCadastro $cadastro)
    {
        return $request->wantsJson()
            ? response()->json(['ok'=>false,'message'=>'Ajustes não aceitam envio sem pagamento existente e pago. Use a tela principal.'], 403)
            : back()->withErrors(['comprovante_assoc' => 'Ajustes não aceitam envio sem pagamento existente e pago. Use a tela principal.']);
    }

    /** ---------------- AJUSTES: limpar (só associado/agente; apenas se PAGO) ---------------- */
    public function ajustesLimpar(Request $request, TesourariaPagamento $pagamento)
    {
        $debugId = (string) Str::uuid();

        if ($pagamento->status !== 'pago') {
            Log::warning("ajustesLimpar:not_paid debug_id={$debugId}", ['pay_id'=>$pagamento->id,'status'=>$pagamento->status]);
            return back()->withErrors(['clear' => 'Ajustes só podem limpar arquivos de pagamentos já pagos.'])->with('debug_id',$debugId);
        }

        $paths = array_filter([
            (string) $pagamento->comprovante_associado_path,
            (string) $pagamento->comprovante_agente_path,
        ]);

        foreach ($paths as $rel) {
            $rel = $this->normalizePublicPath($rel);
            if (Storage::disk('public')->exists($rel)) {
                Storage::disk('public')->delete($rel);
            }
        }

        $pagamento->forceFill([
            'comprovante_associado_path' => null,
            'comprovante_agente_path'    => null,
        ])->save();

        Log::info("ajustesLimpar:done debug_id={$debugId}", ['pay_id'=>$pagamento->id]);

        $mes   = $request->input('mes');
        $query = trim((string)$request->input('q',''));

        return redirect()->route('tesoureiro.ajustes.index', [
            'mes'        => $mes ?: now()->format('Y-m'),
            'q'          => $query ?: null,
        ])->with('ok', 'Arquivos do associado e do agente foram limpos. O legado, status e data de pagamento foram preservados.')
          ->with('debug_id',$debugId);
    }

    /** ---------------- AJUSTES: efetivar — BLOQUEADO ---------------- */
    public function ajustesEfetuar(Request $request, TesourariaPagamento $pagamento)
    {
        return back()->withErrors(['efetuar' => 'Ajustes não efetivam pagamentos. Use a tela principal (Dashboard do Tesoureiro).']);
    }

    // ====================== CONFIRMAÇÕES (Ligação + Averbação) ======================

public function confirmacoesIndex(Request $r)
{
    // Competência vira CONTEXTO (não filtra a lista)
    [$mesISO, $ini, $fimEx, $fimUI, $TZ_OFF, $TS_LOCAL, $betweenSql, $betweenArgs] = self::parseCompetencia($r);

    $q       = trim((string) $r->input('q',''));
    $perPage = 10;

    $hasTblConf = Schema::hasTable('tesouraria_confirmacoes');

    // 1) IDs que apareceram em pagamentos (qualquer data)
    $idsFromPagamentos = DB::table('tesouraria_pagamentos as p')
        ->whereNotNull('p.agente_cadastro_id')
        ->selectRaw('p.agente_cadastro_id as cad_id');

    // 2) IDs que apareceram em confirmações (qualquer data)
    $idsUnion = $idsFromPagamentos;
    if ($hasTblConf) {
        $idsUnion = $idsUnion->unionAll(
            DB::table('tesouraria_confirmacoes as t')
                ->whereNotNull('t.cad_id')
                ->selectRaw('t.cad_id as cad_id')
        );
    }

    // DISTINCT em cima do UNION
    $idsDistinct = DB::query()
        ->fromSub($idsUnion, 'u')
        ->select('u.cad_id')
        ->distinct();

    // Base paginada diretamente no banco (bem mais leve que carregar tudo e fazer slice)
    $baseQuery = DB::table('agente_cadastros as c')
        ->joinSub($idsDistinct, 'u', function($join){
            $join->on('u.cad_id', '=', 'c.id');
        })
        ->select([
            'c.id as cad_id',
            'c.full_name as nome',
        ])
        ->when($q !== '', function($qq) use ($q){
            $qLower = mb_strtolower($q, 'UTF-8');
            $qq->whereRaw('LOWER(c.full_name) LIKE ?', ['%'.$qLower.'%']);
        })
        ->orderBy('c.full_name','asc');

    $p = $baseQuery->paginate($perPage)->appends($r->query());

    // Se não tem nada, devolve view vazia
    if ((int)$p->total() === 0) {
        return view('tesoureiro.dashboardtesoureiroconfirmacao', [
            'rows'        => collect(),
            'mesSel'      => $mesISO,
            'q'           => $q,
            'total'       => 0,
            'from'        => 0,
            'to'          => 0,
            'currentPage' => 1,
            'lastPage'    => 1,
        ]);
    }

    // Busca confirmações só dos IDs da página atual
    $pageCadIds = collect($p->items())->pluck('cad_id')->map(fn($v)=>(int)$v)->all();

    $confirmacoesByCad = collect();
    if ($hasTblConf) {
        $confirmacoesByCad = TesourariaConfirmacao::whereIn('cad_id', $pageCadIds)
            ->get()
            ->keyBy('cad_id');
    }

    $rows = collect($p->items())->map(function($row) use ($confirmacoesByCad) {
        $cadId = (int)($row->cad_id ?? 0);
        $conf  = $confirmacoesByCad->get($cadId);

        return (object)[
            'cad_id'               => $cadId,
            'nome'                 => (string)($row->nome ?? ''),
            'link_chamada'         => $conf?->link_chamada,
            'ligacao_recebida'     => (bool)($conf?->ligacao_recebida),
            'averbacao_confirmada' => (bool)($conf?->averbacao_confirmada),
        ];
    });

    return view('tesoureiro.dashboardtesoureiroconfirmacao', [
        'rows'        => $rows,
        'mesSel'      => $mesISO, // contexto
        'q'           => $q,
        'total'       => (int)$p->total(),
        'from'        => (int)($p->firstItem() ?? 0),
        'to'          => (int)($p->lastItem() ?? 0),
        'currentPage' => (int)$p->currentPage(),
        'lastPage'    => (int)$p->lastPage(),
    ]);
}


    public function confirmacoesSetLink(Request $req, AgenteCadastro $cadastro)
    {
        $data = $req->validate([
            'link_chamada' => ['nullable','string','max:2048'],
        ]);

        if (!Schema::hasTable('tesouraria_confirmacoes')) {
            return $req->wantsJson()
                ? response()->json(['ok' => false, 'message' => 'Tabela tesouraria_confirmacoes ausente. Rode as migrations.'], 409)
                : back()->withErrors('Tabela de confirmações ausente. Rode as migrations.');
        }

        try {
            $conf = TesourariaConfirmacao::firstOrCreate(['cad_id' => $cadastro->id]);
            $conf->link_chamada = $data['link_chamada'] ?? null;

            if ($conf->isDirty('link_chamada')) {
                $conf->ligacao_recebida     = false;
                $conf->ligacao_recebida_at  = null;
            }

            $conf->save();

            return $req->wantsJson()
                ? response()->json(['ok' => true])
                : back()->with('ok', 'Referência salva.');
        } catch (QueryException $e) {
            return $req->wantsJson()
                ? response()->json(['ok' => false, 'message' => 'Falha ao salvar a referência.'], 500)
                : back()->withErrors('Falha ao salvar a referência.');
        }
    }

    public function confirmacoesConfirmLigacao(Request $req, AgenteCadastro $cadastro)
    {
        if (!Schema::hasTable('tesouraria_confirmacoes')) {
            return $req->wantsJson()
                ? response()->json(['ok' => false, 'message' => 'Tabela tesouraria_confirmacoes ausente. Rode as migrations.'], 409)
                : back()->withErrors('Tabela de confirmações ausente. Rode as migrations.');
        }

        try {
            $conf = TesourariaConfirmacao::firstOrCreate(['cad_id' => $cadastro->id]);
            $conf->ligacao_recebida    = true;
            $conf->ligacao_recebida_at = now();
            $conf->save();

            return $req->wantsJson()
                ? response()->json(['ok' => true])
                : back()->with('ok', 'Ligação confirmada.');
        } catch (QueryException $e) {
            return $req->wantsJson()
                ? response()->json(['ok' => false, 'message' => 'Falha ao confirmar ligação.'], 500)
                : back()->withErrors('Falha ao confirmar ligação.');
        }
    }

    public function confirmacoesConfirmAverbacao(Request $req, AgenteCadastro $cadastro)
    {
        if (!Schema::hasTable('tesouraria_confirmacoes')) {
            return $req->wantsJson()
                ? response()->json(['ok' => false, 'message' => 'Tabela tesouraria_confirmacoes ausente. Rode as migrations.'], 409)
                : back()->withErrors('Tabela de confirmações ausente. Rode as migrations.');
        }

        try {
            $conf = TesourariaConfirmacao::firstOrCreate(['cad_id' => $cadastro->id]);
            $conf->averbacao_confirmada    = true;
            $conf->averbacao_confirmada_at = now();
            $conf->save();

            return $req->wantsJson()
                ? response()->json(['ok' => true])
                : back()->with('ok', 'Averbação confirmada.');
        } catch (QueryException $e) {
            return $req->wantsJson()
                ? response()->json(['ok' => false, 'message' => 'Falha ao confirmar averbação.'], 500)
                : back()->withErrors('Falha ao confirmar averbação.');
        }
    }

    // ====================== BENEFÍCIOS (planos) ======================

    public function beneficioModalData(\App\Models\AssociadoDoisCadastro $associadodois)
    {
        // margem do usuário (APP)
        $margem = (float) ($associadodois->contrato_margem_disponivel ?? 0);

        // carrega planos (nome, limite, margem_exigida, status) — tolerante a tabela ausente
        $planos = [];
        if (\Schema::hasTable('beneficio_planos')) {
            $planos = \DB::table('beneficio_planos')
                ->select('id','nome','limite_saque','margem_exigida','status')
                ->when(\Schema::hasColumn('beneficio_planos','status'), fn($q) =>
                    $q->where('status','ativo')
                )
                ->orderBy('limite_saque','asc')
                ->get()
                ->map(function($p){
                    return [
                        'id'             => (int) $p->id,
                        'nome'           => (string) $p->nome,
                        'limite_saque'   => (float) $p->limite_saque,
                        'margem_exigida' => (float) ($p->margem_exigida ?? 0),
                    ];
                })
                ->values();
        }

        return response()->json([
            'ok'      => true,
            'cad'     => [
                'id'      => (int) $associadodois->id,
                'nome'    => (string) ($associadodois->full_name ?? 'Associado'),
                'margem'  => $margem,
                'codigo'  => (string) ($associadodois->contrato_codigo_contrato ?? ''),
            ],
            'planos'  => $planos,
        ]);
    }

    public function beneficioAtribuir(Request $r, \App\Models\AssociadoDoisCadastro $associadodois)
    {
        $r->validate([
            'plano_id'        => ['required','integer','min:1'],
            'limite_aprovado' => ['nullable','numeric','min:0'],
        ]);

        if (!\Schema::hasTable('beneficio_planos')) {
            return response()->json(['ok'=>false,'message'=>'Tabela de planos ausente.'], 409);
        }
        if (!\Schema::hasTable('beneficio_linhas')) {
            return response()->json(['ok'=>false,'message'=>'Tabela beneficio_linhas ausente. Rode a migration abaixo.'], 409);
        }

        $plano = \DB::table('beneficio_planos')->where('id', $r->plano_id)->first();
        if (!$plano) {
            return response()->json(['ok'=>false,'message'=>'Plano não encontrado.'], 404);
        }

        $margemUser   = (float) ($associadodois->contrato_margem_disponivel ?? 0);
        $margemPlano  = (float) ($plano->margem_exigida ?? 0);
        $limitePlano  = (float) ($plano->limite_saque ?? 0);

        if ($margemUser < $margemPlano) {
            return response()->json([
                'ok'=>false,
                'message'=>'Margem do usuário inferior à margem exigida do plano.'
            ], 422);
        }

        $limiteAprovado = $r->filled('limite_aprovado')
            ? (float) $r->limite_aprovado
            : $limitePlano;

        $limiteAprovado = max(0, min($limiteAprovado, $margemUser));

        \DB::table('beneficio_linhas')->updateOrInsert(
            ['associadodois_cadastro_id' => $associadodois->id],
            [
                'beneficio_plano_id' => (int) $plano->id,
                'limite_aprovado'    => $limiteAprovado,
                'status'             => 'ativo',
                'updated_at'         => now(),
                'created_at'         => now(),
                'created_by'         => auth()->id(),
            ]
        );

        // opcional: garantir label “Aplicativo” visível
        if (\Schema::hasColumn('associadodois_cadastros','agente_responsavel') &&
            empty($associadodois->agente_responsavel)) {
            $associadodois->agente_responsavel = 'Aplicativo';
            $associadodois->save();
        }

        return response()->json([
            'ok'              => true,
            'message'         => 'Benefício/linha atribuída com sucesso.',
            'plano'           => ['id'=>$plano->id,'nome'=>$plano->nome],
            'limite_aprovado' => $limiteAprovado,
        ]);
    }

    // ====================== CALENDÁRIO DE PENDÊNCIAS ======================

    /**
     * Janela local (FECHAMENTO_DIA → próximo FECHAMENTO_DIA), no TZ exibido.
     * Retorna [inícioLocal, fimExclusivoLocal].
     */
    protected function calWindow(string $mes, string $tz): array
    {
        $fdia = (int) env('FECHAMENTO_DIA', 5);
        $base = Carbon::createFromFormat('Y-m', $mes, $tz)->startOfMonth();

        $iniLocal   = $base->copy()->day($fdia)->startOfDay();               // ex.: 05/mes 00:00
        $fimExLocal = $base->copy()->addMonth()->day($fdia)->startOfDay();   // ex.: 05/mes+1 00:00 (exclusivo)

        return [$iniLocal, $fimExLocal];
    }

    /**
     * Monta resumo de pendências (status != pago/cancelado) por dia da janela da competência.
     * Conta por dia no TZ de exibição e consulta created_at em UTC com [>= ini, < fim).
     */
    protected function buildPendenciasResumoCal(string $mes): array
    {
        $tz = config('app.display_tz') ?: 'America/Sao_Paulo';

        // Janela de competência: FECHAMENTO_DIA -> FECHAMENTO_DIA do mês seguinte (exclusivo)
        [$iniLocal, $fimExLocal] = $this->calWindow($mes, $tz);

        // Comparação no banco sempre em UTC
        $iniUtc = $iniLocal->copy()->tz('UTC');
        $fimUtc = $fimExLocal->copy()->tz('UTC');

        // Offset fixo para agrupar por DIA no fuso de exibição
        $offMin = $iniLocal->offsetMinutes;
        $sign   = $offMin >= 0 ? '+' : '-';
        $hh     = str_pad((string) floor(abs($offMin)/60), 2, '0', STR_PAD_LEFT);
        $mm     = str_pad((string) (abs($offMin)%60), 2, '0', STR_PAD_LEFT);
        $TZ_OFF = "{$sign}{$hh}:{$mm}";

        $pendentesStatus = ['pendente','ativo','aberto','em_aberto'];

        $raw = \DB::table('tesouraria_pagamentos as p')
            ->selectRaw("DATE(CONVERT_TZ(p.created_at, @@session.time_zone, ?)) as d, COUNT(*) as c", [$TZ_OFF])
            ->whereIn('p.status', $pendentesStatus)
            ->where('p.created_at', '>=', $iniUtc->format('Y-m-d H:i:s'))
            ->where('p.created_at', '<',  $fimUtc->format('Y-m-d H:i:s'))
            ->groupBy('d')
            ->pluck('c','d')
            ->toArray();

        // mapa contínuo (preenche zeros)
        $map = [];
        for ($cur = $iniLocal->copy(); $cur < $fimExLocal; $cur->addDay()) {
            $k = $cur->format('Y-m-d');
            $map[$k] = (int) ($raw[$k] ?? 0);
        }

        return [
            'mes'   => $mes,
            'total' => array_sum($map),
            'days'  => $map,
            'range' => [
                'ini' => $iniLocal->format('Y-m-d H:i:s'),
                'fim' => $fimExLocal->copy()->subSecond()->format('Y-m-d H:i:s'),
                'tz'  => $tz,
            ],
        ];
    }

    /**
     * Endpoint JSON para o calendário/polling
     * GET /tesoureiro/pendencias/summary?mes=YYYY-MM
     * GET /tesoureiro/pendencias/summary?mes_competencia=YYYY-MM
     */
    public function pendenciasSummary(Request $request)
    {
        $tz   = config('app.display_tz') ?: config('app.timezone', 'America/Sao_Paulo');
        $pendentesStatus = ['pendente','ativo','aberto','em_aberto'];
        $tbl = 'tesouraria_pagamentos';
        $col = 'created_at';

        // ===== Janela =====
        if ($mesComp = $request->query('mes_competencia')) {
            // mesma regra da competência (fdia -> fdia do próximo mês), meia-aberta
            [$iniLocal, $fimExLocal] = $this->calWindow($mesComp, $tz);
            $mode = 'competencia';
        } else {
            $mes = $request->query('mes') ?: now($tz)->format('Y-m');
            $m   = \Carbon\Carbon::createFromFormat('Y-m', $mes, $tz)->startOfMonth();
            $iniLocal   = $m->copy()->startOfMonth();
            $fimExLocal = $m->copy()->addMonth()->startOfMonth(); // exclusivo
            $mode = 'mes';
        }

        // Limites em UTC (comparação no banco sempre em UTC)
        $iniUtc = $iniLocal->copy()->tz('UTC');
        $fimUtc = $fimExLocal->copy()->tz('UTC');

        // Offset fixo para converter a data de criação para o fuso exibido na HORA DE AGRUPAR
        $offMin = $iniLocal->offsetMinutes;
        $sign   = $offMin >= 0 ? '+' : '-';
        $hh     = str_pad((string)floor(abs($offMin)/60), 2, '0', STR_PAD_LEFT);
        $mm     = str_pad((string)(abs($offMin)%60), 2, '0', STR_PAD_LEFT);
        $TZ_OFF = "{$sign}{$hh}:{$mm}";

        // Agrupamento por DIA NO FUSO LOCAL
        $raw = \DB::table($tbl)
            ->selectRaw("DATE(CONVERT_TZ($col, @@session.time_zone, ?)) as d, COUNT(*) as c", [$TZ_OFF])
            ->whereIn('status', $pendentesStatus)
            ->where($col, '>=', $iniUtc->format('Y-m-d H:i:s'))
            ->where($col, '<',  $fimUtc->format('Y-m-d H:i:s'))
            ->groupBy('d')
            ->pluck('c','d')
            ->toArray();

        // Mapa contínuo (para preencher dias sem registros)
        $map = [];
        for ($cur = $iniLocal->copy(); $cur < $fimExLocal; $cur->addDay()) {
            $k = $cur->format('Y-m-d');
            $map[$k] = (int) ($raw[$k] ?? 0);
        }

        return response()->json([
            'mode'  => $mode,
            'range' => [$iniLocal->format('Y-m-d'), $fimExLocal->copy()->subDay()->format('Y-m-d')],
            'total' => array_sum($map),
            'days'  => $map,
        ])->header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0');
    }
}
