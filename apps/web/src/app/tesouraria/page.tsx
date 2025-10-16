"use client";

import React, { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { 
  Button, 
  Input, 
  Card, 
  CardBody, 
  CardHeader,
  Chip,
  Dropdown,
  DropdownTrigger,
  DropdownMenu,
  DropdownItem,
  Pagination,
  Spinner,
  Progress
} from '@heroui/react';
import { DataTable, StatusBadge, useToast } from '@abase/ui';
import { useAuth } from '@/contexts/AuthContext';
import { useTesourariaSSE } from '@/hooks/useSSEEvents';
import { formatDate, formatCurrency, formatCPF } from '@/lib/formatters';
import { 
  SearchIcon, 
  MoreVerticalIcon, 
  EyeIcon,
  WifiIcon,
  WifiOffIcon,
  DollarSignIcon,
  FileTextIcon,
  CheckCircleIcon,
  ClockIcon,
  AlertCircleIcon
} from 'lucide-react';

interface Associado {
  id: number;
  nome: string;
  cpf: string;
  email?: string;
}

interface Cadastro {
  id: number;
  associado_id: number;
  associado?: Associado;
  status: string;
  valor_total?: number;
  created_at: string;
  updated_at: string;
  approved_at?: string;
  payment_received_at?: string;
  contract_generated_at?: string;
  contract_signed_at?: string;
  completed_at?: string;
}

interface TesourariaFilters {
  search: string;
  status: string;
  dateFrom: string;
  dateTo: string;
}

export default function TesourariaPage() {
  const router = useRouter();
  const { apiClient, user } = useAuth();
  const { addToast } = useToast();
  
  // State
  const [cadastros, setCadastros] = useState<Cadastro[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [filters, setFilters] = useState<TesourariaFilters>({
    search: "",
    status: "APROVADO",
    dateFrom: "",
    dateTo: ""
  });
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);

  const itemsPerPage = 10;

  // SSE integration
  const { isConnected } = useTesourariaSSE(() => {
    // Refresh data when SSE events are received
    fetchCadastros(currentPage, filters);
  });

  // Fetch cadastros for treasury
  const fetchCadastros = async (page: number = 1, searchParams?: TesourariaFilters) => {
    if (!apiClient) return;

    try {
      setLoading(true);
      setError("");

      const params = new URLSearchParams({
        page: page.toString(),
        limit: itemsPerPage.toString(),
        status: 'APROVADO,PAGAMENTO_PENDENTE,PAGAMENTO_RECEBIDO,CONTRATO_GERADO,ENVIADO_ASSINATURA,ASSINADO,CONCLUIDO', // Only show cadastros in treasury pipeline
      });

      if (searchParams?.search) {
        params.append('search', searchParams.search);
      }

      if (searchParams?.status && searchParams.status !== 'all') {
        params.append('status', searchParams.status);
      }

      if (searchParams?.dateFrom) {
        params.append('date_from', searchParams.dateFrom);
      }

      if (searchParams?.dateTo) {
        params.append('date_to', searchParams.dateTo);
      }

      const response = await apiClient.get<{
        items: Cadastro[];
        total: number;
        page: number;
        pages: number;
      }>(`/api/v1/tesouraria/cadastros?${params}`);

      if (response.error) {
        throw new Error(response.error.message);
      }

      if (response.data) {
        setCadastros(response.data.items);
        setTotalItems(response.data.total);
        setTotalPages(response.data.pages);
        setCurrentPage(response.data.page);
      }
    } catch (err: any) {
      console.error('Error fetching cadastros for treasury:', err);
      setError(err.message || 'Erro ao carregar cadastros para tesouraria');
      
      // Mock data for development
      const mockCadastros: Cadastro[] = [
        {
          id: 1,
          associado_id: 1,
          associado: {
            id: 1,
            nome: "João Silva",
            cpf: "12345678901",
            email: "joao@email.com"
          },
          status: "APROVADO",
          valor_total: 200.00,
          created_at: "2024-01-15T10:30:00Z",
          updated_at: "2024-01-15T10:30:00Z",
          approved_at: "2024-01-15T14:20:00Z"
        },
        {
          id: 2,
          associado_id: 2,
          associado: {
            id: 2,
            nome: "Maria Santos",
            cpf: "98765432100",
            email: "maria@email.com"
          },
          status: "PAGAMENTO_RECEBIDO",
          valor_total: 250.00,
          created_at: "2024-01-14T14:20:00Z",
          updated_at: "2024-01-16T09:15:00Z",
          approved_at: "2024-01-15T09:15:00Z",
          payment_received_at: "2024-01-16T09:15:00Z"
        },
        {
          id: 3,
          associado_id: 3,
          associado: {
            id: 3,
            nome: "Pedro Oliveira",
            cpf: "11122233344",
            email: "pedro@email.com"
          },
          status: "CONTRATO_GERADO",
          valor_total: 180.00,
          created_at: "2024-01-13T09:15:00Z",
          updated_at: "2024-01-17T11:30:00Z",
          approved_at: "2024-01-14T16:45:00Z",
          payment_received_at: "2024-01-16T14:20:00Z",
          contract_generated_at: "2024-01-17T11:30:00Z"
        },
        {
          id: 4,
          associado_id: 4,
          associado: {
            id: 4,
            nome: "Ana Costa",
            cpf: "55566677788",
            email: "ana@email.com"
          },
          status: "CONCLUIDO",
          valor_total: 300.00,
          created_at: "2024-01-10T16:45:00Z",
          updated_at: "2024-01-18T15:20:00Z",
          approved_at: "2024-01-12T11:30:00Z",
          payment_received_at: "2024-01-15T10:30:00Z",
          contract_generated_at: "2024-01-16T14:20:00Z",
          contract_signed_at: "2024-01-17T16:45:00Z",
          completed_at: "2024-01-18T15:20:00Z"
        }
      ];
      
      setCadastros(mockCadastros);
      setTotalItems(mockCadastros.length);
      setTotalPages(1);
      setCurrentPage(1);
    } finally {
      setLoading(false);
    }
  };

  // Initial load
  useEffect(() => {
    fetchCadastros(1, filters);
  }, [apiClient]);

  // Filtered data
  const filteredCadastros = useMemo(() => {
    let filtered = cadastros;

    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      filtered = filtered.filter(cadastro =>
        cadastro.associado?.nome.toLowerCase().includes(searchLower) ||
        cadastro.associado?.cpf.includes(filters.search) ||
        cadastro.id.toString().includes(filters.search)
      );
    }

    if (filters.status !== 'all') {
      filtered = filtered.filter(cadastro => cadastro.status === filters.status);
    }

    return filtered;
  }, [cadastros, filters]);

  // Handle search
  const handleSearch = (value: string) => {
    setFilters(prev => ({ ...prev, search: value }));
    setCurrentPage(1);
  };

  // Handle status filter
  const handleStatusFilter = (status: string) => {
    setFilters(prev => ({ ...prev, status }));
    setCurrentPage(1);
  };

  // Handle page change
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    fetchCadastros(page, filters);
  };

  // Get pipeline step
  const getPipelineStep = (cadastro: Cadastro) => {
    const steps = [
      { key: 'approved', label: 'Aprovado', status: 'APROVADO' },
      { key: 'payment', label: 'Pagamento', status: 'PAGAMENTO_RECEBIDO' },
      { key: 'contract', label: 'Contrato', status: 'CONTRATO_GERADO' },
      { key: 'signature', label: 'Assinatura', status: 'ENVIADO_ASSINATURA' },
      { key: 'signed', label: 'Assinado', status: 'ASSINADO' },
      { key: 'completed', label: 'Concluído', status: 'CONCLUIDO' }
    ];

    const currentStepIndex = steps.findIndex(step => step.status === cadastro.status);
    return {
      current: currentStepIndex >= 0 ? currentStepIndex + 1 : 0,
      total: steps.length,
      steps
    };
  };

  // Table columns
  const columns = [
    {
      key: "id",
      label: "ID",
      sortable: true,
    },
    {
      key: "associado",
      label: "Associado",
      sortable: true,
    },
    {
      key: "status",
      label: "Status",
      sortable: true,
    },
    {
      key: "valor_total",
      label: "Valor Total",
      sortable: true,
    },
    {
      key: "pipeline",
      label: "Pipeline",
      sortable: false,
    },
    {
      key: "approved_at",
      label: "Aprovado em",
      sortable: true,
    },
    {
      key: "actions",
      label: "Ações",
      sortable: false,
    },
  ];

  // Render cell content
  const renderCell = (cadastro: Cadastro, columnKey: React.Key) => {
    switch (columnKey) {
      case "id":
        return (
          <p className="text-bold text-small text-default-600">
            #{cadastro.id}
          </p>
        );
      
      case "associado":
        return (
          <div className="flex flex-col">
            <p className="text-bold text-small capitalize">
              {cadastro.associado?.nome || 'N/A'}
            </p>
            <p className="text-bold text-tiny capitalize text-default-400">
              CPF: {cadastro.associado?.cpf ? formatCPF(cadastro.associado.cpf) : 'N/A'}
            </p>
          </div>
        );
      
      case "status":
        return (
          <StatusBadge status={cadastro.status} size="sm" />
        );
      
      case "valor_total":
        return (
          <p className="text-bold text-small text-default-600">
            {cadastro.valor_total ? formatCurrency(cadastro.valor_total) : '-'}
          </p>
        );
      
      case "pipeline":
        const pipeline = getPipelineStep(cadastro);
        return (
          <div className="flex items-center gap-2">
            <Progress
              value={(pipeline.current / pipeline.total) * 100}
              size="sm"
              color="primary"
              className="flex-1"
            />
            <span className="text-xs text-default-500">
              {pipeline.current}/{pipeline.total}
            </span>
          </div>
        );
      
      case "approved_at":
        return (
          <p className="text-bold text-small text-default-600">
            {cadastro.approved_at ? formatDate(cadastro.approved_at) : '-'}
          </p>
        );
      
      case "actions":
        return (
          <div className="relative flex justify-end items-center gap-2">
            <Dropdown>
              <DropdownTrigger>
                <Button isIconOnly size="sm" variant="light">
                  <MoreVerticalIcon className="w-4 h-4" />
                </Button>
              </DropdownTrigger>
              <DropdownMenu>
                <DropdownItem
                  key="view"
                  startContent={<EyeIcon className="w-4 h-4" />}
                  onPress={() => router.push(`/tesouraria/cadastros/${cadastro.id}`)}
                >
                  Processar
                </DropdownItem>
              </DropdownMenu>
            </Dropdown>
          </div>
        );
      
      default:
        return null;
    }
  };

  // Statistics
  const stats = useMemo(() => {
    const total = cadastros.length;
    const aprovados = cadastros.filter(c => c.status === 'APROVADO').length;
    const pagamentosRecebidos = cadastros.filter(c => c.status === 'PAGAMENTO_RECEBIDO').length;
    const contratosGerados = cadastros.filter(c => c.status === 'CONTRATO_GERADO').length;
    const assinados = cadastros.filter(c => c.status === 'ASSINADO').length;
    const concluidos = cadastros.filter(c => c.status === 'CONCLUIDO').length;
    const valorTotal = cadastros.reduce((sum, c) => sum + (c.valor_total || 0), 0);
    
    return { 
      total, 
      aprovados, 
      pagamentosRecebidos, 
      contratosGerados, 
      assinados, 
      concluidos,
      valorTotal
    };
  }, [cadastros]);

  if (loading && cadastros.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col gap-4 mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div>
              <h1 className="text-2xl font-bold text-default-900">Tesouraria</h1>
              <p className="text-default-600">
                Gerencie o pipeline de pagamentos e contratos
              </p>
            </div>
            <div className="flex items-center gap-2">
              {isConnected ? (
                <Chip
                  color="success"
                  variant="flat"
                  startContent={<WifiIcon className="w-3 h-3" />}
                  size="sm"
                >
                  Conectado
                </Chip>
              ) : (
                <Chip
                  color="warning"
                  variant="flat"
                  startContent={<WifiOffIcon className="w-3 h-3" />}
                  size="sm"
                >
                  Desconectado
                </Chip>
              )}
            </div>
          </div>
        </div>

        {/* Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-6 gap-4">
          <Card>
            <CardBody className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary-100 rounded-lg">
                  <DollarSignIcon className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <p className="text-sm text-default-500">Total</p>
                  <p className="text-2xl font-bold">{stats.total}</p>
                </div>
              </div>
            </CardBody>
          </Card>
          
          <Card>
            <CardBody className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-warning-100 rounded-lg">
                  <ClockIcon className="w-5 h-5 text-warning" />
                </div>
                <div>
                  <p className="text-sm text-default-500">Aprovados</p>
                  <p className="text-2xl font-bold">{stats.aprovados}</p>
                </div>
              </div>
            </CardBody>
          </Card>
          
          <Card>
            <CardBody className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-success-100 rounded-lg">
                  <DollarSignIcon className="w-5 h-5 text-success" />
                </div>
                <div>
                  <p className="text-sm text-default-500">Pagamentos</p>
                  <p className="text-2xl font-bold">{stats.pagamentosRecebidos}</p>
                </div>
              </div>
            </CardBody>
          </Card>
          
          <Card>
            <CardBody className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-info-100 rounded-lg">
                  <FileTextIcon className="w-5 h-5 text-info" />
                </div>
                <div>
                  <p className="text-sm text-default-500">Contratos</p>
                  <p className="text-2xl font-bold">{stats.contratosGerados}</p>
                </div>
              </div>
            </CardBody>
          </Card>
          
          <Card>
            <CardBody className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-secondary-100 rounded-lg">
                  <CheckCircleIcon className="w-5 h-5 text-secondary" />
                </div>
                <div>
                  <p className="text-sm text-default-500">Assinados</p>
                  <p className="text-2xl font-bold">{stats.assinados}</p>
                </div>
              </div>
            </CardBody>
          </Card>
          
          <Card>
            <CardBody className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-success-100 rounded-lg">
                  <CheckCircleIcon className="w-5 h-5 text-success" />
                </div>
                <div>
                  <p className="text-sm text-default-500">Concluídos</p>
                  <p className="text-2xl font-bold">{stats.concluidos}</p>
                </div>
              </div>
            </CardBody>
          </Card>
        </div>

        {/* Revenue Summary */}
        <Card>
          <CardBody className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-default-500">Receita Total</p>
                <p className="text-3xl font-bold text-success">
                  {formatCurrency(stats.valorTotal)}
                </p>
              </div>
              <div className="p-3 bg-success-100 rounded-lg">
                <DollarSignIcon className="w-8 h-8 text-success" />
              </div>
            </div>
          </CardBody>
        </Card>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          <Input
            placeholder="Buscar por nome, CPF ou ID..."
            value={filters.search}
            onChange={(e) => handleSearch(e.target.value)}
            startContent={<SearchIcon className="w-4 h-4 text-default-400" />}
            className="max-w-sm"
            size="sm"
          />
          
          <div className="flex gap-2 flex-wrap">
            <Chip
              variant={filters.status === 'all' ? 'solid' : 'flat'}
              color={filters.status === 'all' ? 'primary' : 'default'}
              onPress={() => handleStatusFilter('all')}
              className="cursor-pointer"
            >
              Todos
            </Chip>
            <Chip
              variant={filters.status === 'APROVADO' ? 'solid' : 'flat'}
              color={filters.status === 'APROVADO' ? 'primary' : 'default'}
              onPress={() => handleStatusFilter('APROVADO')}
              className="cursor-pointer"
            >
              Aprovados
            </Chip>
            <Chip
              variant={filters.status === 'PAGAMENTO_RECEBIDO' ? 'solid' : 'flat'}
              color={filters.status === 'PAGAMENTO_RECEBIDO' ? 'primary' : 'default'}
              onPress={() => handleStatusFilter('PAGAMENTO_RECEBIDO')}
              className="cursor-pointer"
            >
              Pagamentos
            </Chip>
            <Chip
              variant={filters.status === 'CONTRATO_GERADO' ? 'solid' : 'flat'}
              color={filters.status === 'CONTRATO_GERADO' ? 'primary' : 'default'}
              onPress={() => handleStatusFilter('CONTRATO_GERADO')}
              className="cursor-pointer"
            >
              Contratos
            </Chip>
            <Chip
              variant={filters.status === 'CONCLUIDO' ? 'solid' : 'flat'}
              color={filters.status === 'CONCLUIDO' ? 'primary' : 'default'}
              onPress={() => handleStatusFilter('CONCLUIDO')}
              className="cursor-pointer"
            >
              Concluídos
            </Chip>
          </div>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <Card className="mb-6">
          <CardBody>
            <div className="flex items-center gap-2 text-danger">
              <AlertCircleIcon className="w-5 h-5" />
              <span>{error}</span>
            </div>
          </CardBody>
        </Card>
      )}

      {/* Data Table */}
      <Card>
        <CardHeader className="flex gap-3">
          <div className="flex flex-col">
            <p className="text-md">Pipeline de Tesouraria</p>
            <p className="text-small text-default-500">
              {totalItems} cadastro{totalItems !== 1 ? 's' : ''} encontrado{totalItems !== 1 ? 's' : ''}
            </p>
          </div>
        </CardHeader>
        <CardBody>
          <DataTable
            aria-label="Tabela de pipeline de tesouraria"
            columns={columns}
            items={filteredCadastros}
            renderCell={renderCell}
            emptyContent="Nenhum cadastro encontrado no pipeline"
            loading={loading}
            loadingContent={<Spinner />}
          />
        </CardBody>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center mt-6">
          <Pagination
            total={totalPages}
            page={currentPage}
            onChange={handlePageChange}
            showControls
            showShadow
            color="primary"
          />
        </div>
      )}
    </div>
  );
}








