<?php

namespace App\Models;

use Carbon\Carbon;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;

class PagamentoMensalidade extends Model
{
    protected $table = 'pagamentos_mensalidades';

    protected $fillable = [
        'created_by_user_id','import_uuid','referencia_month',
        'status_code','matricula','orgao_pagto','nome_relatorio',
        'cpf_cnpj','agente_cadastro_id','valor','source_file_path',

        // campos manuais (retorno manual)
        'esperado_manual','recebido_manual','manual_status','manual_paid_at',
        'manual_forma_pagamento','manual_comprovante_path','manual_by_user_id',
    ];

    protected $casts = [
        'referencia_month' => 'date',
        'manual_paid_at'   => 'datetime',
        'esperado_manual'  => 'float',
        'recebido_manual'  => 'float',
        'valor'            => 'float',
    ];

    /** "Esperado" efetivo para UI/KPI */
    public function getEsperadoEfetivoAttribute(): float
    {
        // Se tiver override manual usa-o; senão, usa o valor do arquivo
        return (float) ($this->esperado_manual ?? $this->valor ?? 0);
    }

    /** "Recebido" efetivo para UI/KPI */
    public function getRecebidoEfetivoAttribute(): float
    {
        // Automático: status_code === '1' (Lançado e Efetivado) => recebido = valor; caso contrário 0.
        $auto = ((string) $this->status_code === '1') ? (float) ($this->valor ?? 0) : 0.0;

        // Override manual, se existir
        return (float) ($this->recebido_manual ?? $auto);
    }

    /**
     * Flag "esta OK/pago?" para essa mensalidade (regra única)
     */
    public function getIsOkAttribute(): bool
    {
        $manualStatus = strtolower(trim((string)($this->manual_status ?? '')));

        // cancelado nunca conta
        if ($manualStatus === 'cancelado') {
            return false;
        }

        // pago manual conta sempre
        if ($manualStatus === 'pago') {
            return true;
        }

        // regra por valor efetivo (esperado x recebido)
        $esperado = $this->esperado_efetivo;  // accessor acima
        $recebido = $this->recebido_efetivo;  // accessor acima

        if ($esperado > 0 && $recebido >= $esperado) {
            return true;
        }

        // fallback: alguns status do arquivo você ainda considera como ok
        if (in_array((string)$this->status_code, ['1','4'], true)) {
            return true;
        }

        return false;
    }

    /**
     * Mesmo critério acima, só que em SQL, para usar em COUNT/SUM.
     * $alias = alias da tabela (ex: 'pm').
     */
    public static function okSql(string $alias = 'pm'): string
    {
        $p = $alias ? $alias . '.' : '';

        // Esperado/Recebido efetivos em SQL (versão dos accessors)
        $esperadoExpr = "COALESCE({$p}esperado_manual, {$p}valor, 0)";
        $recebidoAuto = "CASE WHEN {$p}status_code = '1'
                              THEN COALESCE({$p}valor,0)
                              ELSE 0 END";
        $recebidoExpr = "COALESCE({$p}recebido_manual, $recebidoAuto, 0)";

        return "CASE
            WHEN LOWER(TRIM(COALESCE({$p}manual_status,''))) = 'cancelado' THEN 0
            WHEN LOWER(TRIM(COALESCE({$p}manual_status,''))) = 'pago'      THEN 1
            WHEN $esperadoExpr > 0 AND $recebidoExpr >= $esperadoExpr      THEN 1
            WHEN {$p}manual_paid_at IS NOT NULL                            THEN 1
            WHEN {$p}status_code IN ('1','4')                              THEN 1
            ELSE 0
        END";
    }

    // ===========================================
    // Relacionamentos
    // ===========================================

    public function cadastro()
    {
        return $this->belongsTo(\App\Models\AgenteCadastro::class, 'agente_cadastro_id');
    }

    public function criadoPor()
    {
        return $this->belongsTo(\App\Models\User::class, 'created_by_user_id');
    }

    /** quem fez a operação manual (upload/alteração) */
    public function manualBy()
    {
        return $this->belongsTo(\App\Models\User::class, 'manual_by_user_id');
    }

    // ===========================================
    // Lógica de "Detalhar" (que você já usava)
    // ===========================================

    public function retornoDetalhar(Request $r, int $n)
    {
        $trace = 'RETORNO/DETALHAR#' . now('UTC')->format('Ymd-His-v') . '-' . substr(bin2hex(random_bytes(2)), 0, 4);

        // === Contexto: se é a janela "Detalhar faltantes"
        $ctx   = strtolower((string)($r->input('modo') ?? $r->input('view') ?? $r->input('filter') ?? ''));
        $isFal = in_array($ctx, ['faltantes','faltante','fal','pendente','pendentes'], true);

        // filtro de mês (YYYY-MM). Se não vier, usa mês atual.
        $mesISO = preg_match('/^\d{4}-\d{2}$/', (string)$r->input('mes'))
            ? (string)$r->input('mes')
            : now()->format('Y-m');

        Log::info("[$trace] INICIO detalhar", [
            'n'      => $n,
            'mesISO' => $mesISO,
            'user'   => auth()->id(),
            'ctx'    => $ctx ?: '(default)',
        ]);

        // janela simples do mês (ajuste se usar regra 06→05)
        $ini   = Carbon::createFromFormat('Y-m-d', $mesISO.'-01')->startOfDay();
        $fimEx = (clone $ini)->addMonth()->startOfDay();

        // consulta base
        $q = PagamentoMensalidade::query()
            ->select([
                'id','nome_relatorio','cpf_cnpj','status_code','valor',
                'esperado_manual','recebido_manual','manual_status',
                'agente_cadastro_id','import_uuid','referencia_month',
            ])
            ->whereBetween(DB::raw("DATE(referencia_month)"), [$ini->toDateString(), $fimEx->toDateString()]);

        // Caso exista um marcador de "arquivo 1/2/3", aplique aqui:
        // $q->where('retorno_n', $n);

        $items = $q->orderBy('nome_relatorio')->get();

        $rows               = [];
        $totEsperadoArquivo = 0.0; // baseline do ARQUIVO
        $totRecebidoEfetivo = 0.0; // recebido efetivo (manual > auto > 0)
        $okCount            = 0;

        foreach ($items as $it) {
            // baseline vindo do ARQUIVO
            $valorArquivo = (float) ($it->valor ?? 0);

            // efetivos (prioridade manual)
            $esperadoEfetivo = (float) ($it->esperado_manual ?? $valorArquivo);
            $recebidoAuto    = in_array((string)$it->status_code, ['1','4'], true) ? $valorArquivo : 0.0;
            $recebidoEfetivo = (float) ($it->recebido_manual ?? $recebidoAuto);

            $ok = $recebidoEfetivo > 0.00001;

            // === ALIAS exibidos na UI ===
            // Para "Detalhar" (default): mostramos a visão do ARQUIVO
            // Para "Detalhar faltantes": mostramos o valor EFETIVO (prioriza manual)
            $aliasEsperado = $isFal ? $esperadoEfetivo : $valorArquivo;
            $aliasRecebido = $isFal ? $recebidoEfetivo : $recebidoAuto;

            $rows[] = [
                'id'                => $it->id,
                'source_id'         => $it->id,
                'nome'              => trim((string)$it->nome_relatorio),
                'cpf'               => $it->cpf_cnpj,
                'status_code'       => (string)$it->status_code,
                'status_label'      => $this->retornoStatusLabel((string)$it->status_code, (string)($it->manual_status ?? '')),

                // valores do arquivo (baseline; útil para tooltips, etc.)
                'valor'             => $valorArquivo,

                // overrides manuais (eco bruto)
                'esperado_manual'   => (float) ($it->esperado_manual ?? 0),
                'recebido_manual'   => (float) ($it->recebido_manual ?? 0),
                'manual_status'     => (string) ($it->manual_status ?? ''),

                // efetivos (p/ regras/kpis)
                'esperado_efetivo'  => $esperadoEfetivo,
                'recebido_efetivo'  => $recebidoEfetivo,

                // flags
                'ok'                => $ok,

                // === Campos que a view usa diretamente ===
                // (no "faltantes" passam a refletir o valor atualizado no banco)
                'esperado'          => $aliasEsperado,
                'recebido'          => $aliasRecebido,
            ];

            $totEsperadoArquivo += $valorArquivo;
            $totRecebidoEfetivo += $recebidoEfetivo;
            if ($ok) $okCount++;
        }

        $payload = [
            'totais' => [
                // Mantém a régua de progresso do card: baseline do ARQUIVO
                'esperado' => round($totEsperadoArquivo, 2),
                // E recebido efetivo (manual > auto > 0) para refletir ajustes/edições
                'recebido' => round($totRecebidoEfetivo, 2),
                'ok'       => $okCount,
                'total'    => count($rows),
            ],
            'rows' => $rows,
        ];

        // LOG detalhado de totais e linhas (se tiver esse helper)
        if (method_exists($this, 'logRetornoPayload')) {
            $this->logRetornoPayload($trace, $payload);
        }

        Log::info("[$trace] FIM detalhar", [
            'tot_ok'    => $payload['totais']['ok'],
            'tot_total' => $payload['totais']['total'],
            'tot_exp'   => $payload['totais']['esperado'],
            'tot_rec'   => $payload['totais']['recebido'],
            'ctx'       => $ctx ?: '(default)',
        ]);

        return response()->json($payload);
    }

    /**
     * Mapeia rótulo de status (arquivo x manual)
     */
    private function retornoStatusLabel(string $statusCode, string $manual = ''): string
    {
        if ($manual === 'pago')      return 'Concluído (manual)';
        if ($manual === 'cancelado') return 'Cancelado (manual)';

        return match ($statusCode) {
            '1'   => 'Lançado e Efetivado',
            '4'   => 'No arquivo',
            '0'   => 'Cancelado',
            '-'   => 'Não lançado (outros)',
            default => 'Pendente',
        };
    }
}
