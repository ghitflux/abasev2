import React, { useCallback, useMemo, useState } from 'react';
import {
  Chip,
  DatePicker,
  Drawer,
  DrawerBody,
  DrawerContent,
  DrawerFooter,
  DrawerHeader,
  Input,
  Select,
  SelectItem,
} from '@heroui/react';
import { Filter as FilterIcon, Plus, Search, X } from '../../icons';
import { z } from 'zod';

import { Button } from '../Button';

export type FilterOperator =
  | 'eq'
  | 'ne'
  | 'in'
  | 'nin'
  | 'gt'
  | 'gte'
  | 'lt'
  | 'lte'
  | 'between'
  | 'ilike'
  | 'isnull';

export interface FilterCondition {
  field: string;
  operator: FilterOperator;
  value: unknown;
  label?: string;
}

export interface FilterGroup {
  type: 'AND' | 'OR';
  conditions: FilterCondition[];
}

export interface FilterConfig {
  field: string;
  label: string;
  type: 'text' | 'number' | 'date' | 'select' | 'multiselect' | 'boolean';
  operators?: FilterOperator[];
  options?: { value: string; label: string }[];
  placeholder?: string;
  validation?: z.ZodSchema;
}

interface FilterBuilderProps {
  configs: FilterConfig[];
  filters: FilterGroup;
  onFiltersChange: (filters: FilterGroup) => void;
  quickFilters?: { label: string; filters: FilterCondition[] }[];
  onSearch?: (query: string) => void;
}

const HeroSelect = Select as any;
const HeroSelectItem = SelectItem as any;

export const FilterBuilder: React.FC<FilterBuilderProps> = ({
  configs,
  filters,
  onFiltersChange,
  quickFilters,
  onSearch,
}) => {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [tempFilters, setTempFilters] = useState<FilterGroup>(filters);

  const defaultField = useMemo(() => configs[0]?.field ?? '', [configs]);

  const getOperatorsForType = useCallback((type: FilterConfig['type']): FilterOperator[] => {
    switch (type) {
      case 'text':
        return ['eq', 'ne', 'ilike', 'isnull'];
      case 'number':
        return ['eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'between', 'isnull'];
      case 'date':
        return ['eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'between', 'isnull'];
      case 'select':
        return ['eq', 'ne', 'isnull'];
      case 'multiselect':
        return ['in', 'nin'];
      case 'boolean':
        return ['eq'];
      default:
        return ['eq'];
    }
  }, []);

  const addCondition = useCallback(() => {
    const next: FilterCondition = {
      field: defaultField,
      operator: 'eq',
      value: null,
    };

    setTempFilters((prev) => ({
      ...prev,
      conditions: [...prev.conditions, next],
    }));
  }, [defaultField]);

  const removeCondition = useCallback((index: number) => {
    setTempFilters((prev) => ({
      ...prev,
      conditions: prev.conditions.filter((_, i) => i !== index),
    }));
  }, []);

  const updateCondition = useCallback(
    (index: number, update: Partial<FilterCondition>) => {
      setTempFilters((prev) => {
        const conditions = [...prev.conditions];
        conditions[index] = { ...conditions[index], ...update };
        return { ...prev, conditions };
      });
    },
    [],
  );

  const applyFilters = useCallback(() => {
    onFiltersChange(tempFilters);
    setIsDrawerOpen(false);
  }, [onFiltersChange, tempFilters]);

  const clearFilters = useCallback(() => {
    const empty: FilterGroup = { type: 'AND', conditions: [] };
    setTempFilters(empty);
    onFiltersChange(empty);
  }, [onFiltersChange]);

  const applyQuickFilter = useCallback(
    (conditions: FilterCondition[]) => {
      const next: FilterGroup = { type: 'AND', conditions };
      setTempFilters(next);
      onFiltersChange(next);
    },
    [onFiltersChange],
  );

  const handleSearch = useCallback(
    (query: string) => {
      setSearchQuery(query);
      onSearch?.(query);
    },
    [onSearch],
  );

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Input
          placeholder="Buscar..."
          value={searchQuery}
          onChange={(event) => handleSearch(event.target.value)}
          startContent={<Search className="h-4 w-4 text-default-400" />}
          className="flex-1"
        />
        <Button
          color="primary"
          variant="flat"
          onPress={() => setIsDrawerOpen(true)}
          leftIcon={<FilterIcon className="h-4 w-4" />}
        >
          Filtros Avançados
          {filters.conditions.length > 0 && (
            <Chip size="sm" color="primary" className="ml-2">
              {filters.conditions.length}
            </Chip>
          )}
        </Button>
      </div>

      {quickFilters && quickFilters.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {quickFilters.map((quickFilter, index) => (
            <Chip
              key={index}
              variant="flat"
              onClick={() => applyQuickFilter(quickFilter.filters)}
              className="cursor-pointer hover:opacity-80"
            >
              {quickFilter.label}
            </Chip>
          ))}
        </div>
      )}

      {filters.conditions.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {filters.conditions.map((condition, index) => {
            const config = configs.find((cfg) => cfg.field === condition.field);
            return (
              <Chip
                key={`${condition.field}-${index}`}
                variant="flat"
                color="primary"
                onClose={() => {
                  const nextConditions = filters.conditions.filter((_, i) => i !== index);
                  onFiltersChange({ ...filters, conditions: nextConditions });
                }}
              >
                {config?.label ?? condition.field}: {getOperatorLabel(condition.operator)}{' '}
                {formatConditionValue(condition.value)}
              </Chip>
            );
          })}
          <button onClick={clearFilters} className="text-xs text-default-500 hover:text-default-700">
            Limpar todos
          </button>
        </div>
      )}

      <Drawer isOpen={isDrawerOpen} onOpenChange={setIsDrawerOpen} placement="right" size="md">
        <DrawerContent>
          <DrawerHeader className="flex flex-col gap-1">
            <h3 className="text-lg font-semibold">Filtros Avançados</h3>
            <p className="text-sm text-default-500">Combine filtros para refinar os resultados.</p>
          </DrawerHeader>
          <DrawerBody className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-default-600">Lógica:</span>
              <select
                className="rounded-md border border-default-200 px-3 py-2 text-sm"
                value={tempFilters.type}
                onChange={(event) =>
                  setTempFilters({ ...tempFilters, type: event.target.value as 'AND' | 'OR' })
                }
              >
                <option value="AND">E</option>
                <option value="OR">OU</option>
              </select>
            </div>

            <div className="space-y-3">
              {tempFilters.conditions.map((condition, index) => {
                const config =
                  configs.find((cfg) => cfg.field === condition.field) ?? configs[0];
                const availableOperators = config?.operators ?? getOperatorsForType(config?.type || 'text');

                return (
                  <div key={`${condition.field}-${index}`} className="flex items-start gap-2">
                    <HeroSelect
                      aria-label="Campo do filtro"
                      selectedKeys={new Set([condition.field])}
                      onSelectionChange={(keys: any) =>
                        updateCondition(index, { field: Array.from(keys)[0] as string })
                      }
                      className="w-40"
                    >
                      {configs.map((cfg) => (
                        <HeroSelectItem key={cfg.field}>{cfg.label}</HeroSelectItem>
                      ))}
                    </HeroSelect>

                    <HeroSelect
                      aria-label="Operador do filtro"
                      selectedKeys={new Set([condition.operator])}
                      onSelectionChange={(keys: any) =>
                        updateCondition(index, {
                          operator: Array.from(keys)[0] as FilterOperator,
                        })
                      }
                      className="w-32"
                    >
                      {availableOperators.map((operator) => (
                        <HeroSelectItem key={operator}>{getOperatorLabel(operator)}</HeroSelectItem>
                      ))}
                    </HeroSelect>

                    <div className="flex-1">
                      {renderValueInput(config, condition, (value) => updateCondition(index, { value }))}
                    </div>

                    <button
                      onClick={() => removeCondition(index)}
                      className="rounded-lg p-2 hover:bg-default-100"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                );
              })}
            </div>

            <Button
              variant="flat"
              onPress={addCondition}
              leftIcon={<Plus className="h-4 w-4" />}
              className="w-full"
            >
              Adicionar Condição
            </Button>
          </DrawerBody>
          <DrawerFooter>
            <Button variant="flat" onPress={() => setIsDrawerOpen(false)}>
              Cancelar
            </Button>
            <Button color="primary" onPress={applyFilters}>
              Aplicar Filtros
            </Button>
          </DrawerFooter>
        </DrawerContent>
      </Drawer>
    </div>
  );
};

function renderValueInput(
  config: FilterConfig | undefined,
  condition: FilterCondition,
  onChange: (value: unknown) => void,
) {
  if (!config) return null;

  switch (config.type) {
    case 'text':
      return (
        <Input
          value={(condition.value as string) ?? ''}
          onChange={(event) => onChange(event.target.value)}
          placeholder={config.placeholder}
        />
      );

    case 'number':
      if (condition.operator === 'between') {
        const [from = '', to = ''] = (condition.value as [string, string]) ?? [];
        return (
          <div className="flex gap-2">
            <Input
              type="number"
              value={from}
              onChange={(event) => onChange([event.target.value, to])}
              placeholder="De"
            />
            <Input
              type="number"
              value={to}
              onChange={(event) => onChange([from, event.target.value])}
              placeholder="Até"
            />
          </div>
        );
      }
      return (
        <Input
          type="number"
          value={(condition.value as string) ?? ''}
          onChange={(event) => onChange(event.target.value)}
          placeholder={config.placeholder}
        />
      );

    case 'date':
      if (condition.operator === 'between') {
        const [startValue, endValue] = (condition.value as [Date | null, Date | null]) ?? [null, null];
        return (
          <div className="flex gap-2">
            <DatePicker
              label="Data inicial"
              value={startValue as any}
              onChange={(value) => onChange([value, endValue])}
            />
            <DatePicker
              label="Data final"
              value={endValue as any}
              onChange={(value) => onChange([startValue, value])}
            />
          </div>
        );
      }
      return (
        <DatePicker
          label={config.placeholder}
          value={(condition.value as Date) as any}
          onChange={(value) => onChange(value)}
        />
      );

    case 'select':
      return (
        <HeroSelect
          selectedKeys={new Set([String(condition.value ?? '')])}
          onSelectionChange={(keys: any) => {
            const value = Array.from(keys)[0];
            onChange(value === '__empty' ? '' : value ?? '');
          }}
        >
          <HeroSelectItem key="__empty">Selecione...</HeroSelectItem>
          {(config.options?.map((option) => (
            <HeroSelectItem key={option.value}>{option.label}</HeroSelectItem>
          )) ?? null)}
        </HeroSelect>
      );

    case 'multiselect':
      return (
        <HeroSelect
          selectionMode="multiple"
          selectedKeys={new Set((condition.value as string[]) ?? [])}
          onSelectionChange={(keys: any) => onChange(Array.from(keys) as string[])}
        >
          {(config.options?.map((option) => (
            <HeroSelectItem key={option.value}>{option.label}</HeroSelectItem>
          )) ?? null)}
        </HeroSelect>
      );

    case 'boolean':
      return (
        <HeroSelect
          selectedKeys={new Set([String(condition.value ?? 'false')])}
          onSelectionChange={(keys: any) => onChange(Array.from(keys)[0] === 'true')}
        >
          <HeroSelectItem key="true">Sim</HeroSelectItem>
          <HeroSelectItem key="false">Não</HeroSelectItem>
        </HeroSelect>
      );

    default:
      return null;
  }
}

function getOperatorLabel(operator: FilterOperator): string {
  const labels: Record<FilterOperator, string> = {
    eq: 'Igual a',
    ne: 'Diferente de',
    in: 'Está em',
    nin: 'Não está em',
    gt: 'Maior que',
    gte: 'Maior ou igual',
    lt: 'Menor que',
    lte: 'Menor ou igual',
    between: 'Entre',
    ilike: 'Contém',
    isnull: 'É nulo',
  };

  return labels[operator] ?? operator;
}

function formatConditionValue(value: unknown): string {
  if (value === null || value === undefined) return '—';

  if (Array.isArray(value)) {
    return value.filter(Boolean).join(' ~ ');
  }

  if (value instanceof Date) {
    return new Intl.DateTimeFormat('pt-BR').format(value);
  }

  return String(value);
}
