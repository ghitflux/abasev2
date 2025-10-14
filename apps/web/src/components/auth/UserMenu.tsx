"use client";

import React from 'react';
import {
  Dropdown,
  DropdownTrigger,
  DropdownMenu,
  DropdownItem,
  Avatar,
  Button,
} from '@heroui/react';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';

export interface UserMenuProps {
  showName?: boolean;
  avatarSize?: 'sm' | 'md' | 'lg';
}

/**
 * Menu do usuário autenticado
 *
 * @example
 * ```tsx
 * <UserMenu showName avatarSize="md" />
 * ```
 */
export function UserMenu({ showName = true, avatarSize = 'md' }: UserMenuProps) {
  const { user, logout, isAuthenticated } = useAuth();
  const router = useRouter();

  if (!isAuthenticated || !user) {
    return (
      <Button
        color="primary"
        variant="flat"
        onPress={() => router.push('/login')}
      >
        Entrar
      </Button>
    );
  }

  const handleLogout = async () => {
    await logout();
  };

  const getRoleColor = (role: string): 'default' | 'primary' | 'success' | 'warning' | 'danger' => {
    switch (role) {
      case 'ADMIN':
        return 'danger';
      case 'ANALISTA':
        return 'primary';
      case 'TESOURARIA':
        return 'success';
      case 'AGENTE':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getRoleLabel = (role: string): string => {
    const labels: Record<string, string> = {
      ADMIN: 'Administrador',
      ANALISTA: 'Analista',
      TESOURARIA: 'Tesouraria',
      AGENTE: 'Agente',
      ASSOCIADO: 'Associado',
    };
    return labels[role] || role;
  };

  // Gerar iniciais do nome
  const getInitials = (name: string, email: string): string => {
    if (name && name.trim()) {
      const parts = name.trim().split(' ');
      if (parts.length >= 2) {
        return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
      }
      return name.substring(0, 2).toUpperCase();
    }
    return email.substring(0, 2).toUpperCase();
  };

  return (
    <Dropdown placement="bottom-end">
      <DropdownTrigger>
        <div className="flex items-center gap-3 cursor-pointer hover:opacity-80 transition-opacity">
          <Avatar
            size={avatarSize}
            name={getInitials(user.full_name, user.email)}
            color={getRoleColor(user.perfil)}
            className="cursor-pointer"
          />
          {showName && (
            <div className="hidden md:flex flex-col items-start">
              <span className="text-sm font-semibold">
                {user.full_name || user.email}
              </span>
              <span className="text-xs text-default-500">
                {getRoleLabel(user.perfil)}
              </span>
            </div>
          )}
        </div>
      </DropdownTrigger>

      <DropdownMenu aria-label="Menu do usuário" variant="flat">
        <DropdownItem
          key="profile"
          className="h-14 gap-2"
          textValue="Perfil"
        >
          <div className="flex flex-col">
            <span className="font-semibold">{user.full_name || 'Usuário'}</span>
            <span className="text-xs text-default-500">{user.email}</span>
          </div>
        </DropdownItem>

        <DropdownItem
          key="role"
          className="h-10"
          textValue="Role"
          isReadOnly
        >
          <div className="flex items-center justify-between">
            <span className="text-sm">Perfil:</span>
            <span
              className={`text-sm font-medium text-${getRoleColor(user.perfil)}`}
            >
              {getRoleLabel(user.perfil)}
            </span>
          </div>
        </DropdownItem>

        <DropdownItem
          key="dashboard"
          onPress={() => router.push('/dashboard')}
        >
          Dashboard
        </DropdownItem>

        <DropdownItem
          key="settings"
          onPress={() => router.push('/configuracoes')}
        >
          Configurações
        </DropdownItem>

        <DropdownItem
          key="help"
          onPress={() => router.push('/ajuda')}
        >
          Ajuda
        </DropdownItem>

        <DropdownItem
          key="logout"
          color="danger"
          onPress={handleLogout}
          className="text-danger"
        >
          Sair
        </DropdownItem>
      </DropdownMenu>
    </Dropdown>
  );
}
