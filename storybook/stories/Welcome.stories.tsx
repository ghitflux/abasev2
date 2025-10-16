import type { Meta, StoryObj } from '@storybook/react-vite';
import React from 'react';
import { Button, useToast } from '@abase/ui';

const meta: Meta = {
  title: 'Foundations/GettingStarted',
  render: function WelcomeStory() {
    const { addToast } = useToast();

    return (
      <div className="flex flex-col gap-4 rounded-2xl border border-default-200 bg-content1 p-8 shadow-sm">
        <div>
          <h1 className="text-2xl font-bold">ABASE Design System</h1>
          <p className="text-default-500">
            Conjunto inicial de componentes construídos com HeroUI + Tailwind, focados em produtividade do time.
          </p>
        </div>
        <div className="flex gap-3">
          <Button
            color="primary"
            onPress={() =>
              addToast({
                type: 'success',
                title: 'Integração concluída',
                description: 'Toast provider e botões prontos para uso.',
              })
            }
          >
            Abrir Toast
          </Button>
          <Button variant="flat">Ação secundária</Button>
        </div>
      </div>
    );
  },
};

export default meta;

export const Default: StoryObj = {};
