"use client";

import React, { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Spinner } from '@heroui/react';
import { useAuth } from '@/contexts/AuthContext';

export type Role = 'ADMIN' | 'ANALISTA' | 'TESOURARIA' | 'AGENTE' | 'ASSOCIADO';

export interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRoles?: Role[];
  fallback?: React.ReactNode;
  redirectTo?: string;
}

/**
 * Componente para proteger rotas que requerem autenticação
 *
 * @example
 * ```tsx
 * <ProtectedRoute requiredRoles={['ADMIN', 'ANALISTA']}>
 *   <AdminPage />
 * </ProtectedRoute>
 * ```
 */
export function ProtectedRoute({
  children,
  requiredRoles,
  fallback,
  redirectTo = '/login',
}: ProtectedRouteProps) {
  const { user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading) {
      // Não autenticado
      if (!isAuthenticated) {
        // Salvar URL atual para redirect após login
        if (typeof window !== 'undefined') {
          localStorage.setItem('auth_redirect', pathname || '/dashboard');
        }
        router.push(redirectTo);
        return;
      }

      // Verificar roles se especificado
      if (requiredRoles && requiredRoles.length > 0) {
        const userRole = user?.perfil;

        if (!userRole || !requiredRoles.includes(userRole)) {
          // Usuário não tem permissão
          router.push('/unauthorized');
          return;
        }
      }
    }
  }, [isLoading, isAuthenticated, user, requiredRoles, router, pathname, redirectTo]);

  // Loading
  if (isLoading) {
    return (
      fallback || (
        <div className="flex min-h-screen items-center justify-center">
          <div className="text-center space-y-4">
            <Spinner size="lg" color="primary" />
            <p className="text-default-500">Carregando...</p>
          </div>
        </div>
      )
    );
  }

  // Não autenticado ou sem permissão (redirect será feito pelo useEffect)
  if (!isAuthenticated || (requiredRoles && user && !requiredRoles.includes(user.perfil))) {
    return (
      fallback || (
        <div className="flex min-h-screen items-center justify-center">
          <div className="text-center space-y-4">
            <Spinner size="lg" color="primary" />
            <p className="text-default-500">Verificando permissões...</p>
          </div>
        </div>
      )
    );
  }

  // Autenticado e com permissão
  return <>{children}</>;
}

/**
 * HOC para proteger páginas
 *
 * @example
 * ```tsx
 * export default withAuth(AdminPage, { requiredRoles: ['ADMIN'] });
 * ```
 */
export function withAuth<P extends object>(
  Component: React.ComponentType<P>,
  options?: Omit<ProtectedRouteProps, 'children'>
) {
  return function ProtectedComponent(props: P) {
    return (
      <ProtectedRoute {...options}>
        <Component {...props} />
      </ProtectedRoute>
    );
  };
}
