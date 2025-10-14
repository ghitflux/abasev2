"use client";

import React from 'react';
import { useRouter } from 'next/navigation';
import { AssociadoForm } from '@/components/associados/AssociadoForm';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@abase/ui';

export default function NovoAssociadoPage() {
  const router = useRouter();
  const { apiClient } = useAuth();
  const { addToast } = useToast();

  const handleSubmit = async (data: any) => {
    if (!apiClient) {
      throw new Error('API Client não inicializado');
    }

    try {
      const response = await apiClient.post('/api/v1/cadastros/associados', data);

      if (response.error) {
        throw new Error(response.error.message);
      }

      addToast({
        type: 'success',
        title: 'Associado criado',
        description: `${data.nome} foi cadastrado com sucesso.`,
      });

      router.push('/associados');
    } catch (error: any) {
      console.error('Error creating associado:', error);
      addToast({
        type: 'error',
        title: 'Erro ao criar associado',
        description: error.message || 'Não foi possível criar o associado.',
      });
      throw error;
    }
  };

  const handleCancel = () => {
    router.push('/associados');
  };

  return (
    <div className="p-6">
      <AssociadoForm
        onSubmit={handleSubmit}
        onCancel={handleCancel}
        mode="create"
      />
    </div>
  );
}
