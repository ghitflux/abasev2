import type { Meta, StoryObj } from '@storybook/react-vite';
import React, { useState } from 'react';
import { MultiStepForm, Step, useToast } from '@abase/ui';
import { Input } from '@heroui/react';

const meta: Meta<typeof MultiStepForm> = {
  title: 'Components/MultiStepForm',
  component: MultiStepForm,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof MultiStepForm>;

export const Default: Story = {
  render: function DefaultStory() {
    const [currentStep, setCurrentStep] = useState(0);
    const { addToast } = useToast();

    const steps: Step[] = [
      {
        id: 'personal',
        title: 'Dados Pessoais',
        description: 'Informações básicas',
        isActive: currentStep === 0,
        isCompleted: currentStep > 0,
      },
      {
        id: 'address',
        title: 'Endereço',
        description: 'Onde você mora',
        isActive: currentStep === 1,
        isCompleted: currentStep > 1,
      },
      {
        id: 'review',
        title: 'Revisão',
        description: 'Confirme seus dados',
        isActive: currentStep === 2,
        isCompleted: currentStep > 2,
      },
    ];

    return (
      <MultiStepForm
        steps={steps}
        currentStep={currentStep}
        onStepChange={setCurrentStep}
        onFinish={() => addToast({ type: 'success', title: 'Formulário concluído!' })}
      >
        {currentStep === 0 && (
          <div className="space-y-4">
            <Input label="Nome Completo" placeholder="Digite seu nome" />
            <Input label="Email" type="email" placeholder="seu@email.com" />
          </div>
        )}
        {currentStep === 1 && (
          <div className="space-y-4">
            <Input label="CEP" placeholder="00000-000" />
            <Input label="Endereço" placeholder="Rua, número" />
            <Input label="Cidade" placeholder="Cidade" />
          </div>
        )}
        {currentStep === 2 && (
          <div className="space-y-4 text-sm">
            <p><strong>Nome:</strong> João Silva</p>
            <p><strong>Email:</strong> joao@example.com</p>
            <p><strong>Endereço:</strong> Rua das Flores, 123</p>
            <p><strong>Cidade:</strong> São Paulo</p>
          </div>
        )}
      </MultiStepForm>
    );
  },
};

export const WithLoading: Story = {
  render: function WithLoadingStory() {
    const [currentStep, setCurrentStep] = useState(0);
    const [isLoading, setIsLoading] = useState(false);

    const steps: Step[] = [
      { id: '1', title: 'Etapa 1', isActive: currentStep === 0, isCompleted: currentStep > 0 },
      { id: '2', title: 'Etapa 2', isActive: currentStep === 1, isCompleted: currentStep > 1 },
      { id: '3', title: 'Etapa 3', isActive: currentStep === 2, isCompleted: currentStep > 2 },
    ];

    const handleNext = () => {
      setIsLoading(true);
      setTimeout(() => {
        setCurrentStep((prev) => prev + 1);
        setIsLoading(false);
      }, 1000);
    };

    return (
      <MultiStepForm
        steps={steps}
        currentStep={currentStep}
        onStepChange={setCurrentStep}
        onNext={handleNext}
        isLoading={isLoading}
      >
        <div className="p-8 text-center">Conteúdo da Etapa {currentStep + 1}</div>
      </MultiStepForm>
    );
  },
};
