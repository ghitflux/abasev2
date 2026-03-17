<?php

namespace App\Http\Controllers;

use Carbon\Carbon;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;
use App\Models\Refinanciamento;
use Illuminate\Support\Facades\Log;

class TesoureiroRefinanciamentoController extends Controller
{
    public function __construct()
    {
        $this->middleware(['auth', 'role:tesoureiro']);
    }

    private function tz(): string
    {
        return config('app.display_tz') ?: (config('app.timezone') ?: 'America/Sao_Paulo');
    }

    private function normDoc(string $doc): string
    {
        return preg_replace('/\D+/', '', (string) $doc) ?: '';
    }

    private function cpfNormExpr(string $col): string
    {
        // remove . - / e espaços
        return "REPLACE(REPLACE(REPLACE(REPLACE({$col},'.',''),'-',''),'/',''),' ','')";
    }

    /**
     * Retorna: [$mesSel, $mesC, $rIni, $rFim]
     * - $mesSel: "YYYY-MM"
     * - $mesC: Carbon startOfMonth (tz)
     * - $rIni/$rFim: janela do mês (start/end) no tz
     */
    private function parseCompetencia(Request $request): array
    {
        $tz   = $this->tz();
        $fdia = (int) env('FECHAMENTO_DIA', 5);

        $mesSel = trim((string) $request->query('mes', ''));

        // default inteligente quando não vem mes
        if (!$mesSel || !preg_match('/^\d{4}\-\d{2}$/', $mesSel)) {
            $nowTz  = now($tz);
            $mesSel = ($nowTz->day <= $fdia)
                ? $nowTz->copy()->subMonth()->format('Y-m')
                : $nowTz->format('Y-m');
        }

        try {
            $mesC = Carbon::createFromFormat('Y-m', $mesSel, $tz)->startOfMonth();
        } catch (\Throwable $e) {
            $nowTz  = now($tz);
            $mesSel = ($nowTz->day <= $fdia)
                ? $nowTz->copy()->subMonth()->format('Y-m')
                : $nowTz->format('Y-m');

            $mesC = Carbon::createFromFormat('Y-m', $mesSel, $tz)->startOfMonth();
        }

        $rIni = $mesC->copy()->startOfMonth()->startOfDay();
        $rFim = $mesC->copy()->endOfMonth()->endOfDay();

        return [$mesSel, $mesC, $rIni, $rFim];
    }

    /**
     * Retorna: [$dia, $dIni, $dFim]
     * - $dia: "YYYY-MM-DD"
     */
    private function parseDia(Request $request): array
    {
        $tz  = $this->tz();
        $dia = trim((string) $request->query('dia', ''));

        if (!$dia || !preg_match('/^\d{4}\-\d{2}\-\d{2}$/', $dia)) {
            $dia = now($tz)->toDateString();
        }

        try {
            $dC = Carbon::parse($dia, $tz);
        } catch (\Throwable $e) {
            $dC  = now($tz);
            $dia = $dC->toDateString();
        }

        return [$dia, $dC->copy()->startOfDay(), $dC->copy()->endOfDay()];
    }

    /**
     * Monta query base (SEM groupBy) com:
     * - agentes (por ID quando existir e fallback por CPF sem duplicar)
     * - tesouraria_pagamentos agregada
     * - última solicitação (req_status)
     * - selects calculados (valor_total, repasses, paid_flag, etc.)
     */
private function baseRefiQuery(): array
{
    if (!Schema::hasTable('refinanciamentos')) {
        return [null, []];
    }

    $meta = [];

    // Qual coluna liga refinanciamentos -> agente_cadastros?
    $cadCol = null;
    if (Schema::hasColumn('refinanciamentos', 'agente_cadastro_id')) $cadCol = 'agente_cadastro_id';
    elseif (Schema::hasColumn('refinanciamentos', 'cadastro_id')) $cadCol = 'cadastro_id';

    $meta['cadCol']     = $cadCol;
    $meta['hasAgentes'] = Schema::hasTable('agente_cadastros');
    $meta['hasTesPay']  = Schema::hasTable('tesouraria_pagamentos');
    $meta['hasCompTbl'] = Schema::hasTable('refinanciamento_comprovantes');
    $meta['hasSolTbl']  = Schema::hasTable('refinanciamento_solicitacoes');
    $meta['hasMargens'] = Schema::hasTable('agente_margens');
    $meta['hasUsers']   = Schema::hasTable('users');

    $cpfNormR = $this->cpfNormExpr('r.cpf_cnpj');

    $qb = DB::table('refinanciamentos as r');

    // ==========================================================
    // AGENTES (sem duplicar linhas)
    // ==========================================================
    $acFullNameExpr      = "NULL";
    $acMargExpr          = "NULL";
    $acMensExpr          = "NULL";
    $acCalcExpr          = "NULL";
    $acAuxExpr           = "NULL";
    $agRespExpr          = "NULL";
    $agRespFallbackExpr  = "NULL";

    $cadOwnerCol = null;
    if ($meta['hasAgentes']) {
        foreach (['agente_user_id', 'user_id', 'created_by_user_id', 'agente_id'] as $cand) {
            if (Schema::hasColumn('agente_cadastros', $cand)) {
                $cadOwnerCol = $cand;
                break;
            }
        }
    }
    $meta['cadOwnerCol'] = $cadOwnerCol;

    if ($meta['hasAgentes']) {
        $hasMarg = Schema::hasColumn('agente_cadastros', 'contrato_margem_disponivel');
        $hasMens = Schema::hasColumn('agente_cadastros', 'contrato_mensalidade');
        $hasCalc = Schema::hasColumn('agente_cadastros', 'calc_mensalidade_associativa');
        $hasAux  = Schema::hasColumn('agente_cadastros', 'auxilio_taxa');
        $hasAgResp = Schema::hasColumn('agente_cadastros', 'agente_responsavel');

        if ($cadCol) {
            // primário por ID
            $qb->leftJoin('agente_cadastros as ac', 'ac.id', '=', "r.{$cadCol}");

            // fallback por CPF (1 cadastro mais recente por CPF)
            $acx = DB::table('agente_cadastros')
                ->select([
                    DB::raw($this->cpfNormExpr('cpf_cnpj') . ' as cpf_norm'),
                    DB::raw('MAX(id) as id'),
                ])
                ->groupBy(DB::raw($this->cpfNormExpr('cpf_cnpj')));

            $qb->leftJoinSub($acx, 'acx', function ($j) use ($cpfNormR) {
                $j->on(DB::raw($cpfNormR), '=', 'acx.cpf_norm');
            });

            $qb->leftJoin('agente_cadastros as acc', 'acc.id', '=', 'acx.id');

            $acFullNameExpr = "COALESCE(NULLIF(TRIM(ac.full_name),''), NULLIF(TRIM(acc.full_name),''))";

            if ($hasMarg) $acMargExpr = "COALESCE(ac.contrato_margem_disponivel, acc.contrato_margem_disponivel)";
            if ($hasMens) $acMensExpr = "COALESCE(ac.contrato_mensalidade, acc.contrato_mensalidade)";
            if ($hasCalc) $acCalcExpr = "COALESCE(ac.calc_mensalidade_associativa, acc.calc_mensalidade_associativa)";
            if ($hasAux)  $acAuxExpr  = "COALESCE(ac.auxilio_taxa, acc.auxilio_taxa)";
            if ($hasAgResp) {
                $agRespExpr         = "NULLIF(TRIM(ac.agente_responsavel),'')";
                $agRespFallbackExpr = "NULLIF(TRIM(acc.agente_responsavel),'')";
            }
        } else {
            // somente por CPF
            $cpfNormAc = $this->cpfNormExpr('ac.cpf_cnpj');
            $qb->leftJoin('agente_cadastros as ac', function ($j) use ($cpfNormAc, $cpfNormR) {
                $j->on(DB::raw($cpfNormAc), '=', DB::raw($cpfNormR));
            });

            $acFullNameExpr = "NULLIF(TRIM(ac.full_name),'')";

            if ($hasMarg) $acMargExpr = "ac.contrato_margem_disponivel";
            if ($hasMens) $acMensExpr = "ac.contrato_mensalidade";
            if ($hasCalc) $acCalcExpr = "ac.calc_mensalidade_associativa";
            if ($hasAux)  $acAuxExpr  = "ac.auxilio_taxa";
            if ($hasAgResp) $agRespExpr = "NULLIF(TRIM(ac.agente_responsavel),'')";
        }
    }

    // ==========================================================
    // RESOLUÇÃO DO AGENTE USER ID
    // prioridade:
    // 1) coluna dona do cadastro
    // 2) fallback por users.name = agente_responsavel
    // ==========================================================
    $agenteUserExpr = "NULL";

    if ($meta['hasUsers']) {
        if ($agRespExpr !== "NULL") {
            $qb->leftJoin('users as uag', function ($j) use ($agRespExpr) {
                $j->on(DB::raw($agRespExpr), '=', 'uag.name');
            });
        }

        if ($agRespFallbackExpr !== "NULL") {
            $qb->leftJoin('users as uagf', function ($j) use ($agRespFallbackExpr) {
                $j->on(DB::raw($agRespFallbackExpr), '=', 'uagf.name');
            });
        }
    }

    if ($cadOwnerCol) {
        if ($cadCol) {
            $agenteUserExpr = "COALESCE(ac.{$cadOwnerCol}, acc.{$cadOwnerCol}, uag.id, uagf.id)";
        } else {
            $agenteUserExpr = "COALESCE(ac.{$cadOwnerCol}, uag.id)";
        }
    } else {
        if ($cadCol) {
            $agenteUserExpr = "COALESCE(uag.id, uagf.id)";
        } else {
            $agenteUserExpr = "COALESCE(uag.id)";
        }
    }

    // ==========================================================
    // MARGEM VIGENTE DO AGENTE
    // mesma filosofia do AgenteController
    // ==========================================================
    $percBackendExpr = "NULL";
    $hasMargemDbExpr = "0";

    if ($meta['hasMargens']) {
        $gmLatest = DB::table('agente_margens as gm1')
            ->select([
                'gm1.agente_user_id',
                DB::raw('MAX(gm1.vigente_desde) as max_vigente_desde'),
            ])
            ->where('gm1.vigente_desde', '<=', now())
            ->where(function ($w) {
                $w->whereNull('gm1.vigente_ate')
                  ->orWhere('gm1.vigente_ate', '>', now());
            })
            ->groupBy('gm1.agente_user_id');

        $qb->leftJoinSub($gmLatest, 'amx', function ($j) use ($agenteUserExpr) {
            $j->on(DB::raw($agenteUserExpr), '=', 'amx.agente_user_id');
        });

        $qb->leftJoin('agente_margens as am', function ($j) {
            $j->on('am.agente_user_id', '=', 'amx.agente_user_id')
              ->on('am.vigente_desde', '=', 'amx.max_vigente_desde');
        });

        $percBackendExpr = "am.percentual";
        $hasMargemDbExpr = "CASE WHEN am.percentual IS NULL THEN 0 ELSE 1 END";
    }

    // ==========================================================
    // TESOURARIA (subquery agregada)
    // ==========================================================
    $tpAggJoined = false;

    if ($meta['hasTesPay']) {
        $tpHasRefiId = Schema::hasColumn('tesouraria_pagamentos', 'refinanciamento_id');
        $tpHasCpf    = Schema::hasColumn('tesouraria_pagamentos', 'cpf_cnpj');
        $tpHasValor  = Schema::hasColumn('tesouraria_pagamentos', 'valor_pago');
        $tpHasStatus = Schema::hasColumn('tesouraria_pagamentos', 'status');
        $tpHasMargem = Schema::hasColumn('tesouraria_pagamentos', 'contrato_margem_disponivel');

        if ($tpHasRefiId) {
            $tpAgg = DB::table('tesouraria_pagamentos')
                ->select([
                    'refinanciamento_id',
                    DB::raw('SUM(COALESCE(' . ($tpHasValor ? 'valor_pago' : '0') . ',0)) as paid_total'),
                    DB::raw($tpHasStatus
                        ? "MAX(CASE WHEN LOWER(TRIM(COALESCE(status,'')))='pago' THEN 1 ELSE 0 END) as paid_flag"
                        : "0 as paid_flag"
                    ),
                    DB::raw($tpHasMargem ? 'MAX(COALESCE(contrato_margem_disponivel,0)) as tp_margem' : 'NULL as tp_margem'),
                ])
                ->groupBy('refinanciamento_id');

            $qb->leftJoinSub($tpAgg, 'tp', function ($j) {
                $j->on('tp.refinanciamento_id', '=', 'r.id');
            });

            $tpAggJoined = true;
        } elseif ($tpHasCpf) {
            $tpAgg = DB::table('tesouraria_pagamentos')
                ->select([
                    DB::raw($this->cpfNormExpr('cpf_cnpj') . ' as cpf_norm'),
                    DB::raw('SUM(COALESCE(' . ($tpHasValor ? 'valor_pago' : '0') . ',0)) as paid_total'),
                    DB::raw($tpHasStatus
                        ? "MAX(CASE WHEN LOWER(TRIM(COALESCE(status,'')))='pago' THEN 1 ELSE 0 END) as paid_flag"
                        : "0 as paid_flag"
                    ),
                    DB::raw($tpHasMargem ? 'MAX(COALESCE(contrato_margem_disponivel,0)) as tp_margem' : 'NULL as tp_margem'),
                ])
                ->groupBy(DB::raw($this->cpfNormExpr('cpf_cnpj')));

            $qb->leftJoinSub($tpAgg, 'tp', function ($j) use ($cpfNormR) {
                $j->on(DB::raw($cpfNormR), '=', 'tp.cpf_norm');
            });

            $tpAggJoined = true;
        }
    }

    $meta['tpAggJoined'] = $tpAggJoined;

    // ==========================================================
    // SOLICITAÇÕES
    // ==========================================================
    if ($meta['hasSolTbl']) {
        $solHasId     = Schema::hasColumn('refinanciamento_solicitacoes', 'id');
        $solHasRefiId = Schema::hasColumn('refinanciamento_solicitacoes', 'refinanciamento_id');

        if ($solHasId && $solHasRefiId) {
            $latest = DB::table('refinanciamento_solicitacoes')
                ->select([
                    'refinanciamento_id',
                    DB::raw('MAX(id) as last_id'),
                ])
                ->groupBy('refinanciamento_id');

            $qb->leftJoinSub($latest, 'rsl', function ($j) {
                $j->on('rsl.refinanciamento_id', '=', 'r.id');
            });

            $qb->leftJoin('refinanciamento_solicitacoes as rs', function ($j) {
                $j->on('rs.id', '=', 'rsl.last_id');
            });
        }
    }

    // ==========================================================
    // SELECT base + cálculos
    // ==========================================================
    $qb->select('r.*');

    $qb->addSelect(DB::raw("{$acFullNameExpr} as nome_resolvido"));
    $qb->addSelect(DB::raw("{$agenteUserExpr} as agente_user_id_resolvido"));
    $qb->addSelect(DB::raw("COALESCE({$agRespExpr}, {$agRespFallbackExpr}) as agente_responsavel_resolvido"));

    $rHasValorRef   = Schema::hasColumn('refinanciamentos', 'valor_refinanciamento');
    $rHasValorTotal = Schema::hasColumn('refinanciamentos', 'valor_total');

    $valorBaseExpr = "COALESCE("
        . ($tpAggJoined ? "tp.tp_margem" : "NULL") . ", "
        . ($acMargExpr !== "NULL" ? $acMargExpr : "NULL") . ", "
        . ($rHasValorRef ? "r.valor_refinanciamento" : "NULL") . ", "
        . ($rHasValorTotal ? "r.valor_total" : "NULL") . ", 0)";

    $qb->addSelect(DB::raw("{$valorBaseExpr} as valor_total"));

    $qb->addSelect(DB::raw(($tpAggJoined ? "tp.tp_margem" : "NULL") . " as tp_margem"));
    $qb->addSelect(DB::raw(($acMargExpr !== "NULL" ? $acMargExpr : "NULL") . " as ac_margem"));
    $qb->addSelect(DB::raw("{$percBackendExpr} as perc_vigente_backend"));
    $qb->addSelect(DB::raw("{$hasMargemDbExpr} as has_margem_db"));
    $qb->addSelect(DB::raw(($acAuxExpr !== "NULL" ? $acAuxExpr : "NULL") . " as auxilio_taxa_legado"));

    $mensalidadeBaseExpr = "COALESCE("
        . ($acMensExpr !== "NULL" ? $acMensExpr : "NULL") . ", "
        . ($acCalcExpr !== "NULL" ? $acCalcExpr : "NULL") . ", 0)";

    $qb->addSelect(DB::raw("{$mensalidadeBaseExpr} as mensalidade_base"));

    // ✅ regra final igual ao agente:
    // usa margem vigente do backend; se não existir, fallback 5
    $auxTaxExpr = "COALESCE({$percBackendExpr}, 5)";
    $qb->addSelect(DB::raw("{$auxTaxExpr} as auxilio_taxa"));

    $repasseExpr = "ROUND(({$valorBaseExpr}) * ({$auxTaxExpr} / 100), 2)";
    $qb->addSelect(DB::raw("{$repasseExpr} as repasse_agente"));
    $qb->addSelect(DB::raw("{$repasseExpr} as repasse_agente_calc"));

    $qb->addSelect(DB::raw("GREATEST(0, ROUND(({$valorBaseExpr}) - ({$repasseExpr}), 2)) as associado_valor"));
    $qb->addSelect(DB::raw("ROUND({$repasseExpr}, 2) as agente_valor"));

    if ($tpAggJoined) {
        $qb->addSelect(DB::raw("COALESCE(tp.paid_total, 0) as paid_total"));
        $qb->addSelect(DB::raw("COALESCE(tp.paid_flag, 0) as paid_flag"));
    } else {
        $qb->addSelect(DB::raw("0 as paid_total"));
        $qb->addSelect(DB::raw("0 as paid_flag"));
    }

    if ($meta['hasSolTbl'] && Schema::hasColumn('refinanciamento_solicitacoes', 'status')) {
        $qb->addSelect(DB::raw("LOWER(TRIM(COALESCE(rs.status,''))) as req_status"));
    } else {
        $qb->addSelect(DB::raw("'' as req_status"));
    }

    return [$qb, $meta];
}

    // ==========================================================
    // INDEX (dashboard) — AGORA TRAZ TODOS OS REGISTROS (SEM FILTRO POR ANO/MÊS)
    // ==========================================================
public function index(Request $request)
{
    $tz = $this->tz();

    // Mantém competência só para UI/PDF (não filtra mais a lista por mês/ano)
    [$mesSel, $mesC, $rIni, $rFim] = $this->parseCompetencia($request);

    // ✅ Força SEMPRE mostrar todos
    $only3        = '0';
    $statusFiltro = strtolower(trim((string) $request->query('status', '')));
    $q            = trim((string) $request->query('q', ''));

    // ✅ filtro por período (inputs from/to)
    $from = trim((string) $request->query('from', ''));
    $to   = trim((string) $request->query('to', ''));

    $hasPeriodo = (bool)(
        preg_match('/^\d{4}\-\d{2}\-\d{2}$/', $from) ||
        preg_match('/^\d{4}\-\d{2}\-\d{2}$/', $to)
    );

    $dIni = null;
    $dFim = null;

    if ($hasPeriodo) {
        if (!preg_match('/^\d{4}\-\d{2}\-\d{2}$/', $from)) {
            $from = now($tz)->subDays(7)->toDateString();
        }
        if (!preg_match('/^\d{4}\-\d{2}\-\d{2}$/', $to)) {
            $to = now($tz)->toDateString();
        }

        try {
            $dIni = Carbon::parse($from, $tz)->startOfDay();
        } catch (\Throwable $e) {
            $from = now($tz)->subDays(7)->toDateString();
            $dIni = Carbon::parse($from, $tz)->startOfDay();
        }

        try {
            $dFim = Carbon::parse($to, $tz)->endOfDay();
        } catch (\Throwable $e) {
            $to   = now($tz)->toDateString();
            $dFim = Carbon::parse($to, $tz)->endOfDay();
        }

        if ($dIni->gt($dFim)) {
            [$dIni, $dFim] = [$dFim->copy()->startOfDay(), $dIni->copy()->endOfDay()];
            [$from, $to]   = [$to, $from];
        }
    }

    if (!Schema::hasTable('refinanciamentos')) {
        return view('tesoureiro.dashboardrefinanciamento', [
            'tz'           => $tz,
            'mesSel'       => $mesSel,
            'rIni'         => $rIni,
            'rFim'         => $rFim,
            'only3'        => $only3,
            'statusFiltro' => $statusFiltro,
            'q'            => $q,
            'rows'         => new \Illuminate\Pagination\LengthAwarePaginator([], 0, 50),
        ])->withErrors(['Tabela refinanciamentos não existe.']);
    }

    [$qb, $meta] = $this->baseRefiQuery();
    if (!$qb) {
        return view('tesoureiro.dashboardrefinanciamento', [
            'tz'           => $tz,
            'mesSel'       => $mesSel,
            'rIni'         => $rIni,
            'rFim'         => $rFim,
            'only3'        => $only3,
            'statusFiltro' => $statusFiltro,
            'q'            => $q,
            'rows'         => new \Illuminate\Pagination\LengthAwarePaginator([], 0, 50),
        ])->withErrors(['Falha ao montar consulta base.']);
    }

    // ==========================================================
    // ✅ Regra de "pago" (igual ao Blade): baseado em comprovantes
    // ==========================================================
    $paidSql = null;

    if (!empty($meta['hasCompTbl'])) {
        $kindCol = null;
        if (Schema::hasColumn('refinanciamento_comprovantes', 'kind')) $kindCol = 'kind';
        elseif (Schema::hasColumn('refinanciamento_comprovantes', 'tipo')) $kindCol = 'tipo';

        if ($kindCol) {
            $paidSql = "
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
        } else {
            $paidSql = "EXISTS (SELECT 1 FROM refinanciamento_comprovantes rc WHERE rc.refinanciamento_id = r.id)";
        }
    }

    // ==========================================================
    // ✅ PERÍODO (AJUSTADO):
    // - Se status=pendente => filtra por r.created_at
    // - Se status=pago     => filtra por data de pagamento (r.* / rc.paid_max / rc.anexo_max)
    // - Se status=all      => CASE (pago -> pagamento; pendente -> created_at)
    // ==========================================================
    if ($hasPeriodo) {

        // (A) data de pagamento em refinanciamentos (se existir)
        $rPaidCandidates = [];
        foreach (['paid_at','data_pagamento','payment_date','pago_em','dt_pagamento','paid_date','pagamento_em'] as $c) {
            if (Schema::hasColumn('refinanciamentos', $c)) {
                $rPaidCandidates[] = "NULLIF(TRIM(CAST(r.{$c} AS CHAR)), '')";
            }
        }
        $rPaidExpr = $rPaidCandidates
            ? ("COALESCE(" . implode(',', $rPaidCandidates) . ")")
            : "NULL";

        // (B) agregado dos comprovantes: MAX(data anexação) e MAX(data pagamento se existir)
        $rcAggAlias  = 'rcw';
        $rcAggJoined = false;

        if (Schema::hasTable('refinanciamento_comprovantes')) {

            $rcDateCol = 'created_at';
            foreach (['created_at','uploaded_at','anexado_em','data_anexacao'] as $c) {
                if (Schema::hasColumn('refinanciamento_comprovantes', $c)) {
                    $rcDateCol = $c;
                    break;
                }
            }

            $rcPaidCandidates = [];
            foreach (['paid_at','data_pagamento','payment_date','pago_em','dt_pagamento','paid_date','pagamento_em'] as $c) {
                if (Schema::hasColumn('refinanciamento_comprovantes', $c)) {
                    $rcPaidCandidates[] = "NULLIF(TRIM(CAST(rc.{$c} AS CHAR)), '')";
                }
            }

            $rcPaidExpr = $rcPaidCandidates
                ? ("COALESCE(" . implode(',', $rcPaidCandidates) . ")")
                : "NULL";

            $rcAgg = DB::table("refinanciamento_comprovantes as rc")
                ->select([
                    'rc.refinanciamento_id',
                    DB::raw("MAX(rc.{$rcDateCol}) as anexo_max"),
                    DB::raw("MAX({$rcPaidExpr}) as paid_max"),
                ])
                ->groupBy('rc.refinanciamento_id');

            $qb->leftJoinSub($rcAgg, $rcAggAlias, function ($j) use ($rcAggAlias) {
                $j->on("{$rcAggAlias}.refinanciamento_id", '=', 'r.id');
            });

            $rcAggJoined = true;
        }

        $anexoExpr = $rcAggJoined ? "{$rcAggAlias}.anexo_max" : "NULL";
        $rcPaidMax = $rcAggJoined ? "{$rcAggAlias}.paid_max"  : "NULL";

        // pago = COALESCE(rPaidExpr, rcPaidMax, anexoExpr)
        $paidDateExpr = "COALESCE({$rPaidExpr}, {$rcPaidMax}, {$anexoExpr})";

        // ✅ pendente agora = created_at (do refinanciamento)
        $pendingDateExpr = "r.created_at";

        // isPaid expr (se não existe paidSql, considera 0)
        $isPaidExpr = $paidSql ? "CASE WHEN ({$paidSql}) THEN 1 ELSE 0 END" : "0";

        // ✅ escolhe qual data usar no filtro
        if ($statusFiltro === 'pendente') {
            // pendente: SEMPRE created_at
            $qb->whereBetween(DB::raw($pendingDateExpr), [$dIni, $dFim]);
        } elseif ($statusFiltro === 'pago') {
            // pago: data de pagamento (com fallback)
            $qb->whereBetween(DB::raw($paidDateExpr), [$dIni, $dFim]);
        } else {
            // todos: CASE (pago -> pagamento, pendente -> created_at)
            $displayDateExpr = "CASE WHEN ({$isPaidExpr}) = 1 THEN {$paidDateExpr} ELSE {$pendingDateExpr} END";
            $qb->whereBetween(DB::raw($displayDateExpr), [$dIni, $dFim]);
        }
    }

    // ==========================================================
    // filtro "pago/pendente" baseado em COMPROVANTES
    // ==========================================================
    if ($statusFiltro === 'pago' || $statusFiltro === 'pendente') {

        if (!empty($meta['hasCompTbl']) && $paidSql) {
            if ($statusFiltro === 'pago') {
                $qb->whereRaw($paidSql);
            } else {
                $qb->whereRaw("NOT ({$paidSql})");
            }
        } else {
            if ($statusFiltro === 'pago') {
                $qb->whereRaw('0 = 1');
            }
        }
    }

    // busca
    if ($q !== '') {
        $qDoc = $this->normDoc($q);

        $qb->where(function ($w) use ($q, $qDoc, $meta) {
            if ($qDoc !== '') {
                $w->orWhereRaw($this->cpfNormExpr('r.cpf_cnpj') . " LIKE ?", ["%{$qDoc}%"]);
            }

            $w->orWhere('r.nome_snapshot', 'like', "%{$q}%");

            if (!empty($meta['hasAgentes'])) {
                $w->orWhere('ac.full_name', 'like', "%{$q}%");
                if (!empty($meta['cadCol'])) {
                    $w->orWhere('acc.full_name', 'like', "%{$q}%");
                }
            }
        });
    }

    $qb->orderByDesc('r.id');

    $rows = $qb->paginate(50)->appends($request->query());

    // ==========================================================
    // HIDRATAÇÃO: comprovantes + itens dinâmicos em blocos de 3
    // ==========================================================
    $items = $rows->items();
    $ids   = collect($items)->pluck('id')->values();

    // comprovantes
    if (!empty($meta['hasCompTbl']) && $ids->isNotEmpty()) {
        $comps = DB::table('refinanciamento_comprovantes')
            ->whereIn('refinanciamento_id', $ids->all())
            ->orderBy('id')
            ->get()
            ->groupBy('refinanciamento_id');

        foreach ($items as $r) {
            $r->comprovantes = collect($comps[$r->id] ?? []);
        }
    } else {
        foreach ($items as $r) {
            $r->comprovantes = collect();
        }
    }

    // prepara CPFs da página
    $cpfNorms    = [];
    $cpfByRefiId = [];

    foreach ($items as $r) {
        $cpf = $this->normDoc((string) ($r->cpf_cnpj ?? ''));
        $cpfByRefiId[(int) $r->id] = $cpf;
        if ($cpf !== '') {
            $cpfNorms[$cpf] = true;
        }
    }
    $cpfNorms = array_keys($cpfNorms);

    // posição do refinanciamento dentro do CPF (0,1,2,...)
    $refiPos = [];
    if (!empty($cpfNorms)) {
        $refiAll = DB::table('refinanciamentos')
            ->select([
                'id',
                DB::raw($this->cpfNormExpr('cpf_cnpj') . ' as cpf_norm'),
                'created_at',
            ])
            ->whereIn(DB::raw($this->cpfNormExpr('cpf_cnpj')), $cpfNorms)
            ->orderBy('created_at', 'asc')
            ->orderBy('id', 'asc')
            ->get();

        $ctr = [];
        foreach ($refiAll as $x) {
            $cn = (string) ($x->cpf_norm ?? '');
            if ($cn === '') continue;
            if (!isset($ctr[$cn])) $ctr[$cn] = 0;
            $refiPos[(int) $x->id] = $ctr[$cn];
            $ctr[$cn]++;
        }
    }

    // histórico de pagamentos_mensalidades por CPF
    $pmHist = [];
    $pmHas  = Schema::hasTable('pagamentos_mensalidades');

    if ($pmHas && !empty($cpfNorms)) {
        $pmHasStatusCode  = Schema::hasColumn('pagamentos_mensalidades', 'status_code');
        $pmHasValor       = Schema::hasColumn('pagamentos_mensalidades', 'valor');
        $pmHasEsperado    = Schema::hasColumn('pagamentos_mensalidades', 'esperado_manual');
        $pmHasRecebido    = Schema::hasColumn('pagamentos_mensalidades', 'recebido_manual');
        $pmHasManualSt    = Schema::hasColumn('pagamentos_mensalidades', 'manual_status');
        $pmHasManualPaid  = Schema::hasColumn('pagamentos_mensalidades', 'manual_paid_at');
        $pmHasManualForma = Schema::hasColumn('pagamentos_mensalidades', 'manual_forma_pagamento');

        $pmQ = DB::table('pagamentos_mensalidades')
            ->select([
                'id',
                DB::raw($this->cpfNormExpr('cpf_cnpj') . ' as cpf_norm'),
                'referencia_month',
                ($pmHasStatusCode ? 'status_code' : DB::raw("NULL as status_code")),
                ($pmHasValor      ? 'valor'       : DB::raw("0 as valor")),
                ($pmHasEsperado   ? 'esperado_manual' : DB::raw("NULL as esperado_manual")),
                ($pmHasRecebido   ? 'recebido_manual' : DB::raw("NULL as recebido_manual")),
                ($pmHasManualSt   ? 'manual_status'   : DB::raw("NULL as manual_status")),
                ($pmHasManualPaid ? 'manual_paid_at'  : DB::raw("NULL as manual_paid_at")),
                ($pmHasManualForma ? 'manual_forma_pagamento' : DB::raw("NULL as manual_forma_pagamento")),
                DB::raw("COALESCE(" . ($pmHasManualPaid ? "manual_paid_at" : "NULL") . ", created_at) as ord_dt"),
            ])
            ->whereIn(DB::raw($this->cpfNormExpr('cpf_cnpj')), $cpfNorms)
            ->orderBy('ord_dt', 'asc')
            ->orderBy('referencia_month', 'asc')
            ->orderBy('id', 'asc');

        $pmRows = $pmQ->get();

        foreach ($pmRows as $pm) {
            $cn = (string) ($pm->cpf_norm ?? '');
            if ($cn === '') continue;
            if (!isset($pmHist[$cn])) $pmHist[$cn] = [];
            $pmHist[$cn][] = $pm;
        }
    }

    // MAPA DE AGENTES / APP POR CPF
    $agByCpf  = [];
    $appByCpf = [];

    if (!empty($cpfNorms)) {
        if (Schema::hasTable('agente_cadastros')) {
            $agRows = DB::table('agente_cadastros')
                ->select([
                    'id',
                    'full_name',
                    'agente_responsavel',
                    DB::raw($this->cpfNormExpr('cpf_cnpj') . ' as cpf_norm'),
                ])
                ->whereIn(DB::raw($this->cpfNormExpr('cpf_cnpj')), $cpfNorms)
                ->orderBy('id', 'asc')
                ->get();

            foreach ($agRows as $ag) {
                $cn = (string) ($ag->cpf_norm ?? '');
                if ($cn === '') continue;
                if (!isset($agByCpf[$cn]) || $ag->id > $agByCpf[$cn]->id) {
                    $agByCpf[$cn] = $ag;
                }
            }
        }

        if (Schema::hasTable('associadodois_cadastros')) {
            $appRows = DB::table('associadodois_cadastros')
                ->select([
                    'id',
                    'full_name',
                    'agente_responsavel',
                    DB::raw($this->cpfNormExpr('cpf_cnpj') . ' as cpf_norm'),
                ])
                ->whereIn(DB::raw($this->cpfNormExpr('cpf_cnpj')), $cpfNorms)
                ->orderBy('id', 'asc')
                ->get();

            foreach ($appRows as $ap) {
                $cn = (string) ($ap->cpf_norm ?? '');
                if ($cn === '') continue;
                if (!isset($appByCpf[$cn]) || $ap->id > $appByCpf[$cn]->id) {
                    $appByCpf[$cn] = $ap;
                }
            }
        }
    }

    // aplica itens (blocos de 3) + resolve agente_responsavel
    foreach ($items as $r) {
        $cpf = $cpfByRefiId[(int) $r->id] ?? '';
        $idx = $refiPos[(int) $r->id] ?? 0;

        $hist   = ($cpf !== '' && isset($pmHist[$cpf])) ? $pmHist[$cpf] : [];
        $offset = $idx * 3;
        $slice  = array_slice($hist, $offset, 3);

        $itens = collect();

        foreach ($slice as $pm) {
            $refMonth = !empty($pm->referencia_month)
                ? Carbon::parse($pm->referencia_month)->startOfMonth()->toDateString()
                : null;

            $st = '-';
            $ms = isset($pm->manual_status) ? trim((string) $pm->manual_status) : '';
            if ($ms !== '') {
                $st = strtolower($ms);
            } else {
                $sc = isset($pm->status_code) ? trim((string) $pm->status_code) : '';
                if ($sc !== '') $st = $sc;
            }

            $val = 0.0;
            $rm  = isset($pm->recebido_manual) ? (float) $pm->recebido_manual : 0.0;
            $em  = isset($pm->esperado_manual) ? (float) $pm->esperado_manual : 0.0;
            $vv  = isset($pm->valor) ? (float) $pm->valor : 0.0;

            if ($rm > 0) $val = $rm;
            elseif ($em > 0) $val = $em;
            else $val = $vv;

            $itens->push((object) [
                'refinanciamento_id'       => (int) $r->id,
                'referencia_month'         => $refMonth,
                'status_code'              => $st,
                'valor'                    => $val,
                'manual_paid_at'           => $pm->manual_paid_at ?? null,
                'manual_forma_pagamento'   => $pm->manual_forma_pagamento ?? null,
            ]);
        }

        while ($itens->count() < 3) {
            $itens->push((object) [
                'refinanciamento_id'       => (int) $r->id,
                'referencia_month'         => null,
                'status_code'              => '-',
                'valor'                    => 0,
                'manual_paid_at'           => null,
                'manual_forma_pagamento'   => null,
            ]);
        }

        $r->itens = $itens;

        $agenteNome = null;

        if ($cpf !== '') {
            if (isset($agByCpf[$cpf])) {
                $ag = $agByCpf[$cpf];
                $agenteNome = trim((string) ($ag->agente_responsavel ?: $ag->full_name ?: ''));
            }

            if (!$agenteNome && isset($appByCpf[$cpf])) {
                $ap = $appByCpf[$cpf];
                $agenteNome = trim((string) ($ap->agente_responsavel ?: $ap->full_name ?: ''));
            }
        }

        if ($agenteNome) {
            $r->agente_responsavel = $agenteNome;
        }
    }

    return view('tesoureiro.dashboardrefinanciamento', [
        'tz'           => $tz,
        'mesSel'       => $mesSel,
        'rIni'         => $rIni,
        'rFim'         => $rFim,
        'only3'        => $only3,
        'statusFiltro' => $statusFiltro,
        'q'            => $q,
        'rows'         => $rows,
    ]);
}

    // ==========================================================
    // RELATÓRIO DO DIA (JSON RESUMO)
    // ==========================================================

    public function relatorioDiaResumo(Request $request)
    {
        $tz  = config('app.display_tz') ?: config('app.timezone', 'America/Sao_Paulo');
        $dia = $request->query('dia');

        if (!$dia) {
            $dia = now($tz)->toDateString();
        }

        try {
            // Carrega todos os refinanciamentos relevantes.
            $rows = DB::table('refinanciamentos')->get();

            $dayStart = Carbon::parse($dia, $tz)->startOfDay()->timestamp;
            $dayEnd   = Carbon::parse($dia, $tz)->endOfDay()->timestamp;

            $map = collect($rows)->map(function ($r) use ($tz) {

                // ---------- COMPROVANTES (JSON na própria tabela, modo defensivo) ----------
                $rawComps = data_get($r, 'comprovantes', []);

                if (is_string($rawComps)) {
                    $decoded = json_decode($rawComps, true);
                    if (json_last_error() === JSON_ERROR_NONE && is_array($decoded)) {
                        $rawComps = $decoded;
                    } else {
                        $rawComps = [];
                    }
                }

                if ($rawComps instanceof \Illuminate\Support\Collection) {
                    $comps = $rawComps->map(fn ($c) => is_array($c) ? (object) $c : $c)->filter();
                } elseif (is_array($rawComps)) {
                    $comps = collect($rawComps)->map(fn ($c) => is_array($c) ? (object) $c : $c)->filter();
                } else {
                    $comps = collect();
                }

                // Origem / tipo (APP ou WEB)
                $origRaw = strtolower(trim((string)($r->origem ?? $r->origin ?? $r->source ?? '')));

                $isApp = in_array($origRaw, [
                        'app','associadodois','associado2','associado_dois','associado-dois'
                    ], true)
                    || !empty($r->associadodois_cadastro_id ?? null)
                    || !empty($r->orig_associadodois_cadastro_id ?? null)
                    || !empty($r->new_associadodois_cadastro_id ?? null)
                    || $comps->contains(function ($c) {
                        $k = strtolower(trim((string)($c->kind ?? $c->tipo ?? '')));
                        return $k === 'app';
                    });

                $compApp = $comps->first(function ($c) {
                    $k = strtolower(trim((string)($c->kind ?? $c->tipo ?? '')));
                    return $k === 'app';
                });

                $compA = $comps->first(function ($c) {
                    $k = strtolower(trim((string)($c->kind ?? $c->tipo ?? '')));
                    return $k === 'associado';
                });

                $compB = $comps->first(function ($c) {
                    $k = strtolower(trim((string)($c->kind ?? $c->tipo ?? '')));
                    return $k === 'agente';
                });

                $hasSingle = $isApp && (!empty($compApp) || $comps->first());
                $hasA = !$isApp && !empty($compA);
                $hasB = !$isApp && !empty($compB);

                // Mesma regra do dashboard: pago = (tem tudo que precisa)
                $pago = $isApp ? $hasSingle : ($hasA && $hasB);

                // ---------- DATA DA ANEXAÇÃO ----------
                $anexoTs = 0;
                if ($comps->count() > 0) {
                    $maxA = 0;
                    foreach ($comps as $c) {
                        $ts = $this->toTsAny(
                            $c->created_at
                            ?? $c->uploaded_at
                            ?? $c->anexado_em
                            ?? $c->data_anexacao
                            ?? null,
                            $tz
                        );
                        if ($ts > $maxA) $maxA = $ts;
                    }
                    $anexoTs = $maxA;
                }
                if ($anexoTs <= 0) {
                    $anexoTs = $this->toTsAny(
                        $r->updated_at ?? $r->created_at ?? null,
                        $tz
                    );
                }

                // ---------- VALOR TOTAL ----------
                $valorTotal = (float) (
                    $r->valor_refinanciamento
                    ?? $r->valor_total
                    ?? $r->tp_margem
                    ?? $r->ac_margem
                    ?? $r->contrato_margem_disponivel
                    ?? $r->margem_disponivel
                    ?? 0
                );

                return (object) [
                    'valor'    => $valorTotal,
                    'pago'     => $pago,
                    'anexo_ts' => $anexoTs,
                ];
            })->filter(function ($x) use ($dayStart, $dayEnd) {
                if (!$x->anexo_ts) return false;
                return $x->anexo_ts >= $dayStart && $x->anexo_ts <= $dayEnd;
            });

            $count        = $map->count();
            $total        = $map->sum('valor');
            $paidTotal    = $map->where('pago', true)->sum('valor');
            $pendingTotal = $total - $paidTotal;

            return response()->json([
                'ok'            => true,
                'dia'           => $dia,
                'count'         => $count,
                'total'         => $total,
                'paid_total'    => $paidTotal,
                'pending_total' => $pendingTotal,
            ]);
        } catch (\Throwable $e) {
            \Log::error('[tesoureiro.refinanciamentos.relatorio_dia_resumo] erro', [
                'dia' => $dia,
                'err' => $e->getMessage(),
            ]);

            return response()->json([
                'ok'            => false,
                'dia'           => $dia,
                'message'       => 'Erro ao gerar resumo do dia.',
                'count'         => 0,
                'total'         => 0,
                'paid_total'    => 0,
                'pending_total' => 0,
            ], 500);
        }
    }

    /**
     * Helper igual ao da view, só que no controller.
     */
    private function toTsAny($v, string $tz): int
    {
        if ($v === null) return 0;
        try {
            if ($v instanceof \Carbon\CarbonInterface) {
                return $v->copy()->timezone($tz)->timestamp;
            }
            if ($v instanceof \DateTimeInterface) {
                return \Carbon\Carbon::instance($v)->timezone($tz)->timestamp;
            }
            $s = trim((string) $v);
            if ($s === '' || $s === '0000-00-00' || $s === '0000-00-00 00:00:00') return 0;
            return \Carbon\Carbon::parse($s, $tz)->timestamp;
        } catch (\Throwable $e) {
            return 0;
        }
    }

    // ==========================================================
    // RELATÓRIO DO DIA (PDF)  ✅ AQUI ESTÁ A CORREÇÃO
    // ==========================================================

    public function relatorioDia(Request $request)
    {
        $tz = $this->tz();
        [$dia, $dIni, $dFim] = $this->parseDia($request);

        if (!Schema::hasTable('refinanciamentos') || !Schema::hasTable('refinanciamento_comprovantes')) {
            return back()->withErrors(['Tabelas necessárias não existem (refinanciamentos/refinanciamento_comprovantes).']);
        }

        [$qb, $meta] = $this->baseRefiQuery();
        if (!$qb) {
            return back()->withErrors(['Falha ao montar consulta base.']);
        }

        // Definir coluna de data dos comprovantes (compatível com várias estruturas)
        $compTbl   = 'refinanciamento_comprovantes';
        $rcDateCol = 'created_at';
        foreach (['created_at', 'uploaded_at', 'anexado_em', 'data_anexacao'] as $c) {
            if (Schema::hasColumn($compTbl, $c)) {
                $rcDateCol = $c;
                break;
            }
        }

        // Aggregado por refinanciamento, apenas anexados naquele dia
        $rcAgg = DB::table("{$compTbl} as rc")
            ->select([
                'rc.refinanciamento_id',
                DB::raw("MAX(rc.{$rcDateCol}) as anexado_em"),
                DB::raw('COUNT(rc.id) as qtd_comprovantes'),
            ])
            ->whereBetween("rc.{$rcDateCol}", [$dIni, $dFim])
            ->groupBy('rc.refinanciamento_id');

        $qb->joinSub($rcAgg, 'rcw', function ($j) {
            $j->on('rcw.refinanciamento_id', '=', 'r.id');
        });

        $qb->addSelect(DB::raw('rcw.anexado_em as anexado_em'));
        $qb->addSelect(DB::raw('rcw.qtd_comprovantes as qtd_comprovantes'));

        $statusFiltro = strtolower(trim((string) $request->query('status', '')));
        if ($statusFiltro === 'pago') {
            if (!empty($meta['tpAggJoined'])) $qb->whereRaw("COALESCE(tp.paid_flag,0) = 1");
            else $qb->whereRaw("0 = 1");
        } elseif ($statusFiltro === 'pendente') {
            if (!empty($meta['tpAggJoined'])) $qb->whereRaw("COALESCE(tp.paid_flag,0) = 0");
        }

        $q = trim((string) $request->query('q', ''));
        if ($q !== '') {
            $qDoc = $this->normDoc($q);

            $qb->where(function ($w) use ($q, $qDoc, $meta) {
                if ($qDoc !== '') {
                    $w->orWhereRaw($this->cpfNormExpr('r.cpf_cnpj') . " LIKE ?", ["%{$qDoc}%"]);
                }

                $w->orWhere('r.nome_snapshot', 'like', "%{$q}%");

                if (!empty($meta['hasAgentes'])) {
                    $w->orWhere('ac.full_name', 'like', "%{$q}%");
                    if (!empty($meta['cadCol'])) {
                        $w->orWhere('acc.full_name', 'like', "%{$q}%");
                    }
                }
            });
        }

        $qb->orderByDesc('anexado_em');

        $rows = $qb->get();

        // ✅ HIDRATAÇÃO DOS COMPROVANTES PARA O PDF
        foreach ($rows as $row) {
            $row->comprovantes = collect();
        }

        $ids = collect($rows)->pluck('id')->filter()->values()->all();

        if (!empty($ids) && Schema::hasTable($compTbl)) {
            $kindCol = Schema::hasColumn($compTbl, 'kind') ? 'kind'
                : (Schema::hasColumn($compTbl, 'tipo') ? 'tipo' : null);

            $fileCol = null;
            foreach (['path', 'file_path', 'arquivo', 'filename', 'nome_arquivo', 'file', 'url'] as $c) {
                if (Schema::hasColumn($compTbl, $c)) {
                    $fileCol = $c;
                    break;
                }
            }

            $dateCol = $rcDateCol ?: 'created_at';

            $select = [
                'rc.id',
                'rc.refinanciamento_id',
                DB::raw("rc.{$dateCol} as anexado_em"),
            ];

            if ($kindCol) {
                $select[] = DB::raw("LOWER(TRIM(COALESCE(rc.{$kindCol}, ''))) as kind");
            } else {
                $select[] = DB::raw("'' as kind");
            }

            if ($fileCol) {
                $select[] = DB::raw("rc.{$fileCol} as arquivo");
            } else {
                $select[] = DB::raw("'' as arquivo");
            }

            foreach (['disk', 'mime', 'size', 'original_name', 'nome_original'] as $c) {
                if (Schema::hasColumn($compTbl, $c)) {
                    if ($c === 'nome_original' && !Schema::hasColumn($compTbl, 'original_name')) {
                        $select[] = DB::raw("rc.{$c} as original_name");
                    } else {
                        $select[] = "rc.{$c}";
                    }
                }
            }

            $comps = DB::table("{$compTbl} as rc")
                ->select($select)
                ->whereIn('rc.refinanciamento_id', $ids)
                ->whereBetween("rc.{$dateCol}", [$dIni, $dFim])
                ->orderByDesc("rc.{$dateCol}")
                ->get();

            $byRef = [];
            foreach ($comps as $c) {
                $rid = (int) $c->refinanciamento_id;
                if (!isset($byRef[$rid])) $byRef[$rid] = collect();
                $byRef[$rid]->push($c);
            }

            foreach ($rows as $row) {
                $rid = (int) $row->id;
                $row->comprovantes = $byRef[$rid] ?? collect();
            }
        }

        $title = "Refinanciamentos (comprovantes anexados em {$dia})";

        $data = [
            'title' => $title,
            'tz'    => $tz,
            'dia'   => $dia,
            'dIni'  => $dIni,
            'dFim'  => $dFim,
            'rows'  => $rows,
        ];

        $download = (string) $request->query('download', '1');

        if ($download === '0') {
            return view('tesoureiro.refinanciamentos_pdf', $data);
        }

        try {
            $pdf = app('dompdf.wrapper');
            $pdf->loadView('tesoureiro.refinanciamentos_pdf', $data)->setPaper('a4', 'portrait');

            $filename = "refinanciamentos_anexados_{$dia}.pdf";
            return $pdf->download($filename);
        } catch (\Throwable $e) {
            return view('tesoureiro.refinanciamentos_pdf', $data)
                ->with('err', 'Não foi possível gerar PDF automaticamente. Exibindo HTML. Erro: ' . $e->getMessage());
        }
    }

    // ===========================
    // COMPROVANTES (UPLOAD/STREAM/LIMPAR)
    // ===========================

    private function compColPath(): string
    {
        foreach (['path', 'file_path', 'storage_path', 'arquivo_path'] as $c) {
            if (Schema::hasColumn('refinanciamento_comprovantes', $c)) return $c;
        }
        return 'path';
    }

    private function compColKind(): ?string
    {
        foreach (['kind', 'tipo'] as $c) {
            if (Schema::hasColumn('refinanciamento_comprovantes', $c)) return $c;
        }
        return null;
    }

    private function compColOriginalName(): ?string
    {
        foreach (['original_name', 'original_filename', 'nome_original', 'filename'] as $c) {
            if (Schema::hasColumn('refinanciamento_comprovantes', $c)) return $c;
        }
        return null;
    }

    private function compColMime(): ?string
    {
        foreach (['mime', 'mime_type'] as $c) {
            if (Schema::hasColumn('refinanciamento_comprovantes', $c)) return $c;
        }
        return null;
    }

    private function compColSize(): ?string
    {
        foreach (['size', 'file_size', 'filesize'] as $c) {
            if (Schema::hasColumn('refinanciamento_comprovantes', $c)) return $c;
        }
        return null;
    }

    private function compColDisk(): ?string
    {
        foreach (['disk'] as $c) {
            if (Schema::hasColumn('refinanciamento_comprovantes', $c)) return $c;
        }
        return null;
    }

    private function compColUploadedBy(): ?string
    {
        foreach (['uploaded_by_user_id', 'user_id', 'created_by_user_id'] as $c) {
            if (Schema::hasColumn('refinanciamento_comprovantes', $c)) return $c;
        }
        return null;
    }

/**
 * POST /tesoureiro/refinanciamentos/{refinanciamento}/upload-comprovante
 */
public function uploadComprovante(Request $request, int $refinanciamento)
{
    if (!Schema::hasTable('refinanciamentos')) {
        return back()->withErrors(['Tabela refinanciamentos não existe.']);
    }

    if (!Schema::hasTable('refinanciamento_comprovantes')) {
        return back()->withErrors(['Tabela refinanciamento_comprovantes não existe.']);
    }

    // Carrega o refinanciamento para pegar snapshots / cpf
    $refRow = DB::table('refinanciamentos')->where('id', $refinanciamento)->first();
    if (!$refRow) {
        return back()->withErrors(['Refinanciamento não encontrado.']);
    }

    // Detecta se a tabela de comprovantes tem as novas colunas de snapshot
    $compHasAgId       = Schema::hasColumn('refinanciamento_comprovantes', 'agente_cadastro_id');
    $compHasAgSnap     = Schema::hasColumn('refinanciamento_comprovantes', 'agente_snapshot');
    $compHasFilialSnap = Schema::hasColumn('refinanciamento_comprovantes', 'filial_snapshot');

    // Lê os snapshots já existentes no próprio refinanciamento (se existirem)
    $agenteCadastroId = data_get($refRow, 'agente_cadastro_id') ?: null;
    $agenteSnapshot   = trim((string) (data_get($refRow, 'agente_snapshot')   ?: ''));
    $filialSnapshot   = trim((string) (data_get($refRow, 'filial_snapshot')   ?: ''));

    // CPF do refinanciamento normalizado (só dígitos)
    $cpfRef = $this->normDoc((string) ($refRow->cpf_cnpj ?? ''));

    /**
     * ✅ NOVO: se os snapshots estiverem vazios no refinanciamento,
     * tenta resolver a partir de agente_cadastros (ID ou CPF) e
     * já grava de volta em `refinanciamentos`.
     */
    try {
        if (
            ($compHasAgId || $compHasAgSnap || $compHasFilialSnap) &&
            Schema::hasTable('agente_cadastros')
        ) {
            $agRow = null;

            // 1) tenta pelo próprio agente_cadastro_id, se já tiver algo lá
            if ($agenteCadastroId) {
                $agRow = DB::table('agente_cadastros')
                    ->where('id', $agenteCadastroId)
                    ->first();
            }

            // 2) se não achar ou não tiver id, tenta pelo CPF do refinanciamento
            if (!$agRow && $cpfRef !== '') {
                $agRow = DB::table('agente_cadastros')
                    ->whereRaw($this->cpfNormExpr('cpf_cnpj') . ' = ?', [$cpfRef])
                    ->orderByDesc('id')
                    ->first();
            }

            if ($agRow) {
                // garante id do cadastro
                if ($compHasAgId && !$agenteCadastroId) {
                    $agenteCadastroId = (int) $agRow->id;
                }

                // snapshot do agente: preferir agente_responsavel, senão full_name
                if ($agenteSnapshot === '') {
                    $agenteSnapshot = trim((string) (
                        $agRow->agente_responsavel
                        ?? $agRow->full_name
                        ?? ''
                    ));
                }

                // snapshot da filial: usar campo certo da tabela (agente_filial)
                if ($filialSnapshot === '') {
                    $filialSnapshot = trim((string) (
                        $agRow->agente_filial ?? ''
                    ));
                }

                // Atualiza o próprio refinanciamento com os snapshots resolvidos
                $updRef = [];

                if ($compHasAgId && $agenteCadastroId && empty($refRow->agente_cadastro_id)) {
                    $updRef['agente_cadastro_id'] = $agenteCadastroId;
                }
                if ($compHasAgSnap && $agenteSnapshot !== '' && empty($refRow->agente_snapshot)) {
                    $updRef['agente_snapshot'] = $agenteSnapshot;
                }
                if ($compHasFilialSnap && $filialSnapshot !== '' && empty($refRow->filial_snapshot)) {
                    $updRef['filial_snapshot'] = $filialSnapshot;
                }

                if (!empty($updRef)) {
                    DB::table('refinanciamentos')
                        ->where('id', $refinanciamento)
                        ->update($updRef);

                    Log::info('[TESOUREIRO][uploadComprovante] snapshots_ref_atualizados', [
                        'refinanciamento_id' => $refinanciamento,
                        'cpf_ref'            => $cpfRef,
                        'upd'                => $updRef,
                    ]);

                    // Atualiza o objeto em memória também
                    foreach ($updRef as $k => $v) {
                        $refRow->{$k} = $v;
                    }
                }
            } else {
                Log::info('[TESOUREIRO][uploadComprovante] agente_nao_resolvido', [
                    'refinanciamento_id' => $refinanciamento,
                    'cpf_ref'            => $cpfRef,
                    'agente_cadastro_id' => $agenteCadastroId,
                ]);
            }
        }
    } catch (\Throwable $e) {
        Log::warning('[TESOUREIRO][uploadComprovante] erro_resolvendo_snapshots', [
            'refinanciamento_id' => $refinanciamento,
            'msg'                => $e->getMessage(),
            'line'               => $e->getLine(),
        ]);
    }

    // ===================== validação dos arquivos =====================
    $request->validate([
        'comprovante'            => 'nullable|file|mimes:pdf,jpg,jpeg,png,webp|max:10240',
        'comprovante_associado'  => 'nullable|file|mimes:pdf,jpg,jpeg,png,webp|max:10240',
        'comprovante_agente'     => 'nullable|file|mimes:pdf,jpg,jpeg,png,webp|max:10240',

        'files'                  => 'nullable|array|max:5',
        'files.*'                => 'file|mimes:pdf,jpg,jpeg,png,webp|max:10240',

        'comprovantes'           => 'nullable|array|max:5',
        'comprovantes.*'         => 'file|mimes:pdf,jpg,jpeg,png,webp|max:10240',

        'kind'                   => 'nullable|string|max:30',
        'is_app'                 => 'nullable|in:0,1',
    ]);

    $toSave = [];

    if ($request->hasFile('comprovante_associado')) {
        $toSave[] = ['file' => $request->file('comprovante_associado'), 'kind' => 'associado'];
    }
    if ($request->hasFile('comprovante_agente')) {
        $toSave[] = ['file' => $request->file('comprovante_agente'), 'kind' => 'agente'];
    }

    if (empty($toSave) && $request->hasFile('files')) {
        foreach ((array) $request->file('files') as $i => $f) {
            if (!$f) continue;
            $toSave[] = ['file' => $f, 'kind' => (string) ($request->input("kinds.$i") ?? '')];
        }
    }

    if (empty($toSave) && $request->hasFile('comprovantes')) {
        foreach ((array) $request->file('comprovantes') as $i => $f) {
            if (!$f) continue;
            $kindGuess = ($i === 0) ? 'associado' : (($i === 1) ? 'agente' : '');
            $toSave[]  = ['file' => $f, 'kind' => $kindGuess];
        }
    }

    if (empty($toSave) && $request->hasFile('comprovante')) {
        $kind = (string) $request->input('kind', '');

        if (trim($kind) === '' && (string) $request->input('is_app', '0') === '1') {
            $kind = 'app';
        }

        $toSave[] = ['file' => $request->file('comprovante'), 'kind' => $kind];
    }

    if (empty($toSave)) {
        return back()->withErrors(['Nenhum arquivo foi enviado.']);
    }

    $pathCol = $this->compColPath();
    if (!Schema::hasColumn('refinanciamento_comprovantes', $pathCol)) {
        return back()->withErrors(["A coluna de caminho do arquivo não existe em refinanciamento_comprovantes (tentado: {$pathCol})."]);
    }

    $kindCol = $this->compColKind();
    $nameCol = $this->compColOriginalName();
    $mimeCol = $this->compColMime();
    $sizeCol = $this->compColSize();
    $diskCol = $this->compColDisk();
    $upByCol = $this->compColUploadedBy();

    $disk = config('filesystems.default', 'local');
    $dir  = "refinanciamentos/{$refinanciamento}/comprovantes";

    $saved = 0;

    foreach ($toSave as $item) {
        /** @var \Illuminate\Http\UploadedFile $file */
        $file = $item['file'];
        $kind = strtolower(trim((string) ($item['kind'] ?? '')));

        if ($kind === '') $kind = 'comprovante';

        $ext  = $file->getClientOriginalExtension() ?: 'bin';
        $uuid = (string) Str::uuid();

        Storage::disk($disk)->putFileAs($dir, $file, "{$uuid}.{$ext}");

        $path = "{$dir}/{$uuid}.{$ext}";

        $ins = [
            'refinanciamento_id' => $refinanciamento,
            $pathCol             => $path,
            'created_at'         => now(),
            'updated_at'         => now(),
        ];

        if ($kindCol) $ins[$kindCol] = $kind;
        if ($nameCol) $ins[$nameCol] = (string) $file->getClientOriginalName();
        if ($mimeCol) $ins[$mimeCol] = (string) ($file->getClientMimeType() ?: '');
        if ($sizeCol) $ins[$sizeCol] = (int) ($file->getSize() ?: 0);
        if ($diskCol) $ins[$diskCol] = $disk;
        if ($upByCol) $ins[$upByCol] = Auth::id();

        // ✅ Snapshots agora SEMPRE vão, se conseguimos resolver lá em cima
        if ($compHasAgId && $agenteCadastroId) {
            $ins['agente_cadastro_id'] = $agenteCadastroId;
        }
        if ($compHasAgSnap && $agenteSnapshot !== '') {
            $ins['agente_snapshot'] = $agenteSnapshot;
        }
        if ($compHasFilialSnap && $filialSnapshot !== '') {
            $ins['filial_snapshot'] = $filialSnapshot;
        }

        DB::table('refinanciamento_comprovantes')->insert($ins);
        $saved++;
    }

    return back()->with('ok', "✅ {$saved} comprovante(s) enviado(s) com sucesso.");
}




    /**
     * GET /tesoureiro/refinanciamentos/{refinanciamento}/comprovantes
     */
    public function streamComprovante(Request $request, int $refinanciamento)
    {
        if (!Schema::hasTable('refinanciamento_comprovantes')) abort(404);

        $pathCol = $this->compColPath();
        $kindCol = $this->compColKind();
        $nameCol = $this->compColOriginalName();
        $mimeCol = $this->compColMime();
        $diskCol = $this->compColDisk();

        $id   = (int) $request->query('id', 0);
        $kind = strtolower(trim((string) $request->query('kind', '')));

        // compat antigo (?i=1|2)
        if ($kind === '') {
            $i = (int) $request->query('i', 0);
            if ($i === 1) $kind = 'associado';
            if ($i === 2) $kind = 'agente';
        }

        $q = DB::table('refinanciamento_comprovantes')
            ->where('refinanciamento_id', $refinanciamento);

        if ($id > 0) {
            $q->where('id', $id);
        } elseif ($kind !== '' && $kindCol) {
            $q->whereRaw("LOWER(TRIM(COALESCE({$kindCol},''))) = ?", [$kind]);
        }

        $comp = $q->orderByDesc('id')->first();
        if (!$comp) abort(404);

        $disk = ($diskCol && !empty($comp->{$diskCol}))
            ? (string) $comp->{$diskCol}
            : config('filesystems.default', 'local');

        $path = (string) ($comp->{$pathCol} ?? '');

        if ($path === '' || !Storage::disk($disk)->exists($path)) {
            abort(404);
        }

        $filename = ($nameCol && !empty($comp->{$nameCol}))
            ? (string) $comp->{$nameCol}
            : basename($path);

        $headers = [];
        if ($mimeCol && !empty($comp->{$mimeCol})) {
            $headers['Content-Type'] = (string) $comp->{$mimeCol};
        }

        // NOVO: abrir inline (outra aba) em vez de forçar download
        return Storage::disk($disk)->response($path, $filename, $headers);
    }

    /**
     * POST /tesoureiro/refinanciamentos/{refinanciamento}/limpar-comprovantes
     */
    public function limparComprovantes(Request $request, int $refinanciamento)
    {
        if (!Schema::hasTable('refinanciamento_comprovantes')) {
            return back()->withErrors(['Tabela refinanciamento_comprovantes não existe.']);
        }

        $pathCol = $this->compColPath();
        $diskCol = $this->compColDisk();

        $rows = DB::table('refinanciamento_comprovantes')
            ->where('refinanciamento_id', $refinanciamento)
            ->get();

        foreach ($rows as $r) {
            $disk = ($diskCol && !empty($r->{$diskCol}))
                ? (string) $r->{$diskCol}
                : config('filesystems.default', 'local');

            $path = (string) ($r->{$pathCol} ?? '');
            if ($path !== '') {
                Storage::disk($disk)->delete($path);
            }
        }

        DB::table('refinanciamento_comprovantes')
            ->where('refinanciamento_id', $refinanciamento)
            ->delete();

        return back()->with('ok', '🧹 Comprovantes removidos com sucesso.');
    }

    public function relatorioPeriodo(Request $request)
    {
        $tz = $this->tz();

        $from = trim((string) $request->query('from', ''));
        $to   = trim((string) $request->query('to', ''));

        if (!preg_match('/^\d{4}\-\d{2}\-\d{2}$/', $from)) {
            $from = now($tz)->subDays(7)->toDateString();
        }
        if (!preg_match('/^\d{4}\-\d{2}\-\d{2}$/', $to)) {
            $to = now($tz)->toDateString();
        }

        try {
            $dIni = Carbon::parse($from, $tz)->startOfDay();
        } catch (\Throwable $e) {
            $from = now($tz)->subDays(7)->toDateString();
            $dIni = Carbon::parse($from, $tz)->startOfDay();
        }

        try {
            $dFim = Carbon::parse($to, $tz)->endOfDay();
        } catch (\Throwable $e) {
            $to   = now($tz)->toDateString();
            $dFim = Carbon::parse($to, $tz)->endOfDay();
        }

        if ($dIni->gt($dFim)) {
            [$dIni, $dFim] = [$dFim->copy()->startOfDay(), $dIni->copy()->endOfDay()];
            [$from, $to]   = [$to, $from];
        }

        if (!Schema::hasTable('refinanciamentos') || !Schema::hasTable('refinanciamento_comprovantes')) {
            return back()->withErrors(['Tabelas necessárias não existem (refinanciamentos/refinanciamento_comprovantes).']);
        }

        [$qb, $meta] = $this->baseRefiQuery();
        if (!$qb) {
            return back()->withErrors(['Falha ao montar consulta base.']);
        }

        $rcDateCol = 'created_at';
        foreach (['created_at', 'uploaded_at', 'anexado_em', 'data_anexacao'] as $c) {
            if (Schema::hasColumn('refinanciamento_comprovantes', $c)) {
                $rcDateCol = $c;
                break;
            }
        }

        $rcAgg = DB::table('refinanciamento_comprovantes as rc')
            ->select([
                'rc.refinanciamento_id',
                DB::raw("MAX(rc.{$rcDateCol}) as anexado_em"),
                DB::raw('COUNT(rc.id) as qtd_comprovantes'),
            ])
            ->whereBetween("rc.{$rcDateCol}", [$dIni, $dFim])
            ->groupBy('rc.refinanciamento_id');

        $qb->joinSub($rcAgg, 'rcw', function ($j) {
            $j->on('rcw.refinanciamento_id', '=', 'r.id');
        });

        $qb->addSelect(DB::raw('rcw.anexado_em as anexado_em'));
        $qb->addSelect(DB::raw('rcw.qtd_comprovantes as qtd_comprovantes'));

        $statusFiltro = strtolower(trim((string) $request->query('status', '')));
        if ($statusFiltro === 'pago' || $statusFiltro === 'pendente') {

            $paidSql = null;

            if (!empty($meta['hasCompTbl'])) {
                $kindCol = null;
                if (Schema::hasColumn('refinanciamento_comprovantes', 'kind')) $kindCol = 'kind';
                elseif (Schema::hasColumn('refinanciamento_comprovantes', 'tipo')) $kindCol = 'tipo';

                if ($kindCol) {
                    $paidSql = "
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
                } else {
                    $paidSql = "EXISTS (SELECT 1 FROM refinanciamento_comprovantes rc WHERE rc.refinanciamento_id = r.id)";
                }
            }

            if ($paidSql) {
                if ($statusFiltro === 'pago') $qb->whereRaw($paidSql);
                else $qb->whereRaw("NOT ({$paidSql})");
            } else {
                if ($statusFiltro === 'pago') $qb->whereRaw('0 = 1');
            }
        }

        $q = trim((string) $request->query('q', ''));
        if ($q !== '') {
            $qDoc = $this->normDoc($q);

            $qb->where(function ($w) use ($q, $qDoc, $meta) {
                if ($qDoc !== '') {
                    $w->orWhereRaw($this->cpfNormExpr('r.cpf_cnpj') . " LIKE ?", ["%{$qDoc}%"]);
                }

                $w->orWhere('r.nome_snapshot', 'like', "%{$q}%");

                if (!empty($meta['hasAgentes'])) {
                    $w->orWhere('ac.full_name', 'like', "%{$q}%");
                    if (!empty($meta['cadCol'])) {
                        $w->orWhere('acc.full_name', 'like', "%{$q}%");
                    }
                }
            });
        }

        $qb->orderByDesc('anexado_em')->orderByDesc('r.id');

        $rows = $qb->get();

        // garantir propriedade comprovantes para o PDF
        foreach ($rows as $row) {
            $row->comprovantes = collect();
        }

        $ids = collect($rows)->pluck('id')->filter()->values()->all();

        if (!empty($ids) && Schema::hasTable('refinanciamento_comprovantes')) {

            $compTbl = 'refinanciamento_comprovantes';

            $kindCol = Schema::hasColumn($compTbl, 'kind') ? 'kind'
                    : (Schema::hasColumn($compTbl, 'tipo') ? 'tipo' : null);

            $fileCol = null;
            foreach (['path','file_path','arquivo','filename','nome_arquivo','file','url'] as $c) {
                if (Schema::hasColumn($compTbl, $c)) { $fileCol = $c; break; }
            }

            $dateCol = $rcDateCol ?: 'created_at';

            $select = [
                'rc.id',
                'rc.refinanciamento_id',
                DB::raw("rc.{$dateCol} as anexado_em"),
            ];

            if ($kindCol) $select[] = DB::raw("LOWER(TRIM(COALESCE(rc.{$kindCol}, ''))) as kind");
            else          $select[] = DB::raw("'' as kind");

            if ($fileCol) $select[] = DB::raw("rc.{$fileCol} as arquivo");
            else          $select[] = DB::raw("'' as arquivo");

            foreach (['disk','mime','size','original_name','nome_original'] as $c) {
                if (Schema::hasColumn($compTbl, $c)) {
                    if ($c === 'nome_original' && !Schema::hasColumn($compTbl, 'original_name')) {
                        $select[] = DB::raw("rc.{$c} as original_name");
                    } else {
                        $select[] = "rc.{$c}";
                    }
                }
            }

            $comps = DB::table("{$compTbl} as rc")
                ->select($select)
                ->whereIn('rc.refinanciamento_id', $ids)
                ->whereBetween("rc.{$dateCol}", [$dIni, $dFim])
                ->orderByDesc("rc.{$dateCol}")
                ->get();

            $byRef = [];
            foreach ($comps as $c) {
                $rid = (int) $c->refinanciamento_id;
                if (!isset($byRef[$rid])) $byRef[$rid] = collect();
                $byRef[$rid]->push($c);
            }

            foreach ($rows as $row) {
                $rid = (int) $row->id;
                $row->comprovantes = $byRef[$rid] ?? collect();
            }
        }

        $title = "Refinanciamentos (comprovantes anexados de "
            . Carbon::parse($from, $tz)->format('d/m/Y')
            . " a "
            . Carbon::parse($to, $tz)->format('d/m/Y')
            . ")";

        $data = [
            'title' => $title,
            'tz'    => $tz,
            'from'  => $from,
            'to'    => $to,
            'dIni'  => $dIni,
            'dFim'  => $dFim,
            'rows'  => $rows,
        ];

        $download = (string) $request->query('download', '1');

        if ($download === '0') {
            return view('tesoureiro.refinanciamentos_pdf', $data);
        }

        try {
            $pdf = app('dompdf.wrapper');
            $pdf->loadView('tesoureiro.refinanciamentos_pdf', $data)->setPaper('a4', 'portrait');

            $filename = "refinanciamentos_anexados_{$from}_a_{$to}.pdf";
            return $pdf->download($filename);
        } catch (\Throwable $e) {
            return view('tesoureiro.refinanciamentos_pdf', $data)
                ->with('err', 'Não foi possível gerar PDF automaticamente. Exibindo HTML. Erro: ' . $e->getMessage());
        }
    }

    // dados bancarios 
    
    /**
     * Retorna os dados bancários (snapshot) de um refinanciamento em JSON.
     * Útil para abrir modal "Dados bancários" via AJAX.
     */
public function dadosBancarios(Request $request, \App\Models\Refinanciamento $refinanciamento)
{
    $rid = (string) \Illuminate\Support\Str::uuid();

    try {
        $row = $refinanciamento;

        // =====================================================
        // 1) Identificadores base: CPF/CNPJ, contrato, vínculos
        // =====================================================
        $doc = trim((string) (
            data_get($row, 'cpf_cnpj')
            ?: data_get($row, 'cpf_cnpj_snapshot')
            ?: data_get($row, 'cpf')
            ?: data_get($row, 'cnpj')
            ?: ''
        ));

        // sempre que possível, só dígitos
        $docDigits = preg_replace('/\D+/', '', $doc);
        if ($docDigits !== '') {
            $doc = $docDigits;
        }

        $contrato = trim((string) (
            data_get($row, 'contrato_codigo_contrato')
            ?: data_get($row, 'codigo_contrato')
            ?: data_get($row, 'codigo')
            ?: ''
        ));

        $agCadId  = data_get($row, 'agente_cadastro_id')
                 ?: data_get($row, 'cadastro_id');
        $appCadId = data_get($row, 'associadodois_cadastro_id');
        $payId    = data_get($row, 'tesouraria_pagamento_id')
                 ?: data_get($row, 'pagamento_id');

        // Começa sempre com o próprio refinanciamento
        $sources = [$row];

        // ================================
        // 2) TesourariaPagamento (pagamento)
        // ================================
        if (\Schema::hasTable('tesouraria_pagamentos')) {
            $pay = null;

            // por id direto
            if ($payId) {
                $pay = \App\Models\TesourariaPagamento::find($payId);
            }

            // por agente_cadastro_id
            if (!$pay && $agCadId) {
                $pay = \App\Models\TesourariaPagamento::where('agente_cadastro_id', $agCadId)
                    ->orderByDesc('id')
                    ->first();
            }

            // por associadodois_cadastro_id
            if (!$pay && $appCadId) {
                $pay = \App\Models\TesourariaPagamento::where('associadodois_cadastro_id', $appCadId)
                    ->orderByDesc('id')
                    ->first();
            }

            // por CPF/CNPJ
            if (!$pay && $doc !== '') {
                $pay = \App\Models\TesourariaPagamento::where('cpf_cnpj', $doc)
                    ->orderByDesc('id')
                    ->first();
            }

            // por código de contrato
            if (!$pay && $contrato !== '') {
                $pay = \App\Models\TesourariaPagamento::where('contrato_codigo_contrato', $contrato)
                    ->orderByDesc('id')
                    ->first();
            }

            if ($pay) {
                $sources[] = $pay;
            }
        }

        // ================================
        // 3) Cadastro WEB (agente_cadastros)
        // ================================
        if (\Schema::hasTable('agente_cadastros')) {
            $cadWeb = null;

            if ($agCadId) {
                $cadWeb = \App\Models\AgenteCadastro::find($agCadId);
            }

            if (!$cadWeb && $doc !== '') {
                $cadWeb = \App\Models\AgenteCadastro::where('cpf_cnpj', $doc)
                    ->orderByDesc('id')
                    ->first();
            }

            if (!$cadWeb && $contrato !== '') {
                $cadWeb = \App\Models\AgenteCadastro::where('contrato_codigo_contrato', $contrato)
                    ->orderByDesc('id')
                    ->first();
            }

            if ($cadWeb) {
                $sources[] = $cadWeb;
            }
        }

        // ================================
        // 4) Cadastro APP (associadodois_cadastros)
        // ================================
        if (\Schema::hasTable('associadodois_cadastros')) {
            $cadApp = null;

            if ($appCadId) {
                $cadApp = \App\Models\AssociadoDoisCadastro::find($appCadId);
            }

            if (!$cadApp && $doc !== '') {
                $cadApp = \App\Models\AssociadoDoisCadastro::where('cpf_cnpj', $doc)
                    ->orderByDesc('id')
                    ->first();
            }

            if (!$cadApp && $contrato !== '') {
                $cadApp = \App\Models\AssociadoDoisCadastro::where('contrato_codigo_contrato', $contrato)
                    ->orderByDesc('id')
                    ->first();
            }

            if ($cadApp) {
                $sources[] = $cadApp;
            }
        }

        // =====================================================
        // Helper: pega o primeiro campo não vazio em todas fontes
        // =====================================================
        $resolve = function (array $fields) use ($sources) {
            foreach ($sources as $src) {
                if (!$src) continue;
                foreach ($fields as $f) {
                    $v = data_get($src, $f);
                    if (is_string($v) || is_numeric($v)) {
                        $v = trim((string) $v);
                        if ($v !== '') {
                            return $v;
                        }
                    }
                }
            }
            return null;
        };

        // Nome
        $nome = $resolve([
            'nome_snapshot',
            'nome_resolvido',
            'nome',
            'cliente_nome',
            'full_name',
            'nome_associado',
        ]);

        // ✅ Matrícula (abaixo do nome no modal)
        $matricula = $resolve([
            'matricula_servidor_publico',   // agente_cadastros
            'matricula_snapshot',
            'matricula',
            'matricula_associado',
            'matricula_servidor',
        ]);

        // Documento (garante fallback se não veio do refi)
        if ($doc === '') {
            $doc = $resolve([
                'cpf_cnpj',
                'cpf_cnpj_snapshot',
                'cpf',
                'cnpj',
            ]) ?? '';
            if ($doc !== '') {
                $doc = preg_replace('/\D+/', '', $doc);
            }
        }

        // Banco / agência / conta / tipo
        $bankName = $resolve([
            'bank_name_snapshot',
            'bank_name',
            'bank_nome',
            'banco_nome',
        ]);

        $bankAgency = $resolve([
            'bank_agency_snapshot',
            'bank_agency',
            'bank_agencia',
            'agencia',
        ]);

        $bankAccount = $resolve([
            'bank_account_snapshot',
            'bank_account',
            'bank_conta',
            'conta',
        ]);

        $accType = $resolve([
            'account_type_snapshot',
            'account_type',
            'tipo_conta',
            'conta_tipo',
        ]);

        // Chave PIX
        $pixChave = $resolve([
            'pix_resolved',
            'pix_snapshot',
            'chave_pix',
            'pix_key',
            'pix',
            'bank_pix',
            'pix_chave',
            'key_pix',
            'pixcode',
        ]);

        if (!$bankName && !$bankAgency && !$bankAccount && !$pixChave) {
            \Log::info('[TesoureiroRefi.dadosBancarios] empty_data', [
                'rid'      => $rid,
                'ref_id'   => $refinanciamento->id,
                'cpf_cnpj' => $doc,
                'contrato' => $contrato,
            ]);
        }

        return response()->json([
            'ok'        => true,
            'id'        => $refinanciamento->id,
            'nome'      => $nome ?: null,
            'matricula' => $matricula ?: null,   // ✅ nova info
            'cpf_cnpj'  => $doc !== '' ? $doc : null,
            'banco'     => [
                'nome'    => $bankName ?: null,
                'agencia' => $bankAgency ?: null,
                'conta'   => $bankAccount ?: null,
                'tipo'    => $accType ?: null,
            ],
            'pix'       => $pixChave ?: null,
        ]);
    } catch (\Throwable $e) {
        \Log::warning('[TesoureiroRefinanciamento.dadosBancarios] FAIL', [
            'rid'  => $rid,
            'id'   => $refinanciamento->id ?? null,
            'err'  => $e->getMessage(),
            'line' => $e->getLine(),
        ]);

        return response()->json([
            'ok'      => false,
            'message' => 'Não foi possível carregar os dados bancários deste refinanciamento.',
        ], 500);
    }
}

}
