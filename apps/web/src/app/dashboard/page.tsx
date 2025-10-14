"use client";

import React from 'react';
import { Card, CardBody, CardHeader } from '@heroui/react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { UserMenu } from '@/components/auth/UserMenu';
import { PermissionGate, usePermissions } from '@/components/auth/PermissionGate';
import { useAuth } from '@/contexts/AuthContext';

function DashboardContent() {
  const { user } = useAuth();
  const permissions = usePermissions();

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-default-200 bg-content1">
        <div className="container mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold text-primary">ABASE Manager</h1>
            <span className="text-sm text-default-500">Dashboard</span>
          </div>
          <UserMenu showName avatarSize="md" />
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-8">
        <div className="space-y-6">
          {/* Welcome Card */}
          <Card>
            <CardHeader>
              <h2 className="text-xl font-semibold">
                Bem-vindo, {user?.full_name || user?.email}!
              </h2>
            </CardHeader>
            <CardBody>
              <p className="text-default-600">
                Você está logado como <strong>{user?.perfil}</strong>.
              </p>
            </CardBody>
          </Card>

          {/* Grid de Cards de Funcionalidades */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Card: Criar Cadastro */}
            <PermissionGate requiredRoles={['ADMIN', 'AGENTE']}>
              <Card className="hover:shadow-lg transition-shadow cursor-pointer">
                <CardHeader className="flex gap-3">
                  <div className="flex flex-col">
                    <p className="text-md font-semibold">Criar Cadastro</p>
                    <p className="text-small text-default-500">
                      Novo cadastro de associado
                    </p>
                  </div>
                </CardHeader>
                <CardBody>
                  <p className="text-sm text-default-600">
                    Inicie um novo processo de cadastro de associado.
                  </p>
                </CardBody>
              </Card>
            </PermissionGate>

            {/* Card: Análise */}
            <PermissionGate requiredRoles={['ADMIN', 'ANALISTA']}>
              <Card className="hover:shadow-lg transition-shadow cursor-pointer">
                <CardHeader className="flex gap-3">
                  <div className="flex flex-col">
                    <p className="text-md font-semibold">Análise de Cadastros</p>
                    <p className="text-small text-default-500">
                      Aprovar ou pendenciar
                    </p>
                  </div>
                </CardHeader>
                <CardBody>
                  <p className="text-sm text-default-600">
                    Avalie cadastros submetidos e tome decisões.
                  </p>
                </CardBody>
              </Card>
            </PermissionGate>

            {/* Card: Tesouraria */}
            <PermissionGate requiredRoles={['ADMIN', 'TESOURARIA']}>
              <Card className="hover:shadow-lg transition-shadow cursor-pointer">
                <CardHeader className="flex gap-3">
                  <div className="flex flex-col">
                    <p className="text-md font-semibold">Tesouraria</p>
                    <p className="text-small text-default-500">
                      Pagamentos e contratos
                    </p>
                  </div>
                </CardHeader>
                <CardBody>
                  <p className="text-sm text-default-600">
                    Gerencie pagamentos e contratos de associados.
                  </p>
                </CardBody>
              </Card>
            </PermissionGate>

            {/* Card: Relatórios */}
            <PermissionGate requiredRoles={['ADMIN', 'ANALISTA', 'TESOURARIA']}>
              <Card className="hover:shadow-lg transition-shadow cursor-pointer">
                <CardHeader className="flex gap-3">
                  <div className="flex flex-col">
                    <p className="text-md font-semibold">Relatórios</p>
                    <p className="text-small text-default-500">
                      Visualize e exporte dados
                    </p>
                  </div>
                </CardHeader>
                <CardBody>
                  <p className="text-sm text-default-600">
                    Acesse relatórios completos e exports.
                  </p>
                </CardBody>
              </Card>
            </PermissionGate>

            {/* Card: Admin */}
            <PermissionGate requiredRoles={['ADMIN']}>
              <Card className="hover:shadow-lg transition-shadow cursor-pointer border-2 border-danger">
                <CardHeader className="flex gap-3">
                  <div className="flex flex-col">
                    <p className="text-md font-semibold text-danger">
                      Administração
                    </p>
                    <p className="text-small text-default-500">
                      Gerenciar sistema
                    </p>
                  </div>
                </CardHeader>
                <CardBody>
                  <p className="text-sm text-default-600">
                    Configurações avançadas e gestão de usuários.
                  </p>
                </CardBody>
              </Card>
            </PermissionGate>
          </div>

          {/* Informações de Permissões */}
          <Card>
            <CardHeader>
              <h3 className="text-lg font-semibold">Suas Permissões</h3>
            </CardHeader>
            <CardBody>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <PermissionItem
                  label="Criar Cadastros"
                  allowed={permissions.canCreateCadastro}
                />
                <PermissionItem
                  label="Aprovar Cadastros"
                  allowed={permissions.canApproveCadastro}
                />
                <PermissionItem
                  label="Processar Pagamentos"
                  allowed={permissions.canProcessPayment}
                />
                <PermissionItem
                  label="Ver Relatórios"
                  allowed={permissions.canViewReports}
                />
                <PermissionItem
                  label="Exportar Relatórios"
                  allowed={permissions.canExportReports}
                />
                <PermissionItem
                  label="Gerenciar Usuários"
                  allowed={permissions.canManageUsers}
                />
              </div>
            </CardBody>
          </Card>
        </div>
      </main>
    </div>
  );
}

function PermissionItem({ label, allowed }: { label: string; allowed: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`text-2xl ${allowed ? 'text-success' : 'text-default-300'}`}>
        {allowed ? '✓' : '✗'}
      </span>
      <span className={`text-sm ${allowed ? 'text-default-700' : 'text-default-400'}`}>
        {label}
      </span>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}
