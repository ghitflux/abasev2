"use client";

import React, { useEffect, useMemo, useState } from "react";
import { DataTable, FilterConfig, FilterCondition, FilterGroup, useToast } from '@abase/ui';
import { Button } from '@heroui/react';

type Company = {
  id: string;
  name: string;
  status: 'Ativo' | 'Inativo';
  owner: string;
  createdAt: Date;
};

const companies: Company[] = [
  { id: '1', name: 'Abase LTDA', status: 'Ativo', owner: 'Ana Lima', createdAt: new Date('2024-01-12') },
  { id: '2', name: 'Fluxo Digital', status: 'Ativo', owner: 'Carlos Silva', createdAt: new Date('2024-02-02') },
  { id: '3', name: 'VisionX', status: 'Inativo', owner: 'Beatriz Melo', createdAt: new Date('2023-11-23') },
];

export default function HomePage() {
  const { addToast } = useToast();
  const [filters, setFilters] = useState<FilterGroup>({ type: "AND", conditions: [] });
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  const filterConfigs: FilterConfig[] = useMemo(
    () => [
      {
        field: "name",
        label: "Empresa",
        type: "text",
        placeholder: "Nome da empresa",
      },
      {
        field: "status",
        label: "Status",
        type: "select",
        options: [
          { value: "Ativo", label: "Ativo" },
          { value: "Inativo", label: "Inativo" },
        ],
      },
      {
        field: "createdAt",
        label: "Data de criação",
        type: "date",
      },
    ],
    [],
  );

  const filteredData = useMemo(() => {
    if (filters.conditions.length === 0) return companies;

    return companies.filter((company) => {
      return filters.conditions.every((condition) => {
        if (condition.field === "status") {
          return company.status === condition.value;
        }
        if (condition.field === "name") {
          return new RegExp(String(condition.value), 'i').test(company.name);
        }
        if (condition.field === "createdAt" && condition.value instanceof Date) {
          return company.createdAt.toDateString() === condition.value.toDateString();
        }
        return true;
      });
    });
  }, [filters]);

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-8 px-6 py-10">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold">ABASE Manager v2</h1>
        <p className="text-default-500">
          Foundation pronta com Design System moderno, componentes reutilizáveis e infraestrutura integrada.
        </p>
      </header>

      <section className="flex flex-wrap gap-3">
        <Button
          color="primary"
          onPress={() => {
            addToast({
              type: "success",
              title: "Pronto para evoluir",
              description: "Design system inicial configurado com HeroUI + Tailwind.",
            });
          }}
        >
          Mostrar Toast
        </Button>
        <Button
          variant="bordered"
          onPress={() => {
            addToast({
              type: "info",
              title: "Atualização",
              description: "Bloco 1 finalizado com componentes base e Storybook prontos.",
            });
          }}
        >
          Overview do Bloco
        </Button>
      </section>

      <section className="rounded-2xl border border-default-200 bg-content1 p-6 shadow-sm">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold">Empresas em destaque</h2>
            <p className="text-sm text-default-500">Demonstração de DataTable com filtros integrados.</p>
          </div>
        </header>

        {isClient ? (
          <DataTable<Company>
            columns={[
              { key: "name", label: "Empresa", sortable: true },
              { key: "owner", label: "Responsável", sortable: true },
              { key: "status", label: "Status", sortable: true },
              { key: "createdAt", label: "Criado em", sortable: true },
            ]}
            data={filteredData}
            filters={{
              configs: filterConfigs,
              current: filters,
              onChange: setFilters,
              quickFilters: [
                {
                  label: "Só Ativos",
                  filters: [{ field: "status", operator: "eq", value: "Ativo" } as FilterCondition],
                },
              ],
            }}
          />
        ) : null}
      </section>
    </main>
  );
}
