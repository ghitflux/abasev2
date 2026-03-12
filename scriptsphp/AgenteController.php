<?php

namespace App\Http\Controllers;
use Carbon\Carbon;
use Illuminate\Http\Request;
use Illuminate\Support\Str;
use Illuminate\Support\Facades\Log;
use App\Models\AgenteCadastro;
use App\Models\AgenteDocIssue;
use App\Models\AgenteDocReupload;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use App\Models\AgenteCadastroAssumption;
use App\Models\TesourariaPagamento;
use App\Models\Refinanciamento;

class AgenteController extends Controller
{
    public function index()
    {
        return view('agente.dashboardagente');
    }

    /* ===================== Helpers ===================== */

    private function onlyDigits(?string $s): string
    {
        return preg_replace('/\D+/', '', (string) $s) ?? '';
    }

    private function brlToDecimal(?string $s): ?float
    {
        if ($s === null) return null;
        $s = trim($s);
        if ($s === '') return null;
        $s = str_replace(['R$', ' '], '', $s);
        $s = str_replace('.', '', $s);
        $s = str_replace(',', '.', $s);
        return is_numeric($s) ? (float) $s : null;
    }

    private function pctToDecimal(?string $s): ?float
    {
        if ($s === null) return null;
        $s = trim($s);
        $s = str_replace(['%',' '], '', $s);
        $s = str_replace('.', '', $s);
        $s = str_replace(',', '.', $s);
        if (!is_numeric($s)) return null;
        return round((float)$s, 2);
    }

    private function dateBrToIso(?string $s): ?string
    {
        if (!$s) return null;
        $s = trim($s);
        if (preg_match('~^(\d{2})/(\d{2})/(\d{4})$~', $s, $m)) return "{$m[3]}-{$m[2]}-{$m[1]}";
        if (preg_match('~^\d{4}-\d{2}-\d{2}$~', $s)) return $s;
        return null;
    }

    private function monthToDate(?string $s): ?string
    {
        if (!$s) return null;
        $s = trim($s);
        if (preg_match('~^\d{4}-\d{2}$~', $s)) return $s.'-01';
        return $this->dateBrToIso($s);
    }

    private function mapEstadoCivil(?string $val): ?string
    {
        $map = [
            'single'   => 'Solteiro(a)',
            'married'  => 'Casado(a)',
            'divorced' => 'Divorciado(a)',
            'widowed'  => 'Viúvo(a)',
        ];
        if (!$val) return null;
        $val = strtolower(trim($val));
        return $map[$val] ?? null;
    }

    /**
     * SIMULADOR — MARGEM = Líquido − (30% do Bruto)
     */
    private function calcularMargem(?float $valorBruto, ?float $liqCc, ?float $mensalidade = null, int $prazo = 3): array
    {
        $vb   = (float) ($valorBruto ?? 0);
        $liq  = (float) ($liqCc ?? 0);
        $mens = (float) ($mensalidade ?? 0);
        $pz   = max((int) $prazo, 0);

        $trintaBruto      = round($vb * 0.30, 2);
        $margem           = round($liq - $trintaBruto, 2);
        $valorAntecipacao = round($mens * $pz, 2);
        $doacaoFundo      = round($valorAntecipacao * 0.30, 2);

        return [
            'trinta_bruto'      => $trintaBruto,
            'margem'            => $margem,
            'valor_antecipacao' => $valorAntecipacao,
            'doacao_fundo'      => $doacaoFundo,
            'pode_prosseguir'   => ($margem > 0),
        ];
    }

    /**
     * Localiza um cadastro por CPF (opcionalmente ignorando um ID).
     */
    private function findCadastroByCPF(string $cpf, ?int $ignoreId = null)
    {
        $q = AgenteCadastro::select('id','full_name','agente_responsavel','created_at')
            ->where('doc_type','CPF')
            ->where('cpf_cnpj',$cpf);

        if ($ignoreId) $q->where('id','<>',$ignoreId);

        return $q->first();
    }

    /** Regras de upload padronizadas (50MB + pdf/jpg/jpeg/png/webp). */
    private function fileRules50MB(): array
    {
        return [
            'documents.*'        => 'nullable|file|max:51200|mimes:pdf,jpg,jpeg,png,webp',
            'cpf_frente'         => 'nullable|file|max:51200|mimes:jpg,jpeg,png,webp,pdf',
            'cpf_verso'          => 'nullable|file|max:51200|mimes:jpg,jpeg,png,webp,pdf',
            'comp_endereco'      => 'nullable|file|max:51200|mimes:jpg,jpeg,png,webp,pdf',
            'comp_renda'         => 'nullable|file|max:51200|mimes:jpg,jpeg,png,webp,pdf',
            'contracheque_atual' => 'nullable|file|max:51200|mimes:jpg,jpeg,png,webp,pdf',
            'termo_adesao'       => 'nullable|file|max:51200|mimes:jpg,jpeg,png,webp,pdf',
            'termo_antecipacao'  => 'nullable|file|max:51200|mimes:jpg,jpeg,png,webp,pdf',
        ];
    }

    /** Mensagens amigáveis para os uploads (aplicadas nos dois métodos). */
    private function fileMessages50MB(): array
    {
        return [
            'comp_renda.max'         => 'Simulação acima do limite (máx. 50MB).',
            'comp_renda.mimes'       => 'Simulação deve ser PDF/JPG/PNG/WebP.',
            'comp_renda.uploaded'    => 'Falha no upload (tamanho excede limites do servidor ou conexão interrompida).',

            'cpf_frente.max'         => 'Documento (frente) acima do limite (máx. 50MB).',
            'cpf_verso.max'          => 'Documento (verso) acima do limite (máx. 50MB).',
            'comp_endereco.max'      => 'Comprovante acima do limite (máx. 50MB).',
            'contracheque_atual.max' => 'Contracheque acima do limite (máx. 50MB).',
            'termo_adesao.max'       => 'Termo de Adesão acima do limite (máx. 50MB).',
            'termo_antecipacao.max'  => 'Termo de Antecipação acima do limite (máx. 50MB).',
        ];
    }

    /** Snapshot de diagnóstico dos uploads (mostra erros do PHP: INI_SIZE, FORM_SIZE, etc.). */
    private function logUploadSnapshot(Request $r, array $fields): void
    {
        try {
            $phpIniLimits = [
                'upload_max_filesize' => ini_get('upload_max_filesize'),
                'post_max_size'       => ini_get('post_max_size'),
                'max_file_uploads'    => ini_get('max_file_uploads'),
                'memory_limit'        => ini_get('memory_limit'),
                'content_length'      => $r->server('CONTENT_LENGTH'),
            ];
            $errName = static function ($code) {
                switch ((int)$code) {
                    case UPLOAD_ERR_OK:         return 'OK';
                    case UPLOAD_ERR_INI_SIZE:   return 'INI_SIZE';
                    case UPLOAD_ERR_FORM_SIZE:  return 'FORM_SIZE';
                    case UPLOAD_ERR_PARTIAL:    return 'PARTIAL';
                    case UPLOAD_ERR_NO_FILE:    return 'NO_FILE';
                    case UPLOAD_ERR_NO_TMP_DIR: return 'NO_TMP_DIR';
                    case UPLOAD_ERR_CANT_WRITE: return 'CANT_WRITE';
                    case UPLOAD_ERR_EXTENSION:  return 'EXTENSION';
                    default:                    return 'UNKNOWN';
                }
            };
            $inputs = [];
            foreach ($fields as $k) {
                $f   = $r->file($k);
                $raw = $_FILES[$k] ?? null;
                $inputs[$k] = [
                    'present_in_request'  => $r->hasFile($k),
                    'is_valid'            => $f ? $f->isValid() : null,
                    'client_name'         => $f ? $f->getClientOriginalName() : null,
                    'client_mime'         => $f ? $f->getClientMimeType() : null,
                    'size_bytes'          => $f ? $f->getSize() : ($raw['size'] ?? null),
                    'phpfiles_error'      => $raw['error'] ?? null,
                    'phpfiles_error_name' => isset($raw['error']) ? $errName($raw['error']) : null,
                ];
            }
            \Log::info('Uploads snapshot', ['php_ini' => $phpIniLimits, 'inputs' => $inputs]);
        } catch (\Throwable $e) {
            \Log::warning('Uploads snapshot failed', ['err' => $e->getMessage()]);
        }
    }

    /* ===================== Store ===================== */

public function store(Request $r)
{
    // === Diagnóstico de upload (ver limites do PHP/Nginx/Apache) ===
    $this->logUploadSnapshot($r, [
        'cpf_frente','cpf_verso','comp_endereco','comp_renda',
        'contracheque_atual','termo_adesao','termo_antecipacao','documents'
    ]);

    // Snapshot bruto do $_FILES (ajuda quando não chega UploadedFile)
    try {
        $raw = $_FILES ?? [];
        Log::info('AgenteController@store: $_FILES snapshot', [
            'keys'   => array_keys($raw),
            'detail' => array_map(function($x){
                if (!is_array($x)) return gettype($x);
                if (is_array($x['name'] ?? null)) {
                    return [
                        'name_count' => count($x['name']),
                        'errors'     => $x['error'] ?? null,
                    ];
                }
                return [
                    'name'  => $x['name']  ?? null,
                    'type'  => $x['type']  ?? null,
                    'size'  => $x['size']  ?? null,
                    'error' => $x['error'] ?? null,
                ];
            }, $raw),
        ]);
    } catch (\Throwable $e) {
        Log::warning('AgenteController@store: falha ao logar $_FILES', ['err' => $e->getMessage()]);
    }

    // ===== Validação com 50MB =====
    $rules = [
        // nome obrigatório e com conteúdo real (não só espaços)
        'fullName'                => ['required','string','min:3','regex:/\S/'],

        'docType'                  => 'nullable|in:CPF,CNPJ',
        'cpfCnpj'                  => 'required',
        'matriculaServidorPublico' => 'required|string',
        'email'                    => 'nullable|email',

        'anticipations'                           => 'nullable|array',
        'anticipations.*.numeroMensalidade'       => 'nullable|integer|min:1',
        'anticipations.*.valorAuxilio'            => 'nullable',
        'anticipations.*.dataEnvio'               => 'nullable',
        'anticipations.*.observacao'              => 'nullable',

        // Dados bancários (opcionais)
        'bank_name'    => 'nullable|string|max:100',
        'bank_agency'  => 'nullable|string|max:40',
        'bank_account' => 'nullable|string|max:40',
        'account_type' => 'nullable|in:corrente,poupanca',
        'pix_key'      => 'nullable|string|max:120',
    ] + $this->fileRules50MB();

    $messages = [
        'fullName.required' => 'Informe o nome completo.',
        'fullName.min'      => 'O nome precisa ter ao menos 3 caracteres.',
        'fullName.regex'    => 'O nome não pode ser composto apenas por espaços.',
    ] + $this->fileMessages50MB();

    $r->validate($rules, $messages);

    try {
        Log::info('AgenteController@store: arquivos recebidos (allFiles keys)', [
            'keys' => array_keys($r->allFiles())
        ]);
    } catch (\Throwable $e) {
        Log::warning('AgenteController@store: falha ao inspecionar allFiles', ['err' => $e->getMessage()]);
    }

    // Documento
    $docTypeIn = strtoupper((string)$r->input('docType', ''));
    $cpfCnpj   = $this->onlyDigits($r->input('cpfCnpj'));

    if (in_array($docTypeIn, ['CPF','CNPJ'])) {
        $docType = $docTypeIn;
    } else {
        $docType = strlen($cpfCnpj) === 14 ? 'CNPJ' : 'CPF';
    }

    if ($docType === 'CPF' && strlen($cpfCnpj) !== 11) {
        return back()->withErrors(['cpfCnpj' => 'CPF inválido (11 dígitos).'])->withInput();
    }
    if ($docType === 'CNPJ' && strlen($cpfCnpj) !== 14) {
        return back()->withErrors(['cpfCnpj' => 'CNPJ inválido (14 dígitos).'])->withInput();
    }

    // Bloqueio CPF duplicado
    if ($docType === 'CPF') {
        if ($existing = $this->findCadastroByCPF($cpfCnpj)) {
            return back()
                ->withErrors([
                    'cpfCnpj' => 'CPF já cadastrado para "'.$existing->full_name.
                                '" pelo agente "'.$existing->agente_responsavel.'".'
                ])
                ->withInput();
        }
    }

    $birthDate     = $this->dateBrToIso($r->input('birthDate'));
    $maritalStatus = $this->mapEstadoCivil($r->input('maritalStatus'));

    // ===================== Contrato (com Fallback SP) =====================
    $c = (array) $r->input('contrato', []);

    if (
        empty($c['dataAprovacao']) &&
        empty($c['mesAverbacao']) &&
        empty($c['dataEnvioPrimeira'])
    ) {
        $auto = $this->autoContratoDatesFromNowSP();
        $c['dataAprovacao']     = $auto['dataAprovacao'];
        $c['mesAverbacao']      = $auto['mesAverbacao'];
        $c['dataEnvioPrimeira'] = $auto['dataPrimeira'];
        $r->merge(['contrato' => $c]);

        Log::info('AgenteController@store: contrato datas auto-preenchidas (SP)', $auto);
    }

    $contrato_mensalidade         = $this->brlToDecimal($c['mensalidade'] ?? null);
    $contrato_data_aprovacao      = $this->dateBrToIso($c['dataAprovacao'] ?? null);
    $contrato_data_envio_primeira = $this->dateBrToIso($c['dataEnvioPrimeira'] ?? null);
    $contrato_mes_averbacao       = $this->monthToDate($c['mesAverbacao'] ?? null);
    $contrato_doacao_associado    = $this->brlToDecimal($c['doacaoAssociado'] ?? null);

    $prazoFixado               = 3;
    $contrato_codigo_contrato  = strtoupper('CTR-'.now()->format('YmdHis').'-'.\Illuminate\Support\Str::random(5));

    $mens = (float) ($contrato_mensalidade ?? 0);
    $contrato_valor_antecipacao = round($mens * $prazoFixado, 2);
    $contrato_margem_disponivel = round($contrato_valor_antecipacao * .7, 2);

    // Cálculo
    $calc = (array) $r->input('calc', []);
    $calc_valor_bruto             = $this->brlToDecimal($calc['valor_bruto'] ?? null);
    $calc_liquido_cc              = $this->brlToDecimal($calc['liquido_cc'] ?? null);

    if ($calc_valor_bruto !== null || $calc_liquido_cc !== null || $contrato_mensalidade !== null) {
        $this->calcularMargem($calc_valor_bruto, $calc_liquido_cc, $contrato_mensalidade, $prazoFixado);
    }

    // Agente / Auxílio
    $agente_nome         = trim((string)$r->input('agente.responsavel')) ?: optional($r->user())->name;
    $agente_responsavel  = $agente_nome;
    $agente_filial       = $agente_nome;

    $auxilio_data   = $contrato_data_aprovacao;

    // Antecipações
    $anticip = [];
    foreach ((array) $r->input('anticipations', []) as $row) {
        $anticip[] = [
            'numeroMensalidade' => isset($row['numeroMensalidade']) ? (int)$row['numeroMensalidade'] : null,
            'valorAuxilio'      => $this->brlToDecimal($row['valorAuxilio'] ?? null),
            'dataEnvio'         => $this->dateBrToIso($row['dataEnvio'] ?? null),
            'status'            => $row['status'] ?? null,
            'observacao'        => $row['observacao'] ?? null,
        ];
    }

    // Dados bancários
    $bank_name    = trim((string)$r->input('bank_name'));
    $bank_agency  = trim((string)$r->input('bank_agency'));
    $bank_account = trim((string)$r->input('bank_account'));
    $account_type = in_array($r->input('account_type'), ['corrente','poupanca']) ? $r->input('account_type') : null;
    $pix_key      = trim((string)$r->input('pix_key'));

    Log::info('AgenteController@store: dados bancários recebidos', [
        'bank_name'    => $bank_name,
        'bank_agency'  => $bank_agency,
        'bank_account' => $bank_account,
        'account_type' => $account_type,
        'pix_key'      => $pix_key ? '(informado)' : null,
    ]);

    if (!$bank_name && !$bank_agency && !$bank_account && !$account_type && !$pix_key) {
        Log::warning('AgenteController@store: seção de dados bancários veio vazia.');
    }

    // Payload
    $payload = [
        'doc_type'         => $docType,
        'cpf_cnpj'         => $cpfCnpj,
        'rg'               => $r->input('rg'),
        'orgao_expedidor'  => $r->input('orgaoExpedidor'),
        'full_name'        => $r->input('fullName'),
        'birth_date'       => $birthDate,
        'profession'       => $r->input('profession'),
        'marital_status'   => $maritalStatus,

        'cep'            => $r->input('cep'),
        'address'        => $r->input('address'),
        'address_number' => $r->input('addressNumber'),
        'complement'     => $r->input('complement'),
        'neighborhood'   => $r->input('neighborhood'),
        'city'           => $r->input('city'),
        'uf'             => $r->input('uf'),

        'cellphone'                  => $r->input('cellphone'),
        'orgao_publico'              => $r->input('orgaoPublico'),
        'situacao_servidor'          => $r->input('situacaoServidor'),
        'matricula_servidor_publico' => $r->input('matriculaServidorPublico'),
        'email'                      => $r->input('email'),

        // Dados bancários
        'bank_name'    => $bank_name,
        'bank_agency'  => $bank_agency,
        'bank_account' => $bank_account,
        'account_type' => $account_type,
        'pix_key'      => $pix_key,

        'contrato_mensalidade'         => $contrato_mensalidade,
        'contrato_prazo_meses'         => 3,
        'contrato_taxa_antecipacao'    => 30.00,
        'contrato_margem_disponivel'   => $contrato_margem_disponivel,
        'contrato_data_aprovacao'      => $contrato_data_aprovacao,
        'contrato_data_envio_primeira' => $contrato_data_envio_primeira,
        'contrato_valor_antecipacao'   => $contrato_valor_antecipacao,
        'contrato_status_contrato'     => 'Pendente',
        'contrato_mes_averbacao'       => $contrato_mes_averbacao,
        'contrato_codigo_contrato'     => $contrato_codigo_contrato,
        'contrato_doacao_associado'    => $contrato_doacao_associado,

        'calc_valor_bruto'             => $calc_valor_bruto,
        'calc_liquido_cc'              => $calc_liquido_cc,
        'calc_prazo_antecipacao'       => 3,
        'calc_mensalidade_associativa' => $contrato_mensalidade,

        'anticipations_json' => $anticip,
        'agente_responsavel' => $agente_responsavel,
        'agente_filial'      => $agente_filial,
        'observacoes'        => $r->input('observacoes'),

        'auxilio_taxa'       => 10.00,
        'auxilio_data_envio' => $auxilio_data,
        'auxilio_status'     => 'Pendente',
    ];

    // ✅ cria o cadastro
    $cadastro = AgenteCadastro::create($payload);

    // ✅ CORREÇÃO: cria/garante a linha na fila SEM analista (analista_id = NULL)
    try {
        $this->ensureAssumptionCreated($cadastro);
    } catch (\Throwable $e) {
        Log::error('AgenteController@store: ensureAssumptionCreated falhou', [
            'cadastro_id' => $cadastro->id,
            'err'         => $e->getMessage(),
            'trace'       => substr($e->getTraceAsString(), 0, 1500),
        ]);
    }

    // ===== Arquivos =====
    $docsMeta = [];
    $namedKeys = [
        'cpf_frente','cpf_verso','comp_endereco','comp_renda',
        'contracheque_atual','termo_adesao','termo_antecipacao',
    ];

    // Log de presença/validez por campo nomeado
    try {
        $dbg = [];
        foreach ($namedKeys as $k) {
            $f   = $r->file($k);
            $raw = $_FILES[$k] ?? null;
            $dbg[$k] = [
                'hasFile'     => $r->hasFile($k),
                'isValid'     => $f ? $f->isValid() : null,
                'name'        => $f ? $f->getClientOriginalName() : ($raw['name'] ?? null),
                'size'        => $f ? $f->getSize() : ($raw['size'] ?? null),
                'mime'        => $f ? $f->getClientMimeType() : ($raw['type'] ?? null),
                'php_error'   => $raw['error'] ?? null,
            ];
        }
        $dbg['documents'] = [
            'hasFile' => $r->hasFile('documents'),
            'class'   => is_object($r->file('documents')) ? get_class($r->file('documents')) : gettype($r->file('documents')),
        ];
        Log::info('AgenteController@store: presença de arquivos (named/documents)', $dbg);
    } catch (\Throwable $e) {
        Log::warning('AgenteController@store: falha ao logar presença de arquivos', ['err' => $e->getMessage()]);
    }

    $files = [];

    // (A) campos nomeados
    foreach ($namedKeys as $k) {
        $f = $r->file($k);
        if ($f instanceof \Illuminate\Http\UploadedFile && $f->isValid()) {
            $files[] = [$k, $f];
        } elseif ($f instanceof \Illuminate\Http\UploadedFile && !$f->isValid()) {
            Log::error('AgenteController@store: UploadedFile inválido (named)', [
                'field' => $k,
                'name'  => $f->getClientOriginalName(),
                'err'   => method_exists($f,'getErrorMessage') ? $f->getErrorMessage() : $f->getError(),
            ]);
        }
    }

    // (B) fluxo antigo: documents[]
    $filesInput = $r->file('documents');
    if ($filesInput instanceof \Illuminate\Http\UploadedFile) {
        if ($filesInput->isValid()) {
            $files[] = ['documents[]', $filesInput];
        } else {
            Log::error('AgenteController@store: UploadedFile inválido (documents[])', [
                'name' => $filesInput->getClientOriginalName(),
                'err'  => method_exists($filesInput,'getErrorMessage') ? $filesInput->getErrorMessage() : $filesInput->getError(),
            ]);
        }
    } else {
        foreach ($this->flattenFilesArray($filesInput) as $f) {
            if ($f instanceof \Illuminate\Http\UploadedFile && $f->isValid()) {
                $files[] = ['documents[]', $f];
            } elseif ($f instanceof \Illuminate\Http\UploadedFile && !$f->isValid()) {
                Log::error('AgenteController@store: UploadedFile inválido (documents[] array)', [
                    'name' => $f->getClientOriginalName(),
                    'err'  => method_exists($f,'getErrorMessage') ? $f->getErrorMessage() : $f->getError(),
                ]);
            }
        }
    }

    Log::info('AgenteController@store: total de arquivos a salvar', ['count' => count($files)]);

    try {
        if (!empty($files)) {
            $baseDir = public_path('uploads/associados/' . $cadastro->id);

            Log::info('AgenteController@store: baseDir diagnóstico', [
                'baseDir'        => $baseDir,
                'exists'         => is_dir($baseDir),
                'parent_writable'=> is_writable(dirname($baseDir)),
                'umask'          => sprintf('%04o', umask()),
            ]);

            if (!is_dir($baseDir)) {
                $mk = @mkdir($baseDir, 0775, true);
                Log::info('AgenteController@store: mkdir', [
                    'baseDir'    => $baseDir,
                    'ok'         => $mk,
                    'error_last' => error_get_last(),
                ]);
            }

            foreach ($files as [$field, $f]) {
                try {
                    $orig   = $f->getClientOriginalName();
                    $ext    = strtolower($f->getClientOriginalExtension() ?: 'bin');
                    $mime   = $f->getClientMimeType() ?: 'application/octet-stream';
                    $size   = $f->getSize();
                    $stored = now()->format('Ymd_His') . '_' . \Illuminate\Support\Str::random(6) . '.' . $ext;

                    Log::info('AgenteController@store: movendo arquivo', [
                        'field'        => $field,
                        'orig'         => $orig,
                        'stored'       => $stored,
                        'dest_full'    => $baseDir . DIRECTORY_SEPARATOR . $stored,
                        'size'         => $size,
                        'mime'         => $mime,
                        'baseWritable' => is_writable($baseDir),
                    ]);

                    $f->move($baseDir, $stored);

                    $fullPath = $baseDir . DIRECTORY_SEPARATOR . $stored;
                    $exists   = file_exists($fullPath);
                    if (!$size) $size = @filesize($fullPath) ?: 0;

                    Log::info('AgenteController@store: arquivo movido', [
                        'dest_exists' => $exists,
                        'dest_size'   => $size,
                        'dest_perm'   => $exists ? substr(sprintf('%o', fileperms($fullPath)), -4) : null,
                    ]);

                    $docsMeta[] = [
                        'original_name' => $orig,
                        'stored_name'   => $stored,
                        'mime'          => $mime,
                        'size_bytes'    => (int) $size,
                        'relative_path' => 'uploads/associados/' . $cadastro->id . '/' . $stored,
                        'uploaded_at'   => now()->toDateTimeString(),
                        'field'         => $field,
                    ];
                } catch (\Throwable $exFile) {
                    Log::error('AgenteController@store: erro ao mover arquivo individual', [
                        'field'      => $field,
                        'name'       => $f->getClientOriginalName(),
                        'err'        => $exFile->getMessage(),
                        'trace'      => substr($exFile->getTraceAsString(), 0, 1500),
                        'error_last' => error_get_last(),
                    ]);
                }
            }
        }

        if ($docsMeta) {
            $cadastro->documents_json = array_values($docsMeta);
            $cadastro->save();
            Log::info('AgenteController@store: documentos salvos', [
                'cadastro_id' => $cadastro->id,
                'qtd'         => count($docsMeta),
                'campos'      => array_values(array_unique(array_map(fn($m) => $m['field'] ?? '-', $docsMeta))),
            ]);
        } else {
            Log::warning('AgenteController@store: nenhum documento anexado ou todos falharam', [
                'cadastro_id' => $cadastro->id,
                'files_count' => isset($files) ? count($files) : 0
            ]);
        }
    } catch (\Throwable $e) {
        Log::error('AgenteController@store: erro ao salvar arquivos (bloco geral)', [
            'cadastro_id' => $cadastro->id,
            'err'         => $e->getMessage(),
            'trace'       => substr($e->getTraceAsString(), 0, 2000),
            'error_last'  => error_get_last(),
        ]);
        return back()
            ->withErrors(['documents' => 'Falha ao salvar os arquivos. Tente novamente.'])
            ->withInput();
    }

    return back()->with('ok', 'Cadastro salvo com sucesso!');
}




private function pickAnalistaId(): ?int
{
    if (!Schema::hasTable('users')) return null;

    // ⚠️ Ajuste aqui conforme sua coluna real de papel (role/perfil/tipo/etc).
    $q = DB::table('users as u');

    if (Schema::hasColumn('users', 'role')) {
        $q->where('u.role', 'analista');
    } elseif (Schema::hasColumn('users', 'perfil')) {
        $q->where('u.perfil', 'analista');
    } elseif (Schema::hasColumn('users', 'tipo')) {
        $q->where('u.tipo', 'analista');
    } elseif (Schema::hasColumn('users', 'is_analista')) {
        $q->where('u.is_analista', 1);
    } else {
        // Se você não tem uma coluna clara, não vou "chutar" qualquer usuário.
        return null;
    }

    // Menos carregado (conta quantos estão "assumidos" por analista)
    $load = DB::table('agente_cadastro_assumptions as a')
        ->select('a.analista_id', DB::raw('COUNT(*) as cnt'))
        ->where('a.status', 'assumido')
        ->groupBy('a.analista_id');

    $id = $q->leftJoinSub($load, 'l', function ($j) {
            $j->on('l.analista_id', '=', 'u.id');
        })
        ->orderByRaw('COALESCE(l.cnt,0) ASC')
        ->orderBy('u.id', 'ASC')
        ->value('u.id');

    return $id ? (int) $id : null;
}

private function ensureAssumptionCreated(\App\Models\AgenteCadastro $cadastro): void
{
    try {
        // 1) tenta criar direto (o UNIQUE garante 1 linha por cadastro)
        AgenteCadastroAssumption::create([
            'agente_cadastro_id' => $cadastro->id,
            'analista_id'        => null,
            'status'             => 'liberado',
            'liberado_em'        => now(),
            'assumido_em'        => null,
            'heartbeat_at'       => null,
        ]);

        Log::info('AgenteController@store: assumption criada (fila liberado)', [
            'cadastro_id' => $cadastro->id,
        ]);

        return;

    } catch (\Illuminate\Database\QueryException $e) {
        // 2) Se já existe (corrida/duplicado), só recupera e garante mínimos sem sobrescrever analista
        // MySQL duplicate key: 1062
        $isDuplicate = (int)($e->errorInfo[1] ?? 0) === 1062;
        if (!$isDuplicate) {
            throw $e; // erro real, não engole
        }
    }

    // já existia: garante mínimos
    $ass = AgenteCadastroAssumption::where('agente_cadastro_id', $cadastro->id)->first();

    if (!$ass) {
        // extremamente raro (mas por segurança)
        Log::warning('AgenteController@store: assumption duplicada mas não encontrada após catch', [
            'cadastro_id' => $cadastro->id,
        ]);
        return;
    }

    $dirty = false;

    if (!$ass->status) {
        $ass->status = 'liberado';
        $dirty = true;
    }

    if (!$ass->liberado_em) {
        $ass->liberado_em = now();
        $dirty = true;
    }

    if ($dirty) {
        $ass->save();
    }

    Log::info('AgenteController@store: assumption já existia (não sobrescrito)', [
        'cadastro_id'   => $cadastro->id,
        'assumption_id' => $ass->id,
        'status'        => $ass->status,
        'analista_id'   => $ass->analista_id,
    ]);
}





    private function flattenFilesArray($items): array
    {
        $out = [];
        if (!$items) return $out;
        $walker = function ($v) use (&$out, &$walker) {
            if ($v instanceof UploadedFile) $out[] = $v;
            elseif (is_array($v)) foreach ($v as $vv) $walker($vv);
        };
        $walker($items);
        return $out;
    }

    /* ===================== Pendências ===================== */

    public function pendenciasIndex(Request $r)
    {
        $q       = trim((string) $r->input('q', ''));
        $digits  = preg_replace('/\D+/', '', $q);
        $meName  = trim((string) optional($r->user())->name);

        if ($meName === '') {
            Log::warning('AgenteController@pendenciasIndex: usuário sem nome, retornando vazio', [
                'user_id' => optional($r->user())->id,
                'q'       => $q,
            ]);
            $issues = collect();
            return view('agente.pendencias', ['issues' => $issues, 'q' => $q]);
        }

        // Estados que caracterizam "já foi reenviado e está em análise/pendente" (com OU sem arquivos)
        $hideIfHasReuploadStatuses = ['received', 'submitted', 'pending', 'pending_review'];

        // Estados considerados "abertos" para exibir
        $openIssueStatuses = ['incomplete', 'reopened'];

        $rows = AgenteDocIssue::with([
                'cadastro',
                'reuploads' => function ($q) { $q->orderByDesc('uploaded_at'); },
            ])
            // Mostra apenas pendências abertas (compatível com legados em que status pode ser null)
            ->where(function ($w) use ($openIssueStatuses) {
                $w->whereIn('status', $openIssueStatuses)
                  ->orWhereNull('status');
            })

            // Esconde assim que houver QUALQUER reenvio pendente/encaminhado (com ou sem arquivo)
            ->whereDoesntHave('reuploads', function ($q2) use ($hideIfHasReuploadStatuses) {
                $q2->whereIn('status', $hideIfHasReuploadStatuses);
            })

            // Restringe ao agente logado (responsável ou filial)
            ->whereHas('cadastro', function ($c) use ($meName) {
                $c->where(function ($w) use ($meName) {
                    $w->where('agente_responsavel', $meName)
                      ->orWhere('agente_filial', $meName);
                });
            })

            // Busca rápida por contrato, CPF ou nome
            ->when($q !== '', function ($w) use ($q, $digits) {
                $w->where(function ($qq) use ($q, $digits) {
                    $qq->where('contrato_codigo_contrato', 'like', "%{$q}%")
                       ->orWhere('cpf_cnpj', 'like', "%{$digits}%")
                       ->orWhereHas('cadastro', function ($c) use ($q) {
                           $c->where('full_name', 'like', "%{$q}%");
                       });
                });
            })
            ->orderByDesc('id')
            ->get();

        // Evita duplicatas se houver mais de uma issue para o mesmo cadastro/contrato/CPF
        $issues = $rows->unique(function ($i) {
            $contrato = (string) ($i->contrato_codigo_contrato ?? '');
            $cadId    = (string) ($i->agente_cadastro_id ?? '');
            $cpf      = (string) ($i->cpf_cnpj ?? '');
            return ($contrato ?: 'NO-CTR') . '|' . ($cadId ?: 'NO-CAD') . '|' . ($cpf ?: 'NO-CPF');
        })->values();

        Log::info('AgenteController@pendenciasIndex: pendências carregadas', [
            'user_id'           => optional($r->user())->id,
            'agente_nome'       => $meName,
            'filtro_q'          => $q,
            'rows_total'        => $rows->count(),
            'issues_unicas'     => $issues->count(),
            'issues_ids'        => $issues->pluck('id')->all(),
            'tem_reuploads_map' => $issues->map(fn($i) => [
                'issue_id'      => $i->id,
                'reuploads_cnt' => optional($i->reuploads)->count(),
            ])->all(),
        ]);

        return view('agente.pendencias', ['issues' => $issues, 'q' => $q]);
    }




    public function pendenciasUpload(Request $request, AgenteDocIssue $issue)
    {
        Log::info('AgenteController@pendenciasUpload: início', [
            'issue_id'       => $issue->id,
            'agente_cadastro_id' => $issue->agente_cadastro_id,
            'contrato_codigo_contrato' => $issue->contrato_codigo_contrato,
            'cpf_cnpj'       => $issue->cpf_cnpj,
            'user_id'        => optional($request->user())->id,
            'user_name'      => optional($request->user())->name,
            'ip'             => $request->ip(),
            'all_files_keys' => array_keys($request->allFiles()),
        ]);

        $meName = trim((string) optional($request->user())->name);

        $belongsToMe = $issue->cadastro
            && ($issue->cadastro->agente_responsavel === $meName
                || $issue->cadastro->agente_filial === $meName);

        if (!$belongsToMe) {
            Log::warning('AgenteController@pendenciasUpload: tentativa não autorizada', [
                'issue_id'   => $issue->id,
                'me_name'    => $meName,
                'resp'       => optional($issue->cadastro)->agente_responsavel,
                'filial'     => optional($issue->cadastro)->agente_filial,
                'user_id'    => optional($request->user())->id,
            ]);
            abort(403, 'Você não tem permissão para enviar documentos para esta pendência.');
        }

        $request->validate([
            'files'   => 'required|array|min:1',
            'files.*' => 'file|max:51200|mimes:pdf,jpg,jpeg,png,webp',
        ], [
            'files.required' => 'Selecione pelo menos um documento.',
        ]);

        $filesReq = $request->file('files', []);
        Log::info('AgenteController@pendenciasUpload: arquivos para processar', [
            'issue_id'   => $issue->id,
            'count'      => is_array($filesReq) ? count($filesReq) : 0,
            'file_names' => array_map(fn($f) => $f instanceof UploadedFile ? $f->getClientOriginalName() : '—', $filesReq),
        ]);

        $userId = optional($request->user())->id;
        $dir = 'agent-reuploads/'.$issue->id;

        $created = [];
        $failed  = [];

        foreach ($filesReq as $idx => $file) {
            if (!($file instanceof UploadedFile)) {
                Log::warning('AgenteController@pendenciasUpload: item não é UploadedFile', [
                    'issue_id' => $issue->id,
                    'index'    => $idx,
                    'type'     => is_object($file) ? get_class($file) : gettype($file),
                ]);
                continue;
            }

            try {
                $ext        = strtolower($file->getClientOriginalExtension() ?: 'bin');
                $storedName = now()->format('Ymd_His').'-'.Str::random(8).'.'.$ext;

                $path       = $file->storeAs($dir, $storedName, 'public');
                $relative   = 'storage/'.$path;

                $mime       = $file->getClientMimeType() ?: $file->getMimeType();
                $size       = $file->getSize();

                Log::info('AgenteController@pendenciasUpload: arquivo salvo em disk public', [
                    'issue_id'        => $issue->id,
                    'index'           => $idx,
                    'original_name'   => $file->getClientOriginalName(),
                    'stored_name'     => $storedName,
                    'disk_path'       => $path,
                    'relative_url'    => $relative,
                    'exists_public'   => \Storage::disk('public')->exists($path),
                    'mime'            => $mime,
                    'size_bytes'      => $size,
                ]);

                $reup = AgenteDocReupload::create([
                    'agente_doc_issue_id'      => $issue->id,
                    'agente_cadastro_id'       => $issue->agente_cadastro_id,
                    'uploaded_by_user_id'      => $userId,
                    'cpf_cnpj'                 => $issue->cpf_cnpj,
                    'contrato_codigo_contrato' => $issue->contrato_codigo_contrato,
                    'file_original_name'       => $file->getClientOriginalName(),
                    'file_stored_name'         => $storedName,
                    'file_relative_path'       => $relative,
                    'file_mime'                => $mime,
                    'file_size_bytes'          => $size,
                    'status'                   => 'received',
                    'uploaded_at'              => now(),
                    'notes'                    => 'Reenvio via uploader (pendências).',
                    'extras'                   => null,
                ]);

                $created[] = $reup->id;

            } catch (\Throwable $e) {
                $failed[] = [
                    'index' => $idx,
                    'name'  => $file->getClientOriginalName(),
                    'err'   => $e->getMessage(),
                ];
                Log::error('AgenteController@pendenciasUpload: falha ao processar arquivo', [
                    'issue_id'      => $issue->id,
                    'index'         => $idx,
                    'original_name' => $file->getClientOriginalName(),
                    'error'         => $e->getMessage(),
                    'trace'         => substr($e->getTraceAsString(), 0, 2000),
                ]);
            }
        }

        // Anota na Issue que houve reenvio
        if (count($created) > 0) {
            $extraMsg = 'Documentação reenviada pelo agente em '.now()->format('d/m/Y H:i').'. — Aguardando validação do analista.';
            try {
                $issue->mensagem = trim(($issue->mensagem ? ($issue->mensagem."\n\n") : '').$extraMsg);
                $issue->updated_at = now();
                $issue->save();
            } catch (\Throwable $e) {
                Log::warning('pendenciasUpload: falha ao adicionar nota de reenvio na Issue', ['issue_id' => $issue->id, 'err' => $e->getMessage()]);
            }
        }

        Log::info('AgenteController@pendenciasUpload: resumo do reenvio', [
            'issue_id'     => $issue->id,
            'cadastro_id'  => $issue->agente_cadastro_id,
            'user_id'      => $userId,
            'created_ids'  => $created,
            'failed_count' => count($failed),
            'failed_list'  => $failed,
        ]);

        return back()->with('ok', 'Documento(s) reenviado(s) ao analista com sucesso. Aguardando validação.');
    }

    /* ===================== Contratos (lista) ===================== */

public function contratos()
{
    $uid    = auth()->id();
    $meName = trim((string) (auth()->user()->name ?? ''));

    $tbl = 'agente_cadastros';

    // =========================
    // NOVO: percentual vigente do agente (agente_margens)
    // =========================
    $percVigente = null;

    if (\Schema::hasTable('agente_margens')) {
        $percVigente = \DB::table('agente_margens')
            ->where('agente_user_id', $uid)
            ->where(function($w){
                $w->whereNull('vigente_ate')
                  ->orWhere('vigente_ate', '>', now());
            })
            ->where('vigente_desde', '<=', now())
            ->orderByDesc('vigente_desde')
            ->value('percentual');
    }

    // ✅ aqui NÃO tem fallback 10.00
    $percVigente = (is_numeric($percVigente)) ? (float)$percVigente : null;

    \Log::info('[AGENTE][contratos] margem_vigente', [
        'user_id'     => $uid,
        'perc'        => $percVigente,
        'hasMargemDb' => is_numeric($percVigente) ? 1 : 0,
    ]);

    // =========================
    // Picks (colunas dinâmicas)
    // =========================
    $pick = function(array $cands) use ($tbl) {
        foreach ($cands as $c) if (\Schema::hasColumn($tbl, $c)) return $c;
        return null;
    };

    $COL_FULLNAME = $pick(['full_name','fullName','nome_razao_social','nome']);
    $COL_CPF      = $pick(['cpf_cnpj','cpfCnpj','documento','cpf','cnpj']);
    $COL_STATUS   = $pick(['contrato_status_contrato','status_contrato','statusContrato']);
    $COL_ORGAO    = $pick(['orgao_publico','orgaoPublico']);
    $COL_MATRIC   = $pick(['matricula_servidor_publico','matriculaServidorPublico','matricula']);
    $COL_MENSAL   = $pick(['contrato_mensalidade','valor_mensalidade','mensalidade']);
    $COL_DATA_APR = $pick(['contrato_data_aprovacao','data_aprovacao','dataAprovacao']);
    $COL_DATA_1A  = $pick(['contrato_data_envio_primeira','data_envio_primeira','dataEnvioPrimeira']);
    $COL_MARGEM   = $pick(['contrato_margem_disponivel','margem_disponivel','margemDisponivel','contrato_margem']);

    // (não usamos mais a % do cadastro como base do cálculo na view)
    // mas manteremos no select como "auxilio_taxa" por compatibilidade, se existir:
    $COL_AUX_TAXA = $pick(['auxilio_taxa','auxilioTaxa']);

    // telefone/celular
    $COL_PHONE    = $pick(['cellphone','celular','telefone','phone','fone','whatsapp']);

    // =========================
    // PAGAMENTOS (mensalidades)
    // =========================
    $PM_TBL = 'pagamentos_mensalidades';
    $pmHasTable = \Schema::hasTable($PM_TBL);

    $pmPick = function(array $cands) use ($PM_TBL, $pmHasTable) {
        if (!$pmHasTable) return null;
        foreach ($cands as $c) if (\Schema::hasColumn($PM_TBL, $c)) return $c;
        return null;
    };

    $pmAgenteIdCol = $pmPick(['agente_cadastro_id','agenteCadastroId','cadastro_id','cadastroId','contrato_id','contratoId']);
    $pmCpfCol      = $pmPick(['cpf_cnpj','cpfCnpj','documento','cpf','cnpj']);
    $pmStatusCol   = $pmPick(['status_code','status','statusCode','codigo_status','code']);

    $pmManualStatusCol   = $pmPick(['manual_status','status_manual','manualStatus','statusManual']);
    $pmManualPaidAtCol   = $pmPick(['manual_paid_at','paid_at_manual','manualPaidAt','manualPaid']);
    $pmRecebidoManualCol = $pmPick(['recebido_manual','valor_recebido_manual','recebidoManual','manual_amount','manualAmount']);
    $pmManualCompCol     = $pmPick(['manual_comprovante_path','comprovante_manual_path','manualComprovantePath','comprovante_manual','comprovanteManual']);
    $pmManualByCol       = $pmPick(['manual_by_user_id','manualByUserId','manual_by','approved_by_user_id']);
    $pmRefCol            = $pmPick(['referencia_month','referencia','mes_referencia','competencia','reference_month']);

    $sqlCpfNorm = function(string $expr) {
        return "REPLACE(REPLACE(REPLACE(REPLACE(TRIM($expr),'.',''),'-',''),'/',''),' ','')";
    };

    $refKeyExpr = $pmRefCol
        ? "COALESCE(DATE_FORMAT(p.$pmRefCol,'%Y-%m'), LEFT(CAST(p.$pmRefCol AS CHAR), 7), CAST(p.id AS CHAR))"
        : "CAST(p.id AS CHAR)";

    $autoPaidExpr = "0";
    if ($pmStatusCol) {
        $autoPaidExpr = "UPPER(TRIM(CAST(p.$pmStatusCol AS CHAR))) IN ('1','4')";
    }

    $manualEvidenceParts = [];
    if ($pmManualStatusCol) {
        $manualEvidenceParts[] =
            "LOWER(TRIM(CAST(p.$pmManualStatusCol AS CHAR))) IN (" .
            "'pago','paid','ok','quitado','concluido','concluído','concluido.','concluído.','efetivado','confirmado','sim','true','1'" .
            ")";
    }
    if ($pmManualPaidAtCol)   $manualEvidenceParts[] = "p.$pmManualPaidAtCol IS NOT NULL";
    if ($pmRecebidoManualCol) $manualEvidenceParts[] = "COALESCE(p.$pmRecebidoManualCol,0) > 0";
    if ($pmManualCompCol)     $manualEvidenceParts[] = "(p.$pmManualCompCol IS NOT NULL AND TRIM(p.$pmManualCompCol) <> '')";

    $manualEvidenceExpr = $manualEvidenceParts ? '(' . implode(' OR ', $manualEvidenceParts) . ')' : '0';

    $manualAdminExpr = $pmManualByCol ? "COALESCE(p.$pmManualByCol,0) > 0" : "1";

    $manualNotCanceledExpr = $pmManualStatusCol
        ? "LOWER(TRIM(CAST(p.$pmManualStatusCol AS CHAR))) NOT IN ('cancelado','cancelada','canceled','cancelled','estornado','anulado')"
        : "1";

    $manualPaidExpr  = "($manualAdminExpr AND $manualNotCanceledExpr AND $manualEvidenceExpr)";
    $isEfetivadoExpr = "($autoPaidExpr OR $manualPaidExpr)";

    $pAggById = ($pmHasTable && $pmAgenteIdCol)
        ? \DB::table($PM_TBL.' as p')
            ->select(
                "p.$pmAgenteIdCol as agente_cadastro_id",
                \DB::raw("COUNT(DISTINCT $refKeyExpr) as pagamentos_total"),
                \DB::raw("COUNT(DISTINCT CASE WHEN $isEfetivadoExpr THEN $refKeyExpr END) as pagamentos_efetivados"),
                \DB::raw("COUNT(DISTINCT CASE WHEN $autoPaidExpr THEN $refKeyExpr END) as pagamentos_auto_efetivados"),
                \DB::raw("COUNT(DISTINCT CASE WHEN (NOT($autoPaidExpr) AND $manualPaidExpr) THEN $refKeyExpr END) as pagamentos_manual_efetivados")
            )
            ->whereNotNull("p.$pmAgenteIdCol")
            ->groupBy("p.$pmAgenteIdCol")
        : null;

    $pAggByCpf = null;
    if ($pmHasTable && $pmCpfCol) {
        $cpfNormP = $sqlCpfNorm("p.$pmCpfCol");

        $qCpf = \DB::table($PM_TBL.' as p')
            ->select(
                \DB::raw("$cpfNormP as cpf_norm"),
                \DB::raw("COUNT(DISTINCT $refKeyExpr) as pagamentos_total"),
                \DB::raw("COUNT(DISTINCT CASE WHEN $isEfetivadoExpr THEN $refKeyExpr END) as pagamentos_efetivados"),
                \DB::raw("COUNT(DISTINCT CASE WHEN $autoPaidExpr THEN $refKeyExpr END) as pagamentos_auto_efetivados"),
                \DB::raw("COUNT(DISTINCT CASE WHEN (NOT($autoPaidExpr) AND $manualPaidExpr) THEN $refKeyExpr END) as pagamentos_manual_efetivados")
            )
            ->whereNotNull("p.$pmCpfCol");

        if ($pmAgenteIdCol) {
            $qCpf->where(function($w) use ($pmAgenteIdCol){
                $w->whereNull("p.$pmAgenteIdCol")->orWhere("p.$pmAgenteIdCol", 0);
            });
        }

        $qCpf->groupBy(\DB::raw("cpf_norm"));
        $pAggByCpf = $qCpf;
    }

    // =========================
    // BLOCO: CPF já refinanciado
    // =========================
    $blockUnion = null;
    $badStatus = ['failed','fail','reverted','revertido','cancelado','cancelada','canceled','cancelled','recusado','rejeitado'];

    $cpfNormExpr = function(string $expr) {
        return "REPLACE(REPLACE(REPLACE(REPLACE(TRIM($expr),'.',''),'-',''),'/',''),' ','')";
    };

    if (\Schema::hasTable('refinanciamentos')) {
        $refTable     = 'refinanciamentos';
        $refCpfCol    = \Schema::hasColumn($refTable, 'cpf_cnpj') ? 'cpf_cnpj' : (\Schema::hasColumn($refTable, 'cpf') ? 'cpf' : null);
        $refStatusCol = \Schema::hasColumn($refTable, 'status') ? 'status' : null;

        if ($refCpfCol) {
            $refCpfNorm = $cpfNormExpr("r.$refCpfCol");

            $qRef = \DB::table("$refTable as r")
                ->selectRaw("$refCpfNorm as cpf_norm")
                ->whereRaw("$refCpfNorm <> ''");

            if ($refStatusCol) {
                $expr = "LOWER(TRIM(COALESCE(r.$refStatusCol,'')))";
                $ph   = implode(',', array_fill(0, count($badStatus), '?'));
                $qRef->whereRaw("$expr NOT IN ($ph)", $badStatus);
            }

            $blockUnion = $qRef;
        }
    }

    if (\Schema::hasTable('retorno_refinanciamentos')) {
        $rt       = 'retorno_refinanciamentos';
        $rtCpfCol = \Schema::hasColumn($rt, 'cpf_cnpj') ? 'cpf_cnpj' : (\Schema::hasColumn($rt, 'cpf') ? 'cpf' : null);

        if ($rtCpfCol) {
            $rtCpfNorm = $cpfNormExpr("rr.$rtCpfCol");

            $qRt = \DB::table("$rt as rr")
                ->selectRaw("$rtCpfNorm as cpf_norm")
                ->whereRaw("$rtCpfNorm <> ''");

            $blockUnion = $blockUnion ? $blockUnion->unionAll($qRt) : $qRt;
        }
    }

    $blockSub = null;
    if ($blockUnion) {
        $blockSub = \DB::query()
            ->fromSub($blockUnion, 'bx')
            ->selectRaw("cpf_norm")
            ->whereRaw("cpf_norm <> ''")
            ->groupBy('cpf_norm');
    }

    // =========================
    // Query base contratos
    // =========================
    $q = \DB::table('agente_cadastros as c');

    if ($pAggById) {
        $q->leftJoinSub($pAggById, 'pp_id', function($j){
            $j->on('pp_id.agente_cadastro_id','=','c.id');
        });
    }

    $cpfNormC = null;
    if ($COL_CPF) $cpfNormC = $sqlCpfNorm("c.$COL_CPF");

    if ($pAggByCpf && $COL_CPF && $cpfNormC) {
        $q->leftJoinSub($pAggByCpf, 'pp_cpf', function($j) use ($cpfNormC){
            $j->on(\DB::raw($cpfNormC), '=', 'pp_cpf.cpf_norm');
        });
    }

    if ($blockSub && $cpfNormC) {
        $q->leftJoinSub($blockSub, 'refi_blk', function($j) use ($cpfNormC){
            $j->on(\DB::raw($cpfNormC), '=', 'refi_blk.cpf_norm');
        });
    }

    // =========================
    // TESOURARIA (apenas exibição)
    // =========================
    $TES_TBL = 'tesouraria_pagamentos';
    if (\Schema::hasTable($TES_TBL)) {
        $tLast = \DB::table($TES_TBL.' as tt')
            ->select(\DB::raw('MAX(tt.id) as id'), 'tt.agente_cadastro_id')
            ->groupBy('tt.agente_cadastro_id');

        $q->leftJoinSub($tLast, 't_last', function($j){
            $j->on('t_last.agente_cadastro_id','=','c.id');
        });
        $q->leftJoin($TES_TBL.' as t', 't.id', '=', 't_last.id');

        $q->addSelect(
            \DB::raw('t.status as tes_status'),
            \DB::raw('t.paid_at as tes_paid_at'),
            \DB::raw('t.comprovante_path as tes_comprovante_path')
        );
    } else {
        $q->addSelect(
            \DB::raw('NULL as tes_status'),
            \DB::raw('NULL as tes_paid_at'),
            \DB::raw('NULL as tes_comprovante_path')
        );
    }

    // =========================
    // Filtro de dono
    // =========================
    if (\Schema::hasColumn($tbl, 'agente_user_id')) {
        $q->where('c.agente_user_id', $uid);
    } elseif (\Schema::hasColumn($tbl, 'user_id')) {
        $q->where('c.user_id', $uid);
    } elseif (\Schema::hasColumn($tbl, 'created_by_user_id')) {
        $q->where('c.created_by_user_id', $uid);
    } elseif (\Schema::hasColumn($tbl, 'agente_responsavel') || \Schema::hasColumn($tbl, 'agente_filial')) {
        $q->where(function($w) use ($tbl, $meName) {
            if (\Schema::hasColumn($tbl, 'agente_responsavel')) $w->orWhere('c.agente_responsavel', $meName);
            if (\Schema::hasColumn($tbl, 'agente_filial'))      $w->orWhere('c.agente_filial', $meName);
        });
    }

    // =========================
    // Campos principais
    // =========================
    $q->addSelect('c.id');
    $q->when($COL_FULLNAME, fn($qq) => $qq->addSelect(\DB::raw("c.$COL_FULLNAME as full_name")), fn($qq) => $qq->addSelect(\DB::raw('NULL as full_name')));
    $q->when($COL_CPF,      fn($qq) => $qq->addSelect(\DB::raw("c.$COL_CPF as cpf_cnpj")), fn($qq) => $qq->addSelect(\DB::raw('NULL as cpf_cnpj')));
    $q->when($COL_PHONE,    fn($qq) => $qq->addSelect(\DB::raw("c.$COL_PHONE as cellphone")), fn($qq) => $qq->addSelect(\DB::raw('NULL as cellphone')));
    $q->when($COL_STATUS,   fn($qq) => $qq->addSelect(\DB::raw("c.$COL_STATUS as status_contrato")), fn($qq) => $qq->addSelect(\DB::raw('NULL as status_contrato')));
    $q->when($COL_ORGAO,    fn($qq) => $qq->addSelect(\DB::raw("c.$COL_ORGAO as orgao_publico")), fn($qq) => $qq->addSelect(\DB::raw('NULL as orgao_publico')));
    $q->when($COL_MATRIC,   fn($qq) => $qq->addSelect(\DB::raw("c.$COL_MATRIC as matricula_servidor_publico")), fn($qq) => $qq->addSelect(\DB::raw('NULL as matricula_servidor_publico')));
    $q->when($COL_MENSAL,   fn($qq) => $qq->addSelect(\DB::raw("c.$COL_MENSAL as mensalidade")), fn($qq) => $qq->addSelect(\DB::raw('NULL as mensalidade')));
    $q->when($COL_DATA_APR, fn($qq) => $qq->addSelect(\DB::raw("c.$COL_DATA_APR as data_aprovacao")), fn($qq) => $qq->addSelect(\DB::raw('NULL as data_aprovacao')));
    $q->when($COL_DATA_1A,  fn($qq) => $qq->addSelect(\DB::raw("c.$COL_DATA_1A as data_envio_primeira")), fn($qq) => $qq->addSelect(\DB::raw('NULL as data_envio_primeira')));
    $q->when($COL_MARGEM,   fn($qq) => $qq->addSelect(\DB::raw("c.$COL_MARGEM as margem_disponivel")), fn($qq) => $qq->addSelect(\DB::raw('NULL as margem_disponivel')));

    // compat (se existir no cadastro)
    $q->when($COL_AUX_TAXA, fn($qq) => $qq->addSelect(\DB::raw("c.$COL_AUX_TAXA as auxilio_taxa")), fn($qq) => $qq->addSelect(\DB::raw('NULL as auxilio_taxa')));

    if ($blockSub && $cpfNormC) {
        $q->addSelect(\DB::raw("CASE WHEN refi_blk.cpf_norm IS NULL THEN 0 ELSE 1 END as cpf_refinanciado"));
    } else {
        $q->addSelect(\DB::raw("0 as cpf_refinanciado"));
    }

    $q->addSelect(\DB::raw("(COALESCE(pp_id.pagamentos_total,0) + COALESCE(pp_cpf.pagamentos_total,0)) as pagamentos_total"));
    $q->addSelect(\DB::raw("(COALESCE(pp_id.pagamentos_efetivados,0) + COALESCE(pp_cpf.pagamentos_efetivados,0)) as pagamentos_efetivados"));
    $q->addSelect(\DB::raw("(COALESCE(pp_id.pagamentos_auto_efetivados,0) + COALESCE(pp_cpf.pagamentos_auto_efetivados,0)) as pagamentos_auto_efetivados"));
    $q->addSelect(\DB::raw("(COALESCE(pp_id.pagamentos_manual_efetivados,0) + COALESCE(pp_cpf.pagamentos_manual_efetivados,0)) as pagamentos_manual_efetivados"));

    $q->orderByDesc('c.created_at');

    try {
        $contratos = $q->get();
    } catch (\Throwable $e) {
        return view('agente.contratos', [
            'contratos'          => collect(),
            'paymentsByContrato' => collect(),
            'erroQuery'          => $e->getMessage(),
            'percVigente'        => $percVigente, // agora pode ser null ✅
        ]);
    }

    $ids = $contratos->pluck('id')->all();

    // =========================
    // Detalhamento (lista): por ID + órfãos por CPF
    // =========================
    $payments = collect();

    if ($pmHasTable && $pmAgenteIdCol && !empty($ids)) {
        $qId = \DB::table($PM_TBL)->whereIn($pmAgenteIdCol, $ids);
        if (\Schema::hasColumn($PM_TBL, 'referencia_month')) $qId->orderBy('referencia_month');
        else $qId->orderBy('id');
        $payments = $qId->get();
    }

    $paymentsOrphans = collect();
    if ($pmHasTable && $pmCpfCol && $COL_CPF) {
        $cpfNorm = fn($s) => preg_replace('/\D/', '', (string)$s);

        $cidByCpf = [];
        foreach ($contratos as $c) {
            $cpf = $cpfNorm($c->cpf_cnpj ?? '');
            if ($cpf) $cidByCpf[$cpf] = (int)$c->id;
        }
        $cpfList = array_values(array_unique(array_keys($cidByCpf)));

        if (!empty($cpfList)) {
            $qOrf = \DB::table($PM_TBL);

            if ($pmAgenteIdCol) {
                $qOrf->where(function($w) use ($pmAgenteIdCol){
                    $w->whereNull($pmAgenteIdCol)->orWhere($pmAgenteIdCol, 0);
                });
            }

            $cpfNormP2 = $sqlCpfNorm($pmCpfCol);
            $qOrf->whereIn(\DB::raw($cpfNormP2), $cpfList);

            if (\Schema::hasColumn($PM_TBL, 'referencia_month')) $qOrf->orderBy('referencia_month');
            else $qOrf->orderBy('id');

            $paymentsOrphans = $qOrf->get();

            $extra = collect();
            foreach ($paymentsOrphans as $p) {
                $cpf = $cpfNorm($p->{$pmCpfCol} ?? '');
                $cid = $cidByCpf[$cpf] ?? null;
                if ($cid) {
                    $pp = clone $p;
                    $pp->{$pmAgenteIdCol ?? 'agente_cadastro_id'} = $cid;
                    $extra->push($pp);
                }
            }
            $payments = $payments->merge($extra);
        }
    }

    $paymentsByContrato = $pmAgenteIdCol ? $payments->groupBy($pmAgenteIdCol) : collect();

    return view('agente.contratos', [
        'contratos'          => $contratos,
        'paymentsByContrato' => $paymentsByContrato,
        'percVigente'        => $percVigente, // agora pode ser null ✅
    ]);
}




    /* ===================== Renovação ===================== */

public function renovarContrato(Request $request, \App\Models\AgenteCadastro $cadastro)
{
    // ====== Contexto inicial ======
    \Log::info('RENOVAR:hit', [
        'route'       => 'agente.contratos.renovar',
        'user_id'     => optional($request->user())->id,
        'user_name'   => trim((string) optional($request->user())->name),
        'orig_id'     => $cadastro->id,
        'orig_codigo' => $cadastro->contrato_codigo_contrato ?? null,
        'orig_status' => $cadastro->contrato_status_contrato ?? $cadastro->status_contrato ?? null,
        'orig_created'=> optional($cadastro->created_at)?->toDateTimeString(),
    ]);

    // ====== Autorização ======
    $me = trim((string) optional($request->user())->name);
    $belongsToMe = $cadastro
        && ($cadastro->agente_responsavel === $me || $cadastro->agente_filial === $me);

    if (!$belongsToMe) {
        \Log::warning('RENOVAR:auth_denied', [
            'orig_id' => $cadastro->id,
            'me'      => $me,
            'resp'    => $cadastro->agente_responsavel,
            'filial'  => $cadastro->agente_filial,
        ]);
        abort(403, 'Você não tem permissão para renovar este contrato.');
    }

    // ====== Elegibilidade (igual ao que a view considera) ======
    $hasConcludedFlag = (
        ($cadastro->contrato_status_contrato ?? null) === 'Concluído'
        || ($cadastro->status_contrato ?? null) === 'Concluído'
    );

    // Tesouraria
    $tesRow  = \App\Models\TesourariaPagamento::where('agente_cadastro_id', $cadastro->id)->first();
    $tesPago = $tesRow && strtolower($tesRow->status ?? '') === 'pago';

    // Mensalidades: por cadastro; se 0, cai para CPF
    $cpfDigits = preg_replace('/\D+/', '', (string) $cadastro->cpf_cnpj);
    $totById = \App\Models\PagamentoMensalidade::where('agente_cadastro_id', $cadastro->id)->count();
    $effById = \App\Models\PagamentoMensalidade::where('agente_cadastro_id', $cadastro->id)
                ->whereIn('status_code',['1','4'])->count();

    $totByCpf = $totById;
    $effByCpf = $effById;

    if ($totById === 0 && $cpfDigits !== '') {
        $totByCpf = \App\Models\PagamentoMensalidade::where('cpf_cnpj', $cpfDigits)->count();
        $effByCpf = \App\Models\PagamentoMensalidade::where('cpf_cnpj', $cpfDigits)
                    ->whereIn('status_code', ['1','4'])->count();
    }

    // Se houver cache no cadastro, mantenha o MAIOR valor
    $cacheTot = \Schema::hasColumn($cadastro->getTable(),'pagamentos_total')
        ? (int)($cadastro->pagamentos_total ?? 0) : null;
    $cacheEff = \Schema::hasColumn($cadastro->getTable(),'pagamentos_efetivados')
        ? (int)($cadastro->pagamentos_efetivados ?? 0) : null;

    $tot = max($cacheTot ?? 0, $totById, $totByCpf);
    $eff = max($cacheEff ?? 0, $effById, $effByCpf);

    $eligible = $hasConcludedFlag || (($eff >= 3) && ($tot >= 3)) || $tesPago;

    \Log::info('RENOVAR:eligibility', [
        'hasConcludedFlag' => $hasConcludedFlag,
        'tesPago'          => $tesPago,
        'tes_row'          => $tesRow ? ['id'=>$tesRow->id,'status'=>$tesRow->status] : null,
        'tot'              => $tot,
        'eff'              => $eff,
        'eligible'         => $eligible,
    ]);

    if (!$eligible) {
        return back()->withErrors([
            'renovar' => 'Este contrato ainda não está apto para renovação. Conclua o ciclo (3/3 efetivadas ou pagamento confirmado).'
        ]);
    }

    // ===========================================================
    // NOVO COMPORTAMENTO:
    // Não cria mais contrato novo. Só marca visualmente no frontend
    // como "Solicitação enviada" para este contrato.
    // ===========================================================

    \Log::info('RENOVAR:visual_only_mark', [
        'cadastro_id' => $cadastro->id,
        'cpf_digits'  => $cpfDigits,
        'user_id'     => optional($request->user())->id,
    ]);

    return redirect()
        ->route('agente.contratos')
        ->with('ok', 'Solicitação de renovação enviada para este contrato.')
        ->with('renovacao_solicitada_contrato_id', $cadastro->id);
}


    /**
     * UPDATE das pendências (form do agente)
     * - Update PARCIAL
     * - Reuploads “nomeados” => storage/app/public/agent-reuploads/{issue}
     * - Finalizar sem anexos => placeholder com status 'received'
     * - NÃO mistura reuploads dentro de documents_json (para não duplicar na tela)
     */
public function pendenciasUpdate(Request $r, \App\Models\AgenteDocIssue $issue)
{
    // --- Autorização ---
    $meName = trim((string) optional($r->user())->name);
    $belongsToMe = $issue->cadastro
        && ($issue->cadastro->agente_responsavel === $meName
            || $issue->cadastro->agente_filial === $meName);
    if (!$belongsToMe) abort(403, 'Você não tem permissão para editar este cadastro.');

    // === DEBUG REUPLOADS (antes da validação) ===
    try {
        $namedKeysDebug = ['cpf_frente','cpf_verso','comp_endereco','comp_renda','contracheque_atual','termo_adesao','termo_antecipacao'];
        $phpIniLimits = [
            'upload_max_filesize' => ini_get('upload_max_filesize'),
            'post_max_size'       => ini_get('post_max_size'),
            'max_file_uploads'    => ini_get('max_file_uploads'),
            'memory_limit'        => ini_get('memory_limit'),
            'content_length'      => $r->server('CONTENT_LENGTH'),
        ];
        $errName = function ($code) {
            switch ((int)$code) {
                case UPLOAD_ERR_OK:         return 'OK';
                case UPLOAD_ERR_INI_SIZE:   return 'INI_SIZE';
                case UPLOAD_ERR_FORM_SIZE:  return 'FORM_SIZE';
                case UPLOAD_ERR_PARTIAL:    return 'PARTIAL';
                case UPLOAD_ERR_NO_FILE:    return 'NO_FILE';
                case UPLOAD_ERR_NO_TMP_DIR: return 'NO_TMP_DIR';
                case UPLOAD_ERR_CANT_WRITE: return 'CANT_WRITE';
                case UPLOAD_ERR_EXTENSION:  return 'EXTENSION';
                default:                    return 'UNKNOWN';
            }
        };
        $filesDbg = [];
        foreach ($namedKeysDebug as $k) {
            $f = $r->file($k);
            $raw = $_FILES[$k] ?? null;
            $entry = [
                'present_in_request'  => $r->hasFile($k),
                'symfony_class'       => $f ? get_class($f) : null,
                'is_valid'            => $f ? $f->isValid() : null,
                'client_name'         => $f ? $f->getClientOriginalName() : null,
                'client_mime'         => $f ? $f->getClientMimeType() : null,
                'size_bytes'          => $f ? $f->getSize() : ($raw['size'] ?? null),
                'phpfiles_error'      => $raw['error'] ?? null,
                'phpfiles_error_name' => isset($raw['error']) ? $errName($raw['error']) : null,
            ];
            if ($f && !$f->isValid()) {
                try { $entry['error_message'] = $f->getErrorMessage(); } catch (\Throwable $e) {}
            }
            $filesDbg[$k] = $entry;
        }
        \Log::info('PEND-UPD: pre-validate named uploads snapshot', [
            'issue_id'    => $issue->id,
            'cadastro_id' => optional($issue->cadastro)->id,
            'php_ini'     => $phpIniLimits,
            'inputs'      => $filesDbg,
        ]);
    } catch (\Throwable $e) {
        \Log::warning('PEND-UPD: failed to snapshot files before validate', ['err' => $e->getMessage()]);
    }

    // --- Validação mínima + 50MB para anexos nomeados ---
    $rules = [
        'docType'                   => 'nullable|in:CPF,CNPJ',
        'cpfCnpj'                   => 'required',
        'matriculaServidorPublico'  => 'required|string',
        'email'                     => 'nullable|email',
        // Cálculo / Contrato
        'calc.valor_bruto'            => 'nullable',
        'calc.liquido_cc'             => 'nullable',
        'contrato.mensalidade'        => 'nullable',
        'contrato.dataAprovacao'      => 'nullable',
        'contrato.dataEnvioPrimeira'  => 'nullable',
        'contrato.mesAverbacao'       => 'nullable',
        'contrato.doacaoAssociado'    => 'nullable',
        // Antecipações
        'anticipations'                           => 'nullable|array',
        'anticipations.*.numeroMensalidade'       => 'nullable|integer|min:1',
        'anticipations.*.valorAuxilio'            => 'nullable',
        'anticipations.*.dataEnvio'               => 'nullable',
        'anticipations.*.observacao'              => 'nullable',
        // Agente / Observações
        'agente.responsavel'  => 'nullable|string',
        'observacoes'         => 'nullable|string',
        // Auxílio do Agente
        'auxilioAgente.taxa'      => 'nullable',
        'auxilioAgente.dataEnvio' => 'nullable',
    ] + $this->fileRules50MB();

    $messages = $this->fileMessages50MB() + [
        'comp_renda.uploaded' => 'Falha no upload (limites do servidor).',
    ];
    $r->validate($rules, $messages);

    $cadastro = $issue->cadastro;
    if (!$cadastro) return back()->withErrors(['cadastro' => 'Cadastro não encontrado para esta pendência.']);

    // Helper p/ set condicional
    $setIf = function(array &$dst, string $key, $val) {
        if ($val === null) return;
        if (is_string($val) && trim($val) === '') return;
        $dst[$key] = $val;
    };

    // --- Documento ---
    $docTypeIn = strtoupper((string)$r->input('docType', ''));
    $cpfCnpj   = $this->onlyDigits($r->input('cpfCnpj'));
    $docType   = in_array($docTypeIn, ['CPF','CNPJ']) ? $docTypeIn : ( $cpfCnpj ? (strlen($cpfCnpj) === 14 ? 'CNPJ' : 'CPF') : null );

    if ($docType === 'CPF' && strlen($cpfCnpj) !== 11) return back()->withErrors(['cpfCnpj' => 'CPF inválido (11 dígitos).']);
    if ($docType === 'CNPJ' && strlen($cpfCnpj) !== 14) return back()->withErrors(['cpfCnpj' => 'CNPJ inválido (14 dígitos).']);

    // CPF duplicado — só se mudou
    if ($docType === 'CPF') {
        $cpfAtual = $this->onlyDigits($cadastro->cpf_cnpj);
        $cpfMudou = ($cpfCnpj !== '' && $cpfCnpj !== $cpfAtual);
        if ($cpfMudou) {
            if ($existing = $this->findCadastroByCPF($cpfCnpj, $cadastro->id ?? null)) {
                return back()->withErrors([
                    'cpfCnpj' => 'CPF já cadastrado para "'.$existing->full_name.'" pelo agente "'.$existing->agente_responsavel.'".'
                ]);
            }
        }
    }

    // --- Monta updates parciais ---
    $updates = [];
    $setIf($updates, 'doc_type', $docType);
    $setIf($updates, 'cpf_cnpj', $cpfCnpj);
    $setIf($updates, 'rg', $r->input('rg'));
    $setIf($updates, 'orgao_expedidor', $r->input('orgaoExpedidor'));
    $setIf($updates, 'full_name', $r->input('fullName'));
    if (($bd = $r->input('birthDate')) !== null && trim($bd) !== '') $setIf($updates, 'birth_date', $this->dateBrToIso($bd));
    $setIf($updates, 'profession', $r->input('profession'));
    $setIf($updates, 'marital_status', $this->mapEstadoCivil($r->input('maritalStatus')));

    foreach ([
        'cep' => 'cep','address' => 'address','address_number' => 'addressNumber',
        'complement' => 'complement','neighborhood' => 'neighborhood',
        'city' => 'city','uf' => 'uf'
    ] as $col => $req) $setIf($updates, $col, $r->input($req));

    $setIf($updates, 'cellphone', $r->input('cellphone'));
    $setIf($updates, 'orgao_publico', $r->input('orgaoPublico'));
    $setIf($updates, 'situacao_servidor', $r->input('situacaoServidor'));
    $setIf($updates, 'matricula_servidor_publico', $r->input('matriculaServidorPublico'));
    $setIf($updates, 'email', $r->input('email'));

    // Bancário
    $setIf($updates, 'bank_name', $r->input('bank_name'));
    $setIf($updates, 'bank_agency', $r->input('bank_agency'));
    $setIf($updates, 'bank_account', $r->input('bank_account'));
    $accType = $r->input('account_type');
    if (in_array($accType, ['corrente','poupanca'])) $setIf($updates, 'account_type', $accType);
    $setIf($updates, 'pix_key', $r->input('pix_key'));

    // Contrato
    $c = (array) $r->input('contrato', []);
    $mensalidade = array_key_exists('mensalidade',$c) ? $this->brlToDecimal($c['mensalidade']) : null;
    if ($mensalidade !== null) $updates['contrato_mensalidade'] = $mensalidade;
    if (!empty($c['dataAprovacao']))     $updates['contrato_data_aprovacao'] = $this->dateBrToIso($c['dataAprovacao']);
    if (!empty($c['dataEnvioPrimeira'])) $updates['contrato_data_envio_primeira'] = $this->dateBrToIso($c['dataEnvioPrimeira']);
    if (!empty($c['mesAverbacao']))      $updates['contrato_mes_averbacao'] = $this->monthToDate($c['mesAverbacao']);
    if (array_key_exists('doacaoAssociado',$c)) {
        $v = $this->brlToDecimal($c['doacaoAssociado']);
        if ($v !== null) $updates['contrato_doacao_associado'] = $v;
    }
    if (array_key_exists('mensalidade',$c) && $mensalidade !== null) {
        $prazo = 3;
        $updates['contrato_prazo_meses']       = $prazo;
        $updates['contrato_taxa_antecipacao']  = 30.00;
        $updates['contrato_valor_antecipacao'] = round($mensalidade * $prazo, 2);
        $updates['contrato_margem_disponivel'] = round($updates['contrato_valor_antecipacao'] * 0.70, 2);
    }

    // Cálculo
    $calc = (array) $r->input('calc', []);
    if (array_key_exists('valor_bruto',$calc))  { $v = $this->brlToDecimal($calc['valor_bruto']); if ($v !== null) $updates['calc_valor_bruto'] = $v; }
    if (array_key_exists('liquido_cc',$calc))   { $v = $this->brlToDecimal($calc['liquido_cc']);  if ($v !== null) $updates['calc_liquido_cc']  = $v; }
    if ($mensalidade !== null) $updates['calc_mensalidade_associativa'] = $mensalidade;
    $updates['calc_prazo_antecipacao'] = 3;

    // Agente / Observações
    $agente_nome = trim((string)$r->input('agente.responsavel'));
    if ($agente_nome !== '') $updates['agente_responsavel'] = $agente_nome;
    if ($agente_nome !== '' && empty($cadastro->agente_filial)) $updates['agente_filial'] = $agente_nome;
    if ($r->filled('observacoes')) $updates['observacoes'] = $r->input('observacoes');

    // Antecipações – merge incremental
    if (is_array($r->input('anticipations'))) {
        $old = $cadastro->anticipations_json;
        if (is_string($old)) { $tmp = json_decode($old, true); if (json_last_error() === JSON_ERROR_NONE) $old = $tmp; }
        if (!is_array($old)) $old = [];
        $new = $old;
        foreach ((array)$r->input('anticipations') as $k => $row) {
            if (!isset($new[$k]) || !is_array($new[$k])) $new[$k] = [];
            if (array_key_exists('numeroMensalidade',$row) && $row['numeroMensalidade'] !== '' && $row['numeroMensalidade'] !== null)
                $new[$k]['numeroMensalidade'] = (int)$row['numeroMensalidade'];
            if (array_key_exists('valorAuxilio',$row) && $row['valorAuxilio'] !== '' && $row['valorAuxilio'] !== null) {
                $v = $this->brlToDecimal($row['valorAuxilio']);
                if ($v !== null) $new[$k]['valorAuxilio'] = $v;
            }
            if (array_key_exists('dataEnvio',$row) && trim((string)$row['dataEnvio'])!=='')
                $new[$k]['dataEnvio'] = $this->dateBrToIso($row['dataEnvio']);
            if (array_key_exists('status',$row) && trim((string)$row['status'])!=='')
                $new[$k]['status'] = $row['status'];
            if (array_key_exists('observacao',$row))
                $new[$k]['observacao'] = $row['observacao'];
        }
        $updates['anticipations_json'] = $new;
    }

    // ===== Detecta mudanças reais =====
    $changedUpdates = [];
    foreach ($updates as $k => $v) {
        $cur = $cadastro->getAttribute($k);
        if (is_array($v) || is_object($v)) {
            $curNorm = (is_array($cur) || is_object($cur))
                ? json_encode($cur, JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES)
                : (string)$cur;
            $vNorm   = json_encode($v, JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
            $equal   = ($curNorm === $vNorm);
        } else {
            if ($cur instanceof \Carbon\Carbon) $cur = $cur->format('Y-m-d H:i:s');
            $equal = (is_numeric($cur) && is_numeric($v)) ? ((float)$cur == (float)$v)
                    : (((string)$cur) === ((string)$v));
        }
        if (!$equal) $changedUpdates[$k] = $v;
    }
    if (!empty($changedUpdates)) $cadastro->fill($changedUpdates)->save();

    // ===== Uploads nomeados -> cria REUPLOADS =====
    $namedKeys = ['cpf_frente','cpf_verso','comp_endereco','comp_renda','contracheque_atual','termo_adesao','termo_antecipacao'];
    $userId    = optional($r->user())->id;
    $dir       = 'agent-reuploads/'.$issue->id;
    $createdReuploads = 0;

    foreach ($namedKeys as $k) {
        $f = $r->file($k);

        if ($f instanceof \Illuminate\Http\UploadedFile && !$f->isValid()) {
            \Log::error('PEND-UPD: named upload INVALID (skipped)', [
                'issue_id'    => $issue->id,
                'field'       => $k,
                'client_name' => $f->getClientOriginalName(),
                'size_bytes'  => $f->getSize(),
                'mime'        => $f->getClientMimeType(),
                'error'       => method_exists($f,'getError') ? $f->getError() : null,
                'error_msg'   => method_exists($f,'getErrorMessage') ? $f->getErrorMessage() : null,
            ]);
        }

        if ($f instanceof \Illuminate\Http\UploadedFile && $f->isValid()) {
            $orig   = $f->getClientOriginalName();
            $ext    = strtolower($f->getClientOriginalExtension() ?: 'bin');
            $stored = now()->format('Ymd_His').'-'.\Illuminate\Support\Str::random(8).'.'.$ext;

            $path     = $f->storeAs($dir, $stored, 'public');
            $relative = 'storage/'.$path;

            $mime   = $f->getClientMimeType() ?: 'application/octet-stream';
            $size   = $f->getSize();

            \Log::info('PEND-UPD: named upload SAVED', [
                'issue_id'        => $issue->id,
                'field'           => $k,
                'original_name'   => $orig,
                'stored_name'     => $stored,
                'disk_path'       => $path,
                'relative_url'    => $relative,
                'mime'            => $mime,
                'size_bytes'      => $size,
                'exists_public'   => \Storage::disk('public')->exists($path),
            ]);

            \App\Models\AgenteDocReupload::create([
                'agente_doc_issue_id'      => $issue->id,
                'agente_cadastro_id'       => $cadastro->id,
                'uploaded_by_user_id'      => $userId,
                'cpf_cnpj'                 => $cadastro->cpf_cnpj,
                'contrato_codigo_contrato' => $cadastro->contrato_codigo_contrato,
                'file_original_name'       => $orig,
                'file_stored_name'         => $stored,
                'file_relative_path'       => $relative,
                'file_mime'                => $mime,
                'file_size_bytes'          => $size,
                'status'                   => 'received',
                'uploaded_at'              => now(),
                'notes'                    => 'Reenvio via formulário do agente (documento nomeado: '.$k.').',
                // <- array (o cast do model já salva como JSON)
                'extras'                   => ['field' => $k],
            ]);

            $createdReuploads++;
        }
    }

    // ===== Finalizar (enviar ao analista) =====
    if ($r->boolean('finalizar')) {

        // SEM NOVOS ARQUIVOS: placeholder como RECEIVED e snapshot
        if ($createdReuploads === 0) {
            try {
                $docsSnap = $cadastro->documents_json;
                if (is_string($docsSnap)) {
                    $tmp = json_decode($docsSnap, true);
                    if (json_last_error() === JSON_ERROR_NONE) $docsSnap = $tmp;
                }
                if (!is_array($docsSnap)) $docsSnap = [];

                if (\Illuminate\Support\Facades\Schema::hasColumn($issue->getTable(), 'documents_snapshot_json') && !empty($docsSnap)) {
                    $issue->documents_snapshot_json = array_values($docsSnap);
                    $issue->save();
                }
            } catch (\Throwable $e) {
                \Log::warning('pendenciasUpdate: falha ao atualizar snapshot', [
                    'issue_id' => $issue->id, 'err' => $e->getMessage()
                ]);
            }

            try {
                $docsCount = isset($docsSnap) && is_array($docsSnap) ? count($docsSnap) : null;
                \App\Models\AgenteDocReupload::create([
                    'agente_doc_issue_id'      => $issue->id,
                    'agente_cadastro_id'       => $cadastro->id,
                    'uploaded_by_user_id'      => $userId,
                    'cpf_cnpj'                 => $cadastro->cpf_cnpj,
                    'contrato_codigo_contrato' => $cadastro->contrato_codigo_contrato,
                    'file_original_name'       => '(sem arquivo)',
                    'file_stored_name'         => 'NOFILE-'.$issue->id.'-'.now()->format('YmdHis').'-'.\Illuminate\Support\Str::random(6),
                    'file_relative_path'       => null, // <- nullable na migration
                    'file_mime'                => 'application/octet-stream',
                    'file_size_bytes'          => 0,
                    'status'                   => 'received',
                    'uploaded_at'              => now(),
                    'notes'                    => 'Reenvio finalizado sem anexos. Solicita considerar os últimos documentos já enviados.',
                    'extras'                   => [
                        'placeholder'        => true,
                        'use_last_documents' => true,
                        'last_docs_count'    => $docsCount,
                    ],
                ]);
            } catch (\Throwable $e) {
                \Log::warning('pendenciasUpdate: placeholder sem arquivos falhou', [
                    'issue_id' => $issue->id, 'err' => $e->getMessage()
                ]);
            }
        }

        // Apenas acrescenta nota na Issue (NÃO muda status: enum é ['incomplete','resolved'])
        try {
            $issue->mensagem = trim(
                ($issue->mensagem ? $issue->mensagem."\n\n" : '').
                'Reenvio registrado pelo agente em '.now()->format('d/m/Y H:i').'. Aguardando validação do analista.'
            );
            $issue->updated_at = now();
            $issue->save();
        } catch (\Throwable $e) {
            \Log::warning('pendenciasUpdate: falha ao atualizar Issue', [
                'issue_id' => $issue->id, 'err' => $e->getMessage()
            ]);
        }

        \Log::info('pendenciasUpdate: FINALIZADO', [
            'issue_id'          => $issue->id,
            'cadastro_id'       => $cadastro->id,
            'created_reuploads' => $createdReuploads,
            'status_issue'      => $issue->status,
        ]);

        return redirect()
            ->route('agente.pendencias')
            ->with('ok', 'Cadastro atualizado e documentação reenviada ao analista. Aguardando validação.');
    }

    // Somente atualização de dados
    return back()->with('ok', !empty($changedUpdates) ? 'Cadastro atualizado com sucesso.' : 'Nada a atualizar — nenhum dado foi alterado.');
}


    /* ===================== AJAX ===================== */

    /**
     * Verifica se um CPF já está cadastrado (somente para doc_type = CPF).
     * GET /agente/check-cpf?cpf=###########
     */
    public function checkCpf(Request $r)
    {
        $cpf = $this->onlyDigits($r->input('cpf'));
        if (strlen($cpf) !== 11) {
            return response()->json(['exists' => false]); // só checamos CPF completo
        }

        $row = $this->findCadastroByCPF($cpf);
        if (!$row) return response()->json(['exists' => false]);

        return response()->json([
            'exists' => true,
            'data'   => [
                'full_name'          => $row->full_name,
                'agente_responsavel' => $row->agente_responsavel,
                'created_at'         => optional($row->created_at)->toDateTimeString(),
            ],
        ]);
    }


    private function spClosingDayForMonth(Carbon $month): int
    {
        $overrides = [
            '2026-01' => 7,
            '2026-02' => 6,
        ];
        $key = $month->format('Y-m');
        $day = $overrides[$key] ?? (int) env('FECHAMENTO_DIA', 5);
        $dim = $month->daysInMonth;

        // empurra sábado/domingo para segunda, sem passar do fim do mês
        $day = min($day, $dim);
        $wd = Carbon::create($month->year, $month->month, $day, 0,0,0, 'America/Sao_Paulo')->dayOfWeekIso; // 1..7
        if ($wd === 6) $day = min($day + 2, $dim);     // sábado -> +2
        if ($wd === 7) $day = min($day + 1, $dim);     // domingo -> +1
        return $day;
    }

    /**
     * Calcula datas padrão em SP: aprovação (hoje), mês de averbação e 1ª mensalidade.
     * Retorna strings no formato esperado pelo formulário.
     */
private function autoContratoDatesFromNowSP(): array
{
    $now = Carbon::now('America/Sao_Paulo');

    // Regra 06→05: até 05 ainda é do mês; 06 já conta como próximo.
    $cut = (int) env('FECHAMENTO_DIA', 5);
    $addMonth = ($now->day > $cut) ? 1 : 0;

    // Mês de averbação (início do mês atual ou próximo, conforme corte)
    $averb = $now->copy()->startOfMonth()->addMonths($addMonth);

    // 1ª mensalidade = mês seguinte ao mês de averbação, no "dia de fechamento" (ajustado p/ 2ª caso caia em fds)
    $firstStart = $averb->copy()->addMonthNoOverflow()->startOfMonth();
    $d1 = $this->spClosingDayForMonth($firstStart); // mantém sua função de ajuste p/ segunda-feira
    $primeira = $firstStart->copy()->day($d1);

    return [
        'dataAprovacao' => $now->format('d/m/Y'),
        'mesAverbacao'  => $averb->format('Y-m'),
        'dataPrimeira'  => $primeira->format('d/m/Y'),
    ];
}

// PAGAMENTOS AGENTE (TESOURARIA + VÍNCULO COM REFINANCIAMENTO/COMPROVANTES)
public function pagamentosIndex(\Illuminate\Http\Request $r)
{
    $user = \Illuminate\Support\Facades\Auth::user();

    // Filtros
    $q       = trim((string) $r->query('q', ''));
    $status  = trim((string) $r->query('status', '')); // pendente | pago | cancelado | (vazio = todos)
    $mesISO  = trim((string) $r->query('mes', ''));    // YYYY-MM (opcional)
    $perPage = (int) max(5, min(50, (int) $r->query('per_page', 15)));

    // Descobrir coluna de "dono" no agente_cadastros
    $ownerCol = null;
    foreach (['created_by_user_id', 'agente_user_id', 'user_id', 'agente_id'] as $col) {
        if (\Illuminate\Support\Facades\Schema::hasColumn('agente_cadastros', $col)) {
            $ownerCol = $col;
            break;
        }
    }
    $ownerMode = $ownerCol ? "coluna:$ownerCol" : 'fallback:agente_responsavel';

    // Descobrir coluna de comissão do agente em tesouraria_pagamentos
    $commissionCol = null;
    foreach ([
        'valor_comissao_agente',
        'valor_comissao',
        'valor_agente',
        'valor_pago_agente',
        'comissao_agente',
        'commission_value',
    ] as $col) {
        if (\Illuminate\Support\Facades\Schema::hasColumn('tesouraria_pagamentos', $col)) {
            $commissionCol = $col;
            break;
        }
    }
    $commissionMode = $commissionCol ? "coluna:$commissionCol" : 'sem_coluna';

    // Janela por competência (opcional)
    $range = null;
    if ($mesISO !== '' && preg_match('~^\d{4}-\d{2}$~', $mesISO)) {
        $tz  = config('app.timezone') ?: 'America/Sao_Paulo';
        $fd  = (int) env('FECHAMENTO_DIA', 5);

        $comp  = \Carbon\Carbon::createFromFormat('Y-m', $mesISO, $tz)->startOfMonth();
        $ini   = $comp->copy()->day($fd)->startOfDay();
        $fimEx = $comp->copy()->addMonth()->day($fd)->startOfDay();

        $range = [
            'ini'   => $ini->copy(),
            'fimEx' => $fimEx->copy(),
            'fimUi' => $fimEx->copy()->subSecond(),
            'tz'    => $tz,
        ];
    }

    // Função para aplicar os MESMOS filtros em qualquer query builder
    $applyFilters = function ($qb) use ($user, $ownerCol, $q, $status, $range) {

        // "meus cadastros"
        if ($ownerCol) {
            $qb->where("c.$ownerCol", '=', $user->id);
        } else {
            // fallback por agente_responsavel
            if (\Illuminate\Support\Facades\Schema::hasColumn('agente_cadastros', 'agente_responsavel')) {
                $name = trim((string)($user->name ?? ''));
                if ($name !== '') {
                    $qb->where('c.agente_responsavel', 'like', '%' . $name . '%');
                } else {
                    $qb->whereRaw('1=0');
                }
            } else {
                $qb->whereRaw('1=0');
            }
        }

        // competência (opcional)
        if (!empty($range)) {
            $ini   = $range['ini'];
            $fimEx = $range['fimEx'];

            $qb->where(function ($w) use ($ini, $fimEx) {
                $w->whereBetween('p.paid_at', [$ini, $fimEx])
                  ->orWhere(function ($x) use ($ini, $fimEx) {
                      $x->whereNull('p.paid_at')
                        ->whereBetween('p.created_at', [$ini, $fimEx]);
                  });
            });
        }

        // status (opcional)
        if ($status !== '' && in_array($status, ['pendente', 'pago', 'cancelado'], true)) {
            $qb->where('p.status', '=', $status);
        }

        // busca (nome/cpf/contrato)
        if ($q !== '') {
            $qLower  = mb_strtolower($q, 'UTF-8');
            $qDigits = preg_replace('/\D+/', '', $q);
            $qUpper  = mb_strtoupper($q, 'UTF-8');

            $qb->where(function ($w) use ($qLower, $qDigits, $qUpper) {
                $w->orWhereRaw('LOWER(COALESCE(c.full_name, p.full_name, "")) LIKE ?', ['%' . $qLower . '%']);

                if ($qDigits !== '') {
                    $w->orWhereRaw(
                        'REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(c.cpf_cnpj, p.cpf_cnpj, ""),".",""),"-",""),"/","")," ","") LIKE ?',
                        ['%' . $qDigits . '%']
                    );
                }

                $w->orWhereRaw('UPPER(COALESCE(c.contrato_codigo_contrato, p.contrato_codigo_contrato, "")) LIKE ?', ['%' . $qUpper . '%']);
            });
        }
    };

    // =========================
    // QUERY BASE (com joins do refinanciamento)
    // =========================
    $base = \Illuminate\Support\Facades\DB::table('tesouraria_pagamentos as p')
        ->join('agente_cadastros as c', 'c.id', '=', 'p.agente_cadastro_id')
        ->leftJoin('refinanciamento_itens as ri', 'ri.tesouraria_pagamento_id', '=', 'p.id')
        ->leftJoin('refinanciamentos as rf', 'rf.id', '=', 'ri.refinanciamento_id');

    $applyFilters($base);

    // =========================
    // CONTADORES (SEM misturar select)
    // =========================
    $countsQ = \Illuminate\Support\Facades\DB::table('tesouraria_pagamentos as p')
        ->join('agente_cadastros as c', 'c.id', '=', 'p.agente_cadastro_id')
        ->leftJoin('refinanciamento_itens as ri', 'ri.tesouraria_pagamento_id', '=', 'p.id')
        ->leftJoin('refinanciamentos as rf', 'rf.id', '=', 'ri.refinanciamento_id');

    $applyFilters($countsQ);

    $comissaoExpr = $commissionCol ? "SUM(COALESCE(p.$commissionCol,0))" : "0";

    $countsRow = $countsQ->selectRaw("
        COUNT(*) as total,
        SUM(CASE WHEN p.status = 'pendente' THEN 1 ELSE 0 END) as pendente,
        SUM(CASE WHEN p.status = 'pago' THEN 1 ELSE 0 END) as pago,
        SUM(CASE WHEN p.status = 'cancelado' THEN 1 ELSE 0 END) as cancelado,
        $comissaoExpr as comissao_sum
    ")->first();

    $counts = [
        'total'       => (int)($countsRow->total ?? 0),
        'pendente'    => (int)($countsRow->pendente ?? 0),
        'pago'        => (int)($countsRow->pago ?? 0),
        'cancelado'   => (int)($countsRow->cancelado ?? 0),
        'comissao_sum'=> (float)($countsRow->comissao_sum ?? 0),
    ];

    // =========================
    // SELECT DA LISTA (com comprovantes via subquery)
    // =========================
    $commissionSelect = $commissionCol
        ? "p.$commissionCol as valor_comissao"
        : "NULL as valor_comissao";

    $rows = $base->selectRaw("
        p.id as pagamento_id,
        p.status,
        p.valor_pago,
        p.paid_at,
        p.created_at as pagamento_criado_em,
        p.forma_pagamento,
        p.notes,
        p.contrato_codigo_contrato as p_codigo,
        p.cpf_cnpj as p_cpf,
        p.full_name as p_nome,

        c.id as cadastro_id,
        c.full_name as nome,
        c.cpf_cnpj as cpf_cnpj,
        c.contrato_codigo_contrato as codigo,
        c.contrato_margem_disponivel as margem,
        c.agente_responsavel as agente_responsavel,

        ri.id as refinanciamento_item_id,
        ri.referencia_month as refi_mes,
        ri.valor as refi_valor,

        rf.id as refinanciamento_id,
        rf.cycle_key as refi_cycle_key,
        rf.executed_at as refi_executed_at,
        rf.status as refi_status,

        $commissionSelect,

        (
          SELECT COUNT(*)
          FROM refinanciamento_comprovantes rc
          WHERE rc.refinanciamento_id = rf.id
        ) as comprovantes_count,

        (
          SELECT GROUP_CONCAT(CONCAT_WS('@@',
              rc.id,
              rc.kind,
              rc.path,
              COALESCE(rc.original_name,''),
              COALESCE(rc.mime,'')
          ) SEPARATOR '||')
          FROM refinanciamento_comprovantes rc
          WHERE rc.refinanciamento_id = rf.id
        ) as comprovantes_pack
    ")
    ->orderByDesc('p.id')
    ->paginate($perPage)
    ->withQueryString();

    return view('agente.pagamentoagente', [
        'rows'            => $rows,
        'q'               => $q,
        'status'          => $status,
        'mesSel'          => ($mesISO !== '' ? $mesISO : null),
        'counts'          => $counts,
        'range'           => $range,
        'ownerMode'       => $ownerMode,
        'commissionMode'  => $commissionMode,
    ]);
}


// ABRIR/VER COMPROVANTE DO REFINANCIAMENTO (somente se for do agente dono)
public function pagamentosComprovante($comprovanteId)
{
    $user = \Illuminate\Support\Facades\Auth::user();

    // Descobrir coluna dono do agente_cadastros
    $ownerCol = null;
    foreach (['created_by_user_id', 'agente_user_id', 'user_id', 'agente_id'] as $col) {
        if (\Illuminate\Support\Facades\Schema::hasColumn('agente_cadastros', $col)) {
            $ownerCol = $col;
            break;
        }
    }

    $q = \Illuminate\Support\Facades\DB::table('refinanciamento_comprovantes as rc')
        ->join('refinanciamentos as rf', 'rf.id', '=', 'rc.refinanciamento_id')
        ->leftJoin('agente_cadastros as c', 'c.id', '=', 'rf.agente_cadastro_id')
        ->select([
            'rc.id','rc.kind','rc.path','rc.original_name','rc.mime','rc.created_at',
            'rf.id as refinanciamento_id',
            'rf.agente_cadastro_id',
        ])
        ->where('rc.id', '=', (int)$comprovanteId);

    // Autoriza: somente comprovante cujo refinanciamento pertence a um cadastro do agente
    if ($ownerCol) {
        $q->where("c.$ownerCol", '=', $user->id);
    } else {
        if (\Illuminate\Support\Facades\Schema::hasColumn('agente_cadastros', 'agente_responsavel')) {
            $name = trim((string)($user->name ?? ''));
            if ($name !== '') {
                $q->where('c.agente_responsavel', 'like', '%' . $name . '%');
            } else {
                abort(404);
            }
        } else {
            abort(404);
        }
    }

    $row = $q->first();
    if (!$row) abort(404);

    $path = (string)($row->path ?? '');
    if ($path === '') abort(404);

    // Tentativa de discos comuns (public -> default)
    $disk = 'public';
    try {
        if (!\Illuminate\Support\Facades\Storage::disk($disk)->exists($path)) {
            $disk = config('filesystems.default') ?: 'local';
        }
        if (!\Illuminate\Support\Facades\Storage::disk($disk)->exists($path)) {
            abort(404);
        }

        $full = \Illuminate\Support\Facades\Storage::disk($disk)->path($path);
        $mime = $row->mime ?: (\Illuminate\Support\Facades\Storage::disk($disk)->mimeType($path) ?: 'application/octet-stream');

        return response()->file($full, [
            'Content-Type' => $mime,
        ]);
    } catch (\Throwable $e) {
        abort(404);
    }
}

// AgenteController.php  (SÓ o método)

public function refinanciadosIndex(\Illuminate\Http\Request $r)
{
    $user = \Illuminate\Support\Facades\Auth::user();

    if (!\Illuminate\Support\Facades\Schema::hasTable('refinanciamentos')) {
        return view('agente.refinanciados', [
            'rows'      => new \Illuminate\Pagination\LengthAwarePaginator([], 0, 15),
            'q'         => '',
            'st'        => 'all',
            'cycle'     => '',
            'counts'    => ['total'=>0,'done'=>0,'failed'=>0,'reverted'=>0],
            'ownerMode' => 'no_table_refinanciamentos',
        ]);
    }

    if (!\Illuminate\Support\Facades\Schema::hasTable('agente_cadastros')) {
        return view('agente.refinanciados', [
            'rows'      => new \Illuminate\Pagination\LengthAwarePaginator([], 0, 15),
            'q'         => '',
            'st'        => 'all',
            'cycle'     => '',
            'counts'    => ['total'=>0,'done'=>0,'failed'=>0,'reverted'=>0],
            'ownerMode' => 'no_table_agente_cadastros',
        ]);
    }

    // =========================
    // NOVO: percentual vigente do agente (agente_margens)
    // =========================
    $percVigente = null;
    if (\Illuminate\Support\Facades\Schema::hasTable('agente_margens')) {
        $percVigente = \Illuminate\Support\Facades\DB::table('agente_margens')
            ->where('agente_user_id', $user->id)
            ->whereNull('vigente_ate')
            ->orderByDesc('vigente_desde')
            ->value('percentual');
    }
    $percVigente = is_null($percVigente) ? 10.00 : (float)$percVigente;

    \Illuminate\Support\Facades\Log::info('[AGENTE][refinanciados] margem_vigente', [
        'user_id' => $user->id,
        'perc' => $percVigente,
    ]);

    // =========================
    // Filtros
    // =========================
    $q       = trim((string) $r->query('q', ''));
    $st      = strtolower(trim((string) $r->query('st', 'all')));     // all|done|failed|reverted
    $cycle   = trim((string) $r->query('cycle', ''));                // cycle_key (opcional)
    $perPage = (int) max(5, min(50, (int) $r->query('per_page', 15)));

    // =========================
    // Descobrir coluna de vínculo refinanciamentos -> agente_cadastros
    // =========================
    $joinKey = null;
    foreach (['agente_cadastro_id', 'cadastro_id', 'agente_cadastros_id', 'agente_id'] as $col) {
        if (\Illuminate\Support\Facades\Schema::hasColumn('refinanciamentos', $col)) {
            $joinKey = $col;
            break;
        }
    }

    if (!$joinKey) {
        return view('agente.refinanciados', [
            'rows'      => new \Illuminate\Pagination\LengthAwarePaginator([], 0, $perPage),
            'q'         => $q,
            'st'        => $st,
            'cycle'     => $cycle,
            'counts'    => ['total'=>0,'done'=>0,'failed'=>0,'reverted'=>0],
            'ownerMode' => 'no_join_key_refinanciamentos',
        ]);
    }

    // =========================
    // Descobrir coluna "dono" no agente_cadastros
    // =========================
    $ownerCol = null;
    foreach (['created_by_user_id', 'agente_user_id', 'user_id', 'agente_id'] as $col) {
        if (\Illuminate\Support\Facades\Schema::hasColumn('agente_cadastros', $col)) {
            $ownerCol = $col;
            break;
        }
    }
    $ownerMode = $ownerCol ? "coluna:$ownerCol" : 'fallback:agente_responsavel';

    $applyOwner = function ($qb) use ($user, $ownerCol) {
        if ($ownerCol) {
            $qb->where("c.$ownerCol", '=', $user->id);
        } else {
            if (\Illuminate\Support\Facades\Schema::hasColumn('agente_cadastros', 'agente_responsavel')) {
                $name = trim((string)($user->name ?? ''));
                if ($name !== '') {
                    $qb->where('c.agente_responsavel', 'like', '%' . $name . '%');
                } else {
                    $qb->whereRaw('1=0');
                }
            } else {
                $qb->whereRaw('1=0');
            }
        }
    };

    $applyFilters = function ($qb) use ($q, $st, $cycle) {

        if ($st !== '' && $st !== 'all' && in_array($st, ['done','failed','reverted'], true)) {
            $qb->whereRaw('LOWER(TRIM(rf.status)) = ?', [$st]);
        }

        if ($cycle !== '') {
            $qb->where('rf.cycle_key', '=', $cycle);
        }

        if ($q !== '') {
            $qLower  = mb_strtolower($q, 'UTF-8');
            $qDigits = preg_replace('/\D+/', '', $q);
            $qUpper  = mb_strtoupper($q, 'UTF-8');

            $qb->where(function ($w) use ($qLower, $qDigits, $qUpper) {
                $w->orWhereRaw('LOWER(COALESCE(rf.nome_snapshot, c.full_name, "")) LIKE ?', ['%' . $qLower . '%']);

                if ($qDigits !== '') {
                    $w->orWhereRaw(
                        'REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(rf.cpf_cnpj, c.cpf_cnpj, "" ),".",""),"-",""),"/","")," ","") LIKE ?',
                        ['%' . $qDigits . '%']
                    );
                }

                $w->orWhereRaw('UPPER(COALESCE(c.contrato_codigo_contrato,"")) LIKE ?', ['%' . $qUpper . '%']);
                $w->orWhereRaw('UPPER(COALESCE(rf.cycle_key,"")) LIKE ?', ['%' . $qUpper . '%']);
            });
        }
    };

    // =========================
    // Detectar valor do refinanciamento (para repasse)
    // =========================
    $detectMoneyCol = function (string $table, array $cands) {
        foreach ($cands as $c) {
            if (\Illuminate\Support\Facades\Schema::hasColumn($table, $c)) return $c;
        }
        return null;
    };

    $hasItens = \Illuminate\Support\Facades\Schema::hasTable('refinanciamento_itens');
    $hasPm    = \Illuminate\Support\Facades\Schema::hasTable('pagamentos_mensalidades');
    $hasTp    = \Illuminate\Support\Facades\Schema::hasTable('tesouraria_pagamentos');

    $pmValCol = $hasPm ? $detectMoneyCol('pagamentos_mensalidades', ['valor','value','amount','valor_pago','valor_pagamento','valor_total']) : null;
    $tpValCol = $hasTp ? $detectMoneyCol('tesouraria_pagamentos', ['valor','value','amount','valor_pago','valor_pagamento','valor_total']) : null;
    $riValCol = $hasItens ? $detectMoneyCol('refinanciamento_itens', ['valor','value','amount','valor_pago','valor_pagamento','valor_total']) : null;

    $rfValCol = $detectMoneyCol('refinanciamentos', ['valor_total','valor','value','amount']);

    $itemsAgg = null;
    if ($hasItens && ($pmValCol || $tpValCol || $riValCol)) {

        $coalesceArgs = [];
        if ($hasPm && $pmValCol) $coalesceArgs[] = "pm.$pmValCol";
        if ($hasTp && $tpValCol) $coalesceArgs[] = "tp.$tpValCol";
        if ($riValCol)           $coalesceArgs[] = "ri.$riValCol";
        $coalesceArgs[] = "0";

        $coalesce = "COALESCE(" . implode(',', $coalesceArgs) . ")";

        $itemsAgg = \Illuminate\Support\Facades\DB::table('refinanciamento_itens as ri')
            ->selectRaw("ri.refinanciamento_id as refi_id, ROUND(SUM($coalesce), 2) as valor_total");

        if ($hasPm && $pmValCol) {
            $itemsAgg->leftJoin('pagamentos_mensalidades as pm', 'pm.id', '=', 'ri.pagamento_mensalidade_id');
        }
        if ($hasTp && $tpValCol) {
            $itemsAgg->leftJoin('tesouraria_pagamentos as tp', 'tp.id', '=', 'ri.tesouraria_pagamento_id');
        }

        $itemsAgg->groupBy('ri.refinanciamento_id');
    }

    $valorTotalExpr = $itemsAgg ? "COALESCE(it.valor_total, 0)" : ($rfValCol ? "COALESCE(rf.$rfValCol, 0)" : "0");

    // ✅ NOVO: repasse usa percentual vigente (agente_margens)
    $repasseExpr = "ROUND(($valorTotalExpr) * (" . number_format($percVigente, 2, '.', '') . " / 100), 2)";

    // =========================
    // BASE
    // =========================
    $base = \Illuminate\Support\Facades\DB::table('refinanciamentos as rf')
        ->join('agente_cadastros as c', 'c.id', '=', "rf.$joinKey");

    if ($itemsAgg) {
        $base->leftJoinSub($itemsAgg, 'it', function($j){
            $j->on('it.refi_id', '=', 'rf.id');
        });
    }

    $applyOwner($base);
    $applyFilters($base);

    // =========================
    // COUNTS
    // =========================
    $countsQ = \Illuminate\Support\Facades\DB::table('refinanciamentos as rf')
        ->join('agente_cadastros as c', 'c.id', '=', "rf.$joinKey");

    if ($itemsAgg) {
        $countsQ->leftJoinSub($itemsAgg, 'it', function($j){
            $j->on('it.refi_id', '=', 'rf.id');
        });
    }

    $applyOwner($countsQ);
    $applyFilters($countsQ);

    $countsRow = $countsQ->selectRaw("
        COUNT(*) as total,
        SUM(CASE WHEN LOWER(TRIM(rf.status))='done' THEN 1 ELSE 0 END) as done,
        SUM(CASE WHEN LOWER(TRIM(rf.status))='failed' THEN 1 ELSE 0 END) as failed,
        SUM(CASE WHEN LOWER(TRIM(rf.status))='reverted' THEN 1 ELSE 0 END) as reverted
    ")->first();

    $counts = [
        'total'    => (int)($countsRow->total ?? 0),
        'done'     => (int)($countsRow->done ?? 0),
        'failed'   => (int)($countsRow->failed ?? 0),
        'reverted' => (int)($countsRow->reverted ?? 0),
    ];

    // =========================
    // Comprovantes: só do AGENTE
    // =========================
    $hasRc = \Illuminate\Support\Facades\Schema::hasTable('refinanciamento_comprovantes');
    $rcHasKind = $hasRc && \Illuminate\Support\Facades\Schema::hasColumn('refinanciamento_comprovantes', 'kind');

    $rcWhereAgente = "";
    if ($hasRc && $rcHasKind) {
        $rcWhereAgente = " AND LOWER(TRIM(rc.kind)) = 'agente' ";
    } elseif ($hasRc) {
        $rcWhereAgente = "";
    }

    $compsCountSql = $hasRc
        ? "(
            SELECT COUNT(*)
            FROM refinanciamento_comprovantes rc
            WHERE rc.refinanciamento_id = rf.id
            $rcWhereAgente
          )"
        : "0";

    $compsPackSql = $hasRc
        ? "(
            SELECT GROUP_CONCAT(CONCAT_WS('@@',
                rc.id,
                COALESCE(rc.kind,''),
                COALESCE(rc.path,''),
                COALESCE(rc.original_name,''),
                COALESCE(rc.mime,'')
            ) SEPARATOR '||')
            FROM refinanciamento_comprovantes rc
            WHERE rc.refinanciamento_id = rf.id
            $rcWhereAgente
          )"
        : "''";

    // =========================
    // LISTA
    // =========================
    $rows = $base->selectRaw("
        rf.id,
        rf.cpf_cnpj,
        rf.nome_snapshot,
        rf.cycle_key,
        rf.ref1, rf.ref2, rf.ref3,
        rf.executed_at,
        rf.status,
        rf.created_at,

        c.id as cadastro_id,
        c.full_name as cadastro_nome,
        c.cpf_cnpj as cadastro_cpf,
        c.contrato_codigo_contrato as contrato_codigo,
        c.agente_responsavel as agente_responsavel,

        $valorTotalExpr as valor_total,
        $repasseExpr as repasse_valor,

        " . number_format($percVigente, 2, '.', '') . " as repasse_percentual,

        $compsCountSql as comprovantes_count,
        $compsPackSql  as comprovantes_pack
    ")
    ->orderByDesc('rf.id')
    ->paginate($perPage)
    ->withQueryString();

    return view('agente.refinanciados', [
        'rows'      => $rows,
        'q'         => $q,
        'st'        => $st,
        'cycle'     => $cycle,
        'counts'    => $counts,
        'ownerMode' => $ownerMode,
    ]);
}



public function solicitarRefinanciamento(Request $request, \App\Models\AgenteCadastro $cadastro)
{
    $rid = (string) \Illuminate\Support\Str::uuid();

    // 1) Garantias básicas
    if (!\Illuminate\Support\Facades\Schema::hasTable('pagamentos_mensalidades')) {
        \Log::warning('[AGENTE][solicitarRefinanciamento] NO_TABLE', ['rid'=>$rid]);
        return back()->withErrors(['refi' => 'Tabela pagamentos_mensalidades não existe.']);
    }
    if (!\Illuminate\Support\Facades\Schema::hasColumn('pagamentos_mensalidades', 'agente_refi_solicitado')) {
        \Log::warning('[AGENTE][solicitarRefinanciamento] NO_COL', ['rid'=>$rid]);
        return back()->withErrors(['refi' => 'Coluna agente_refi_solicitado não existe em pagamentos_mensalidades.']);
    }

    // 2) Autorização: só o agente dono do cadastro pode solicitar
    $user   = \Illuminate\Support\Facades\Auth::user();
    $uid    = (int) ($user->id ?? 0);
    $meName = trim((string) ($user->name ?? ''));

    $ownerCol = null;
    foreach (['created_by_user_id', 'agente_user_id', 'user_id', 'agente_id'] as $col) {
        if (\Illuminate\Support\Facades\Schema::hasColumn('agente_cadastros', $col)) { $ownerCol = $col; break; }
    }

    $belongsToMe = false;
    if ($ownerCol) {
        $belongsToMe = ((int)($cadastro->{$ownerCol} ?? 0) === $uid);
    } else {
        $belongsToMe = (
            ($meName !== '') &&
            (
                (string)($cadastro->agente_responsavel ?? '') === $meName ||
                (string)($cadastro->agente_filial ?? '') === $meName
            )
        );
    }

    if (!$belongsToMe) {
        \Log::warning('[AGENTE][solicitarRefinanciamento] FORBIDDEN', [
            'rid'=>$rid,'user_id'=>$uid,'me'=>$meName,'cadastro_id'=>$cadastro->id
        ]);
        abort(403, 'Você não tem permissão para solicitar refinanciamento deste contrato.');
    }

    // 3) Detecta colunas úteis
    $PM = 'pagamentos_mensalidades';

    $pmAgIdCol = null;
    foreach (['agente_cadastro_id','cadastro_id','agenteCadastroId','cadastroId'] as $c) {
        if (\Illuminate\Support\Facades\Schema::hasColumn($PM, $c)) { $pmAgIdCol = $c; break; }
    }

    $pmCpfCol = null;
    foreach (['cpf_cnpj','cpf','cpfCnpj','documento'] as $c) {
        if (\Illuminate\Support\Facades\Schema::hasColumn($PM, $c)) { $pmCpfCol = $c; break; }
    }

    $pmRefCol = \Illuminate\Support\Facades\Schema::hasColumn($PM, 'referencia_month') ? 'referencia_month' : null;

    $cpfDigits = preg_replace('/\D+/', '', (string) ($cadastro->cpf_cnpj ?? ''));

    // Normalizador SQL simples (sem REGEXP_REPLACE)
    $sqlCpfNorm = function (string $expr) {
        return "REPLACE(REPLACE(REPLACE(REPLACE(TRIM($expr),'.',''),'-',''),'/',''),' ','')";
    };

    // ==========================================================
    // ✅ BLOQUEAR SOLICITAÇÃO se CPF já estiver em refinanciamentos (done)
    // ==========================================================
    if ($cpfDigits !== '' && \Illuminate\Support\Facades\Schema::hasTable('refinanciamentos')) {

        $refTable = 'refinanciamentos';

        $refCpfCol = \Illuminate\Support\Facades\Schema::hasColumn($refTable, 'cpf_cnpj') ? 'cpf_cnpj'
                   : (\Illuminate\Support\Facades\Schema::hasColumn($refTable, 'cpf') ? 'cpf' : null);

        $hasStatus = \Illuminate\Support\Facades\Schema::hasColumn($refTable, 'status');

        $refQ = \Illuminate\Support\Facades\DB::table("$refTable as rf");

        $refQ->where(function($w) use ($refCpfCol, $cpfDigits, $sqlCpfNorm, $cadastro, $refTable) {

            $did = false;

            if ($refCpfCol) {
                $w->whereRaw($sqlCpfNorm("rf.$refCpfCol")." = ?", [$cpfDigits]);
                $did = true;
            }

            foreach (['orig_agente_cadastro_id','agente_cadastro_id'] as $col) {
                if (\Illuminate\Support\Facades\Schema::hasColumn($refTable, $col)) {
                    if ($did) $w->orWhere("rf.$col", '=', (int)$cadastro->id);
                    else { $w->where("rf.$col", '=', (int)$cadastro->id); $did = true; }
                }
            }

            if (!$did) {
                $w->whereRaw('1=0');
            }
        });

        if ($hasStatus) {
            $doneList = ['done','ok','concluido','concluído','concluido.','concluído.','finalizado','finalizada','aprovado','aprovada'];
            $refQ->whereIn(\Illuminate\Support\Facades\DB::raw("LOWER(TRIM(rf.status))"), $doneList);
        }

        if ($refQ->exists()) {
            \Log::info('[AGENTE][solicitarRefinanciamento] BLOCK_ALREADY_REFINANCED', [
                'rid'         => $rid,
                'user_id'     => $uid,
                'cadastro_id' => $cadastro->id,
                'cpf'         => $cpfDigits,
            ]);

            return redirect()
                ->route('agente.contratos')
                ->withErrors(['refi' => 'CPF já refinanciado. Solicitação bloqueada para este contrato.'])
                ->with('refi_ja_refinanciado_contrato_id', $cadastro->id);
        }
    }
    // ==========================================================

    // 4) refs
    $toMonthStartIso = function ($v) {
        if (!$v) return null;
        $s = trim((string)$v);
        if ($s === '') return null;
        try {
            return \Carbon\Carbon::parse($s)->startOfMonth()->toDateString(); // YYYY-MM-01
        } catch (\Throwable $e) {
            return null;
        }
    };

    $refs = array_values(array_filter([
        $toMonthStartIso($request->input('ref1')),
        $toMonthStartIso($request->input('ref2')),
        $toMonthStartIso($request->input('ref3')),
    ]));

    // request_key (define “qual solicitação” é essa)
    $requestKey = (count($refs) > 0) ? implode('|', $refs) : 'ALL';

    // 5) Atualiza + cria registro na fila/lock
    $affected = 0;

    $affected = \Illuminate\Support\Facades\DB::transaction(function () use (
        $PM, $pmAgIdCol, $pmCpfCol, $pmRefCol, $cpfDigits, $sqlCpfNorm, $cadastro, $refs,
        $uid, $rid, $requestKey
    ) {

        $qb = \Illuminate\Support\Facades\DB::table($PM);

        // por ID (se existir)
        if ($pmAgIdCol) {
            $qb->where($pmAgIdCol, '=', (int)$cadastro->id);
        } else {
            if ($pmCpfCol && $cpfDigits !== '') {
                $qb->whereRaw($sqlCpfNorm("{$PM}.{$pmCpfCol}")." = ?", [$cpfDigits]);
            } else {
                throw new \RuntimeException('Não consegui vincular pagamentos ao contrato (sem agente_cadastro_id e sem CPF).');
            }
        }

        // inclui órfãos por CPF (quando existir)
        if ($pmCpfCol && $cpfDigits !== '') {
            $qb->orWhere(function($w) use ($PM, $pmCpfCol, $pmAgIdCol, $cpfDigits, $sqlCpfNorm) {
                if ($pmAgIdCol) {
                    $w->where(function($x) use ($pmAgIdCol){
                        $x->whereNull($pmAgIdCol)->orWhere($pmAgIdCol, 0);
                    });
                }
                $w->whereRaw($sqlCpfNorm("{$PM}.{$pmCpfCol}")." = ?", [$cpfDigits]);
            });
        }

        if ($pmRefCol && count($refs) > 0) {
            $qb->whereIn($pmRefCol, $refs);
        }

        $affectedLocal = $qb->update([
            'agente_refi_solicitado' => 1,
            'updated_at'             => now(),
        ]);

        // ✅ NOVO: cria/atualiza a fila/lock da solicitação (se a tabela existir)
        if (\Illuminate\Support\Facades\Schema::hasTable('refinanciamento_assumptions')) {

            $tb = 'refinanciamento_assumptions';

            // trava a linha se existir
            $row = \Illuminate\Support\Facades\DB::table($tb)
                ->where('agente_cadastro_id', (int)$cadastro->id)
                ->where('request_key', $requestKey)
                ->lockForUpdate()
                ->first();

            $base = [
                'cpf_cnpj'              => $cpfDigits !== '' ? $cpfDigits : null,
                'refs_json'             => (count($refs) > 0) ? json_encode($refs, JSON_UNESCAPED_UNICODE) : null,
                'solicitado_por_user_id'=> $uid ?: null,
                'solicitado_em'         => now(),
                'updated_at'            => now(),
            ];

            if (!$row) {
                \Illuminate\Support\Facades\DB::table($tb)->insert(array_merge($base, [
                    'agente_cadastro_id' => (int)$cadastro->id,
                    'request_key'        => $requestKey,
                    'status'             => 'liberado',
                    'analista_id'         => null,
                    'liberado_em'         => now(),
                    'assumido_em'         => null,
                    'finalizado_em'       => null,
                    'heartbeat_at'        => null,
                    'created_at'          => now(),
                ]));

            } else {
                // Se já está assumido por outro analista, NÃO sobrescreve o lock
                $rowStatus = (string)($row->status ?? '');
                $rowAnal   = (int)($row->analista_id ?? 0);

                if ($rowStatus === 'assumido' && $rowAnal > 0) {
                    \Illuminate\Support\Facades\DB::table($tb)
                        ->where('id', (int)$row->id)
                        ->update($base);
                } else {
                    // Se não está assumido, “recoloca” na fila como liberado
                    \Illuminate\Support\Facades\DB::table($tb)
                        ->where('id', (int)$row->id)
                        ->update(array_merge($base, [
                            'status'       => 'liberado',
                            'analista_id'   => null,
                            'liberado_em'   => now(),
                            'assumido_em'   => null,
                            'finalizado_em' => null,
                            'heartbeat_at'  => null,
                        ]));
                }
            }
        } else {
            \Log::warning('[AGENTE][solicitarRefinanciamento] ASSUMPTION_TABLE_MISSING', [
                'rid'         => $rid,
                'cadastro_id' => (int)$cadastro->id,
                'request_key' => $requestKey,
            ]);
        }

        return $affectedLocal;
    });

    \Log::info('[AGENTE][solicitarRefinanciamento] OK', [
        'rid'         => $rid,
        'user_id'     => $uid,
        'cadastro_id' => $cadastro->id,
        'request_key' => $requestKey,
        'refs'        => $refs,
        'affected'    => $affected,
    ]);

    return redirect()
        ->route('agente.contratos')
        ->with('ok', 'Solicitação de refinanciamento enviada.')
        ->with('refi_solicitada_contrato_id', $cadastro->id);
}

public function painelAgente(Request $request)
{
    $user = $request->user();

    Log::info('[AGENTE][painel] hit', [
        'user_id'                 => optional($user)->id,
        'user_cpf_cnpj'           => $user->cpf_cnpj ?? null,
        'user_agente_cadastro_id' => $user->agente_cadastro_id ?? null,
        'query'                   => $request->query(),
        'ip'                      => $request->ip(),
    ]);

    // ===================== RESOLVE AGENTE =====================
    $agenteQuery = AgenteCadastro::query();

    if (!empty($user->cpf_cnpj)) {
        $cpfLimpo = preg_replace('/\D/', '', $user->cpf_cnpj);
        $agenteQuery->where('cpf_cnpj', $cpfLimpo);
    }

    if (!empty($user->agente_cadastro_id)) {
        $agenteQuery->orWhere('id', $user->agente_cadastro_id);
    }

    $agente = $agenteQuery->first();

    if (!$agente) {
        Log::warning('[AGENTE][painel] agente_nao_encontrado', [
            'user_id'   => optional($user)->id,
            'cpf_cnpj'  => $user->cpf_cnpj ?? null,
        ]);

        return response()->json([
            'total'            => 0,
            'pagamentos'       => [],
            'refinanciamentos' => [],
        ]);
    }

    // nome do associado (cadastro)
    $agenteNome = $agente->full_name
        ?? $agente->nome
        ?? $agente->name
        ?? $agente->agente_nome
        ?? null;

    // nome do usuário logado (Agente Padrão)
    $userNome = $user && $user->name ? trim($user->name) : null;

    Log::info('[AGENTE][painel] agente_resolvido', [
        'agente_id'   => $agente->id,
        'agente_cpf'  => $agente->cpf_cnpj,
        'agente_nome' => $agenteNome,
        'user_name'   => $userNome,
    ]);

    // ===================== ÚLTIMO PAGAMENTO TESOURARIA =====================
    $pagamentos           = [];
    $pagCount             = 0;
    $hasTesPagTable       = Schema::hasTable('tesouraria_pagamentos');
    $ultimoPagamentoBase  = null;   // base numérica para calcular 10% e 5%

    if ($hasTesPagTable) {
        $ult = DB::table('tesouraria_pagamentos')
            ->where('agente_cadastro_id', $agente->id)
            ->where('status', 'pago')
            ->orderByDesc('paid_at')
            ->orderByDesc('id')
            ->first();

        if ($ult) {
            // define base do pagamento (usaremos a mesma para 10% e 5%)
            if (isset($ult->valor_pago) && !is_null($ult->valor_pago)) {
                $ultimoPagamentoBase = (float) $ult->valor_pago;
            } elseif (isset($ult->valor) && !is_null($ult->valor)) {
                $ultimoPagamentoBase = (float) $ult->valor;
            }

            // calcula repasse 10% em cima da base
            $valorBase10 = null;
            if ($ultimoPagamentoBase !== null) {
                $valorBase10 = round($ultimoPagamentoBase * 0.10, 2);
            }

            $pagamentos[] = [
                'id'                      => $ult->id,
                'contrato'                => $ult->contrato_codigo_contrato ?? $ult->contrato ?? null,
                'valor_pago'              => $ultimoPagamentoBase ?? 0,
                'forma_pagamento'         => $ult->forma_pagamento ?? null,
                'paid_at'                 => $ult->paid_at
                    ? Carbon::parse($ult->paid_at)->format('d/m/Y H:i')
                    : null,
                'repasse_agente_10'       => $valorBase10,
                'valor_repasse_agente_10' => $valorBase10,
            ];
            $pagCount = 1;

            Log::info('[AGENTE][painel] ultimo_pagamento', [
                'found'        => true,
                'id'           => $ult->id,
                'status'       => $ult->status,
                'paid_at'      => $ult->paid_at,
                'base'         => $ultimoPagamentoBase,
                'repasse10'    => $valorBase10,
            ]);
        } else {
            Log::info('[AGENTE][painel] ultimo_pagamento', ['found' => false]);
        }
    }

    // ===================== REFINANCIAMENTOS =====================
    $refinanciamentos = [];
    $refCount         = 0;

    $hasRefTable  = Schema::hasTable('refinanciamentos');
    $hasCompTable = Schema::hasTable('refinanciamento_comprovantes');

    $hasStatusCol          = $hasRefTable  && Schema::hasColumn('refinanciamentos', 'status');
    $hasRefAgCol           = $hasRefTable  && Schema::hasColumn('refinanciamentos', 'agente_cadastro_id');
    $hasRefAgSnap          = $hasRefTable  && Schema::hasColumn('refinanciamentos', 'agente_snapshot');
    $hasRefCpfCol          = $hasRefTable  && Schema::hasColumn('refinanciamentos', 'cpf_cnpj');
    $hasRefCycleKey        = $hasRefTable  && Schema::hasColumn('refinanciamentos', 'cycle_key');
    $hasRefExecAtCol       = $hasRefTable  && Schema::hasColumn('refinanciamentos', 'executed_at');
    $hasRefContratoOrigCol = $hasRefTable  && Schema::hasColumn('refinanciamentos', 'contrato_origem');
    $hasRefContratoNovoCol = $hasRefTable  && Schema::hasColumn('refinanciamentos', 'contrato_novo');
    $hasRefNomeSnapCol     = $hasRefTable  && Schema::hasColumn('refinanciamentos', 'nome_snapshot');

    $hasCompAgCol   = $hasCompTable && Schema::hasColumn('refinanciamento_comprovantes', 'agente_cadastro_id');
    $hasCompAgSnap  = $hasCompTable && Schema::hasColumn('refinanciamento_comprovantes', 'agente_snapshot');
    $hasCompKind    = $hasCompTable && Schema::hasColumn('refinanciamento_comprovantes', 'kind');

    $allowedStatus = [
        'done','ok',
        'concluido','concluído','concluido.','concluído.',
        'enabled','enable','habilitado',
        'ativo','actived','active',
    ];

    Log::info('[AGENTE][painel] refi_env', [
        'hasRefTable'           => $hasRefTable,
        'hasCompTable'          => $hasCompTable,
        'hasStatusCol'          => $hasStatusCol,
        'hasCompAgCol'          => $hasCompAgCol,
        'hasCompAgSnap'         => $hasCompAgSnap,
        'hasCompKind'           => $hasCompKind,
        'hasRefAgCol'           => $hasRefAgCol,
        'hasRefAgSnap'          => $hasRefAgSnap,
        'hasRefCpfCol'          => $hasRefCpfCol,
        'hasRefContratoOrigCol' => $hasRefContratoOrigCol,
        'hasRefContratoNovoCol' => $hasRefContratoNovoCol,
        'hasRefCycleKeyCol'     => $hasRefCycleKey,
        'hasRefExecutedAtCol'   => $hasRefExecAtCol,
        'hasRefNomeSnapCol'     => $hasRefNomeSnapCol,
        'status_list'           => $allowedStatus,
        'snapshot_user_name'    => $userNome,
    ]);

    /**
     * Helper para repasse 5%:
     * usa a mesma base do último pagamento (se existir).
     */
    $computeRefiRepasse = function () use ($ultimoPagamentoBase) {
        if ($ultimoPagamentoBase === null) {
            return null;
        }
        return round($ultimoPagamentoBase * 0.05, 2);
    };

    if ($hasRefTable) {

        // ---------- 1ª TENTATIVA: via refinanciamento_comprovantes ----------
        $rcCandidate = null;

        if ($hasCompTable && ($hasCompAgCol || $hasCompAgSnap)) {

            $rcCountById = $hasCompAgCol
                ? DB::table('refinanciamento_comprovantes')
                    ->where('agente_cadastro_id', $agente->id)
                    ->count()
                : 0;

            $rcCountBySnap = ($hasCompAgSnap && ($agenteNome || $userNome))
                ? DB::table('refinanciamento_comprovantes')
                    ->where(function ($q) use ($agenteNome, $userNome) {
                        if ($agenteNome) {
                            $q->orWhere('agente_snapshot', $agenteNome);
                        }
                        if ($userNome) {
                            $q->orWhere('agente_snapshot', $userNome);
                        }
                    })
                    ->count()
                : 0;

            Log::info('[AGENTE][painel] rc_counts', [
                'by_agente_cadastro_id' => $rcCountById,
                'by_agente_snapshot'    => $rcCountBySnap,
            ]);

            $select = [
                'rc.id as rc_id',
                'rc.created_at as rc_created_at',
            ];

            if ($hasCompKind)   $select[] = 'rc.kind as rc_kind';
            if ($hasCompAgCol)  $select[] = 'rc.agente_cadastro_id as rc_agente_id';
            if ($hasCompAgSnap) $select[] = 'rc.agente_snapshot as rc_agente_snapshot';

            // ID do refinanciamento
            $select[] = 'r.id as refin_id';

            if ($hasStatusCol)          $select[] = 'r.status as ref_status';
            if ($hasRefCpfCol)          $select[] = 'r.cpf_cnpj';
            if ($hasRefContratoOrigCol) $select[] = 'r.contrato_origem';
            if ($hasRefContratoNovoCol) $select[] = 'r.contrato_novo';
            if ($hasRefCycleKey)        $select[] = 'r.cycle_key';
            if ($hasRefExecAtCol)       $select[] = 'r.executed_at';
            if ($hasRefNomeSnapCol)     $select[] = 'r.nome_snapshot as ref_nome_snapshot';

            $base = DB::table('refinanciamento_comprovantes as rc')
                ->join('refinanciamentos as r', 'r.id', '=', 'rc.refinanciamento_id')
                ->select($select)
                ->where(function ($w) use ($agente, $agenteNome, $userNome, $hasCompAgCol, $hasCompAgSnap) {
                    $w->whereRaw('1=0');
                    if ($hasCompAgCol) {
                        $w->orWhere('rc.agente_cadastro_id', $agente->id);
                    }
                    if ($hasCompAgSnap && $agenteNome) {
                        $w->orWhere('rc.agente_snapshot', $agenteNome);
                    }
                    if ($hasCompAgSnap && $userNome) {
                        $w->orWhere('rc.agente_snapshot', $userNome);
                    }
                });

            // 🔹 AQUI: para o AGENTE, pega só comprovante com kind = 'agente'
            if ($hasCompKind) {
                $base->where('rc.kind', 'agente');
            }

            $rcCandidate = $base
                ->orderByDesc('rc_created_at')
                ->orderByDesc('rc_id')
                ->first();

            Log::info('[AGENTE][painel] rc_candidate', [
                'found'      => (bool) $rcCandidate,
                'rc_id'      => $rcCandidate->rc_id          ?? null,
                'rc_created' => $rcCandidate->rc_created_at  ?? null,
                'rc_kind'    => $rcCandidate->rc_kind        ?? null,
                'rc_ag_id'   => $rcCandidate->rc_agente_id   ?? null,
                'rc_ag_snap' => $rcCandidate->rc_agente_snapshot ?? null,
                'refin_id'   => $rcCandidate->refin_id       ?? null,
                'ref_status' => $rcCandidate->ref_status     ?? null,
                'cycle_key'  => $rcCandidate->cycle_key      ?? null,
            ]);

            if ($rcCandidate && $hasStatusCol) {
                $st        = strtolower((string) $rcCandidate->ref_status);
                $isAllowed = in_array($st, array_map('strtolower', $allowedStatus), true);

                Log::info('[AGENTE][painel] rc_after_status_filter', [
                    'found'            => $isAllowed,
                    'ref_status_found' => $rcCandidate->ref_status,
                ]);

                if (!$isAllowed) {
                    $rcCandidate = null;
                }
            }

            if ($rcCandidate) {
                $repasse5 = $computeRefiRepasse();

                $refinanciamentos[] = [
                    'cpf_cnpj'         => $rcCandidate->cpf_cnpj        ?? null,
                    'contrato_origem'  => $rcCandidate->contrato_origem ?? null,
                    'contrato_novo'    => $rcCandidate->contrato_novo   ?? null,
                    'cycle_key'        => $rcCandidate->cycle_key       ?? null,
                    'executed_at'      => ($hasRefExecAtCol && $rcCandidate->executed_at)
                        ? Carbon::parse($rcCandidate->executed_at)->format('d/m/Y H:i')
                        : null,
                    'associado_nome'   => $rcCandidate->ref_nome_snapshot ?? '-',
                    'repasse_agente_5' => $repasse5,
                    // 🔹 ID do comprovante para o front montar o link
                    'comprovante_id'   => $rcCandidate->rc_id,
                ];
                $refCount = 1;

                Log::info('[AGENTE][painel] refi_card', [
                    'source'        => 'comprovantes',
                    'refin_id'      => $rcCandidate->refin_id ?? null,
                    'associado'     => $rcCandidate->ref_nome_snapshot ?? null,
                    'repasse_5'     => $repasse5,
                    'base_global'   => $ultimoPagamentoBase,
                    'comprovante_id'=> $rcCandidate->rc_id,
                ]);
            }
        }

        // ---------- 2ª TENTATIVA (FALLBACK): direto em refinanciamentos ----------
        if ($refCount === 0 && ($hasRefAgCol || $hasRefAgSnap)) {

            $selectFb = ['r.id'];

            if ($hasStatusCol)          $selectFb[] = 'r.status';
            if ($hasRefCpfCol)          $selectFb[] = 'r.cpf_cnpj';
            if ($hasRefContratoOrigCol) $selectFb[] = 'r.contrato_origem';
            if ($hasRefContratoNovoCol) $selectFb[] = 'r.contrato_novo';
            if ($hasRefCycleKey)        $selectFb[] = 'r.cycle_key';
            if ($hasRefExecAtCol)       $selectFb[] = 'r.executed_at';
            if ($hasRefAgCol)           $selectFb[] = 'r.agente_cadastro_id';
            if ($hasRefAgSnap)          $selectFb[] = 'r.agente_snapshot';
            if ($hasRefNomeSnapCol)     $selectFb[] = 'r.nome_snapshot as ref_nome_snapshot';

            $fb = DB::table('refinanciamentos as r')
                ->select($selectFb)
                ->where(function ($w) use ($agente, $agenteNome, $userNome, $hasRefAgCol, $hasRefAgSnap) {
                    $w->whereRaw('1=0');
                    if ($hasRefAgCol) {
                        $w->orWhere('r.agente_cadastro_id', $agente->id);
                    }
                    if ($hasRefAgSnap && $agenteNome) {
                        $w->orWhere('r.agente_snapshot', $agenteNome);
                    }
                    if ($hasRefAgSnap && $userNome) {
                        $w->orWhere('r.agente_snapshot', $userNome);
                    }
                });

            if ($hasStatusCol) {
                $fb->whereIn('r.status', $allowedStatus);
            }

            if ($hasRefExecAtCol) {
                $fb->orderByDesc('r.executed_at');
            }
            $fb->orderByDesc('r.id');

            $refRow = $fb->first();

            Log::info('[AGENTE][painel] refi_fallback', [
                'found'       => (bool) $refRow,
                'refin_id'    => $refRow->id                 ?? null,
                'ref_status'  => $refRow->status             ?? null,
                'agente_id'   => $refRow->agente_cadastro_id ?? null,
                'agente_snap' => $refRow->agente_snapshot    ?? null,
            ]);

            if ($refRow) {
                $repasse5 = $computeRefiRepasse();

                $refinanciamentos[] = [
                    'cpf_cnpj'         => $refRow->cpf_cnpj        ?? null,
                    'contrato_origem'  => $refRow->contrato_origem ?? null,
                    'contrato_novo'    => $refRow->contrato_novo   ?? null,
                    'cycle_key'        => $refRow->cycle_key       ?? null,
                    'executed_at'      => ($hasRefExecAtCol && $refRow->executed_at)
                        ? Carbon::parse($refRow->executed_at)->format('d/m/Y H:i')
                        : null,
                    'associado_nome'   => $refRow->ref_nome_snapshot ?? '-',
                    'repasse_agente_5' => $repasse5,
                    // aqui não tem comprovante ligado diretamente
                    'comprovante_id'   => null,
                ];
                $refCount = 1;

                Log::info('[AGENTE][painel] refi_card', [
                    'source'        => 'refinanciamentos_fallback',
                    'refin_id'      => $refRow->id ?? null,
                    'associado'     => $refRow->ref_nome_snapshot ?? null,
                    'repasse_5'     => $repasse5,
                    'base_global'   => $ultimoPagamentoBase,
                    'comprovante_id'=> null,
                ]);
            }
        }

        // DEBUG: amostra de status por agente / snapshot
        if ($hasStatusCol && ($hasRefAgCol || $hasRefAgSnap)) {
            $sampQ = DB::table('refinanciamentos as r')
                ->select('r.status')
                ->whereNotNull('r.status')
                ->where(function ($w) use ($agente, $agenteNome, $userNome, $hasRefAgCol, $hasRefAgSnap) {
                    $w->whereRaw('1=0');
                    if ($hasRefAgCol) {
                        $w->orWhere('r.agente_cadastro_id', $agente->id);
                    }
                    if ($hasRefAgSnap && $agenteNome) {
                        $w->orWhere('r.agente_snapshot', $agenteNome);
                    }
                    if ($hasRefAgSnap && $userNome) {
                        $w->orWhere('r.agente_snapshot', $userNome);
                    }
                })
                ->limit(15);

            $samples = $sampQ->pluck('status');

            Log::warning('[AGENTE][painel] status_samples_for_agent', [
                'samples' => $samples,
                'allowed' => $allowedStatus,
            ]);
        }
    }

    $total = $pagCount + $refCount;

    Log::info('[AGENTE][painel] out', [
        'total'     => $total,
        'pag_count' => $pagCount,
        'ref_count' => $refCount,
    ]);

    return response()->json([
        'total'            => $total,
        'pagamentos'       => $pagamentos,
        'refinanciamentos' => $refinanciamentos,
    ]);
}







}
