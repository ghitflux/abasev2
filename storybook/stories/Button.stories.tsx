import type { Meta, StoryObj } from '@storybook/react-vite';
import React from 'react';
import { Button } from '@abase/ui';
import { Download, Plus, Send } from 'lucide-react';

const meta: Meta<typeof Button> = {
  title: 'Components/Button',
  component: Button,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    color: {
      control: 'select',
      options: ['default', 'primary', 'secondary', 'success', 'warning', 'danger'],
    },
    variant: {
      control: 'select',
      options: ['solid', 'bordered', 'light', 'flat', 'faded', 'shadow', 'ghost'],
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
    },
    radius: {
      control: 'select',
      options: ['none', 'sm', 'md', 'lg', 'full'],
    },
    isDisabled: {
      control: 'boolean',
    },
    loading: {
      control: 'boolean',
    },
  },
};

export default meta;
type Story = StoryObj<typeof Button>;

export const Default: Story = {
  args: {
    children: 'Botão padrão',
  },
};

export const Primary: Story = {
  args: {
    children: 'Botão primário',
    color: 'primary',
  },
};

export const AllColors: Story = {
  render: () => (
    <div className="flex flex-wrap gap-4">
      <Button color="default">Default</Button>
      <Button color="primary">Primary</Button>
      <Button color="secondary">Secondary</Button>
      <Button color="success">Success</Button>
      <Button color="warning">Warning</Button>
      <Button color="danger">Danger</Button>
    </div>
  ),
};

export const AllVariants: Story = {
  render: () => (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-4">
        <Button variant="solid" color="primary">Solid</Button>
        <Button variant="bordered" color="primary">Bordered</Button>
        <Button variant="light" color="primary">Light</Button>
        <Button variant="flat" color="primary">Flat</Button>
        <Button variant="faded" color="primary">Faded</Button>
        <Button variant="shadow" color="primary">Shadow</Button>
        <Button variant="ghost" color="primary">Ghost</Button>
      </div>
    </div>
  ),
};

export const AllSizes: Story = {
  render: () => (
    <div className="flex items-end gap-4">
      <Button size="sm" color="primary">Small</Button>
      <Button size="md" color="primary">Medium</Button>
      <Button size="lg" color="primary">Large</Button>
    </div>
  ),
};

export const AllRadius: Story = {
  render: () => (
    <div className="flex flex-wrap gap-4">
      <Button radius="none" color="primary">None</Button>
      <Button radius="sm" color="primary">Small</Button>
      <Button radius="md" color="primary">Medium</Button>
      <Button radius="lg" color="primary">Large</Button>
      <Button radius="full" color="primary">Full</Button>
    </div>
  ),
};

export const WithLeftIcon: Story = {
  args: {
    children: 'Download',
    color: 'primary',
    leftIcon: <Download size={16} />,
  },
};

export const WithRightIcon: Story = {
  args: {
    children: 'Enviar',
    color: 'primary',
    rightIcon: <Send size={16} />,
  },
};

export const WithBothIcons: Story = {
  args: {
    children: 'Adicionar',
    color: 'primary',
    leftIcon: <Plus size={16} />,
    rightIcon: <Download size={16} />,
  },
};

export const Loading: Story = {
  args: {
    children: 'Salvar',
    color: 'primary',
    loading: true,
  },
};

export const Disabled: Story = {
  args: {
    children: 'Botão desabilitado',
    color: 'primary',
    isDisabled: true,
  },
};

export const FullWidth: Story = {
  args: {
    children: 'Botão full width',
    color: 'primary',
    fullWidth: true,
  },
  parameters: {
    layout: 'padded',
  },
};

export const ActionButtons: Story = {
  render: () => (
    <div className="flex flex-col gap-4 w-96">
      <div className="flex gap-3">
        <Button color="primary" fullWidth leftIcon={<Plus size={16} />}>
          Novo Cadastro
        </Button>
        <Button color="default" variant="bordered" leftIcon={<Download size={16} />}>
          Exportar
        </Button>
      </div>
      <div className="flex gap-3 justify-end">
        <Button color="default" variant="light">
          Cancelar
        </Button>
        <Button color="primary" rightIcon={<Send size={16} />}>
          Enviar
        </Button>
      </div>
    </div>
  ),
};
