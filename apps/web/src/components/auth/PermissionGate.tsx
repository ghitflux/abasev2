"use client";

import React from 'react';
import { useAuth, User } from '@/contexts/AuthContext';

export type Role = 'ADMIN' | 'ANALISTA' | 'TESOURARIA' | 'AGENTE' | 'ASSOCIADO';

export interface PermissionGateProps {
  children: React.ReactNode;
  requiredRoles?: Role[];
  fallback?: React.ReactNode;
  renderCondition?: (user: User | null) => boolean;
}

/**
 * Componente para renderização condicional baseada em permissões
 *
 * @example
 * ```tsx
 * <PermissionGate requiredRoles={['ADMIN', 'ANALISTA']}>
 *   <Button>Aprovar Cadastro</Button>
 * </PermissionGate>
 * ```
 */
export function PermissionGate({
  children,
  requiredRoles,
  fallback = null,
  renderCondition,
}: PermissionGateProps) {
  const { user, isAuthenticated } = useAuth();

  // Não autenticado
  if (!isAuthenticated || !user) {
    return <>{fallback}</>;
  }

  // Condição personalizada
  if (renderCondition) {
    return renderCondition(user) ? <>{children}</> : <>{fallback}</>;
  }

  // Verificar roles
  if (requiredRoles && requiredRoles.length > 0) {
    const userRole = user.perfil;

    if (!requiredRoles.includes(userRole)) {
      return <>{fallback}</>;
    }
  }

  // Autorizado
  return <>{children}</>;
}

/**
 * Hook para verificar permissões
 *
 * @example
 * ```tsx
 * const { hasRole, hasAnyRole, canApprove } = usePermissions();
 *
 * if (hasRole('ADMIN')) {
 *   // ...
 * }
 * ```
 */
export function usePermissions() {
  const { user, isAuthenticated } = useAuth();

  const hasRole = (role: Role): boolean => {
    if (!isAuthenticated || !user) return false;
    return user.perfil === role;
  };

  const hasAnyRole = (roles: Role[]): boolean => {
    if (!isAuthenticated || !user) return false;
    return roles.includes(user.perfil);
  };

  const hasAllRoles = (roles: Role[]): boolean => {
    if (!isAuthenticated || !user) return false;
    // Para ADMIN sempre retorna true
    if (user.perfil === 'ADMIN') return true;
    // Outros roles precisam ter exatamente os roles especificados
    return roles.length === 1 && roles.includes(user.perfil);
  };

  // Verificações específicas por funcionalidade
  const canCreateCadastro = hasAnyRole(['ADMIN', 'AGENTE']);
  const canApproveCadastro = hasAnyRole(['ADMIN', 'ANALISTA']);
  const canProcessPayment = hasAnyRole(['ADMIN', 'TESOURARIA']);
  const canViewReports = hasAnyRole(['ADMIN', 'ANALISTA', 'TESOURARIA']);
  const canExportReports = hasAnyRole(['ADMIN', 'ANALISTA', 'TESOURARIA']);
  const canManageUsers = hasRole('ADMIN');

  const isAdmin = hasRole('ADMIN');
  const isAnalista = hasRole('ANALISTA');
  const isTesouraria = hasRole('TESOURARIA');
  const isAgente = hasRole('AGENTE');
  const isAssociado = hasRole('ASSOCIADO');

  return {
    user,
    isAuthenticated,
    hasRole,
    hasAnyRole,
    hasAllRoles,
    // Permissões específicas
    canCreateCadastro,
    canApproveCadastro,
    canProcessPayment,
    canViewReports,
    canExportReports,
    canManageUsers,
    // Verificações de role
    isAdmin,
    isAnalista,
    isTesouraria,
    isAgente,
    isAssociado,
  };
}
