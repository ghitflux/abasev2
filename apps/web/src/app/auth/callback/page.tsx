"use client";

import React, { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Spinner } from '@heroui/react';
import { useToast } from '@abase/ui';

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { addToast } = useToast();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleCallback = async () => {
      // Extrair código da URL
      const code = searchParams?.get('code');
      const errorParam = searchParams?.get('error');
      const errorDescription = searchParams?.get('error_description');

      // Verificar se houve erro
      if (errorParam) {
        const errorMessage = errorDescription || errorParam;
        setError(errorMessage);

        addToast({
          type: 'error',
          title: 'Erro na autenticação',
          description: errorMessage,
        });

        // Redirecionar para login após 3 segundos
        setTimeout(() => {
          router.push('/login');
        }, 3000);
        return;
      }

      // Verificar se código está presente
      if (!code) {
        setError('Código de autorização não encontrado');

        addToast({
          type: 'error',
          title: 'Erro na autenticação',
          description: 'Código de autorização não encontrado',
        });

        setTimeout(() => {
          router.push('/login');
        }, 3000);
        return;
      }

      try {
        // Obter code verifier do localStorage
        const codeVerifier = localStorage.getItem('code_verifier') || '';

        // Fazer requisição ao backend
        const baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const response = await fetch(`${baseURL}/api/v1/auth/oidc/callback`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            code,
            code_verifier: codeVerifier,
          }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.message || 'Erro na autenticação');
        }

        const data = await response.json();

        // Salvar tokens
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);

        // Limpar code verifier
        localStorage.removeItem('code_verifier');

        // Mostrar sucesso
        addToast({
          type: 'success',
          title: 'Login realizado',
          description: 'Bem-vindo ao ABASE Manager!',
        });

        // Redirecionar
        const redirectTo = localStorage.getItem('auth_redirect') || '/dashboard';
        localStorage.removeItem('auth_redirect');
        router.push(redirectTo);
      } catch (err: any) {
        const errorMessage = err.message || 'Erro ao processar autenticação';
        setError(errorMessage);

        addToast({
          type: 'error',
          title: 'Erro na autenticação',
          description: errorMessage,
        });

        setTimeout(() => {
          router.push('/login');
        }, 3000);
      }
    };

    handleCallback();
  }, [searchParams, router, addToast]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800">
      <div className="text-center space-y-6">
        {error ? (
          <>
            <div className="text-6xl mb-4">⚠️</div>
            <h1 className="text-2xl font-bold text-danger">Erro na Autenticação</h1>
            <p className="text-default-600 max-w-md">{error}</p>
            <p className="text-sm text-default-400">Redirecionando para login...</p>
          </>
        ) : (
          <>
            <Spinner size="lg" color="primary" />
            <h1 className="text-2xl font-bold text-default-700">Processando autenticação</h1>
            <p className="text-default-500">Aguarde enquanto validamos suas credenciais...</p>
          </>
        )}
      </div>
    </div>
  );
}

export default function OIDCCallbackPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center">
        <Spinner size="lg" color="primary" />
      </div>
    }>
      <CallbackContent />
    </Suspense>
  );
}
