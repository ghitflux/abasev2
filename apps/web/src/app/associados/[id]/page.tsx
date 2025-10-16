"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { 
  Button, 
  Card, 
  CardBody, 
  CardHeader, 
  Chip, 
  Divider,
  Spinner,
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  useDisclosure
} from '@heroui/react';
import { StatusBadge, useToast } from '@abase/ui';
import { useAuth } from '@/contexts/AuthContext';
import { formatCPF, formatPhone, formatDate, formatCEP } from '@/lib/formatters';
import { 
  PencilIcon as EditIcon,
  ArrowLeftIcon,
  TrashIcon
} from '@heroicons/react/24/outline';

interface Associado {
  id: number;
  cpf: string;
  nome: string;
  email?: string;
  telefone?: string;
  celular?: string;
  endereco?: string;
  numero?: string;
  complemento?: string;
  bairro?: string;
  cidade?: string;
  estado?: string;
  cep?: string;
  data_nascimento?: string;
  estado_civil?: string;
  profissao?: string;
  nacionalidade?: string;
  observacoes?: string;
  created_at?: string;
  updated_at?: string;
}

interface Cadastro {
  id: number;
  associado_id: number;
  status: string;
  observacao?: string;
  created_at: string;
  updated_at: string;
}

export default function AssociadoDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter();
  const { apiClient } = useAuth();
  const { addToast } = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();
  
  const [associado, setAssociado] = useState<Associado | null>(null);
  const [cadastros, setCadastros] = useState<Cadastro[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [isDeleting, setIsDeleting] = useState(false);

  const [associadoId, setAssociadoId] = useState<number | null>(null);

  useEffect(() => {
    const loadParams = async () => {
      const resolvedParams = await params;
      setAssociadoId(parseInt(resolvedParams.id));
    };
    loadParams();
  }, [params]);

  useEffect(() => {
    if (apiClient && associadoId) {
      fetchAssociado();
      fetchCadastros();
    }
  }, [apiClient, associadoId]);

  const fetchAssociado = async () => {
    if (!apiClient) return;

    try {
      setLoading(true);
      setError("");

      const response = await apiClient.get<Associado>(`/api/v1/cadastros/associados/${associadoId}`);

      if (response.error) {
        throw new Error(response.error.message);
      }

      if (response.data) {
        setAssociado(response.data);
      }
    } catch (err: any) {
      console.error('Error fetching associado:', err);
      setError(err.message || 'Erro ao carregar associado');
      
      // Mock data for development
      const mockAssociado: Associado = {
        id: associadoId || 0,
        cpf: "12345678901",
        nome: "João Silva",
        email: "joao@email.com",
        telefone: "11999999999",
        celular: "11988888888",
        endereco: "Rua das Flores",
        numero: "123",
        complemento: "Apto 45",
        bairro: "Centro",
        cidade: "São Paulo",
        estado: "SP",
        cep: "01234567",
        data_nascimento: "1985-05-15",
        estado_civil: "casado",
        profissao: "Engenheiro",
        nacionalidade: "Brasileira",
        observacoes: "Associado desde 2020",
        created_at: "2024-01-15T10:30:00Z",
        updated_at: "2024-01-15T10:30:00Z"
      };
      
      setAssociado(mockAssociado);
    } finally {
      setLoading(false);
    }
  };

  const fetchCadastros = async () => {
    if (!apiClient) return;

    try {
      // Note: This endpoint doesn't exist yet in the backend
      const response = await apiClient.get<{
        items: Cadastro[];
        total: number;
      }>(`/api/v1/cadastros/associados/${associadoId}/cadastros`);

      if (response.error) {
        throw new Error(response.error.message);
      }

      if (response.data) {
        setCadastros(response.data.items);
      }
    } catch (err: any) {
      console.error('Error fetching cadastros:', err);
      
      // Mock data for development
      const mockCadastros: Cadastro[] = [
        {
          id: 1,
          associado_id: associadoId || 0,
          status: "APROVADO",
          observacao: "Cadastro aprovado para 2024",
          created_at: "2024-01-15T10:30:00Z",
          updated_at: "2024-01-15T10:30:00Z"
        },
        {
          id: 2,
          associado_id: associadoId || 0,
          status: "CONCLUIDO",
          observacao: "Processo finalizado",
          created_at: "2023-12-10T14:20:00Z",
          updated_at: "2023-12-15T16:45:00Z"
        }
      ];
      
      setCadastros(mockCadastros);
    }
  };

  const handleDelete = async () => {
    if (!associado || !apiClient) return;

    try {
      setIsDeleting(true);
      
      const response = await apiClient.delete(`/api/v1/cadastros/associados/${associado.id}`);

      if (response.error) {
        throw new Error(response.error.message);
      }

      addToast({
        type: 'success',
        title: 'Associado removido',
        description: `${associado.nome} foi removido com sucesso.`,
      });

      router.push('/associados');
    } catch (err: any) {
      console.error('Error deleting associado:', err);
      addToast({
        type: 'error',
        title: 'Erro ao remover',
        description: err.message || 'Não foi possível remover o associado.',
      });
    } finally {
      setIsDeleting(false);
      onClose();
    }
  };

  const handleEdit = () => {
    router.push(`/associados/${associadoId}/editar`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !associado) {
    return (
      <div className="p-6">
        <div className="flex items-center gap-4 mb-6">
          <Button
            variant="light"
            startContent={<ArrowLeftIcon className="w-4 h-4" />}
            onPress={() => router.push('/associados')}
          >
            Voltar
          </Button>
        </div>
        
        <Card>
          <CardBody>
            <div className="flex items-center gap-2 text-danger">
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
              <span>{error || 'Associado não encontrado'}</span>
            </div>
          </CardBody>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Button
            variant="light"
            startContent={<ArrowLeftIcon className="w-4 h-4" />}
            onPress={() => router.push('/associados')}
          >
            Voltar
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-default-900">{associado.nome}</h1>
            <p className="text-default-600">Detalhes do associado</p>
          </div>
        </div>
        
        <div className="flex gap-2">
          <Button
            color="primary"
            startContent={<EditIcon className="w-4 h-4" />}
            onPress={handleEdit}
          >
            Editar
          </Button>
          <Button
            color="danger"
            variant="bordered"
            startContent={<TrashIcon className="w-4 h-4" />}
            onPress={onOpen}
          >
            Remover
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Info */}
        <div className="lg:col-span-2 space-y-6">
          {/* Personal Information */}
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold">Informações Pessoais</h2>
            </CardHeader>
            <CardBody>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-default-600">CPF</label>
                  <p className="text-default-900">{formatCPF(associado.cpf)}</p>
                </div>
                
                <div>
                  <label className="text-sm font-medium text-default-600">Data de Nascimento</label>
                  <p className="text-default-900">
                    {associado.data_nascimento ? formatDate(associado.data_nascimento) : '-'}
                  </p>
                </div>
                
                <div>
                  <label className="text-sm font-medium text-default-600">Estado Civil</label>
                  <p className="text-default-900 capitalize">
                    {associado.estado_civil?.replace('_', ' ') || '-'}
                  </p>
                </div>
                
                <div>
                  <label className="text-sm font-medium text-default-600">Profissão</label>
                  <p className="text-default-900">{associado.profissao || '-'}</p>
                </div>
                
                <div>
                  <label className="text-sm font-medium text-default-600">Nacionalidade</label>
                  <p className="text-default-900">{associado.nacionalidade || '-'}</p>
                </div>
              </div>
            </CardBody>
          </Card>

          {/* Contact Information */}
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold">Informações de Contato</h2>
            </CardHeader>
            <CardBody>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-default-600">Email</label>
                  <p className="text-default-900">{associado.email || '-'}</p>
                </div>
                
                <div>
                  <label className="text-sm font-medium text-default-600">Telefone</label>
                  <p className="text-default-900">
                    {associado.telefone ? formatPhone(associado.telefone) : '-'}
                  </p>
                </div>
                
                <div>
                  <label className="text-sm font-medium text-default-600">Celular</label>
                  <p className="text-default-900">
                    {associado.celular ? formatPhone(associado.celular) : '-'}
                  </p>
                </div>
              </div>
            </CardBody>
          </Card>

          {/* Address */}
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold">Endereço</h2>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="text-sm font-medium text-default-600">CEP</label>
                    <p className="text-default-900">
                      {associado.cep ? formatCEP(associado.cep) : '-'}
                    </p>
                  </div>
                  
                  <div className="md:col-span-2">
                    <label className="text-sm font-medium text-default-600">Endereço</label>
                    <p className="text-default-900">
                      {associado.endereco ? `${associado.endereco}, ${associado.numero || ''}` : '-'}
                      {associado.complemento && `, ${associado.complemento}`}
                    </p>
                  </div>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="text-sm font-medium text-default-600">Bairro</label>
                    <p className="text-default-900">{associado.bairro || '-'}</p>
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium text-default-600">Cidade</label>
                    <p className="text-default-900">{associado.cidade || '-'}</p>
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium text-default-600">Estado</label>
                    <p className="text-default-900">{associado.estado || '-'}</p>
                  </div>
                </div>
              </div>
            </CardBody>
          </Card>

          {/* Additional Information */}
          {associado.observacoes && (
            <Card>
              <CardHeader>
                <h2 className="text-lg font-semibold">Observações</h2>
              </CardHeader>
              <CardBody>
                <p className="text-default-900 whitespace-pre-wrap">{associado.observacoes}</p>
              </CardBody>
            </Card>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Status Card */}
          <Card>
            <CardHeader>
              <h3 className="text-lg font-semibold">Status</h3>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-default-600">Cadastrado em</label>
                  <p className="text-default-900">
                    {associado.created_at ? formatDate(associado.created_at) : '-'}
                  </p>
                </div>
                
                <div>
                  <label className="text-sm font-medium text-default-600">Última atualização</label>
                  <p className="text-default-900">
                    {associado.updated_at ? formatDate(associado.updated_at) : '-'}
                  </p>
                </div>
              </div>
            </CardBody>
          </Card>

          {/* Cadastros */}
          <Card>
            <CardHeader>
              <h3 className="text-lg font-semibold">Cadastros</h3>
            </CardHeader>
            <CardBody>
              {cadastros.length > 0 ? (
                <div className="space-y-3">
                  {cadastros.map((cadastro) => (
                    <div key={cadastro.id} className="flex items-center justify-between p-3 bg-default-50 rounded-lg">
                      <div>
                        <p className="text-sm font-medium">Cadastro #{cadastro.id}</p>
                        <p className="text-xs text-default-500">
                          {formatDate(cadastro.created_at)}
                        </p>
                      </div>
                      <StatusBadge status={cadastro.status} size="sm" />
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-default-500">Nenhum cadastro encontrado</p>
              )}
            </CardBody>
          </Card>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      <Modal isOpen={isOpen} onClose={onClose}>
        <ModalContent>
          <ModalHeader className="flex flex-col gap-1">
            Confirmar Remoção
          </ModalHeader>
          <ModalBody>
            <p>
              Tem certeza que deseja remover o associado{' '}
              <strong>{associado.nome}</strong>?
            </p>
            <p className="text-sm text-default-500">
              Esta ação não pode ser desfeita e todos os cadastros relacionados serão removidos.
            </p>
          </ModalBody>
          <ModalFooter>
            <Button color="default" variant="light" onPress={onClose}>
              Cancelar
            </Button>
            <Button
              color="danger"
              onPress={handleDelete}
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
