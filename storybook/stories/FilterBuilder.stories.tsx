import type { Meta, StoryObj } from '@storybook/react-vite';
import React, { useState } from 'react';
import { FilterBuilder, FilterGroup } from '@abase/ui';

const meta: Meta<typeof FilterBuilder> = {
  title: 'Components/FilterBuilder',
  component: FilterBuilder,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof FilterBuilder>;

export const Default: Story = {
  render: function DefaultStory() {
    const [filters, setFilters] = useState<FilterGroup>({ type: 'AND', conditions: [] });

    return (
      <FilterBuilder
        configs={[
          { field: 'name', label: 'Nome', type: 'text', placeholder: 'Digite o nome' },
          { field: 'status', label: 'Status', type: 'select', options: [
            { value: 'active', label: 'Ativo' },
            { value: 'inactive', label: 'Inativo' }
          ]},
          { field: 'createdAt', label: 'Data de Criação', type: 'date' },
        ]}
        filters={filters}
        onFiltersChange={setFilters}
      />
    );
  },
};

export const WithQuickFilters: Story = {
  render: function WithQuickFiltersStory() {
    const [filters, setFilters] = useState<FilterGroup>({ type: 'AND', conditions: [] });

    return (
      <FilterBuilder
        configs={[
          { field: 'name', label: 'Nome', type: 'text' },
          { field: 'status', label: 'Status', type: 'select', options: [
            { value: 'active', label: 'Ativo' },
            { value: 'inactive', label: 'Inativo' }
          ]},
          { field: 'role', label: 'Função', type: 'select', options: [
            { value: 'admin', label: 'Admin' },
            { value: 'user', label: 'Usuário' }
          ]},
        ]}
        filters={filters}
        onFiltersChange={setFilters}
        quickFilters={[
          { label: 'Só Ativos', filters: [{ field: 'status', operator: 'eq', value: 'active' }] },
          { label: 'Administradores', filters: [{ field: 'role', operator: 'eq', value: 'admin' }] },
        ]}
      />
    );
  },
};

export const WithSearch: Story = {
  render: function WithSearchStory() {
    const [filters, setFilters] = useState<FilterGroup>({ type: 'AND', conditions: [] });

    return (
      <FilterBuilder
        configs={[
          { field: 'name', label: 'Nome', type: 'text' },
          { field: 'email', label: 'Email', type: 'text' },
        ]}
        filters={filters}
        onFiltersChange={setFilters}
        onSearch={(query) => console.log('Search:', query)}
      />
    );
  },
};
