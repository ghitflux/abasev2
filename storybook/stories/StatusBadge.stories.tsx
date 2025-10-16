import type { Meta, StoryObj } from '@storybook/react-vite';
import React from 'react';
import { StatusBadge, PendingBadge, ApprovedBadge, RejectedBadge, CompletedBadge, InProgressBadge } from '@abase/ui';

const meta: Meta<typeof StatusBadge> = {
  title: 'Components/StatusBadge',
  component: StatusBadge,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    status: {
      control: 'text',
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
    },
    variant: {
      control: 'select',
      options: ['solid', 'bordered', 'light', 'flat', 'faded', 'shadow', 'dot'],
    },
    showIcon: {
      control: 'boolean',
    },
  },
};

export default meta;
type Story = StoryObj<typeof StatusBadge>;

export const Default: Story = {
  args: {
    status: 'pending',
  },
};

export const GenericStatuses: Story = {
  render: () => (
    <div className="flex flex-wrap gap-3">
      <StatusBadge status="success" />
      <StatusBadge status="warning" />
      <StatusBadge status="danger" />
      <StatusBadge status="primary" />
      <StatusBadge status="secondary" />
      <StatusBadge status="default" />
    </div>
  ),
};

export const BusinessStatuses: Story = {
  render: () => (
    <div className="flex flex-wrap gap-3">
      <StatusBadge status="pending" />
      <StatusBadge status="approved" />
      <StatusBadge status="rejected" />
      <StatusBadge status="cancelled" />
      <StatusBadge status="completed" />
      <StatusBadge status="in_progress" />
    </div>
  ),
};

export const CadastroStatuses: Story = {
  render: () => (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-3">
        <StatusBadge status="RASCUNHO" />
        <StatusBadge status="SUBMETIDO" />
        <StatusBadge status="EM_ANALISE" />
        <StatusBadge status="APROVADO" />
      </div>
      <div className="flex flex-wrap gap-3">
        <StatusBadge status="PENDENTE" />
        <StatusBadge status="CANCELADO" />
        <StatusBadge status="PAGAMENTO_PENDENTE" />
        <StatusBadge status="PAGAMENTO_RECEBIDO" />
      </div>
      <div className="flex flex-wrap gap-3">
        <StatusBadge status="CONTRATO_GERADO" />
        <StatusBadge status="ENVIADO_ASSINATURA" />
        <StatusBadge status="ASSINADO" />
        <StatusBadge status="CONCLUIDO" />
      </div>
    </div>
  ),
};

export const AllSizes: Story = {
  render: () => (
    <div className="flex items-center gap-4">
      <StatusBadge status="approved" size="sm" />
      <StatusBadge status="approved" size="md" />
      <StatusBadge status="approved" size="lg" />
    </div>
  ),
};

export const AllVariants: Story = {
  render: () => (
    <div className="flex flex-wrap gap-3">
      <StatusBadge status="approved" variant="solid" />
      <StatusBadge status="approved" variant="bordered" />
      <StatusBadge status="approved" variant="light" />
      <StatusBadge status="approved" variant="flat" />
      <StatusBadge status="approved" variant="faded" />
      <StatusBadge status="approved" variant="shadow" />
      <StatusBadge status="approved" variant="dot" />
    </div>
  ),
};

export const WithoutIcons: Story = {
  render: () => (
    <div className="flex flex-wrap gap-3">
      <StatusBadge status="pending" showIcon={false} />
      <StatusBadge status="approved" showIcon={false} />
      <StatusBadge status="rejected" showIcon={false} />
      <StatusBadge status="completed" showIcon={false} />
    </div>
  ),
};

export const CustomLabels: Story = {
  render: () => (
    <div className="flex flex-wrap gap-3">
      <StatusBadge status="pending" label="Aguardando revisão" />
      <StatusBadge status="approved" label="Tudo certo!" />
      <StatusBadge status="rejected" label="Precisa correção" />
    </div>
  ),
};

export const ConvenienceComponents: Story = {
  render: () => (
    <div className="flex flex-wrap gap-3">
      <PendingBadge />
      <ApprovedBadge />
      <RejectedBadge />
      <CompletedBadge />
      <InProgressBadge />
    </div>
  ),
};

export const InTableContext: Story = {
  render: () => (
    <div className="rounded-lg border border-default-200 overflow-hidden">
      <table className="w-full">
        <thead className="bg-default-100">
          <tr>
            <th className="px-4 py-3 text-left text-sm font-semibold">ID</th>
            <th className="px-4 py-3 text-left text-sm font-semibold">Associado</th>
            <th className="px-4 py-3 text-left text-sm font-semibold">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-default-200">
          <tr>
            <td className="px-4 py-3 text-sm">#001</td>
            <td className="px-4 py-3 text-sm">João Silva</td>
            <td className="px-4 py-3"><StatusBadge status="APROVADO" /></td>
          </tr>
          <tr>
            <td className="px-4 py-3 text-sm">#002</td>
            <td className="px-4 py-3 text-sm">Maria Santos</td>
            <td className="px-4 py-3"><StatusBadge status="EM_ANALISE" /></td>
          </tr>
          <tr>
            <td className="px-4 py-3 text-sm">#003</td>
            <td className="px-4 py-3 text-sm">Pedro Costa</td>
            <td className="px-4 py-3"><StatusBadge status="PENDENTE" /></td>
          </tr>
        </tbody>
      </table>
    </div>
  ),
};
