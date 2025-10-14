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
import { formatCPF, formatPhone, formatDate } from '@/lib/formatters';
import { SearchIcon, PlusIcon, MoreVerticalIcon, EditIcon, TrashIcon, EyeIcon } from 'lucide-react';

interface Associado {
  id: number;
  cpf: string;
  nome: string;
  email?: string;
  telefone?: string;
  endereco?: string;
  created_at?: string;
  updated_at?: string;
}

interface AssociadoFilters {
  search: string;
  status: string;
}

export default function AssociadosPage() {
  const router = useRouter();
  const { apiClient, user } = useAuth();
  const { addToast } = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();
  
  // State
  const [associados, setAssociados] = useState<Associado[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [selectedAssociado, setSelectedAssociado] = useState<Associado | null>(null);
  const [filters, setFilters] = useState<AssociadoFilters>({
    search: "",
    status: "all"
  });
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [isDeleting, setIsDeleting] = useState(false);

  const itemsPerPage = 10;

  // Fetch associados
  const fetchAssociados = async (page: number = 1, searchParams?: AssociadoFilters) => {
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

      // Note: This endpoint doesn't exist yet in the backend, so we'll mock the data
      // In a real implementation, this would be: `/api/v1/cadastros/associados?${params}`
      const response = await apiClient.get<{
        items: Associado[];
        total: number;
        page: number;
        pages: number;
      }>(`/api/v1/cadastros/associados?${params}`);

      if (response.error) {
        throw new Error(response.error.message);
      }

      if (response.data) {
        setAssociados(response.data.items);
        setTotalItems(response.data.total);
        setTotalPages(response.data.pages);
        setCurrentPage(response.data.page);
      }
    } catch (err: any) {
      console.error('Error fetching associados:', err);
      setError(err.message || 'Erro ao carregar associados');
      
      // Mock data for development
      const mockAssociados: Associado[] = [
        {
          id: 1,
          cpf: "12345678901",
          nome: "João Silva",
          email: "joao@email.com",
          telefone: "11999999999",
          endereco: "Rua das Flores, 123 - São Paulo/SP",
          created_at: "2024-01-15T10:30:00Z",
          updated_at: "2024-01-15T10:30:00Z"
        },
        {
          id: 2,
          cpf: "98765432100",
          nome: "Maria Santos",
          email: "maria@email.com",
          telefone: "11888888888",
          endereco: "Av. Paulista, 456 - São Paulo/SP",
          created_at: "2024-01-14T14:20:00Z",
          updated_at: "2024-01-14T14:20:00Z"
        },
        {
          id: 3,
          cpf: "11122233344",
          nome: "Pedro Oliveira",
          email: "pedro@email.com",
          telefone: "11777777777",
          endereco: "Rua Augusta, 789 - São Paulo/SP",
          created_at: "2024-01-13T09:15:00Z",
          updated_at: "2024-01-13T09:15:00Z"
        }
      ];
      
      setAssociados(mockAssociados);
      setTotalItems(mockAssociados.length);
      setTotalPages(1);
      setCurrentPage(1);
    } finally {
      setLoading(false);
    }
  };

  // Initial load
  useEffect(() => {
    fetchAssociados(1, filters);
  }, [apiClient]);

  // Filtered data
  const filteredAssociados = useMemo(() => {
    let filtered = associados;

    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      filtered = filtered.filter(associado =>
        associado.nome.toLowerCase().includes(searchLower) ||
        associado.cpf.includes(filters.search) ||
        (associado.email && associado.email.toLowerCase().includes(searchLower))
      );
    }

    return filtered;
  }, [associados, filters]);

  // Handle search
  const handleSearch = (value: string) => {
    setFilters(prev => ({ ...prev, search: value }));
    setCurrentPage(1);
  };

  // Handle page change
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    fetchAssociados(page, filters);
  };

  // Handle delete
  const handleDelete = async (associado: Associado) => {
    setSelectedAssociado(associado);
    onOpen();
  };

  const confirmDelete = async () => {
    if (!selectedAssociado || !apiClient) return;

    try {
      setIsDeleting(true);
      
      // Note: This endpoint doesn't exist yet in the backend
      const response = await apiClient.delete(`/api/v1/cadastros/associados/${selectedAssociado.id}`);

      if (response.error) {
        throw new Error(response.error.message);
      }

      addToast({
        type: 'success',
        title: 'Associado removido',
        description: `${selectedAssociado.nome} foi removido com sucesso.`,
      });

      // Refresh list
      fetchAssociados(currentPage, filters);
      onClose();
    } catch (err: any) {
      console.error('Error deleting associado:', err);
      addToast({
        type: 'error',
        title: 'Erro ao remover',
        description: err.message || 'Não foi possível remover o associado.',
      });
    } finally {
      setIsDeleting(false);
    }
  };

  // Table columns
  const columns = [
    {
      key: "nome",
      label: "Nome",
      sortable: true,
    },
    {
      key: "cpf",
      label: "CPF",
      sortable: true,
    },
    {
      key: "email",
      label: "Email",
      sortable: true,
    },
    {
      key: "telefone",
      label: "Telefone",
      sortable: false,
    },
    {
      key: "created_at",
      label: "Data de Cadastro",
      sortable: true,
    },
    {
      key: "actions",
      label: "Ações",
      sortable: false,
    },
  ];

  // Render cell content
  const renderCell = (associado: Associado, columnKey: React.Key) => {
    switch (columnKey) {
      case "nome":
        return (
          <div className="flex flex-col">
            <p className="text-bold text-small capitalize">{associado.nome}</p>
            {associado.endereco && (
              <p className="text-bold text-tiny capitalize text-default-400">
                {associado.endereco}
              </p>
            )}
          </div>
        );
      
      case "cpf":
        return (
          <p className="text-bold text-small text-default-600">
            {formatCPF(associado.cpf)}
          </p>
        );
      
      case "email":
        return (
          <p className="text-bold text-small text-default-600">
            {associado.email || '-'}
          </p>
        );
      
      case "telefone":
        return (
          <p className="text-bold text-small text-default-600">
            {associado.telefone ? formatPhone(associado.telefone) : '-'}
          </p>
        );
      
      case "created_at":
        return (
          <p className="text-bold text-small text-default-600">
            {associado.created_at ? formatDate(associado.created_at) : '-'}
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
                  onPress={() => router.push(`/associados/${associado.id}`)}
                >
                  Visualizar
                </DropdownItem>
                <DropdownItem
                  key="edit"
                  startContent={<EditIcon className="w-4 h-4" />}
                  onPress={() => router.push(`/associados/${associado.id}/editar`)}
                >
                  Editar
                </DropdownItem>
                <DropdownItem
                  key="delete"
                  className="text-danger"
                  color="danger"
                  startContent={<TrashIcon className="w-4 h-4" />}
                  onPress={() => handleDelete(associado)}
                >
                  Remover
                </DropdownItem>
              </DropdownMenu>
            </Dropdown>
          </div>
        );
      
      default:
        return null;
    }
  };

  if (loading && associados.length === 0) {
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
            <h1 className="text-2xl font-bold text-default-900">Associados</h1>
            <p className="text-default-600">
              Gerencie os associados cadastrados no sistema
            </p>
          </div>
          <Button
            color="primary"
            startContent={<PlusIcon className="w-4 h-4" />}
            onPress={() => router.push('/associados/novo')}
          >
            Novo Associado
          </Button>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          <Input
            placeholder="Buscar por nome, CPF ou email..."
            value={filters.search}
            onChange={(e) => handleSearch(e.target.value)}
            startContent={<SearchIcon className="w-4 h-4 text-default-400" />}
            className="max-w-sm"
            size="sm"
          />
          
          <div className="flex gap-2">
            <Chip
              variant={filters.status === 'all' ? 'solid' : 'flat'}
              color={filters.status === 'all' ? 'primary' : 'default'}
              onPress={() => setFilters(prev => ({ ...prev, status: 'all' }))}
              className="cursor-pointer"
            >
              Todos
            </Chip>
            <Chip
              variant={filters.status === 'active' ? 'solid' : 'flat'}
              color={filters.status === 'active' ? 'primary' : 'default'}
              onPress={() => setFilters(prev => ({ ...prev, status: 'active' }))}
              className="cursor-pointer"
            >
              Ativos
            </Chip>
            <Chip
              variant={filters.status === 'inactive' ? 'solid' : 'flat'}
              color={filters.status === 'inactive' ? 'primary' : 'default'}
              onPress={() => setFilters(prev => ({ ...prev, status: 'inactive' }))}
              className="cursor-pointer"
            >
              Inativos
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
            <p className="text-md">Lista de Associados</p>
            <p className="text-small text-default-500">
              {totalItems} associado{totalItems !== 1 ? 's' : ''} encontrado{totalItems !== 1 ? 's' : ''}
            </p>
          </div>
        </CardHeader>
        <CardBody>
          <DataTable
            aria-label="Tabela de associados"
            columns={columns}
            items={filteredAssociados}
            renderCell={renderCell}
            emptyContent="Nenhum associado encontrado"
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
              Tem certeza que deseja remover o associado{' '}
              <strong>{selectedAssociado?.nome}</strong>?
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
