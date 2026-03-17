"use client";

import * as React from "react";
import { SlidersHorizontalIcon } from "lucide-react";
import type { DateRange } from "react-day-picker";

import DateRangePicker from "@/components/custom/date-range-picker";
import MultiSelect from "@/components/custom/multi-select";
import SearchableSelect from "@/components/custom/searchable-select";
import { Button } from "@/components/ui/button";
import { Field, FieldContent, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

type FilterAdvancedProps = {
  statusOptions: Array<{ value: string; label: string }>;
  roleOptions: Array<{ value: string; label: string }>;
  onApply?: (filters: { statuses: string[]; role?: string; dateRange?: DateRange }) => void;
};

export default function FilterAdvanced({
  statusOptions,
  roleOptions,
  onApply,
}: FilterAdvancedProps) {
  const [statuses, setStatuses] = React.useState<string[]>([]);
  const [role, setRole] = React.useState<string | undefined>();
  const [dateRange, setDateRange] = React.useState<DateRange | undefined>();

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline" className="rounded-2xl">
          <SlidersHorizontalIcon className="size-4" />
          Filtros avançados
        </Button>
      </SheetTrigger>
      <SheetContent className="glass-panel w-full border-l border-border/60 sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Filtros avançados</SheetTitle>
        </SheetHeader>
        <div className="mt-8 space-y-6">
          <FieldGroup>
            <Field>
              <FieldLabel>Status</FieldLabel>
              <FieldContent>
                <MultiSelect options={statusOptions} value={statuses} onChange={setStatuses} />
              </FieldContent>
            </Field>
            <Field>
              <FieldLabel>Role</FieldLabel>
              <FieldContent>
                <SearchableSelect options={roleOptions} value={role} onChange={setRole} placeholder="Todos os papéis" />
              </FieldContent>
            </Field>
            <Field>
              <FieldLabel>Período</FieldLabel>
              <FieldContent>
                <DateRangePicker value={dateRange} onChange={setDateRange} />
              </FieldContent>
            </Field>
          </FieldGroup>
          <Button className="w-full rounded-2xl" onClick={() => onApply?.({ statuses, role, dateRange })}>
            Aplicar filtros
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
