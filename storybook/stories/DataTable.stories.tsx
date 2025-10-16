import type { Meta, StoryObj } from '@storybook/react-vite';
import React, { useState } from 'react';
import { DataTable, FilterGroup, StatusBadge, useToast } from '@abase/ui';
import { DocumentTextIcon as FileText } from '@heroicons/react/24/outline';

type User = {
  id: string;
  name: string;
  email: string;
  role: 'admin' | 'user' | 'manager';
  status: 'active' | 'inactive';
  createdAt: Date;
  isVerified: boolean;
};

const sampleData: User[] = [
  { id: '1', name: 'João Silva', email: 'joao@example.com', role: 'admin', status: 'active', createdAt: new Date('2024-01-15'), isVerified: true },
  { id: '2', name: 'Maria Santos', email: 'maria@example.com', role: 'user', status: 'active', createdAt: new Date('2024-02-10'), isVerified: true },
  { id: '3', name: 'Pedro Costa', email: 'pedro@example.com', role: 'manager', status: 'active', createdAt: new Date('2024-03-05'), isVerified: false },
  { id: '4', name: 'Ana Oliveira', email: 'ana@example.com', role: 'user', status: 'inactive', createdAt: new Date('2024-01-20'), isVerified: true },
  { id: '5', name: 'Carlos Pereira', email: 'carlos@example.com', role: 'user', status: 'active', createdAt: new Date('2024-02-25'), isVerified: true },
];

const meta: Meta<typeof DataTable> = {
  title: 'Components/DataTable',
  component: DataTable,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof DataTable>;

export const Default: Story = {
  render: () => (
    <DataTable
      columns={[
        { key: 'name', label: 'Nome', sortable: true },
        { key: 'email', label: 'Email', sortable: true },
        { key: 'role', label: 'Função' },
        { key: 'createdAt', label: 'Criado em', sortable: true },
      ]}
      data={sampleData}
    />
  ),
};

export const WithCustomRenderers: Story = {
  render: () => (
    <DataTable
      columns={[
        {
          key: 'name',
          label: 'Nome',
          sortable: true,
          render: (item) => (
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-full bg-primary-100 flex items-center justify-center text-primary-600 font-semibold">
                {item.name[0]}
              </div>
              <span className="font-medium">{item.name}</span>
            </div>
          ),
        },
        { key: 'email', label: 'Email' },
        {
          key: 'role',
          label: 'Função',
          render: (item) => {
            const roleMap = {
              admin: { label: 'Administrador', color: 'danger' as const },
              manager: { label: 'Gerente', color: 'warning' as const },
              user: { label: 'Usuário', color: 'default' as const },
            };
            const config = roleMap[item.role];
            return <StatusBadge status={config.label.toLowerCase()} label={config.label} />;
          },
        },
        {
          key: 'status',
          label: 'Status',
          render: (item) => (
            <StatusBadge status={item.status === 'active' ? 'success' : 'danger'} label={item.status === 'active' ? 'Ativo' : 'Inativo'} />
          ),
        },
        { key: 'isVerified', label: 'Verificado' },
      ]}
      data={sampleData}
    />
  ),
};

export const WithActions: Story = {
  render: function WithActionsStory() {
    const { addToast } = useToast();

    return (
      <DataTable
        columns={[
          { key: 'name', label: 'Nome', sortable: true },
          { key: 'email', label: 'Email' },
          { key: 'role', label: 'Função' },
          {
            key: 'status',
            label: 'Status',
            render: (item) => (
              <StatusBadge status={item.status === 'active' ? 'success' : 'danger'} label={item.status === 'active' ? 'Ativo' : 'Inativo'} />
            ),
          },
        ]}
        data={sampleData}
        actions={{
          onView: (item) => addToast({ type: 'info', title: 'Visualizar', description: `Visualizando ${item.name}` }),
          onEdit: (item) => addToast({ type: 'info', title: 'Editar', description: `Editando ${item.name}` }),
          onDelete: (item) => addToast({ type: 'warning', title: 'Excluir', description: `Confirmar exclusão de ${item.name}?` }),
          custom: [
            {
              label: 'Gerar relatório',
              icon: <FileText className="h-4 w-4" />,
              color: 'primary',
              onClick: (item) => addToast({ type: 'success', title: 'Relatório', description: `Gerando relatório de ${item.name}` }),
            },
          ],
        }}
      />
    );
  },
};

export const WithPagination: Story = {
  render: function WithPaginationStory() {
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(10);

    // Create more data for pagination
    const largeDataset = Array.from({ length: 50 }, (_, i) => ({
      id: String(i + 1),
      name: `Usuário ${i + 1}`,
      email: `user${i + 1}@example.com`,
      role: ['admin', 'user', 'manager'][i % 3] as 'admin' | 'user' | 'manager',
      status: i % 4 === 0 ? 'inactive' : 'active' as 'active' | 'inactive',
      createdAt: new Date(2024, 0, (i % 28) + 1),
      isVerified: i % 3 !== 0,
    }));

    const paginatedData = largeDataset.slice((page - 1) * pageSize, page * pageSize);

    return (
      <DataTable
        columns={[
          { key: 'name', label: 'Nome', sortable: true },
          { key: 'email', label: 'Email' },
          { key: 'role', label: 'Função' },
          { key: 'status', label: 'Status' },
        ]}
        data={paginatedData}
        pagination={{
          page,
          pageSize,
          total: largeDataset.length,
          onPageChange: setPage,
          onPageSizeChange: (size) => {
            setPageSize(size);
            setPage(1);
          },
        }}
      />
    );
  },
};

export const WithFilters: Story = {
  render: function WithFiltersStory() {
    const [filters, setFilters] = useState<FilterGroup>({ type: 'AND', conditions: [] });

    const filteredData = sampleData.filter((item) => {
      if (filters.conditions.length === 0) return true;

      return filters.conditions.every((condition) => {
        if (condition.field === 'role') {
          return item.role === condition.value;
        }
        if (condition.field === 'status') {
          return item.status === condition.value;
        }
        if (condition.field === 'name') {
          return new RegExp(String(condition.value), 'i').test(item.name);
        }
        return true;
      });
    });

    return (
      <DataTable
        columns={[
          { key: 'name', label: 'Nome', sortable: true },
          { key: 'email', label: 'Email' },
          { key: 'role', label: 'Função' },
          {
            key: 'status',
            label: 'Status',
            render: (item) => (
              <StatusBadge status={item.status === 'active' ? 'success' : 'danger'} label={item.status === 'active' ? 'Ativo' : 'Inativo'} />
            ),
          },
        ]}
        data={filteredData}
        filters={{
          configs: [
            {
              field: 'name',
              label: 'Nome',
              type: 'text',
              placeholder: 'Filtrar por nome',
            },
            {
              field: 'role',
              label: 'Função',
              type: 'select',
              options: [
                { value: 'admin', label: 'Administrador' },
                { value: 'manager', label: 'Gerente' },
                { value: 'user', label: 'Usuário' },
              ],
            },
            {
              field: 'status',
              label: 'Status',
              type: 'select',
              options: [
                { value: 'active', label: 'Ativo' },
                { value: 'inactive', label: 'Inativo' },
              ],
            },
          ],
          current: filters,
          onChange: setFilters,
          quickFilters: [
            {
              label: 'Só Ativos',
              filters: [{ field: 'status', operator: 'eq', value: 'active' }],
            },
            {
              label: 'Administradores',
              filters: [{ field: 'role', operator: 'eq', value: 'admin' }],
            },
          ],
        }}
      />
    );
  },
};

export const WithSelection: Story = {
  render: function WithSelectionStory() {
    const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
    const { addToast } = useToast();

    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm text-default-500">
            {selectedKeys.size} {selectedKeys.size === 1 ? 'item selecionado' : 'itens selecionados'}
          </span>
          {selectedKeys.size > 0 && (
            <button
              className="text-sm text-danger hover:underline"
              onClick={() => {
                addToast({ type: 'success', title: 'Ação em lote', description: `${selectedKeys.size} itens processados` });
                setSelectedKeys(new Set());
              }}
            >
              Processar selecionados
            </button>
          )}
        </div>
        <DataTable
          columns={[
            { key: 'name', label: 'Nome', sortable: true },
            { key: 'email', label: 'Email' },
            { key: 'role', label: 'Função' },
          ]}
          data={sampleData}
          selectable
          onSelectionChange={setSelectedKeys}
        />
      </div>
    );
  },
};

export const Loading: Story = {
  render: () => (
    <DataTable
      columns={[
        { key: 'name', label: 'Nome' },
        { key: 'email', label: 'Email' },
        { key: 'role', label: 'Função' },
      ]}
      data={[]}
      loading
    />
  ),
};

export const Empty: Story = {
  render: () => (
    <DataTable
      columns={[
        { key: 'name', label: 'Nome' },
        { key: 'email', label: 'Email' },
        { key: 'role', label: 'Função' },
      ]}
      data={[]}
      emptyMessage="Nenhum usuário encontrado. Adicione um novo usuário para começar."
    />
  ),
};
