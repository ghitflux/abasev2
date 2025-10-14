"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@heroui/react';
import { AssociadoForm } from '@/components/associados/AssociadoForm';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@abase/ui';

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
}

export default function EditarAssociadoPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { apiClient } = useAuth();
  const { addToast } = useToast();
  
  const [associado, setAssociado] = useState<Associado | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");

  const associadoId = parseInt(params.id);

  useEffect(() => {
    if (apiClient && associadoId) {
      fetchAssociado();
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
        id: associadoId,
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
        observacoes: "Associado desde 2020"
      };
      
      setAssociado(mockAssociado);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (data: any) => {
    if (!apiClient) {
      throw new Error('API Client não inicializado');
    }

    try {
      const response = await apiClient.put(`/api/v1/cadastros/associados/${associadoId}`, data);

      if (response.error) {
        throw new Error(response.error.message);
      }

      addToast({
        type: 'success',
        title: 'Associado atualizado',
        description: `${data.nome} foi atualizado com sucesso.`,
      });

      router.push(`/associados/${associadoId}`);
    } catch (error: any) {
      console.error('Error updating associado:', error);
      addToast({
        type: 'error',
        title: 'Erro ao atualizar associado',
        description: error.message || 'Não foi possível atualizar o associado.',
      });
      throw error;
    }
  };

  const handleCancel = () => {
    router.push(`/associados/${associadoId}`);
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
      </div>
    );
  }

  return (
    <div className="p-6">
      <AssociadoForm
        initialData={associado}
        onSubmit={handleSubmit}
        onCancel={handleCancel}
        mode="edit"
      />
    </div>
  );
}
