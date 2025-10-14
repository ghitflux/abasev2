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
  useDisclosure,
  Input,
  Textarea,
  Select,
  SelectItem
} from '@heroui/react';
import { StatusBadge, Timeline, DocumentPreview, useToast } from '@abase/ui';
import { useAuth } from '@/contexts/AuthContext';
import { formatDate, formatCurrency, formatCPF } from '@/lib/formatters';
import { 
  ArrowLeftIcon, 
  DollarSignIcon,
  FileTextIcon,
  CheckCircleIcon,
  UploadIcon,
  DownloadIcon,
  EyeIcon,
  UserIcon,
  CalculatorIcon,
  ClockIcon,
  AlertCircleIcon
} from 'lucide-react';

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
  approved_at?: string;
  payment_received_at?: string;
  contract_generated_at?: string;
  contract_signed_at?: string;
  completed_at?: string;
  // Payment details
  payment_method?: string;
  payment_date?: string;
  payment_receipt?: string;
  // Contract details
  contract_url?: string;
  signature_url?: string;
}

interface TimelineEvent {
  id: string;
  title: string;
  description: string;
  date: string;
  status: 'completed' | 'current' | 'pending';
  icon: React.ReactNode;
}

interface PaymentData {
  valor: number;
  forma_pagamento: string;
  data_pagamento: string;
  comprovante?: File;
  observacoes?: string;
}

export default function TesourariaCadastroDetailPage() {
  const router = useRouter();
  const params = useParams();
  const { apiClient, user } = useAuth();
  const { addToast } = useToast();
  const { isOpen: isPaymentOpen, onOpen: onPaymentOpen, onClose: onPaymentClose } = useDisclosure();
  const { isOpen: isContractOpen, onOpen: onContractOpen, onClose: onContractClose } = useDisclosure();
  const { isOpen: isDocumentOpen, onOpen: onDocumentOpen, onClose: onDocumentClose } = useDisclosure();

  // State
  const [cadastro, setCadastro] = useState<Cadastro | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState<Documento | null>(null);
  const [paymentData, setPaymentData] = useState<PaymentData>({
    valor: 0,
    forma_pagamento: '',
    data_pagamento: '',
    observacoes: ''
  });

  const cadastroId = params.id as string;

  // Fetch cadastro details
  const fetchCadastro = async () => {
    if (!apiClient) return;

    try {
      setLoading(true);
      setError("");

      const response = await apiClient.get<Cadastro>(`/api/v1/tesouraria/cadastros/${cadastroId}`);

      if (response.error) {
        throw new Error(response.error.message);
      }

      if (response.data) {
        setCadastro(response.data);
        // Set payment data if payment already received
        if (response.data.payment_received_at) {
          setPaymentData({
            valor: response.data.valor_total,
            forma_pagamento: response.data.payment_method || '',
            data_pagamento: response.data.payment_date || '',
            observacoes: ''
          });
        }
      }
    } catch (err: any) {
      console.error('Error fetching cadastro for treasury:', err);
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
          }
        ],
        status: 'APROVADO',
        observacoes: 'Cadastro aprovado para pagamento',
        valor_total: 250.00,
        created_at: '2024-01-15T10:30:00Z',
        updated_at: '2024-01-15T10:30:00Z',
        approved_at: '2024-01-15T14:20:00Z'
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

  // Handle register payment
  const handleRegisterPayment = () => {
    if (cadastro) {
      setPaymentData({
        valor: cadastro.valor_total,
        forma_pagamento: '',
        data_pagamento: new Date().toISOString().split('T')[0],
        observacoes: ''
      });
      onPaymentOpen();
    }
  };

  const confirmRegisterPayment = async () => {
    if (!cadastro || !apiClient) return;

    try {
      setIsProcessing(true);
      
      const formData = new FormData();
      formData.append('valor', paymentData.valor.toString());
      formData.append('forma_pagamento', paymentData.forma_pagamento);
      formData.append('data_pagamento', paymentData.data_pagamento);
      formData.append('observacoes', paymentData.observacoes || '');
      
      if (paymentData.comprovante) {
        formData.append('comprovante', paymentData.comprovante);
      }

      const response = await apiClient.post(`/api/v1/tesouraria/cadastros/${cadastro.id}/register-payment`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.error) {
        throw new Error(response.error.message);
      }

      addToast({
        type: 'success',
        title: 'Pagamento registrado',
        description: 'O pagamento foi registrado com sucesso.',
      });

      // Refresh data
      fetchCadastro();
      onPaymentClose();
    } catch (err: any) {
      console.error('Error registering payment:', err);
      addToast({
        type: 'error',
        title: 'Erro ao registrar pagamento',
        description: err.message || 'Não foi possível registrar o pagamento.',
      });
    } finally {
      setIsProcessing(false);
    }
  };

  // Handle generate contract
  const handleGenerateContract = async () => {
    if (!cadastro || !apiClient) return;

    try {
      setIsProcessing(true);
      
      const response = await apiClient.post(`/api/v1/tesouraria/cadastros/${cadastro.id}/generate-contract`);

      if (response.error) {
        throw new Error(response.error.message);
      }

      addToast({
        type: 'success',
        title: 'Contrato gerado',
        description: 'O contrato foi gerado com sucesso.',
      });

      // Refresh data
      fetchCadastro();
    } catch (err: any) {
      console.error('Error generating contract:', err);
      addToast({
        type: 'error',
        title: 'Erro ao gerar contrato',
        description: err.message || 'Não foi possível gerar o contrato.',
      });
    } finally {
      setIsProcessing(false);
    }
  };

  // Handle send for signature
  const handleSendForSignature = async () => {
    if (!cadastro || !apiClient) return;

    try {
      setIsProcessing(true);
      
      const response = await apiClient.post(`/api/v1/tesouraria/cadastros/${cadastro.id}/send-for-signature`);

      if (response.error) {
        throw new Error(response.error.message);
      }

      addToast({
        type: 'success',
        title: 'Enviado para assinatura',
        description: 'O contrato foi enviado para assinatura.',
      });

      // Refresh data
      fetchCadastro();
    } catch (err: any) {
      console.error('Error sending for signature:', err);
      addToast({
        type: 'error',
        title: 'Erro ao enviar para assinatura',
        description: err.message || 'Não foi possível enviar o contrato para assinatura.',
      });
    } finally {
      setIsProcessing(false);
    }
  };

  // Handle complete process
  const handleCompleteProcess = async () => {
    if (!cadastro || !apiClient) return;

    try {
      setIsProcessing(true);
      
      const response = await apiClient.post(`/api/v1/tesouraria/cadastros/${cadastro.id}/complete`);

      if (response.error) {
        throw new Error(response.error.message);
      }

      addToast({
        type: 'success',
        title: 'Processo concluído',
        description: 'O cadastro foi finalizado com sucesso.',
      });

      // Refresh data
      fetchCadastro();
    } catch (err: any) {
      console.error('Error completing process:', err);
      addToast({
        type: 'error',
        title: 'Erro ao finalizar processo',
        description: err.message || 'Não foi possível finalizar o processo.',
      });
    } finally {
      setIsProcessing(false);
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

    if (cadastro.approved_at) {
      events.push({
        id: 'approved',
        title: 'Aprovado',
        description: 'Cadastro foi aprovado pela análise',
        date: cadastro.approved_at,
        status: 'completed',
        icon: <CheckCircleIcon className="w-4 h-4" />
      });
    }

    if (cadastro.payment_received_at) {
      events.push({
        id: 'payment',
        title: 'Pagamento Recebido',
        description: 'Pagamento foi registrado',
        date: cadastro.payment_received_at,
        status: 'completed',
        icon: <DollarSignIcon className="w-4 h-4" />
      });
    }

    if (cadastro.contract_generated_at) {
      events.push({
        id: 'contract',
        title: 'Contrato Gerado',
        description: 'Contrato foi gerado',
        date: cadastro.contract_generated_at,
        status: 'completed',
        icon: <FileTextIcon className="w-4 h-4" />
      });
    }

    if (cadastro.contract_signed_at) {
      events.push({
        id: 'signed',
        title: 'Contrato Assinado',
        description: 'Contrato foi assinado',
        date: cadastro.contract_signed_at,
        status: 'completed',
        icon: <CheckCircleIcon className="w-4 h-4" />
      });
    }

    if (cadastro.completed_at) {
      events.push({
        id: 'completed',
        title: 'Processo Concluído',
        description: 'Cadastro foi finalizado',
        date: cadastro.completed_at,
        status: 'current',
        icon: <CheckCircleIcon className="w-4 h-4" />
      });
    }

    return events;
  };

  // Get current step
  const getCurrentStep = (cadastro: Cadastro) => {
    if (cadastro.completed_at) return 6;
    if (cadastro.contract_signed_at) return 5;
    if (cadastro.contract_generated_at) return 4;
    if (cadastro.payment_received_at) return 3;
    if (cadastro.approved_at) return 2;
    return 1;
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
                onPress={() => router.push('/tesouraria')}
                className="mt-4"
              >
                Voltar para Tesouraria
              </Button>
            </div>
          </CardBody>
        </Card>
      </div>
    );
  }

  const timelineEvents = generateTimelineEvents(cadastro);
  const currentStep = getCurrentStep(cadastro);
  const canRegisterPayment = cadastro.status === 'APROVADO';
  const canGenerateContract = cadastro.status === 'PAGAMENTO_RECEBIDO';
  const canSendForSignature = cadastro.status === 'CONTRATO_GERADO';
  const canComplete = cadastro.status === 'ASSINADO';

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
              Tesouraria - Cadastro #{cadastro.id}
            </h1>
            <p className="text-default-600">
              {cadastro.associado?.nome}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <StatusBadge status={cadastro.status} size="lg" />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Pipeline Progress */}
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold">Pipeline de Processamento</h2>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-default-600">Progresso</span>
                  <span className="text-sm font-medium">{currentStep}/6</span>
                </div>
                <div className="w-full bg-default-200 rounded-full h-2">
                  <div 
                    className="bg-primary h-2 rounded-full transition-all duration-300"
                    style={{ width: `${(currentStep / 6) * 100}%` }}
                  />
                </div>
                <div className="grid grid-cols-6 gap-2 text-xs">
                  <div className={`text-center p-2 rounded ${currentStep >= 1 ? 'bg-primary-100 text-primary' : 'bg-default-100 text-default-400'}`}>
                    Aprovado
                  </div>
                  <div className={`text-center p-2 rounded ${currentStep >= 2 ? 'bg-primary-100 text-primary' : 'bg-default-100 text-default-400'}`}>
                    Pagamento
                  </div>
                  <div className={`text-center p-2 rounded ${currentStep >= 3 ? 'bg-primary-100 text-primary' : 'bg-default-100 text-default-400'}`}>
                    Contrato
                  </div>
                  <div className={`text-center p-2 rounded ${currentStep >= 4 ? 'bg-primary-100 text-primary' : 'bg-default-100 text-default-400'}`}>
                    Assinatura
                  </div>
                  <div className={`text-center p-2 rounded ${currentStep >= 5 ? 'bg-primary-100 text-primary' : 'bg-default-100 text-default-400'}`}>
                    Assinado
                  </div>
                  <div className={`text-center p-2 rounded ${currentStep >= 6 ? 'bg-primary-100 text-primary' : 'bg-default-100 text-default-400'}`}>
                    Concluído
                  </div>
                </div>
              </div>
            </CardBody>
          </Card>

          {/* Actions */}
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold">Ações Disponíveis</h2>
            </CardHeader>
            <CardBody>
              <div className="flex flex-wrap gap-3">
                {canRegisterPayment && (
                  <Button
                    color="success"
                    startContent={<DollarSignIcon className="w-4 h-4" />}
                    onPress={handleRegisterPayment}
                    isLoading={isProcessing}
                  >
                    Registrar Pagamento
                  </Button>
                )}
                
                {canGenerateContract && (
                  <Button
                    color="primary"
                    startContent={<FileTextIcon className="w-4 h-4" />}
                    onPress={handleGenerateContract}
                    isLoading={isProcessing}
                  >
                    Gerar Contrato
                  </Button>
                )}
                
                {canSendForSignature && (
                  <Button
                    color="secondary"
                    startContent={<CheckCircleIcon className="w-4 h-4" />}
                    onPress={handleSendForSignature}
                    isLoading={isProcessing}
                  >
                    Enviar para Assinatura
                  </Button>
                )}
                
                {canComplete && (
                  <Button
                    color="success"
                    startContent={<CheckCircleIcon className="w-4 h-4" />}
                    onPress={handleCompleteProcess}
                    isLoading={isProcessing}
                  >
                    Finalizar Processo
                  </Button>
                )}
              </div>
            </CardBody>
          </Card>

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
              </div>
            </CardBody>
          </Card>

          {/* Payment Information */}
          {cadastro.payment_received_at && (
            <Card>
              <CardHeader>
                <h2 className="text-lg font-semibold">Informações de Pagamento</h2>
              </CardHeader>
              <CardBody>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-default-500">Valor</p>
                    <p className="font-medium">{formatCurrency(cadastro.valor_total)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-default-500">Forma de Pagamento</p>
                    <p className="font-medium">{cadastro.payment_method || '-'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-default-500">Data do Pagamento</p>
                    <p className="font-medium">
                      {cadastro.payment_date ? formatDate(cadastro.payment_date) : '-'}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-default-500">Comprovante</p>
                    <p className="font-medium">{cadastro.payment_receipt || '-'}</p>
                  </div>
                </div>
              </CardBody>
            </Card>
          )}

          {/* Contract Information */}
          {cadastro.contract_generated_at && (
            <Card>
              <CardHeader>
                <h2 className="text-lg font-semibold">Informações do Contrato</h2>
              </CardHeader>
              <CardBody>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-default-500">Contrato Gerado</p>
                      <p className="font-medium">
                        {formatDate(cadastro.contract_generated_at)}
                      </p>
                    </div>
                    {cadastro.contract_url && (
                      <Button
                        color="primary"
                        variant="bordered"
                        startContent={<DownloadIcon className="w-4 h-4" />}
                        onPress={() => window.open(cadastro.contract_url, '_blank')}
                      >
                        Download
                      </Button>
                    )}
                  </div>
                  
                  {cadastro.contract_signed_at && (
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-default-500">Contrato Assinado</p>
                        <p className="font-medium">
                          {formatDate(cadastro.contract_signed_at)}
                        </p>
                      </div>
                      {cadastro.signature_url && (
                        <Button
                          color="success"
                          variant="bordered"
                          startContent={<DownloadIcon className="w-4 h-4" />}
                          onPress={() => window.open(cadastro.signature_url, '_blank')}
                        >
                          Download
                        </Button>
                      )}
                    </div>
                  )}
                </div>
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
              <Timeline events={timelineEvents} />
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
                {cadastro.approved_at && (
                  <div>
                    <p className="text-sm text-default-500">Aprovado em</p>
                    <p className="font-medium">{formatDate(cadastro.approved_at)}</p>
                  </div>
                )}
              </div>
            </CardBody>
          </Card>
        </div>
      </div>

      {/* Register Payment Modal */}
      <Modal isOpen={isPaymentOpen} onClose={onPaymentClose} size="2xl">
        <ModalContent>
          <ModalHeader className="flex flex-col gap-1">
            Registrar Pagamento
          </ModalHeader>
          <ModalBody>
            <div className="space-y-4">
              <Input
                label="Valor"
                placeholder="0,00"
                value={paymentData.valor.toString()}
                onChange={(e) => setPaymentData(prev => ({ ...prev, valor: parseFloat(e.target.value) || 0 }))}
                startContent="R$"
                type="number"
                min="0"
                step="0.01"
                isRequired
              />
              
              <Select
                label="Forma de Pagamento"
                placeholder="Selecione a forma de pagamento"
                selectedKeys={paymentData.forma_pagamento ? [paymentData.forma_pagamento] : []}
                onSelectionChange={(keys) => {
                  const value = Array.from(keys)[0] as string;
                  setPaymentData(prev => ({ ...prev, forma_pagamento: value }));
                }}
                isRequired
              >
                <SelectItem key="PIX" value="PIX">PIX</SelectItem>
                <SelectItem key="TRANSFERENCIA" value="TRANSFERENCIA">Transferência Bancária</SelectItem>
                <SelectItem key="BOLETO" value="BOLETO">Boleto Bancário</SelectItem>
                <SelectItem key="CARTAO" value="CARTAO">Cartão de Crédito</SelectItem>
                <SelectItem key="DINHEIRO" value="DINHEIRO">Dinheiro</SelectItem>
              </Select>
              
              <Input
                label="Data do Pagamento"
                type="date"
                value={paymentData.data_pagamento}
                onChange={(e) => setPaymentData(prev => ({ ...prev, data_pagamento: e.target.value }))}
                isRequired
              />
              
              <div>
                <label className="block text-sm font-medium text-default-700 mb-2">
                  Comprovante de Pagamento
                </label>
                <input
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      setPaymentData(prev => ({ ...prev, comprovante: file }));
                    }
                  }}
                  className="block w-full text-sm text-default-600 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
                />
              </div>
              
              <Textarea
                label="Observações"
                placeholder="Observações adicionais sobre o pagamento..."
                value={paymentData.observacoes}
                onChange={(e) => setPaymentData(prev => ({ ...prev, observacoes: e.target.value }))}
                minRows={3}
              />
            </div>
          </ModalBody>
          <ModalFooter>
            <Button color="default" variant="light" onPress={onPaymentClose}>
              Cancelar
            </Button>
            <Button
              color="success"
              onPress={confirmRegisterPayment}
              isLoading={isProcessing}
              startContent={<DollarSignIcon className="w-4 h-4" />}
              isDisabled={!paymentData.forma_pagamento || !paymentData.data_pagamento}
            >
              Registrar Pagamento
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </div>
  );
}



