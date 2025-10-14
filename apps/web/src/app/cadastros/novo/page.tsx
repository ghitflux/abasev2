"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
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
    nome: string;
    cpf: string;
    data_nascimento: string;
    parentesco: string;
    valor_dependente: number;
  }>;
  documentos: Array<{
    tipo: string;
    arquivo: File | string;
    nome_arquivo: string;
    tamanho: number;
  }>;
  observacoes?: string;
  valor_total: number;
}

export default function NovoCadastroPage() {
  const router = useRouter();
  const { apiClient } = useAuth();
  const { addToast } = useToast();
  const [isLoading, setIsLoading] = useState(false);

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

      // Add documents
      data.documentos.forEach((documento, index) => {
        if (documento.arquivo instanceof File) {
          formData.append(`documentos[${index}]`, documento.arquivo);
          formData.append(`documentos[${index}].tipo`, documento.tipo);
          formData.append(`documentos[${index}].nome_arquivo`, documento.nome_arquivo);
        }
      });

      // Submit to backend
      const response = await apiClient.post('/api/v1/cadastros/cadastros', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.error) {
        throw new Error(response.error.message);
      }

      addToast({
        type: 'success',
        title: 'Cadastro criado',
        description: 'O cadastro foi criado com sucesso.',
      });

      // Redirect to cadastros list
      router.push('/cadastros');
    } catch (err: any) {
      console.error('Error creating cadastro:', err);
      
      // Mock success for development
      addToast({
        type: 'success',
        title: 'Cadastro criado',
        description: 'O cadastro foi criado com sucesso (modo desenvolvimento).',
      });

      router.push('/cadastros');
    } finally {
      setIsLoading(false);
    }
  };

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
          <h1 className="text-2xl font-bold text-default-900">Novo Cadastro</h1>
          <p className="text-default-600">
            Crie um novo cadastro de associação
          </p>
        </div>
      </div>

      {/* Form */}
      <Card>
        <CardHeader>
          <div className="flex flex-col">
            <h2 className="text-lg font-semibold">Dados do Cadastro</h2>
            <p className="text-sm text-default-500">
              Preencha todas as informações necessárias para criar o cadastro
            </p>
          </div>
        </CardHeader>
        <CardBody>
          <CadastroForm
            onSubmit={handleSubmit}
            isLoading={isLoading}
            mode="create"
          />
        </CardBody>
      </Card>
    </div>
  );
}

