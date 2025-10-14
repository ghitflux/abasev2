"use client";

import React from 'react';
import { Button, Card, CardBody } from '@heroui/react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';

export default function UnauthorizedPage() {
  const router = useRouter();
  const { user, logout } = useAuth();

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-red-50 to-orange-100 dark:from-gray-900 dark:to-gray-800 px-4">
      <Card className="w-full max-w-md shadow-2xl">
        <CardBody className="gap-6 px-8 py-10 text-center">
          {/* Icon */}
          <div className="text-8xl mb-4">🚫</div>

          {/* Title */}
          <h1 className="text-3xl font-bold text-danger">Acesso Negado</h1>

          {/* Message */}
          <p className="text-default-600">
            Você não tem permissão para acessar esta página.
          </p>

          {user && (
            <div className="bg-default-100 dark:bg-default-50/10 p-4 rounded-lg">
              <p className="text-sm text-default-700">
                <strong>Usuário:</strong> {user.email}
              </p>
              <p className="text-sm text-default-700">
                <strong>Perfil:</strong> {user.perfil}
              </p>
            </div>
          )}

          <p className="text-sm text-default-500">
            Entre em contato com o administrador do sistema se você acredita que deveria ter
            acesso a este recurso.
          </p>

          {/* Actions */}
          <div className="flex flex-col gap-3 w-full">
            <Button
              color="primary"
              size="lg"
              onPress={() => router.push('/dashboard')}
              className="w-full"
            >
              Voltar ao Dashboard
            </Button>

            <Button
              variant="light"
              size="lg"
              onPress={() => router.back()}
              className="w-full"
            >
              Voltar à Página Anterior
            </Button>

            <Button
              variant="light"
              color="danger"
              size="sm"
              onPress={() => logout()}
              className="w-full"
            >
              Sair do Sistema
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
