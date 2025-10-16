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
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  useDisclosure,
  Textarea
} from '@heroui/react';
import { DataTable, StatusBadge, useToast } from '@abase/ui';
import { useAuth } from '@/contexts/AuthContext';
import { useAnaliseSSE } from '@/hooks/useSSEEvents';
import { formatDate, formatCurrency, formatCPF } from '@/lib/formatters';
import {
  MagnifyingGlassIcon as SearchIcon,
  FunnelIcon as FilterIcon,
  EllipsisVerticalIcon as MoreVerticalIcon,
  CheckIcon,
  XMarkIcon as XIcon,
  ExclamationTriangleIcon as AlertTriangleIcon,
  EyeIcon,
  WifiIcon,
  SignalSlashIcon as WifiOffIcon,
  ClockIcon,
  UserIcon as UserCheckIcon
} from '@heroicons/react/24/outline';

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
  observacao?: string;
  valor_total?: number;
  created_at: string;
  updated_at: string;
  submitted_at?: string;
}

interface AnaliseFilters {
  search: string;
  status: string;
  dateFrom: string;
  dateTo: string;
  priority: string;
}

interface PendenciaData {
  cadastro_id: number;
  observacoes: string;
  campos_pendentes: string[];
}

export default function AnalisePage() {
  const router = useRouter();
  const { apiClient, user } = useAuth();
  const { addToast } = useToast();
  const { isOpen: isPendenciaOpen, onOpen: onPendenciaOpen, onClose: onPendenciaClose } = useDisclosure();
  const { isOpen: isAprovarOpen, onOpen: onAprovarOpen, onClose: onAprovarClose } = useDisclosure();
  
  // State
  const [cadastros, setCadastros] = useState<Cadastro[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [selectedCadastro, setSelectedCadastro] = useState<Cadastro | null>(null);
  const [filters, setFilters] = useState<AnaliseFilters>({
    search: "",
    status: "SUBMETIDO",
    dateFrom: "",
    dateTo: "",
    priority: "all"
  });
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const [pendenciaData, setPendenciaData] = useState<PendenciaData>({
    cadastro_id: 0,
    observacoes: '',
    campos_pendentes: []
  });

  const itemsPerPage = 10;

  // SSE integration
  const { isConnected } = useAnaliseSSE(() => {
    // Refresh data when SSE events are received
    fetchCadastros(currentPage, filters);
  });

  // Fetch cadastros for analysis
  const fetchCadastros = async (page: number = 1, searchParams?: AnaliseFilters) => {
    if (!apiClient) return;

    try {
      setLoading(true);
      setError("");

      const params = new URLSearchParams({
        page: page.toString(),
        limit: itemsPerPage.toString(),
        status: 'SUBMETIDO,EM_ANALISE,PENDENTE', // Only show cadastros that need analysis
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
      }>(`/api/v1/analise/cadastros?${params}`);

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
      console.error('Error fetching cadastros for analysis:', err);
      setError(err.message || 'Erro ao carregar cadastros para análise');
      
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
          status: "SUBMETIDO",
          observacao: "Aguardando análise inicial",
          valor_total: 200.00,
          created_at: "2024-01-15T10:30:00Z",
          updated_at: "2024-01-15T10:30:00Z",
          submitted_at: "2024-01-15T10:30:00Z"
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
          status: "EM_ANALISE",
          observacao: "Em análise pelo analista",
          valor_total: 250.00,
          created_at: "2024-01-14T14:20:00Z",
          updated_at: "2024-01-15T09:15:00Z",
          submitted_at: "2024-01-14T14:20:00Z"
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
          status: "PENDENTE",
          observacao: "Documentos pendentes",
          valor_total: 180.00,
          created_at: "2024-01-13T09:15:00Z",
          updated_at: "2024-01-14T16:45:00Z",
          submitted_at: "2024-01-13T09:15:00Z"
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

  // Handle approve cadastro
  const handleApprove = async (cadastro: Cadastro) => {
    setSelectedCadastro(cadastro);
    onAprovarOpen();
  };

  const confirmApprove = async () => {
    if (!selectedCadastro || !apiClient) return;

    try {
      setIsProcessing(true);
      
      const response = await apiClient.post(`/api/v1/analise/cadastros/${selectedCadastro.id}/approve`);

      if (response.error) {
        throw new Error(response.error.message);
      }

      addToast({
        type: 'success',
        title: 'Cadastro aprovado',
        description: `Cadastro #${selectedCadastro.id} foi aprovado com sucesso.`,
      });

      // Refresh list
      fetchCadastros(currentPage, filters);
      onAprovarClose();
    } catch (err: any) {
      console.error('Error approving cadastro:', err);
      addToast({
        type: 'error',
        title: 'Erro ao aprovar',
        description: err.message || 'Não foi possível aprovar o cadastro.',
      });
    } finally {
      setIsProcessing(false);
    }
  };

  // Handle request changes (pendencia)
  const handleRequestChanges = async (cadastro: Cadastro) => {
    setPendenciaData({
      cadastro_id: cadastro.id,
      observacoes: '',
      campos_pendentes: []
    });
    setSelectedCadastro(cadastro);
    onPendenciaOpen();
  };

  const confirmRequestChanges = async () => {
    if (!selectedCadastro || !apiClient) return;

    try {
      setIsProcessing(true);
      
      const response = await apiClient.post(`/api/v1/analise/cadastros/${selectedCadastro.id}/request-changes`, {
        observacoes: pendenciaData.observacoes,
        campos_pendentes: pendenciaData.campos_pendentes
      });

      if (response.error) {
        throw new Error(response.error.message);
      }

      addToast({
        type: 'success',
        title: 'Solicitação de correção enviada',
        description: `Cadastro #${selectedCadastro.id} foi marcado como pendente.`,
      });

      // Refresh list
      fetchCadastros(currentPage, filters);
      onPendenciaClose();
    } catch (err: any) {
      console.error('Error requesting changes:', err);
      addToast({
        type: 'error',
        title: 'Erro ao solicitar correções',
        description: err.message || 'Não foi possível solicitar as correções.',
      });
    } finally {
      setIsProcessing(false);
    }
  };

  // Handle cancel cadastro
  const handleCancel = async (cadastro: Cadastro) => {
    if (!apiClient) return;

    try {
      setIsProcessing(true);
      
      const response = await apiClient.post(`/api/v1/analise/cadastros/${cadastro.id}/cancel`);

      if (response.error) {
        throw new Error(response.error.message);
      }

      addToast({
        type: 'success',
        title: 'Cadastro cancelado',
        description: `Cadastro #${cadastro.id} foi cancelado.`,
      });

      // Refresh list
      fetchCadastros(currentPage, filters);
    } catch (err: any) {
      console.error('Error canceling cadastro:', err);
      addToast({
        type: 'error',
        title: 'Erro ao cancelar',
        description: err.message || 'Não foi possível cancelar o cadastro.',
      });
    } finally {
      setIsProcessing(false);
    }
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
      key: "submitted_at",
      label: "Submetido em",
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
      
      case "submitted_at":
        return (
          <p className="text-bold text-small text-default-600">
            {cadastro.submitted_at ? formatDate(cadastro.submitted_at) : '-'}
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
                  onPress={() => router.push(`/analise/cadastros/${cadastro.id}`)}
                >
                  Analisar
                </DropdownItem>
                
                {cadastro.status === 'SUBMETIDO' || cadastro.status === 'EM_ANALISE' ? (
                  <DropdownItem
                    key="approve"
                    startContent={<CheckIcon className="w-4 h-4" />}
                    onPress={() => handleApprove(cadastro)}
                    className="text-success"
                  >
                    Aprovar
                  </DropdownItem>
                ) : null}
                
                {cadastro.status === 'SUBMETIDO' || cadastro.status === 'EM_ANALISE' ? (
                  <DropdownItem
                    key="request-changes"
                    startContent={<AlertTriangleIcon className="w-4 h-4" />}
                    onPress={() => handleRequestChanges(cadastro)}
                    className="text-warning"
                  >
                    Solicitar Correções
                  </DropdownItem>
                ) : null}
                
                <DropdownItem
                  key="cancel"
                  className="text-danger"
                  color="danger"
                  startContent={<XIcon className="w-4 h-4" />}
                  onPress={() => handleCancel(cadastro)}
                >
                  Cancelar
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
    const submetidos = cadastros.filter(c => c.status === 'SUBMETIDO').length;
    const emAnalise = cadastros.filter(c => c.status === 'EM_ANALISE').length;
    const pendentes = cadastros.filter(c => c.status === 'PENDENTE').length;
    
    return { total, submetidos, emAnalise, pendentes };
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
              <h1 className="text-2xl font-bold text-default-900">Análise de Cadastros</h1>
              <p className="text-default-600">
                Analise e aprove cadastros submetidos
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
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardBody className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary-100 rounded-lg">
                  <ClockIcon className="w-5 h-5 text-primary" />
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
                  <p className="text-sm text-default-500">Submetidos</p>
                  <p className="text-2xl font-bold">{stats.submetidos}</p>
                </div>
              </div>
            </CardBody>
          </Card>
          
          <Card>
            <CardBody className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-info-100 rounded-lg">
                  <UserCheckIcon className="w-5 h-5 text-info" />
                </div>
                <div>
                  <p className="text-sm text-default-500">Em Análise</p>
                  <p className="text-2xl font-bold">{stats.emAnalise}</p>
                </div>
              </div>
            </CardBody>
          </Card>
          
          <Card>
            <CardBody className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-danger-100 rounded-lg">
                  <AlertTriangleIcon className="w-5 h-5 text-danger" />
                </div>
                <div>
                  <p className="text-sm text-default-500">Pendentes</p>
                  <p className="text-2xl font-bold">{stats.pendentes}</p>
                </div>
              </div>
            </CardBody>
          </Card>
        </div>

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
            <Button
              variant={filters.status === 'all' ? 'solid' : 'flat'}
              color={filters.status === 'all' ? 'primary' : 'default'}
              onPress={() => handleStatusFilter('all')}
              size="sm"
            >
              Todos
            </Button>
            <Button
              variant={filters.status === 'SUBMETIDO' ? 'solid' : 'flat'}
              color={filters.status === 'SUBMETIDO' ? 'primary' : 'default'}
              onPress={() => handleStatusFilter('SUBMETIDO')}
              size="sm"
            >
              Submetidos
            </Button>
            <Button
              variant={filters.status === 'EM_ANALISE' ? 'solid' : 'flat'}
              color={filters.status === 'EM_ANALISE' ? 'primary' : 'default'}
              onPress={() => handleStatusFilter('EM_ANALISE')}
              size="sm"
            >
              Em Análise
            </Button>
            <Button
              variant={filters.status === 'PENDENTE' ? 'solid' : 'flat'}
              color={filters.status === 'PENDENTE' ? 'primary' : 'default'}
              onPress={() => handleStatusFilter('PENDENTE')}
              size="sm"
            >
              Pendentes
            </Button>
          </div>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <Card className="mb-6">
          <CardBody>
            <div className="flex items-center gap-2 text-danger">
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
              <span>{error}</span>
            </div>
          </CardBody>
        </Card>
      )}

      {/* Data Table */}
      <Card>
        <CardHeader className="flex gap-3">
          <div className="flex flex-col">
            <p className="text-md">Cadastros para Análise</p>
            <p className="text-small text-default-500">
              {totalItems} cadastro{totalItems !== 1 ? 's' : ''} encontrado{totalItems !== 1 ? 's' : ''}
            </p>
          </div>
        </CardHeader>
        <CardBody>
          <DataTable
            columns={columns}
            data={filteredCadastros}
            loading={loading}
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

      {/* Approve Confirmation Modal */}
      <Modal isOpen={isAprovarOpen} onClose={onAprovarClose}>
        <ModalContent>
          <ModalHeader className="flex flex-col gap-1">
            Confirmar Aprovação
          </ModalHeader>
          <ModalBody>
            <p>
              Tem certeza que deseja aprovar o cadastro{' '}
              <strong>#{selectedCadastro?.id}</strong>?
            </p>
            <p className="text-sm text-default-500">
              Esta ação enviará o cadastro para a tesouraria.
            </p>
          </ModalBody>
          <ModalFooter>
            <Button color="default" variant="light" onPress={onAprovarClose}>
              Cancelar
            </Button>
            <Button
              color="success"
              onPress={confirmApprove}
              isLoading={isProcessing}
              startContent={<CheckIcon className="w-4 h-4" />}
            >
              Aprovar
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Request Changes Modal */}
      <Modal isOpen={isPendenciaOpen} onClose={onPendenciaClose} size="2xl">
        <ModalContent>
          <ModalHeader className="flex flex-col gap-1">
            Solicitar Correções
          </ModalHeader>
          <ModalBody>
            <p className="text-sm text-default-600 mb-4">
              Cadastro #{selectedCadastro?.id} - {selectedCadastro?.associado?.nome}
            </p>
            
            <Textarea
              label="Observações"
              placeholder="Descreva as correções necessárias..."
              value={pendenciaData.observacoes}
              onChange={(e) => setPendenciaData(prev => ({ ...prev, observacoes: e.target.value }))}
              minRows={4}
              isRequired
            />
          </ModalBody>
          <ModalFooter>
            <Button color="default" variant="light" onPress={onPendenciaClose}>
              Cancelar
            </Button>
            <Button
              color="warning"
              onPress={confirmRequestChanges}
              isLoading={isProcessing}
              startContent={<AlertTriangleIcon className="w-4 h-4" />}
              isDisabled={!pendenciaData.observacoes.trim()}
            >
              Solicitar Correções
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </div>
  );
}








