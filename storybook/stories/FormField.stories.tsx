import type { Meta, StoryObj } from '@storybook/react-vite';
import React from 'react';
import { FormField, useToast } from '@abase/ui';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const meta: Meta<typeof FormField> = {
  title: 'Components/FormField',
  component: FormField,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof FormField>;

const schema = z.object({
  name: z.string().min(3, 'Nome deve ter no mínimo 3 caracteres'),
  email: z.string().email('Email inválido'),
  password: z.string().min(6, 'Senha deve ter no mínimo 6 caracteres'),
  description: z.string().optional(),
  role: z.string(),
  birthdate: z.date().optional(),
  newsletter: z.boolean(),
  gender: z.string(),
});

type FormData = z.infer<typeof schema>;

export const AllFieldTypes: Story = {
  render: function AllFieldTypesStory() {
    const { control, handleSubmit } = useForm<FormData>({
      resolver: zodResolver(schema),
      defaultValues: {
        newsletter: false,
      },
    });
    const { addToast } = useToast();

    const onSubmit = (data: FormData) => {
      addToast({ type: 'success', title: 'Formulário enviado!', description: JSON.stringify(data) });
    };

    return (
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 max-w-md">
        <FormField
          control={control}
          name="name"
          label="Nome Completo"
          placeholder="Digite seu nome"
          required
          helperText="Nome como aparece no documento"
        />

        <FormField
          control={control}
          name="email"
          type="email"
          label="Email"
          placeholder="seu@email.com"
          required
        />

        <FormField
          control={control}
          name="password"
          type="password"
          label="Senha"
          placeholder="******"
          required
        />

        <FormField
          control={control}
          name="description"
          type="textarea"
          label="Descrição"
          placeholder="Conte um pouco sobre você"
        />

        <FormField
          control={control}
          name="role"
          type="select"
          label="Função"
          required
          options={[
            { value: 'admin', label: 'Administrador' },
            { value: 'user', label: 'Usuário' },
            { value: 'manager', label: 'Gerente' },
          ]}
        />

        <FormField
          control={control}
          name="gender"
          type="radio"
          label="Gênero"
          options={[
            { value: 'male', label: 'Masculino' },
            { value: 'female', label: 'Feminino' },
            { value: 'other', label: 'Outro' },
          ]}
        />

        <FormField
          control={control}
          name="newsletter"
          type="checkbox"
          label="Desejo receber novidades por email"
        />

        <button type="submit" className="w-full bg-primary text-white rounded-lg py-2 px-4 hover:opacity-90">
          Enviar
        </button>
      </form>
    );
  },
};
