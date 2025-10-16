"use client";

import React, { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  Card,
  CardBody,
  CardHeader,
  Button,
  Spinner,
  Chip,
  Divider,
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  useDisclosure
} from '@heroui/react';
import { StatusBadge, Timeline, DocumentPreview, useToast } from '@abase/ui';
import { useAuth } from '@/contexts/AuthContext';
import { formatDate, formatCurrency, formatCPF } from '@/lib/formatters';
import { 
  ArrowLeftIcon, 
  PencilIcon as EditIcon, 
  PaperAirplaneIcon as SendIcon, 
  ArrowDownTrayIcon as DownloadIcon,
  EyeIcon,
  DocumentTextIcon as FileTextIcon,
  UserIcon,
  CalculatorIcon
} from '@heroicons/react/24/outline';

interface Associado {
  id: number;
  nome: string;
  cpf: string;
  email?: string;
  telefone?: string;
  data_nascimento?: string;
  profissao?: string;
  estado_civil?: string;
  nacionalidade?: string;
  endereco?: {
    cep: string;
    logradouro: string;
    numero: string;
    complemento?: string;
    bairro: string;
    cidade: string;
    estado: string;
  };
}

interface Dependente {
  id: number;
  nome: string;
  cpf: string;
  data_nascimento: string;
  parentesco: string;
  valor_dependente: number;
}

interface Documento {
  id: number;
  tipo: string;
  nome_arquivo: string;
  tamanho: number;
  url?: string;
  created_at: string;
}

interface Cadastro {
  id: number;
  associado_id: number;
  associado?: Associado;
  dependentes: Dependente[];
  documentos: Documento[];
  status: string;
  observacoes?: string;
  valor_total: number;
  created_at: string;
  updated_at: string;
  submitted_at?: string;
  approved_at?: string;
  completed_at?: string;
}

interface TimelineEvent {
  id: string;
  title: string;
  description: string;
  date: string;
  status: 'completed' | 'current' | 'pending';
  icon: React.ReactNode;
}

export default function CadastroDetailPage() {
  const router = useRouter();
  const params = useParams();
  const { apiClient, user } = useAuth();
  const { addToast } = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();

  // State
  const [cadastro, setCadastro] = useState<Cadastro | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState<Documento | null>(null);

  const [cadastroId, setCadastroId] = useState<string | null>(null);

  useEffect(() => {
    const loadParams = async () => {
      const resolvedParams = await params;
      if (resolvedParams.id && typeof resolvedParams.id === 'string') {
        setCadastroId(resolvedParams.id);
      }
    };
    loadParams();
  }, [params]);

  // Fetch cadastro details
  const fetchCadastro = async () => {
    if (!apiClient || !cadastroId) return;

    try {
      setLoading(true);
      setError("");

      const response = await apiClient.get<Cadastro>(`/api/v1/cadastros/cadastros/${cadastroId}`);

      if (response.error) {
        throw new Error(response.error.message);
      }

      if (response.data) {
        setCadastro(response.data);
      }
    } catch (err: any) {
      console.error('Error fetching cadastro:', err);
      setError(err.message || 'Erro ao carregar cadastro');
      
      // Mock data for development
      const mockCadastro: Cadastro = {
        id: parseInt(cadastroId),
        associado_id: 1,
        associado: {
          id: 1,
          nome: 'João Silva',
          cpf: '12345678901',
          email: 'joao@email.com',
          telefone: '11999999999',
          data_nascimento: '1985-05-15',
          profissao: 'Engenheiro',
          estado_civil: 'CASADO',
          nacionalidade: 'Brasileiro',
          endereco: {
            cep: '01234567',
            logradouro: 'Rua das Flores',
            numero: '123',
            complemento: 'Apto 45',
            bairro: 'Centro',
            cidade: 'São Paulo',
            estado: 'SP'
          }
        },
        dependentes: [
          {
            id: 1,
            nome: 'Maria Silva',
            cpf: '98765432100',
            data_nascimento: '1990-03-20',
            parentesco: 'CONJUGE',
            valor_dependente: 50.00
          },
          {
            id: 2,
            nome: 'Pedro Silva',
            cpf: '11122233344',
            data_nascimento: '2010-08-10',
            parentesco: 'FILHO',
            valor_dependente: 50.00
          }
        ],
        documentos: [
          {
            id: 1,
            tipo: 'COMPROVANTE',
            nome_arquivo: 'comprovante_renda.pdf',
            tamanho: 1024000,
            url: '/documents/comprovante_renda.pdf',
            created_at: '2024-01-15T10:30:00Z'
          },
          {
            id: 2,
            tipo: 'IDENTIDADE',
            nome_arquivo: 'rg_frente.jpg',
            tamanho: 512000,
            url: '/documents/rg_frente.jpg',
            created_at: '2024-01-15T10:30:00Z'
          }
        ],
        status: 'SUBMETIDO',
        observacoes: 'Cadastro submetido para análise',
        valor_total: 250.00,
        created_at: '2024-01-15T10:30:00Z',
        updated_at: '2024-01-15T10:30:00Z',
        submitted_at: '2024-01-15T10:30:00Z'
      };
      
      setCadastro(mockCadastro);
    } finally {
      setLoading(false);
    }
  };

  // Initial load
  useEffect(() => {
    if (cadastroId) {
      fetchCadastro();
    }
  }, [cadastroId, apiClient]);

  // Handle submit to analysis
  const handleSubmitToAnalysis = async () => {
    if (!cadastro || !apiClient) return;

    try {
      setIsSubmitting(true);
      
      const response = await apiClient.post(`/api/v1/cadastros/cadastros/${cadastro.id}/submit`);

      if (response.error) {
        throw new Error(response.error.message);
      }

      addToast({
        type: 'success',
        title: 'Cadastro submetido',
        description: 'O cadastro foi enviado para análise com sucesso.',
      });

      // Refresh data
      fetchCadastro();
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

  // Generate timeline events
  const generateTimelineEvents = (cadastro: Cadastro): TimelineEvent[] => {
    const events: TimelineEvent[] = [
      {
        id: 'created',
        title: 'Cadastro Criado',
        description: 'Cadastro foi criado no sistema',
        date: cadastro.created_at,
        status: 'completed',
        icon: <UserIcon className="w-4 h-4" />
      }
    ];

    if (cadastro.submitted_at) {
      events.push({
        id: 'submitted',
        title: 'Submetido para Análise',
        description: 'Cadastro foi enviado para análise',
        date: cadastro.submitted_at,
        status: cadastro.status === 'SUBMETIDO' ? 'current' : 'completed',
        icon: <SendIcon className="w-4 h-4" />
      });
    }

    if (cadastro.approved_at) {
      events.push({
        id: 'approved',
        title: 'Aprovado',
        description: 'Cadastro foi aprovado pela análise',
        date: cadastro.approved_at,
        status: cadastro.status === 'APROVADO' ? 'current' : 'completed',
        icon: <CalculatorIcon className="w-4 h-4" />
      });
    }

    if (cadastro.completed_at) {
      events.push({
        id: 'completed',
        title: 'Concluído',
        description: 'Processo de cadastro foi finalizado',
        date: cadastro.completed_at,
        status: 'current',
        icon: <FileTextIcon className="w-4 h-4" />
      });
    }

    return events;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !cadastro) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="flex items-center gap-4 mb-6">
          <Button
            isIconOnly
            variant="light"
            onPress={() => router.back()}
          >
            <ArrowLeftIcon className="w-5 h-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-default-900">Erro</h1>
          </div>
        </div>
        
        <Card>
          <CardBody>
            <div className="text-center py-8">
              <p className="text-danger">{error || 'Cadastro não encontrado'}</p>
              <Button
                color="primary"
                variant="bordered"
                onPress={() => router.push('/cadastros')}
                className="mt-4"
              >
                Voltar para Lista
              </Button>
            </div>
          </CardBody>
        </Card>
      </div>
    );
  }

  const timelineEvents = generateTimelineEvents(cadastro);

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Button
            isIconOnly
            variant="light"
            onPress={() => router.back()}
          >
            <ArrowLeftIcon className="w-5 h-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-default-900">
              Cadastro #{cadastro.id}
            </h1>
            <p className="text-default-600">
              {cadastro.associado?.nome}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <StatusBadge status={cadastro.status} size="lg" />
          
          {cadastro.status === 'RASCUNHO' && (
            <>
              <Button
                color="primary"
                variant="bordered"
                startContent={<EditIcon className="w-4 h-4" />}
                onPress={() => router.push(`/cadastros/${cadastro.id}/editar`)}
              >
                Editar
              </Button>
              <Button
                color="primary"
                startContent={<SendIcon className="w-4 h-4" />}
                onPress={handleSubmitToAnalysis}
                isLoading={isSubmitting}
              >
                Submeter para Análise
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Associado Information */}
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold">Informações do Associado</h2>
            </CardHeader>
            <CardBody>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-default-500">Nome Completo</p>
                  <p className="font-medium">{cadastro.associado?.nome}</p>
                </div>
                <div>
                  <p className="text-sm text-default-500">CPF</p>
                  <p className="font-medium">{formatCPF(cadastro.associado?.cpf || '')}</p>
                </div>
                <div>
                  <p className="text-sm text-default-500">Email</p>
                  <p className="font-medium">{cadastro.associado?.email || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-default-500">Telefone</p>
                  <p className="font-medium">{cadastro.associado?.telefone || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-default-500">Data de Nascimento</p>
                  <p className="font-medium">
                    {cadastro.associado?.data_nascimento 
                      ? formatDate(cadastro.associado.data_nascimento)
                      : '-'
                    }
                  </p>
                </div>
                <div>
                  <p className="text-sm text-default-500">Profissão</p>
                  <p className="font-medium">{cadastro.associado?.profissao || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-default-500">Estado Civil</p>
                  <p className="font-medium">{cadastro.associado?.estado_civil || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-default-500">Nacionalidade</p>
                  <p className="font-medium">{cadastro.associado?.nacionalidade || '-'}</p>
                </div>
              </div>

              {cadastro.associado?.endereco && (
                <>
                  <Divider className="my-4" />
                  <h3 className="font-semibold mb-3">Endereço</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-default-500">CEP</p>
                      <p className="font-medium">{cadastro.associado.endereco.cep}</p>
                    </div>
                    <div>
                      <p className="text-sm text-default-500">Logradouro</p>
                      <p className="font-medium">{cadastro.associado.endereco.logradouro}</p>
                    </div>
                    <div>
                      <p className="text-sm text-default-500">Número</p>
                      <p className="font-medium">{cadastro.associado.endereco.numero}</p>
                    </div>
                    <div>
                      <p className="text-sm text-default-500">Complemento</p>
                      <p className="font-medium">{cadastro.associado.endereco.complemento || '-'}</p>
                    </div>
                    <div>
                      <p className="text-sm text-default-500">Bairro</p>
                      <p className="font-medium">{cadastro.associado.endereco.bairro}</p>
                    </div>
                    <div>
                      <p className="text-sm text-default-500">Cidade/Estado</p>
                      <p className="font-medium">
                        {cadastro.associado.endereco.cidade}, {cadastro.associado.endereco.estado}
                      </p>
                    </div>
                  </div>
                </>
              )}
            </CardBody>
          </Card>

          {/* Dependentes */}
          {cadastro.dependentes.length > 0 && (
            <Card>
              <CardHeader>
                <h2 className="text-lg font-semibold">
                  Dependentes ({cadastro.dependentes.length})
                </h2>
              </CardHeader>
              <CardBody>
                <div className="space-y-4">
                  {cadastro.dependentes.map((dependente) => (
                    <div key={dependente.id} className="border border-default-200 rounded-lg p-4">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <p className="text-sm text-default-500">Nome</p>
                          <p className="font-medium">{dependente.nome}</p>
                        </div>
                        <div>
                          <p className="text-sm text-default-500">CPF</p>
                          <p className="font-medium">{formatCPF(dependente.cpf)}</p>
                        </div>
                        <div>
                          <p className="text-sm text-default-500">Data de Nascimento</p>
                          <p className="font-medium">{formatDate(dependente.data_nascimento)}</p>
                        </div>
                        <div>
                          <p className="text-sm text-default-500">Parentesco</p>
                          <p className="font-medium">{dependente.parentesco}</p>
                        </div>
                        <div>
                          <p className="text-sm text-default-500">Valor</p>
                          <p className="font-medium">{formatCurrency(dependente.valor_dependente)}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardBody>
            </Card>
          )}

          {/* Documentos */}
          {cadastro.documentos.length > 0 && (
            <Card>
              <CardHeader>
                <h2 className="text-lg font-semibold">
                  Documentos ({cadastro.documentos.length})
                </h2>
              </CardHeader>
              <CardBody>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {cadastro.documentos.map((documento) => (
                    <div key={documento.id} className="border border-default-200 rounded-lg p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <FileTextIcon className="w-5 h-5 text-primary" />
                          <div>
                            <p className="font-medium">{documento.nome_arquivo}</p>
                            <p className="text-sm text-default-500">
                              {Math.round(documento.tamanho / 1024)} KB
                            </p>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button
                            isIconOnly
                            size="sm"
                            variant="light"
                            onPress={() => {
                              setSelectedDocument(documento);
                              onOpen();
                            }}
                          >
                            <EyeIcon className="w-4 h-4" />
                          </Button>
                          {documento.url && (
                            <Button
                              isIconOnly
                              size="sm"
                              variant="light"
                              onPress={() => window.open(documento.url, '_blank')}
                            >
                              <DownloadIcon className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardBody>
            </Card>
          )}

          {/* Observações */}
          {cadastro.observacoes && (
            <Card>
              <CardHeader>
                <h2 className="text-lg font-semibold">Observações</h2>
              </CardHeader>
              <CardBody>
                <p className="text-default-700 whitespace-pre-wrap">
                  {cadastro.observacoes}
                </p>
              </CardBody>
            </Card>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Timeline */}
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold">Status do Processo</h2>
            </CardHeader>
            <CardBody>
              <Timeline events={timelineEvents.map(e => ({
                ...e,
                // Converte o campo 'date' para 'timestamp' conforme esperado pelo componente Timeline
                timestamp: new Date(e.date).toISOString()
              }))} />
            </CardBody>
          </Card>

          {/* Resumo Financeiro */}
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold">Resumo Financeiro</h2>
            </CardHeader>
            <CardBody>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-default-600">Valor Base:</span>
                  <span className="font-medium">R$ 150,00</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-default-600">
                    Dependentes ({cadastro.dependentes.length}):
                  </span>
                  <span className="font-medium">
                    {formatCurrency(cadastro.dependentes.length * 50.00)}
                  </span>
                </div>
                <Divider />
                <div className="flex justify-between text-lg">
                  <span className="font-semibold">Total:</span>
                  <span className="font-bold text-primary">
                    {formatCurrency(cadastro.valor_total)}
                  </span>
                </div>
              </div>
            </CardBody>
          </Card>

          {/* Informações do Cadastro */}
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold">Informações</h2>
            </CardHeader>
            <CardBody>
              <div className="space-y-3">
                <div>
                  <p className="text-sm text-default-500">Criado em</p>
                  <p className="font-medium">{formatDate(cadastro.created_at)}</p>
                </div>
                <div>
                  <p className="text-sm text-default-500">Atualizado em</p>
                  <p className="font-medium">{formatDate(cadastro.updated_at)}</p>
                </div>
                {cadastro.submitted_at && (
                  <div>
                    <p className="text-sm text-default-500">Submetido em</p>
                    <p className="font-medium">{formatDate(cadastro.submitted_at)}</p>
                  </div>
                )}
              </div>
            </CardBody>
          </Card>
        </div>
      </div>

      {/* Document Preview Modal */}
      <Modal isOpen={isOpen} onClose={onClose} size="4xl">
        <ModalContent>
          <ModalHeader>
            {selectedDocument?.nome_arquivo}
          </ModalHeader>
          <ModalBody>
            {selectedDocument && (
              <DocumentPreview
                file={selectedDocument.url || ''}
                fileName={selectedDocument.nome_arquivo}
                fileSize={selectedDocument.tamanho}
              />
            )}
          </ModalBody>
          <ModalFooter>
            <Button color="default" variant="light" onPress={onClose}>
              Fechar
            </Button>
            {selectedDocument?.url && (
              <Button
                color="primary"
                startContent={<DownloadIcon className="w-4 h-4" />}
                onPress={() => window.open(selectedDocument.url, '_blank')}
              >
                Download
              </Button>
            )}
          </ModalFooter>
        </ModalContent>
      </Modal>
    </div>
  );
}

