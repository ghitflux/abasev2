"use client";

import React, { useState, useEffect } from 'react';
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
  Divider,
  Select,
  SelectItem,
} from '@heroui/react';
import { MultiStepForm, Step, useToast } from '@abase/ui';
import { useAuth } from '@/contexts/AuthContext';
import { formatCPF, formatPhone, formatCEP } from '@/lib/formatters';
import { validateCPF, validateEmail, validatePhone, validateCEP } from '@/lib/validators';

// Form validation schema
const associadoSchema = z.object({
  // Step 1: Personal Data
  cpf: z.string()
    .min(1, 'CPF é obrigatório')
    .refine(validateCPF, 'CPF inválido'),
  nome: z.string()
    .min(2, 'Nome deve ter pelo menos 2 caracteres')
    .max(100, 'Nome deve ter no máximo 100 caracteres'),
  data_nascimento: z.string()
    .min(1, 'Data de nascimento é obrigatória'),
  estado_civil: z.string()
    .min(1, 'Estado civil é obrigatório'),
  profissao: z.string()
    .min(1, 'Profissão é obrigatória'),
  nacionalidade: z.string()
    .min(1, 'Nacionalidade é obrigatória'),
  
  // Step 2: Contact Information
  email: z.string()
    .email('Email inválido')
    .optional()
    .or(z.literal('')),
  telefone: z.string()
    .refine((val) => !val || validatePhone(val), 'Telefone inválido')
    .optional(),
  celular: z.string()
    .refine((val) => !val || validatePhone(val), 'Celular inválido')
    .optional(),
  
  // Step 3: Address
  cep: z.string()
    .min(1, 'CEP é obrigatório')
    .refine(validateCEP, 'CEP inválido'),
  endereco: z.string()
    .min(1, 'Endereço é obrigatório'),
  numero: z.string()
    .min(1, 'Número é obrigatório'),
  complemento: z.string()
    .optional(),
  bairro: z.string()
    .min(1, 'Bairro é obrigatório'),
  cidade: z.string()
    .min(1, 'Cidade é obrigatória'),
  estado: z.string()
    .min(1, 'Estado é obrigatório'),
  
  // Step 4: Additional Information
  observacoes: z.string()
    .optional(),
});

type AssociadoFormData = z.infer<typeof associadoSchema>;

interface AssociadoFormProps {
  initialData?: Partial<AssociadoFormData>;
  onSubmit: (data: AssociadoFormData) => Promise<void>;
  onCancel?: () => void;
  isLoading?: boolean;
  mode?: 'create' | 'edit';
}

const steps: Step[] = [
  {
    id: 'personal',
    title: 'Dados Pessoais',
    description: 'Informações básicas do associado',
  },
  {
    id: 'contact',
    title: 'Contato',
    description: 'Informações de contato',
  },
  {
    id: 'address',
    title: 'Endereço',
    description: 'Endereço residencial',
  },
  {
    id: 'additional',
    title: 'Informações Adicionais',
    description: 'Observações e detalhes extras',
  },
];

const estados = [
  { value: 'AC', label: 'Acre' },
  { value: 'AL', label: 'Alagoas' },
  { value: 'AP', label: 'Amapá' },
  { value: 'AM', label: 'Amazonas' },
  { value: 'BA', label: 'Bahia' },
  { value: 'CE', label: 'Ceará' },
  { value: 'DF', label: 'Distrito Federal' },
  { value: 'ES', label: 'Espírito Santo' },
  { value: 'GO', label: 'Goiás' },
  { value: 'MA', label: 'Maranhão' },
  { value: 'MT', label: 'Mato Grosso' },
  { value: 'MS', label: 'Mato Grosso do Sul' },
  { value: 'MG', label: 'Minas Gerais' },
  { value: 'PA', label: 'Pará' },
  { value: 'PB', label: 'Paraíba' },
  { value: 'PR', label: 'Paraná' },
  { value: 'PE', label: 'Pernambuco' },
  { value: 'PI', label: 'Piauí' },
  { value: 'RJ', label: 'Rio de Janeiro' },
  { value: 'RN', label: 'Rio Grande do Norte' },
  { value: 'RS', label: 'Rio Grande do Sul' },
  { value: 'RO', label: 'Rondônia' },
  { value: 'RR', label: 'Roraima' },
  { value: 'SC', label: 'Santa Catarina' },
  { value: 'SP', label: 'São Paulo' },
  { value: 'SE', label: 'Sergipe' },
  { value: 'TO', label: 'Tocantins' },
];

const estadosCivis = [
  { value: 'solteiro', label: 'Solteiro(a)' },
  { value: 'casado', label: 'Casado(a)' },
  { value: 'divorciado', label: 'Divorciado(a)' },
  { value: 'viuvo', label: 'Viúvo(a)' },
  { value: 'uniao_estavel', label: 'União Estável' },
];

export function AssociadoForm({
  initialData,
  onSubmit,
  onCancel,
  isLoading = false,
  mode = 'create',
}: AssociadoFormProps) {
  const { addToast } = useToast();
  const [currentStep, setCurrentStep] = useState(0);
  const [cepData, setCepData] = useState<{
    endereco?: string;
    bairro?: string;
    cidade?: string;
    estado?: string;
  }>({});

  const {
    control,
    handleSubmit,
    formState: { errors, isValid },
    watch,
    setValue,
    trigger,
  } = useForm<AssociadoFormData>({
    resolver: zodResolver(associadoSchema),
    defaultValues: {
      cpf: '',
      nome: '',
      data_nascimento: '',
      estado_civil: '',
      profissao: '',
      nacionalidade: 'Brasileira',
      email: '',
      telefone: '',
      celular: '',
      cep: '',
      endereco: '',
      numero: '',
      complemento: '',
      bairro: '',
      cidade: '',
      estado: '',
      observacoes: '',
      ...initialData,
    },
    mode: 'onChange',
  });

  const watchedCep = watch('cep');
  const watchedCpf = watch('cpf');

  // Format CPF input
  useEffect(() => {
    if (watchedCpf) {
      const formatted = formatCPF(watchedCpf);
      if (formatted !== watchedCpf) {
        setValue('cpf', formatted);
      }
    }
  }, [watchedCpf, setValue]);

  // Format phone inputs
  const handlePhoneChange = (field: 'telefone' | 'celular', value: string) => {
    const formatted = formatPhone(value);
    setValue(field, formatted);
  };

  // Format CEP input and fetch address data
  useEffect(() => {
    if (watchedCep) {
      const formatted = formatCEP(watchedCep);
      if (formatted !== watchedCep) {
        setValue('cep', formatted);
      }

      // Fetch CEP data if complete
      const cepNumbers = watchedCep.replace(/\D/g, '');
      if (cepNumbers.length === 8) {
        fetchCepData(cepNumbers);
      }
    }
  }, [watchedCep, setValue]);

  const fetchCepData = async (cep: string) => {
    try {
      const response = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
      const data = await response.json();
      
      if (!data.erro) {
        setCepData({
          endereco: data.logradouro,
          bairro: data.bairro,
          cidade: data.localidade,
          estado: data.uf,
        });

        // Auto-fill form fields
        if (data.logradouro) setValue('endereco', data.logradouro);
        if (data.bairro) setValue('bairro', data.bairro);
        if (data.localidade) setValue('cidade', data.localidade);
        if (data.uf) setValue('estado', data.uf);
      }
    } catch (error) {
      console.error('Error fetching CEP data:', error);
    }
  };

  const handleStepChange = async (stepIndex: number) => {
    // Validate current step before moving
    const stepFields = getStepFields(currentStep);
    const isStepValid = await trigger(stepFields);
    
    if (isStepValid) {
      setCurrentStep(stepIndex);
    } else {
      addToast({
        type: 'error',
        title: 'Campos obrigatórios',
        description: 'Por favor, preencha todos os campos obrigatórios antes de continuar.',
      });
    }
  };

  const getStepFields = (step: number): (keyof AssociadoFormData)[] => {
    switch (step) {
      case 0:
        return ['cpf', 'nome', 'data_nascimento', 'estado_civil', 'profissao', 'nacionalidade'];
      case 1:
        return ['email', 'telefone', 'celular'];
      case 2:
        return ['cep', 'endereco', 'numero', 'bairro', 'cidade', 'estado'];
      case 3:
        return ['observacoes'];
      default:
        return [];
    }
  };

  const handleFormSubmit = async (data: AssociadoFormData) => {
    try {
      await onSubmit(data);
    } catch (error) {
      console.error('Form submission error:', error);
    }
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Controller
                name="cpf"
                control={control}
                render={({ field }) => (
                  <Input
                    {...field}
                    label="CPF"
                    placeholder="000.000.000-00"
                    isRequired
                    isInvalid={!!errors.cpf}
                    errorMessage={errors.cpf?.message}
                    maxLength={14}
                  />
                )}
              />
              
              <Controller
                name="nome"
                control={control}
                render={({ field }) => (
                  <Input
                    {...field}
                    label="Nome Completo"
                    placeholder="Digite o nome completo"
                    isRequired
                    isInvalid={!!errors.nome}
                    errorMessage={errors.nome?.message}
                  />
                )}
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Controller
                name="data_nascimento"
                control={control}
                render={({ field }) => (
                  <Input
                    {...field}
                    label="Data de Nascimento"
                    type="date"
                    isRequired
                    isInvalid={!!errors.data_nascimento}
                    errorMessage={errors.data_nascimento?.message}
                  />
                )}
              />
              
              <Controller
                name="estado_civil"
                control={control}
                render={({ field }) => (
                  <Select
                    {...field}
                    label="Estado Civil"
                    placeholder="Selecione o estado civil"
                    isRequired
                    isInvalid={!!errors.estado_civil}
                    errorMessage={errors.estado_civil?.message}
                  >
                    {estadosCivis.map((estado) => (
                      <SelectItem key={estado.value} value={estado.value}>
                        {estado.label}
                      </SelectItem>
                    ))}
                  </Select>
                )}
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Controller
                name="profissao"
                control={control}
                render={({ field }) => (
                  <Input
                    {...field}
                    label="Profissão"
                    placeholder="Digite a profissão"
                    isRequired
                    isInvalid={!!errors.profissao}
                    errorMessage={errors.profissao?.message}
                  />
                )}
              />
              
              <Controller
                name="nacionalidade"
                control={control}
                render={({ field }) => (
                  <Input
                    {...field}
                    label="Nacionalidade"
                    placeholder="Digite a nacionalidade"
                    isRequired
                    isInvalid={!!errors.nacionalidade}
                    errorMessage={errors.nacionalidade?.message}
                  />
                )}
              />
            </div>
          </div>
        );

      case 1:
        return (
          <div className="space-y-4">
            <Controller
              name="email"
              control={control}
              render={({ field }) => (
                <Input
                  {...field}
                  label="Email"
                  type="email"
                  placeholder="email@exemplo.com"
                  isInvalid={!!errors.email}
                  errorMessage={errors.email?.message}
                />
              )}
            />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Controller
                name="telefone"
                control={control}
                render={({ field }) => (
                  <Input
                    {...field}
                    label="Telefone"
                    placeholder="(00) 0000-0000"
                    isInvalid={!!errors.telefone}
                    errorMessage={errors.telefone?.message}
                    onChange={(e) => handlePhoneChange('telefone', e.target.value)}
                    maxLength={14}
                  />
                )}
              />
              
              <Controller
                name="celular"
                control={control}
                render={({ field }) => (
                  <Input
                    {...field}
                    label="Celular"
                    placeholder="(00) 00000-0000"
                    isInvalid={!!errors.celular}
                    errorMessage={errors.celular?.message}
                    onChange={(e) => handlePhoneChange('celular', e.target.value)}
                    maxLength={15}
                  />
                )}
              />
            </div>
          </div>
        );

      case 2:
        return (
          <div className="space-y-4">
            <Controller
              name="cep"
              control={control}
              render={({ field }) => (
                <Input
                  {...field}
                  label="CEP"
                  placeholder="00000-000"
                  isRequired
                  isInvalid={!!errors.cep}
                  errorMessage={errors.cep?.message}
                  maxLength={9}
                />
              )}
            />

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Controller
                name="endereco"
                control={control}
                render={({ field }) => (
                  <Input
                    {...field}
                    label="Endereço"
                    placeholder="Rua, Avenida, etc."
                    isRequired
                    isInvalid={!!errors.endereco}
                    errorMessage={errors.endereco?.message}
                    className="md:col-span-2"
                  />
                )}
              />
              
              <Controller
                name="numero"
                control={control}
                render={({ field }) => (
                  <Input
                    {...field}
                    label="Número"
                    placeholder="123"
                    isRequired
                    isInvalid={!!errors.numero}
                    errorMessage={errors.numero?.message}
                  />
                )}
              />
            </div>

            <Controller
              name="complemento"
              control={control}
              render={({ field }) => (
                <Input
                  {...field}
                  label="Complemento"
                  placeholder="Apartamento, sala, etc. (opcional)"
                  isInvalid={!!errors.complemento}
                  errorMessage={errors.complemento?.message}
                />
              )}
            />

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Controller
                name="bairro"
                control={control}
                render={({ field }) => (
                  <Input
                    {...field}
                    label="Bairro"
                    placeholder="Nome do bairro"
                    isRequired
                    isInvalid={!!errors.bairro}
                    errorMessage={errors.bairro?.message}
                  />
                )}
              />
              
              <Controller
                name="cidade"
                control={control}
                render={({ field }) => (
                  <Input
                    {...field}
                    label="Cidade"
                    placeholder="Nome da cidade"
                    isRequired
                    isInvalid={!!errors.cidade}
                    errorMessage={errors.cidade?.message}
                  />
                )}
              />
              
              <Controller
                name="estado"
                control={control}
                render={({ field }) => (
                  <Select
                    {...field}
                    label="Estado"
                    placeholder="Selecione o estado"
                    isRequired
                    isInvalid={!!errors.estado}
                    errorMessage={errors.estado?.message}
                  >
                    {estados.map((estado) => (
                      <SelectItem key={estado.value} value={estado.value}>
                        {estado.label}
                      </SelectItem>
                    ))}
                  </Select>
                )}
              />
            </div>
          </div>
        );

      case 3:
        return (
          <div className="space-y-4">
            <Controller
              name="observacoes"
              control={control}
              render={({ field }) => (
                <Textarea
                  {...field}
                  label="Observações"
                  placeholder="Informações adicionais sobre o associado (opcional)"
                  minRows={4}
                  isInvalid={!!errors.observacoes}
                  errorMessage={errors.observacoes?.message}
                />
              )}
            />
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <MultiStepForm
      steps={steps}
      currentStep={currentStep}
      onStepChange={handleStepChange}
      onFinish={handleSubmit(handleFormSubmit)}
      isLoading={isLoading}
      nextButtonText={currentStep === steps.length - 1 ? 'Salvar' : 'Próximo'}
      finishButtonText={mode === 'create' ? 'Criar Associado' : 'Salvar Alterações'}
      className="max-w-4xl mx-auto"
    >
      {renderStepContent()}
    </MultiStepForm>
  );
}
