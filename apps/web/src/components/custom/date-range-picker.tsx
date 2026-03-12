"use client";

import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { CalendarRange } from "lucide-react";
import type { DateRange } from "react-day-picker";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

type DateRangePickerProps = {
  value?: DateRange;
  onChange?: (value?: DateRange) => void;
  placeholder?: string;
  numberOfMonths?: number;
  className?: string;
};

export default function DateRangePicker({
  value,
  onChange,
  placeholder = "Selecione um período",
  numberOfMonths = 2,
  className,
}: DateRangePickerProps) {
  const label =
    value?.from && value?.to
      ? `${format(value.from, "dd/MM/yyyy")} - ${format(value.to, "dd/MM/yyyy")}`
      : value?.from
        ? `${format(value.from, "dd/MM/yyyy")} - ...`
        : placeholder;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className={cn(
            "w-full justify-between rounded-xl border-border/60 bg-card/60 text-left font-medium",
            !value?.from && "text-muted-foreground",
            className,
          )}
        >
          {label}
          <CalendarRange className="size-4 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto rounded-2xl border-border/60 p-0">
        <Calendar
          mode="range"
          locale={ptBR}
          selected={value}
          onSelect={onChange}
          numberOfMonths={numberOfMonths}
          initialFocus
        />
      </PopoverContent>
    </Popover>
  );
}
