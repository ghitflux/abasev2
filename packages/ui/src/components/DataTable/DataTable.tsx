import React, { useMemo, useState } from 'react';
import {
  Chip,
  Dropdown,
  DropdownItem,
  DropdownMenu,
  DropdownTrigger,
  Pagination,
  Select,
  SelectItem,
  Selection,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableColumn,
  TableHeader,
  TableRow,
} from '@heroui/react';
import { Edit, Eye, MoreVertical, Trash } from '../../icons';

import { FilterBuilder, FilterConfig, FilterCondition, FilterGroup } from '../Filters/FilterBuilder';

export interface Column<T> {
  key: string;
  label: string;
  sortable?: boolean;
  render?: (item: T) => React.ReactNode;
  size?: 'small' | 'medium' | 'large';
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  loading?: boolean;
  pagination?: {
    page: number;
    pageSize: number;
    total: number;
    onPageChange: (page: number) => void;
    onPageSizeChange: (size: number) => void;
  };
  filters?: {
    configs: FilterConfig[];
    current: FilterGroup;
    onChange: (filters: FilterGroup) => void;
    quickFilters?: { label: string; filters: FilterCondition[] }[];
  };
  onRowClick?: (item: T) => void;
  actions?: {
    onView?: (item: T) => void;
    onEdit?: (item: T) => void;
    onDelete?: (item: T) => void;
    custom?: Array<{
      label: string;
      icon?: React.ReactNode;
      onClick: (item: T) => void;
      color?: 'default' | 'primary' | 'success' | 'warning' | 'danger';
    }>;
  };
  selectable?: boolean;
  onSelectionChange?: (keys: Set<string>) => void;
  emptyMessage?: string;
}

const HeroTable = Table as any;
const HeroTableBody = TableBody as any;
const HeroTableCell = TableCell as any;
const HeroTableColumn = TableColumn as any;
const HeroTableHeader = TableHeader as any;
const HeroTableRow = TableRow as any;
const HeroDropdown = Dropdown as any;
const HeroDropdownTrigger = DropdownTrigger as any;
const HeroDropdownMenu = DropdownMenu as any;
const HeroDropdownItem = DropdownItem as any;
const HeroSelect = Select as any;
const HeroSelectItem = SelectItem as any;

export function DataTable<T extends { id: string | number }>(
  {
    columns,
    data,
    loading = false,
    pagination,
    filters,
    onRowClick,
    actions,
    selectable = false,
    onSelectionChange,
    emptyMessage = 'Nenhum registro encontrado',
  }: DataTableProps<T>,
) {
  const [sortDescriptor, setSortDescriptor] = useState<{
    column: string;
    direction: 'ascending' | 'descending';
  }>();
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());

  const handleSelectionChange = (keys: Selection) => {
    const normalized = new Set(Array.from(keys).map(String));
    setSelectedKeys(normalized);
    onSelectionChange?.(normalized);
  };

  const sortedData = useMemo(() => {
    if (!sortDescriptor) return data;

    return [...data].sort((a, b) => {
      const first = a[sortDescriptor.column as keyof T];
      const second = b[sortDescriptor.column as keyof T];

      const comparison = first < second ? -1 : first > second ? 1 : 0;
      return sortDescriptor.direction === 'descending' ? -comparison : comparison;
    });
  }, [data, sortDescriptor]);

  const renderCell = (item: T, column: Column<T>) => {
    if (column.render) {
      return column.render(item);
    }

    const value = item[column.key as keyof T];

    if (value === null || value === undefined) {
      return <span className="text-default-400">—</span>;
    }

    if (typeof value === 'boolean') {
      return (
        <Chip color={value ? 'success' : 'default'} variant="flat" size="sm">
          {value ? 'Sim' : 'Não'}
        </Chip>
      );
    }

    if (value instanceof Date) {
      return new Intl.DateTimeFormat('pt-BR').format(value);
    }

    return String(value);
  };

  const renderActions = (item: T) => {
    if (!actions) return null;

    return (
      <HeroDropdown>
        <HeroDropdownTrigger>
          <button className="rounded-lg p-1 transition-colors hover:bg-default-100">
            <MoreVertical className="h-4 w-4" />
          </button>
        </HeroDropdownTrigger>
        <HeroDropdownMenu aria-label="Ações">
          {actions.onView && (
            <HeroDropdownItem
              key="view"
              startContent={<Eye className="h-4 w-4" />}
              onClick={() => actions.onView?.(item)}
            >
              Visualizar
            </HeroDropdownItem>
          )}
          {actions.onEdit && (
            <HeroDropdownItem
              key="edit"
              startContent={<Edit className="h-4 w-4" />}
              onClick={() => actions.onEdit?.(item)}
            >
              Editar
            </HeroDropdownItem>
          )}
          {actions.onDelete && (
            <HeroDropdownItem
              key="delete"
              color="danger"
              startContent={<Trash className="h-4 w-4" />}
              onClick={() => actions.onDelete?.(item)}
            >
              Excluir
            </HeroDropdownItem>
          )}
          {actions.custom?.map((action, index) => (
            <HeroDropdownItem
              key={`custom-${index}`}
              color={action.color}
              startContent={action.icon}
              onClick={() => action.onClick(item)}
            >
              {action.label}
            </HeroDropdownItem>
          ))}
        </HeroDropdownMenu>
      </HeroDropdown>
    );
  };

  return (
    <div className="space-y-4">
      {filters && (
        <FilterBuilder
          configs={filters.configs}
          filters={filters.current}
          onFiltersChange={filters.onChange}
          quickFilters={filters.quickFilters}
        />
      )}

      <div className="overflow-x-auto">
        <HeroTable
          aria-label="Data table"
          sortDescriptor={sortDescriptor as any}
          onSortChange={(descriptor: any) => setSortDescriptor(descriptor)}
          selectionMode={selectable ? 'multiple' : undefined}
          selectedKeys={selectedKeys}
          onSelectionChange={(keys: Selection) => handleSelectionChange(keys)}
          classNames={{
            wrapper: 'max-h-[600px]',
            th: 'bg-default-100 text-default-600 font-semibold',
          }}
        >
          <HeroTableHeader>
            {columns.map((column) => (
              <HeroTableColumn key={column.key} allowsSorting={column.sortable} width={column.size}>
                {column.label}
              </HeroTableColumn>
            ))}
            {actions && (
              <HeroTableColumn key="actions" width="small">
                Ações
              </HeroTableColumn>
            )}
          </HeroTableHeader>
          <HeroTableBody
            items={sortedData}
            emptyContent={loading ? <Spinner /> : emptyMessage}
            loadingContent={<Spinner />}
            loadingState={loading ? 'loading' : 'idle'}
          >
            {(item: T) => (
              <HeroTableRow
                key={(item as any).id}
                className={onRowClick ? 'cursor-pointer hover:bg-default-50' : ''}
                onClick={() => onRowClick?.(item)}
              >
                {(columnKey: React.Key) => (
                  <HeroTableCell>
                    {columnKey === 'actions'
                      ? renderActions(item)
                      : renderCell(item, columns.find((column) => column.key === columnKey)!)}
                  </HeroTableCell>
                )}
              </HeroTableRow>
            )}
          </HeroTableBody>
        </HeroTable>
      </div>

      {pagination && (
        <div className="flex items-center justify-between px-2">
          <div className="flex items-center gap-2">
            <span className="text-small text-default-400">
              Mostrando {((pagination.page - 1) * pagination.pageSize) + 1} a{' '}
              {Math.min(pagination.page * pagination.pageSize, pagination.total)} de {pagination.total} registros
            </span>
            <HeroSelect
              size="sm"
              selectedKeys={new Set([String(pagination.pageSize)])}
              onSelectionChange={(keys: Selection) =>
                pagination.onPageSizeChange(Number(Array.from(keys)[0]))
              }
              className="w-20"
            >
              {[10, 25, 50, 100].map((option) => (
                <HeroSelectItem key={option}>{option}</HeroSelectItem>
              ))}
            </HeroSelect>
          </div>
          <Pagination
            total={Math.ceil(pagination.total / pagination.pageSize)}
            page={pagination.page}
            onChange={pagination.onPageChange}
            showControls
            boundaries={1}
            siblings={1}
          />
        </div>
      )}
    </div>
  );
}
