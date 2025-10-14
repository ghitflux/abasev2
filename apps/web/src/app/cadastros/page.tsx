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
  useDisclosure
} from '@heroui/react';
import { DataTable, StatusBadge, useToast } from '@abase/ui';
import { useAuth } from '@/contexts/AuthContext';
import { formatDate, formatCurrency } from '@/lib/formatters';
import { SearchIcon, PlusIcon, MoreVerticalIcon, EditIcon, TrashIcon, EyeIcon, SendIcon } from 'lucide-react';

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
}

interface CadastroFilters {
  search: string;
  status: string;
  dateFrom: string;
  dateTo: string;
}

export default function CadastrosPage() {
  const router = useRouter();
  const { apiClient, user } = useAuth();
  const { addToast } = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();
  
  // State
  const [cadastros, setCadastros] = useState<Cadastro[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [selectedCadastro, setSelectedCadastro] = useState<Cadastro | null>(null);
  const [filters, setFilters] = useState<CadastroFilters>({
    search: "",
    status: "all",
    dateFrom: "",
    dateTo: ""
  });
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const itemsPerPage = 10;

  // Fetch cadastros
  const fetchCadastros = async (page: number = 1, searchParams?: CadastroFilters) => {
    if (!apiClient) return;

    try {
      setLoading(true);
      setError("");

      const params = new URLSearchParams({
        page: page.toString(),
        limit: itemsPerPage.toString(),
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

      // Note: This endpoint doesn't exist yet in the backend, so we'll mock the data
      const response = await apiClient.get<{
        items: Cadastro[];
        total: number;
        page: number;
        pages: number;
      }>(`/api/v1/cadastros/cadastros?${params}`);

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
      console.error('Error fetching cadastros:', err);
      setError(err.message || 'Erro ao carregar cadastros');
      
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
          status: "RASCUNHO",
          observacao: "Cadastro em andamento",
          valor_total: 150.00,
          created_at: "2024-01-15T10:30:00Z",
          updated_at: "2024-01-15T10:30:00Z"
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
          status: "SUBMETIDO",
          observacao: "Aguardando análise",
          valor_total: 200.00,
          created_at: "2024-01-14T14:20:00Z",
          updated_at: "2024-01-14T14:20:00Z"
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
          status: "APROVADO",
          observacao: "Aprovado para pagamento",
          valor_total: 180.00,
          created_at: "2024-01-13T09:15:00Z",
          updated_at: "2024-01-13T09:15:00Z"
        },
        {
          id: 4,
          associado_id: 1,
          associado: {
            id: 1,
            nome: "João Silva",
            cpf: "12345678901",
            email: "joao@email.com"
          },
          status: "CONCLUIDO",
          observacao: "Processo finalizado",
          valor_total: 150.00,
          created_at: "2024-01-10T16:45:00Z",
          updated_at: "2024-01-12T11:30:00Z"
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

  // Handle submit to analysis
  const handleSubmitToAnalysis = async (cadastro: Cadastro) => {
    if (!apiClient) return;

    try {
      setIsSubmitting(true);
      
      const response = await apiClient.post(`/api/v1/cadastros/cadastros/${cadastro.id}/submit`);

      if (response.error) {
        throw new Error(response.error.message);
      }

      addToast({
        type: 'success',
        title: 'Cadastro submetido',
        description: `Cadastro #${cadastro.id} foi enviado para análise.`,
      });

      // Refresh list
      fetchCadastros(currentPage, filters);
    } catch (err: any) {
      console.error('Error submitting cadastro:', err);
      addToast({
        type: 'error',
        title: 'Erro ao submeter',
        description: err.message || 'Não foi possível submeter o cadastro.',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle delete
  const handleDelete = async (cadastro: Cadastro) => {
    setSelectedCadastro(cadastro);
    onOpen();
  };

  const confirmDelete = async () => {
    if (!selectedCadastro || !apiClient) return;

    try {
      setIsDeleting(true);
      
      // Note: This endpoint doesn't exist yet in the backend
      const response = await apiClient.delete(`/api/v1/cadastros/cadastros/${selectedCadastro.id}`);

      if (response.error) {
        throw new Error(response.error.message);
      }

      addToast({
        type: 'success',
        title: 'Cadastro removido',
        description: `Cadastro #${selectedCadastro.id} foi removido com sucesso.`,
      });

      // Refresh list
      fetchCadastros(currentPage, filters);
      onClose();
    } catch (err: any) {
      console.error('Error deleting cadastro:', err);
      addToast({
        type: 'error',
        title: 'Erro ao remover',
        description: err.message || 'Não foi possível remover o cadastro.',
      });
    } finally {
      setIsDeleting(false);
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
      key: "created_at",
      label: "Data de Criação",
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
              {cadastro.associado?.email || 'N/A'}
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
      
      case "created_at":
        return (
          <p className="text-bold text-small text-default-600">
            {formatDate(cadastro.created_at)}
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
                  onPress={() => router.push(`/cadastros/${cadastro.id}`)}
                >
                  Visualizar
                </DropdownItem>
                
                {cadastro.status === 'RASCUNHO' && (
                  <DropdownItem
                    key="edit"
                    startContent={<EditIcon className="w-4 h-4" />}
                    onPress={() => router.push(`/cadastros/${cadastro.id}/editar`)}
                  >
                    Editar
                  </DropdownItem>
                )}
                
                {cadastro.status === 'RASCUNHO' && (
                  <DropdownItem
                    key="submit"
                    startContent={<SendIcon className="w-4 h-4" />}
                    onPress={() => handleSubmitToAnalysis(cadastro)}
                    isLoading={isSubmitting}
                  >
                    Submeter para Análise
                  </DropdownItem>
                )}
                
                {cadastro.status === 'RASCUNHO' && (
                  <DropdownItem
                    key="delete"
                    className="text-danger"
                    color="danger"
                    startContent={<TrashIcon className="w-4 h-4" />}
                    onPress={() => handleDelete(cadastro)}
                  >
                    Remover
                  </DropdownItem>
                )}
              </DropdownMenu>
            </Dropdown>
          </div>
        );
      
      default:
        return null;
    }
  };

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
          <div>
            <h1 className="text-2xl font-bold text-default-900">Cadastros</h1>
            <p className="text-default-600">
              Gerencie os cadastros de associação
            </p>
          </div>
          <Button
            color="primary"
            startContent={<PlusIcon className="w-4 h-4" />}
            onPress={() => router.push('/cadastros/novo')}
          >
            Novo Cadastro
          </Button>
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
            <Chip
              variant={filters.status === 'all' ? 'solid' : 'flat'}
              color={filters.status === 'all' ? 'primary' : 'default'}
              onPress={() => handleStatusFilter('all')}
              className="cursor-pointer"
            >
              Todos
            </Chip>
            <Chip
              variant={filters.status === 'RASCUNHO' ? 'solid' : 'flat'}
              color={filters.status === 'RASCUNHO' ? 'primary' : 'default'}
              onPress={() => handleStatusFilter('RASCUNHO')}
              className="cursor-pointer"
            >
              Rascunho
            </Chip>
            <Chip
              variant={filters.status === 'SUBMETIDO' ? 'solid' : 'flat'}
              color={filters.status === 'SUBMETIDO' ? 'primary' : 'default'}
              onPress={() => handleStatusFilter('SUBMETIDO')}
              className="cursor-pointer"
            >
              Submetido
            </Chip>
            <Chip
              variant={filters.status === 'APROVADO' ? 'solid' : 'flat'}
              color={filters.status === 'APROVADO' ? 'primary' : 'default'}
              onPress={() => handleStatusFilter('APROVADO')}
              className="cursor-pointer"
            >
              Aprovado
            </Chip>
            <Chip
              variant={filters.status === 'CONCLUIDO' ? 'solid' : 'flat'}
              color={filters.status === 'CONCLUIDO' ? 'primary' : 'default'}
              onPress={() => handleStatusFilter('CONCLUIDO')}
              className="cursor-pointer"
            >
              Concluído
            </Chip>
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
            <p className="text-md">Lista de Cadastros</p>
            <p className="text-small text-default-500">
              {totalItems} cadastro{totalItems !== 1 ? 's' : ''} encontrado{totalItems !== 1 ? 's' : ''}
            </p>
          </div>
        </CardHeader>
        <CardBody>
          <DataTable
            aria-label="Tabela de cadastros"
            columns={columns}
            items={filteredCadastros}
            renderCell={renderCell}
            emptyContent="Nenhum cadastro encontrado"
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

      {/* Delete Confirmation Modal */}
      <Modal isOpen={isOpen} onClose={onClose}>
        <ModalContent>
          <ModalHeader className="flex flex-col gap-1">
            Confirmar Remoção
          </ModalHeader>
          <ModalBody>
            <p>
              Tem certeza que deseja remover o cadastro{' '}
              <strong>#{selectedCadastro?.id}</strong>?
            </p>
            <p className="text-sm text-default-500">
              Esta ação não pode ser desfeita.
            </p>
          </ModalBody>
          <ModalFooter>
            <Button color="default" variant="light" onPress={onClose}>
              Cancelar
            </Button>
            <Button
              color="danger"
              onPress={confirmDelete}
              isLoading={isDeleting}
            >
              Remover
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </div>
  );
}
