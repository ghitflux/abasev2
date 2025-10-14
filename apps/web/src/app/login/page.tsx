"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Input, Card, CardBody, CardHeader } from '@heroui/react';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@abase/ui';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const { login, loginWithOIDC } = useAuth();
  const { addToast } = useToast();
  const router = useRouter();

  const handleLocalLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login(username, password);

      addToast({
        type: 'success',
        title: 'Login realizado',
        description: 'Bem-vindo ao ABASE Manager!',
      });

      router.push('/dashboard');
    } catch (err: any) {
      const errorMessage = err.message || 'Erro ao fazer login';
      setError(errorMessage);

      addToast({
        type: 'error',
        title: 'Erro no login',
        description: errorMessage,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleOIDCLogin = () => {
    loginWithOIDC('/dashboard');
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 px-4">
      <Card className="w-full max-w-md shadow-2xl">
        <CardHeader className="flex flex-col gap-2 items-center pb-6 pt-8">
          <h1 className="text-3xl font-bold text-primary">ABASE Manager</h1>
          <p className="text-sm text-default-500">Sistema de Gestão de Associados</p>
        </CardHeader>

        <CardBody className="gap-6 px-8 pb-8">
          {/* Login Local */}
          <form onSubmit={handleLocalLogin} className="flex flex-col gap-4">
            <Input
              label="Usuário ou Email"
              placeholder="Digite seu usuário"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              isRequired
              size="lg"
              variant="bordered"
              autoComplete="username"
            />

            <Input
              label="Senha"
              placeholder="Digite sua senha"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              isRequired
              size="lg"
              variant="bordered"
              autoComplete="current-password"
            />

            {error && (
              <div className="text-sm text-danger bg-danger-50 dark:bg-danger-900/20 p-3 rounded-lg">
                {error}
              </div>
            )}

            <Button
              type="submit"
              color="primary"
              size="lg"
              isLoading={isLoading}
              className="w-full font-semibold"
            >
              {isLoading ? 'Entrando...' : 'Entrar'}
            </Button>
          </form>

          {/* Divider */}
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-default-200"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="bg-content1 px-4 text-default-500">Ou continue com</span>
            </div>
          </div>

          {/* Login OIDC */}
          <Button
            variant="bordered"
            size="lg"
            onPress={handleOIDCLogin}
            className="w-full font-semibold"
          >
            <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
            </svg>
            Login com OIDC
          </Button>

          {/* Links auxiliares */}
          <div className="flex justify-between text-sm">
            <a href="/recuperar-senha" className="text-primary hover:underline">
              Esqueceu a senha?
            </a>
            <a href="/primeiro-acesso" className="text-primary hover:underline">
              Primeiro acesso
            </a>
          </div>
        </CardBody>
      </Card>

      {/* Footer */}
      <div className="absolute bottom-4 text-center text-sm text-default-400">
        <p>ABASE Manager v2.0 - Sistema de Gestão</p>
      </div>
    </div>
  );
}
