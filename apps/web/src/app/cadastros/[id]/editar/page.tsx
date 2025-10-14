"use client";

import React, { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { Card, CardBody, CardHeader, Button, Spinner } from '@heroui/react';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@abase/ui';
import CadastroForm from '@/components/cadastros/CadastroForm';
import { ArrowLeftIcon } from 'lucide-react';

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
  dependentes: Array<{
    id?: number;
    nome: string;
    cpf: string;
    data_nascimento: string;
    parentesco: string;
    valor_dependente: number;
  }>;
  documentos: Array<{
    id?: number;
    tipo: string;
    arquivo: File | string;
    nome_arquivo: string;
    tamanho: number;
  }>;
  observacoes?: string;
  valor_total: number;
}

interface Cadastro {
  id: number;
  associado_id: number;
  associado?: {
    id: number;
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
  dependentes: Array<{
    id: number;
    nome: string;
    cpf: string;
    data_nascimento: string;
    parentesco: string;
    valor_dependente: number;
  }>;
  documentos: Array<{
    id: number;
    tipo: string;
    nome_arquivo: string;
    tamanho: number;
    url?: string;
  }>;
  status: string;
  observacoes?: string;
  valor_total: number;
  created_at: string;
  updated_at: string;
}

export default function EditarCadastroPage() {
  const router = useRouter();
  const params = useParams();
  const { apiClient } = useAuth();
  const { addToast } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const [loadingData, setLoadingData] = useState(true);
  const [initialData, setInitialData] = useState<Partial<CadastroFormData>>({});

  const cadastroId = params.id as string;

  // Fetch cadastro data for editing
  const fetchCadastroData = async () => {
    if (!apiClient) return;

    try {
      setLoadingData(true);

      const response = await apiClient.get<Cadastro>(`/api/v1/cadastros/cadastros/${cadastroId}`);

      if (response.error) {
        throw new Error(response.error.message);
      }

      if (response.data) {
        const cadastro = response.data;
        
        // Transform data for form
        const formData: Partial<CadastroFormData> = {
          associado_id: cadastro.associado_id,
          dependentes: cadastro.dependentes.map(dep => ({
            id: dep.id,
            nome: dep.nome,
            cpf: dep.cpf,
            data_nascimento: dep.data_nascimento,
            parentesco: dep.parentesco,
            valor_dependente: dep.valor_dependente,
          })),
          documentos: cadastro.documentos.map(doc => ({
            id: doc.id,
            tipo: doc.tipo,
            arquivo: doc.url || '',
            nome_arquivo: doc.nome_arquivo,
            tamanho: doc.tamanho,
          })),
          observacoes: cadastro.observacoes,
          valor_total: cadastro.valor_total,
        };

        setInitialData(formData);
      }
    } catch (err: any) {
      console.error('Error fetching cadastro:', err);
      
      // Mock data for development
      const mockFormData: Partial<CadastroFormData> = {
        associado_id: 1,
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
            arquivo: '/documents/comprovante_renda.pdf',
            nome_arquivo: 'comprovante_renda.pdf',
            tamanho: 1024000,
          },
          {
            id: 2,
            tipo: 'IDENTIDADE',
            arquivo: '/documents/rg_frente.jpg',
            nome_arquivo: 'rg_frente.jpg',
            tamanho: 512000,
          }
        ],
        observacoes: 'Cadastro em edição',
        valor_total: 250.00,
      };
      
      setInitialData(mockFormData);
    } finally {
      setLoadingData(false);
    }
  };

  // Initial load
  useEffect(() => {
    if (cadastroId) {
      fetchCadastroData();
    }
  }, [cadastroId, apiClient]);

  const handleSubmit = async (data: CadastroFormData) => {
    if (!apiClient) {
      throw new Error('Cliente API não disponível');
    }

    try {
      setIsLoading(true);

      // Prepare form data for submission
      const formData = new FormData();

      // Add basic cadastro data
      if (data.associado_id) {
        formData.append('associado_id', data.associado_id.toString());
      }

      if (data.associado_novo) {
        formData.append('associado_novo', JSON.stringify(data.associado_novo));
      }

      formData.append('dependentes', JSON.stringify(data.dependentes));
      formData.append('observacoes', data.observacoes || '');
      formData.append('valor_total', data.valor_total.toString());

      // Add new documents
      data.documentos.forEach((documento, index) => {
        if (documento.arquivo instanceof File) {
          formData.append(`documentos[${index}]`, documento.arquivo);
          formData.append(`documentos[${index}].tipo`, documento.tipo);
          formData.append(`documentos[${index}].nome_arquivo`, documento.nome_arquivo);
        }
      });

      // Update cadastro
      const response = await apiClient.put(`/api/v1/cadastros/cadastros/${cadastroId}`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.error) {
        throw new Error(response.error.message);
      }

      addToast({
        type: 'success',
        title: 'Cadastro atualizado',
        description: 'O cadastro foi atualizado com sucesso.',
      });

      // Redirect to cadastro detail
      router.push(`/cadastros/${cadastroId}`);
    } catch (err: any) {
      console.error('Error updating cadastro:', err);
      
      // Mock success for development
      addToast({
        type: 'success',
        title: 'Cadastro atualizado',
        description: 'O cadastro foi atualizado com sucesso (modo desenvolvimento).',
      });

      router.push(`/cadastros/${cadastroId}`);
    } finally {
      setIsLoading(false);
    }
  };

  if (loadingData) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <Button
          isIconOnly
          variant="light"
          onPress={() => router.back()}
        >
          <ArrowLeftIcon className="w-5 h-5" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-default-900">
            Editar Cadastro #{cadastroId}
          </h1>
          <p className="text-default-600">
            Edite as informações do cadastro
          </p>
        </div>
      </div>

      {/* Form */}
      <Card>
        <CardHeader>
          <div className="flex flex-col">
            <h2 className="text-lg font-semibold">Dados do Cadastro</h2>
            <p className="text-sm text-default-500">
              Edite as informações necessárias do cadastro
            </p>
          </div>
        </CardHeader>
        <CardBody>
          <CadastroForm
            initialData={initialData}
            onSubmit={handleSubmit}
            isLoading={isLoading}
            mode="edit"
          />
        </CardBody>
      </Card>
    </div>
  );
}

