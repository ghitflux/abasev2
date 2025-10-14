'use client';

import React from 'react';
import { HeroUIProvider } from '@heroui/react';
import { ToastProvider } from '@abase/ui';
import { AuthProvider } from '@/contexts/AuthContext';

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <HeroUIProvider>
      <ToastProvider>
        <AuthProvider>{children}</AuthProvider>
      </ToastProvider>
    </HeroUIProvider>
  );
}
