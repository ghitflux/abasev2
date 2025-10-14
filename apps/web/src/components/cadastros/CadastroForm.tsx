"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Button,
  Input,
  Textarea,
  Card,
  CardBody,
  CardHeader,
  Select,
  SelectItem,
  Divider,
  Spinner,
  Chip,
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  useDisclosure
} from '@heroui/react';
import { MultiStepForm, FileUpload, useToast } from '@abase/ui';
import { useAuth } from '@/contexts/AuthContext';
import { formatCPF, formatCurrency, formatDateForInput } from '@/lib/formatters';
import { validateCPF, validateRequired } from '@/lib/validators';
import { PlusIcon, TrashIcon, SearchIcon, CalculatorIcon, FileTextIcon } from 'lucide-react';

// Types
interface Associado {
  id: number;
  nome: string;
  cpf: string;
  email?: string;
  telefone?: string;
}

interface Dependente {
  id?: number;
  nome: string;
  cpf: string;
  data_nascimento: string;
  parentesco: string;
  valor_dependente: number;
}

interface Documento {
  id?: number;
  tipo: string;
  arquivo: File | string;
  nome_arquivo: string;
  tamanho: number;
}

interface CadastroFormData {
  associado_id?: number;
  associado_novo?: {
    nome: string;
    cpf: string;
    email: string;
    telefone: string;
    data_nascimento: string;
    profissao: string;
    estado_civil: string;
    nacionalidade: string;
    endereco: {
      cep: string;
      logradouro: string;
      numero: string;
      complemento?: string;
      bairro: string;
      cidade: string;
      estado: string;
    };
  };
  dependentes: Dependente[];
  documentos: Documento[];
  observacoes?: string;
  valor_total: number;
}

// Validation schemas
const associadoNovoSchema = z.object({
  nome: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres'),
  cpf: z.string().refine(validateCPF, 'CPF inválido'),
  email: z.string().email('Email inválido'),
  telefone: z.string().min(10, 'Telefone deve ter pelo menos 10 dígitos'),
  data_nascimento: z.string().min(1, 'Data de nascimento é obrigatória'),
  profissao: z.string().min(1, 'Profissão é obrigatória'),
  estado_civil: z.string().min(1, 'Estado civil é obrigatório'),
  nacionalidade: z.string().min(1, 'Nacionalidade é obrigatória'),
  endereco: z.object({
    cep: z.string().min(8, 'CEP deve ter 8 dígitos'),
    logradouro: z.string().min(1, 'Logradouro é obrigatório'),
    numero: z.string().min(1, 'Número é obrigatório'),
    complemento: z.string().optional(),
    bairro: z.string().min(1, 'Bairro é obrigatório'),
    cidade: z.string().min(1, 'Cidade é obrigatória'),
    estado: z.string().min(2, 'Estado é obrigatório'),
  }),
});

const dependenteSchema = z.object({
  nome: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres'),
  cpf: z.string().refine(validateCPF, 'CPF inválido'),
  data_nascimento: z.string().min(1, 'Data de nascimento é obrigatória'),
  parentesco: z.string().min(1, 'Parentesco é obrigatório'),
  valor_dependente: z.number().min(0, 'Valor deve ser positivo'),
});

const cadastroSchema = z.object({
  associado_id: z.number().optional(),
  associado_novo: associadoNovoSchema.optional(),
  dependentes: z.array(dependenteSchema),
  documentos: z.array(z.object({
    tipo: z.string().min(1, 'Tipo de documento é obrigatório'),
    arquivo: z.any(),
    nome_arquivo: z.string().min(1, 'Nome do arquivo é obrigatório'),
    tamanho: z.number().min(1, 'Tamanho do arquivo é obrigatório'),
  })),
  observacoes: z.string().optional(),
  valor_total: z.number().min(0, 'Valor total deve ser positivo'),
}).refine((data) => {
  return data.associado_id || data.associado_novo;
}, {
  message: 'Selecione um associado existente ou preencha os dados do novo associado',
  path: ['associado_id'],
});

interface CadastroFormProps {
  initialData?: Partial<CadastroFormData>;
  onSubmit: (data: CadastroFormData) => Promise<void>;
  isLoading?: boolean;
  mode?: 'create' | 'edit';
}

export default function CadastroForm({ 
  initialData, 
  onSubmit, 
  isLoading = false,
  mode = 'create' 
}: CadastroFormProps) {
  const router = useRouter();
  const { apiClient } = useAuth();
  const { addToast } = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();

  // State
  const [currentStep, setCurrentStep] = useState(0);
  const [associados, setAssociados] = useState<Associado[]>([]);
  const [searchAssociado, setSearchAssociado] = useState('');
  const [loadingAssociados, setLoadingAssociados] = useState(false);
  const [selectedAssociado, setSelectedAssociado] = useState<Associado | null>(null);
  const [useNewAssociado, setUseNewAssociado] = useState(false);
  const [calculatingValues, setCalculatingValues] = useState(false);

  // Form setup
  const {
    control,
    handleSubmit,
    watch,
    setValue,
    getValues,
    formState: { errors, isValid },
    reset
  } = useForm<CadastroFormData>({
    resolver: zodResolver(cadastroSchema),
    defaultValues: {
      dependentes: [],
      documentos: [],
      valor_total: 0,
      ...initialData,
    },
    mode: 'onChange',
  });

  const watchedDependentes = watch('dependentes');
  const watchedAssociadoId = watch('associado_id');
  const watchedAssociadoNovo = watch('associado_novo');

  // Steps configuration
  const steps = [
    {
      title: 'Associado',
      description: 'Selecione ou cadastre o associado',
      icon: <SearchIcon className="w-5 h-5" />,
    },
    {
      title: 'Dependentes',
      description: 'Adicione os dependentes',
      icon: <PlusIcon className="w-5 h-5" />,
    },
    {
      title: 'Valores',
      description: 'Calcule os valores',
      icon: <CalculatorIcon className="w-5 h-5" />,
    },
    {
      title: 'Documentos',
      description: 'Anexe os documentos',
      icon: <FileTextIcon className="w-5 h-5" />,
    },
  ];

  // Fetch associados
  const fetchAssociados = async (search: string = '') => {
    if (!apiClient) return;

    try {
      setLoadingAssociados(true);
      
      const params = new URLSearchParams();
      if (search) {
        params.append('search', search);
      }
      params.append('limit', '20');

      const response = await apiClient.get<{
        items: Associado[];
        total: number;
      }>(`/api/v1/associados?${params}`);

      if (response.data) {
        setAssociados(response.data.items);
      }
    } catch (err: any) {
      console.error('Error fetching associados:', err);
      // Mock data for development
      setAssociados([
        {
          id: 1,
          nome: 'João Silva',
          cpf: '12345678901',
          email: 'joao@email.com',
          telefone: '11999999999'
        },
        {
          id: 2,
          nome: 'Maria Santos',
          cpf: '98765432100',
          email: 'maria@email.com',
          telefone: '11888888888'
        }
      ]);
    } finally {
      setLoadingAssociados(false);
    }
  };

  // Initial load
  useEffect(() => {
    fetchAssociados();
  }, [apiClient]);

  // Search associados
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (searchAssociado.length >= 2) {
        fetchAssociados(searchAssociado);
      } else if (searchAssociado.length === 0) {
        fetchAssociados();
      }
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [searchAssociado]);

  // Calculate values
  const calculateValues = async () => {
    try {
      setCalculatingValues(true);
      
      const dependentes = getValues('dependentes');
      const valorBase = 150.00; // Valor base da associação
      const valorDependente = 50.00; // Valor por dependente
      
      const valorTotal = valorBase + (dependentes.length * valorDependente);
      
      setValue('valor_total', valorTotal);
      
      addToast({
        type: 'success',
        title: 'Valores calculados',
        description: `Valor total: ${formatCurrency(valorTotal)}`,
      });
    } catch (err: any) {
      console.error('Error calculating values:', err);
      addToast({
        type: 'error',
        title: 'Erro ao calcular valores',
        description: 'Não foi possível calcular os valores automaticamente.',
      });
    } finally {
      setCalculatingValues(false);
    }
  };

  // Add dependente
  const addDependente = () => {
    const currentDependentes = getValues('dependentes') || [];
    const newDependente: Dependente = {
      nome: '',
      cpf: '',
      data_nascimento: '',
      parentesco: '',
      valor_dependente: 50.00,
    };
    
    setValue('dependentes', [...currentDependentes, newDependente]);
  };

  // Remove dependente
  const removeDependente = (index: number) => {
    const currentDependentes = getValues('dependentes') || [];
    const updatedDependentes = currentDependentes.filter((_, i) => i !== index);
    setValue('dependentes', updatedDependentes);
  };

  // Update dependente
  const updateDependente = (index: number, field: keyof Dependente, value: any) => {
    const currentDependentes = getValues('dependentes') || [];
    const updatedDependentes = [...currentDependentes];
    updatedDependentes[index] = { ...updatedDependentes[index], [field]: value };
    setValue('dependentes', updatedDependentes);
  };

  // Add documento
  const addDocumento = (files: File[]) => {
    const currentDocumentos = getValues('documentos') || [];
    
    const newDocumentos: Documento[] = files.map(file => ({
      tipo: 'COMPROVANTE',
      arquivo: file,
      nome_arquivo: file.name,
      tamanho: file.size,
    }));
    
    setValue('documentos', [...currentDocumentos, ...newDocumentos]);
  };

  // Remove documento
  const removeDocumento = (index: number) => {
    const currentDocumentos = getValues('documentos') || [];
    const updatedDocumentos = currentDocumentos.filter((_, i) => i !== index);
    setValue('documentos', updatedDocumentos);
  };

  // Handle form submission
  const handleFormSubmit = async (data: CadastroFormData) => {
    try {
      await onSubmit(data);
    } catch (err: any) {
      console.error('Error submitting form:', err);
      addToast({
        type: 'error',
        title: 'Erro ao salvar',
        description: err.message || 'Não foi possível salvar o cadastro.',
      });
    }
  };

  // Render step content
  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <div className="space-y-6">
            <div className="flex gap-4">
              <Button
                variant={!useNewAssociado ? 'solid' : 'bordered'}
                color={!useNewAssociado ? 'primary' : 'default'}
                onPress={() => {
                  setUseNewAssociado(false);
                  setValue('associado_novo', undefined);
                }}
                className="flex-1"
              >
                Associado Existente
              </Button>
              <Button
                variant={useNewAssociado ? 'solid' : 'bordered'}
                color={useNewAssociado ? 'primary' : 'default'}
                onPress={() => {
                  setUseNewAssociado(true);
                  setValue('associado_id', undefined);
                  setSelectedAssociado(null);
                }}
                className="flex-1"
              >
                Novo Associado
              </Button>
            </div>

            {!useNewAssociado ? (
              <div className="space-y-4">
                <Input
                  placeholder="Buscar associado por nome ou CPF..."
                  value={searchAssociado}
                  onChange={(e) => setSearchAssociado(e.target.value)}
                  startContent={<SearchIcon className="w-4 h-4 text-default-400" />}
                  isLoading={loadingAssociados}
                />

                <div className="max-h-60 overflow-y-auto space-y-2">
                  {associados.map((associado) => (
                    <Card
                      key={associado.id}
                      isPressable
                      isHoverable
                      className={`cursor-pointer transition-colors ${
                        selectedAssociado?.id === associado.id
                          ? 'border-2 border-primary bg-primary-50'
                          : 'border border-default-200'
                      }`}
                      onPress={() => {
                        setSelectedAssociado(associado);
                        setValue('associado_id', associado.id);
                      }}
                    >
                      <CardBody className="p-4">
                        <div className="flex justify-between items-start">
                          <div>
                            <p className="font-semibold">{associado.nome}</p>
                            <p className="text-sm text-default-600">
                              CPF: {formatCPF(associado.cpf)}
                            </p>
                            {associado.email && (
                              <p className="text-sm text-default-500">
                                {associado.email}
                              </p>
                            )}
                          </div>
                          {selectedAssociado?.id === associado.id && (
                            <Chip color="primary" size="sm">
                              Selecionado
                            </Chip>
                          )}
                        </div>
                      </CardBody>
                    </Card>
                  ))}
                </div>

                {associados.length === 0 && !loadingAssociados && (
                  <div className="text-center py-8 text-default-500">
                    Nenhum associado encontrado
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Controller
                    name="associado_novo.nome"
                    control={control}
                    render={({ field }) => (
                      <Input
                        {...field}
                        label="Nome Completo"
                        placeholder="Digite o nome completo"
                        isInvalid={!!errors.associado_novo?.nome}
                        errorMessage={errors.associado_novo?.nome?.message}
                        isRequired
                      />
                    )}
                  />

                  <Controller
                    name="associado_novo.cpf"
                    control={control}
                    render={({ field }) => (
                      <Input
                        {...field}
                        label="CPF"
                        placeholder="000.000.000-00"
                        value={formatCPF(field.value || '')}
                        onChange={(e) => field.onChange(e.target.value)}
                        isInvalid={!!errors.associado_novo?.cpf}
                        errorMessage={errors.associado_novo?.cpf?.message}
                        isRequired
                      />
                    )}
                  />

                  <Controller
                    name="associado_novo.email"
                    control={control}
                    render={({ field }) => (
                      <Input
                        {...field}
                        label="Email"
                        placeholder="email@exemplo.com"
                        type="email"
                        isInvalid={!!errors.associado_novo?.email}
                        errorMessage={errors.associado_novo?.email?.message}
                        isRequired
                      />
                    )}
                  />

                  <Controller
                    name="associado_novo.telefone"
                    control={control}
                    render={({ field }) => (
                      <Input
                        {...field}
                        label="Telefone"
                        placeholder="(11) 99999-9999"
                        isInvalid={!!errors.associado_novo?.telefone}
                        errorMessage={errors.associado_novo?.telefone?.message}
                        isRequired
                      />
                    )}
                  />

                  <Controller
                    name="associado_novo.data_nascimento"
                    control={control}
                    render={({ field }) => (
                      <Input
                        {...field}
                        label="Data de Nascimento"
                        type="date"
                        isInvalid={!!errors.associado_novo?.data_nascimento}
                        errorMessage={errors.associado_novo?.data_nascimento?.message}
                        isRequired
                      />
                    )}
                  />

                  <Controller
                    name="associado_novo.profissao"
                    control={control}
                    render={({ field }) => (
                      <Input
                        {...field}
                        label="Profissão"
                        placeholder="Digite a profissão"
                        isInvalid={!!errors.associado_novo?.profissao}
                        errorMessage={errors.associado_novo?.profissao?.message}
                        isRequired
                      />
                    )}
                  />

                  <Controller
                    name="associado_novo.estado_civil"
                    control={control}
                    render={({ field }) => (
                      <Select
                        {...field}
                        label="Estado Civil"
                        placeholder="Selecione o estado civil"
                        isInvalid={!!errors.associado_novo?.estado_civil}
                        errorMessage={errors.associado_novo?.estado_civil?.message}
                        isRequired
                      >
                        <SelectItem key="SOLTEIRO" value="SOLTEIRO">
                          Solteiro(a)
                        </SelectItem>
                        <SelectItem key="CASADO" value="CASADO">
                          Casado(a)
                        </SelectItem>
                        <SelectItem key="DIVORCIADO" value="DIVORCIADO">
                          Divorciado(a)
                        </SelectItem>
                        <SelectItem key="VIUVO" value="VIUVO">
                          Viúvo(a)
                        </SelectItem>
                        <SelectItem key="UNIAO_ESTAVEL" value="UNIAO_ESTAVEL">
                          União Estável
                        </SelectItem>
                      </Select>
                    )}
                  />

                  <Controller
                    name="associado_novo.nacionalidade"
                    control={control}
                    render={({ field }) => (
                      <Input
                        {...field}
                        label="Nacionalidade"
                        placeholder="Digite a nacionalidade"
                        isInvalid={!!errors.associado_novo?.nacionalidade}
                        errorMessage={errors.associado_novo?.nacionalidade?.message}
                        isRequired
                      />
                    )}
                  />
                </div>

                <Divider />

                <h3 className="text-lg font-semibold">Endereço</h3>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Controller
                    name="associado_novo.endereco.cep"
                    control={control}
                    render={({ field }) => (
                      <Input
                        {...field}
                        label="CEP"
                        placeholder="00000-000"
                        isInvalid={!!errors.associado_novo?.endereco?.cep}
                        errorMessage={errors.associado_novo?.endereco?.cep?.message}
                        isRequired
                      />
                    )}
                  />

                  <Controller
                    name="associado_novo.endereco.logradouro"
                    control={control}
                    render={({ field }) => (
                      <Input
                        {...field}
                        label="Logradouro"
                        placeholder="Rua, Avenida, etc."
                        isInvalid={!!errors.associado_novo?.endereco?.logradouro}
                        errorMessage={errors.associado_novo?.endereco?.logradouro?.message}
                        isRequired
                      />
                    )}
                  />

                  <Controller
                    name="associado_novo.endereco.numero"
                    control={control}
                    render={({ field }) => (
                      <Input
                        {...field}
                        label="Número"
                        placeholder="123"
                        isInvalid={!!errors.associado_novo?.endereco?.numero}
                        errorMessage={errors.associado_novo?.endereco?.numero?.message}
                        isRequired
                      />
                    )}
                  />

                  <Controller
                    name="associado_novo.endereco.complemento"
                    control={control}
                    render={({ field }) => (
                      <Input
                        {...field}
                        label="Complemento"
                        placeholder="Apto, Sala, etc."
                      />
                    )}
                  />

                  <Controller
                    name="associado_novo.endereco.bairro"
                    control={control}
                    render={({ field }) => (
                      <Input
                        {...field}
                        label="Bairro"
                        placeholder="Digite o bairro"
                        isInvalid={!!errors.associado_novo?.endereco?.bairro}
                        errorMessage={errors.associado_novo?.endereco?.bairro?.message}
                        isRequired
                      />
                    )}
                  />

                  <Controller
                    name="associado_novo.endereco.cidade"
                    control={control}
                    render={({ field }) => (
                      <Input
                        {...field}
                        label="Cidade"
                        placeholder="Digite a cidade"
                        isInvalid={!!errors.associado_novo?.endereco?.cidade}
                        errorMessage={errors.associado_novo?.endereco?.cidade?.message}
                        isRequired
                      />
                    )}
                  />

                  <Controller
                    name="associado_novo.endereco.estado"
                    control={control}
                    render={({ field }) => (
                      <Select
                        {...field}
                        label="Estado"
                        placeholder="Selecione o estado"
                        isInvalid={!!errors.associado_novo?.endereco?.estado}
                        errorMessage={errors.associado_novo?.endereco?.estado?.message}
                        isRequired
                      >
                        <SelectItem key="AC" value="AC">Acre</SelectItem>
                        <SelectItem key="AL" value="AL">Alagoas</SelectItem>
                        <SelectItem key="AP" value="AP">Amapá</SelectItem>
                        <SelectItem key="AM" value="AM">Amazonas</SelectItem>
                        <SelectItem key="BA" value="BA">Bahia</SelectItem>
                        <SelectItem key="CE" value="CE">Ceará</SelectItem>
                        <SelectItem key="DF" value="DF">Distrito Federal</SelectItem>
                        <SelectItem key="ES" value="ES">Espírito Santo</SelectItem>
                        <SelectItem key="GO" value="GO">Goiás</SelectItem>
                        <SelectItem key="MA" value="MA">Maranhão</SelectItem>
                        <SelectItem key="MT" value="MT">Mato Grosso</SelectItem>
                        <SelectItem key="MS" value="MS">Mato Grosso do Sul</SelectItem>
                        <SelectItem key="MG" value="MG">Minas Gerais</SelectItem>
                        <SelectItem key="PA" value="PA">Pará</SelectItem>
                        <SelectItem key="PB" value="PB">Paraíba</SelectItem>
                        <SelectItem key="PR" value="PR">Paraná</SelectItem>
                        <SelectItem key="PE" value="PE">Pernambuco</SelectItem>
                        <SelectItem key="PI" value="PI">Piauí</SelectItem>
                        <SelectItem key="RJ" value="RJ">Rio de Janeiro</SelectItem>
                        <SelectItem key="RN" value="RN">Rio Grande do Norte</SelectItem>
                        <SelectItem key="RS" value="RS">Rio Grande do Sul</SelectItem>
                        <SelectItem key="RO" value="RO">Rondônia</SelectItem>
                        <SelectItem key="RR" value="RR">Roraima</SelectItem>
                        <SelectItem key="SC" value="SC">Santa Catarina</SelectItem>
                        <SelectItem key="SP" value="SP">São Paulo</SelectItem>
                        <SelectItem key="SE" value="SE">Sergipe</SelectItem>
                        <SelectItem key="TO" value="TO">Tocantins</SelectItem>
                      </Select>
                    )}
                  />
                </div>
              </div>
            )}
          </div>
        );

      case 1:
        return (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-semibold">Dependentes</h3>
              <Button
                color="primary"
                variant="bordered"
                startContent={<PlusIcon className="w-4 h-4" />}
                onPress={addDependente}
              >
                Adicionar Dependente
              </Button>
            </div>

            {watchedDependentes.length === 0 ? (
              <div className="text-center py-8 text-default-500">
                Nenhum dependente adicionado
              </div>
            ) : (
              <div className="space-y-4">
                {watchedDependentes.map((dependente, index) => (
                  <Card key={index} className="border border-default-200">
                    <CardHeader className="flex justify-between items-center">
                      <h4 className="font-semibold">Dependente {index + 1}</h4>
                      <Button
                        isIconOnly
                        size="sm"
                        color="danger"
                        variant="light"
                        onPress={() => removeDependente(index)}
                      >
                        <TrashIcon className="w-4 h-4" />
                      </Button>
                    </CardHeader>
                    <CardBody>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <Input
                          label="Nome Completo"
                          placeholder="Digite o nome completo"
                          value={dependente.nome}
                          onChange={(e) => updateDependente(index, 'nome', e.target.value)}
                          isRequired
                        />

                        <Input
                          label="CPF"
                          placeholder="000.000.000-00"
                          value={formatCPF(dependente.cpf)}
                          onChange={(e) => updateDependente(index, 'cpf', e.target.value)}
                          isRequired
                        />

                        <Input
                          label="Data de Nascimento"
                          type="date"
                          value={dependente.data_nascimento}
                          onChange={(e) => updateDependente(index, 'data_nascimento', e.target.value)}
                          isRequired
                        />

                        <Select
                          label="Parentesco"
                          placeholder="Selecione o parentesco"
                          selectedKeys={dependente.parentesco ? [dependente.parentesco] : []}
                          onSelectionChange={(keys) => {
                            const value = Array.from(keys)[0] as string;
                            updateDependente(index, 'parentesco', value);
                          }}
                          isRequired
                        >
                          <SelectItem key="CONJUGE" value="CONJUGE">
                            Cônjuge
                          </SelectItem>
                          <SelectItem key="FILHO" value="FILHO">
                            Filho(a)
                          </SelectItem>
                          <SelectItem key="PAI" value="PAI">
                            Pai
                          </SelectItem>
                          <SelectItem key="MAE" value="MAE">
                            Mãe
                          </SelectItem>
                          <SelectItem key="IRMAO" value="IRMAO">
                            Irmão/Irmã
                          </SelectItem>
                          <SelectItem key="OUTRO" value="OUTRO">
                            Outro
                          </SelectItem>
                        </Select>

                        <Input
                          label="Valor do Dependente"
                          placeholder="0,00"
                          value={dependente.valor_dependente.toString()}
                          onChange={(e) => updateDependente(index, 'valor_dependente', parseFloat(e.target.value) || 0)}
                          startContent="R$"
                          type="number"
                          min="0"
                          step="0.01"
                          isRequired
                        />
                      </div>
                    </CardBody>
                  </Card>
                ))}
              </div>
            )}
          </div>
        );

      case 2:
        return (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-semibold">Cálculo de Valores</h3>
              <Button
                color="primary"
                variant="bordered"
                startContent={<CalculatorIcon className="w-4 h-4" />}
                onPress={calculateValues}
                isLoading={calculatingValues}
              >
                Calcular Valores
              </Button>
            </div>

            <Card>
              <CardBody>
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span className="text-default-600">Valor Base da Associação:</span>
                    <span className="font-semibold">R$ 150,00</span>
                  </div>
                  
                  <div className="flex justify-between items-center">
                    <span className="text-default-600">
                      Dependentes ({watchedDependentes.length}):
                    </span>
                    <span className="font-semibold">
                      {formatCurrency(watchedDependentes.length * 50.00)}
                    </span>
                  </div>
                  
                  <Divider />
                  
                  <div className="flex justify-between items-center text-lg">
                    <span className="font-semibold">Valor Total:</span>
                    <Controller
                      name="valor_total"
                      control={control}
                      render={({ field }) => (
                        <Input
                          {...field}
                          value={field.value?.toString() || '0'}
                          onChange={(e) => field.onChange(parseFloat(e.target.value) || 0)}
                          startContent="R$"
                          type="number"
                          min="0"
                          step="0.01"
                          className="w-32"
                          classNames={{
                            input: "text-right font-semibold text-lg",
                          }}
                        />
                      )}
                    />
                  </div>
                </div>
              </CardBody>
            </Card>

            <Controller
              name="observacoes"
              control={control}
              render={({ field }) => (
                <Textarea
                  {...field}
                  label="Observações"
                  placeholder="Digite observações adicionais sobre o cadastro..."
                  minRows={3}
                />
              )}
            />
          </div>
        );

      case 3:
        return (
          <div className="space-y-6">
            <h3 className="text-lg font-semibold">Documentos</h3>
            
            <FileUpload
              onFilesSelected={addDocumento}
              accept=".pdf,.jpg,.jpeg,.png"
              maxFiles={10}
              maxSizePerFile={5}
              label="Anexar Documentos"
              description="Arquivos PDF, JPG, JPEG ou PNG (máx. 5MB cada)"
            />

            {getValues('documentos')?.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-medium">Documentos Anexados:</h4>
                {getValues('documentos')?.map((documento, index) => (
                  <Card key={index} className="border border-default-200">
                    <CardBody className="p-4">
                      <div className="flex justify-between items-center">
                        <div className="flex items-center gap-3">
                          <FileTextIcon className="w-5 h-5 text-primary" />
                          <div>
                            <p className="font-medium">{documento.nome_arquivo}</p>
                            <p className="text-sm text-default-500">
                              {(documento.arquivo as File)?.size 
                                ? `${Math.round((documento.arquivo as File).size / 1024)} KB`
                                : `${Math.round(documento.tamanho / 1024)} KB`
                              }
                            </p>
                          </div>
                        </div>
                        <Button
                          isIconOnly
                          size="sm"
                          color="danger"
                          variant="light"
                          onPress={() => removeDocumento(index)}
                        >
                          <TrashIcon className="w-4 h-4" />
                        </Button>
                      </div>
                    </CardBody>
                  </Card>
                ))}
              </div>
            )}
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <MultiStepForm
        steps={steps}
        currentStep={currentStep}
        onStepChange={setCurrentStep}
        onNext={() => setCurrentStep(prev => Math.min(prev + 1, steps.length - 1))}
        onPrevious={() => setCurrentStep(prev => Math.max(prev - 1, 0))}
        canGoNext={currentStep < steps.length - 1}
        canGoPrevious={currentStep > 0}
        isLastStep={currentStep === steps.length - 1}
        onSubmit={handleSubmit(handleFormSubmit)}
        isLoading={isLoading}
        submitLabel={mode === 'create' ? 'Criar Cadastro' : 'Salvar Alterações'}
      >
        {renderStepContent()}
      </MultiStepForm>
    </div>
  );
}

