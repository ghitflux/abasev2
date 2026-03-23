"use client";

import * as React from "react";
import { format, isValid, parse } from "date-fns";
import { ptBR } from "date-fns/locale";
import { CalendarDaysIcon } from "lucide-react";

import { maskMonthYear } from "@/lib/masks";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

type CalendarCompetenciaProps = {
  value?: Date;
  onChange?: (value: Date) => void;
  className?: string;
  disabled?: boolean;
};

const COMPETENCIA_INPUT_REGEX = /^\d{2}\/\d{4}$/;

function normalizeMonth(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), 1);
}

function formatCompetencia(value?: Date) {
  return value ? format(normalizeMonth(value), "MM/yyyy") : "";
}

function parseCompetencia(value: string) {
  if (!COMPETENCIA_INPUT_REGEX.test(value.trim())) {
    return null;
  }

  const parsed = parse(`01/${value}`, "dd/MM/yyyy", new Date(), { locale: ptBR });
  if (!isValid(parsed)) {
    return null;
  }

  return normalizeMonth(parsed);
}

export default function CalendarCompetencia({
  value,
  onChange,
  className,
  disabled,
}: CalendarCompetenciaProps) {
  const [open, setOpen] = React.useState(false);
  const [inputValue, setInputValue] = React.useState(formatCompetencia(value));
  const [displayMonth, setDisplayMonth] = React.useState(
    value ? normalizeMonth(value) : normalizeMonth(new Date()),
  );

  React.useEffect(() => {
    if (value) {
      const normalized = normalizeMonth(value);
      setInputValue(formatCompetencia(normalized));
      setDisplayMonth(normalized);
      return;
    }

    setInputValue("");
  }, [value]);

  const handleInputChange = (nextValue: string) => {
    const maskedValue = maskMonthYear(nextValue);
    setInputValue(maskedValue);

    const parsed = parseCompetencia(maskedValue);
    if (parsed) {
      setDisplayMonth(parsed);
      onChange?.(parsed);
    }
  };

  const handleInputBlur = () => {
    if (!inputValue.trim()) {
      setInputValue("");
      return;
    }

    const parsed = parseCompetencia(inputValue);
    if (!parsed) {
      setInputValue(formatCompetencia(value));
      return;
    }

    setInputValue(formatCompetencia(parsed));
    setDisplayMonth(parsed);
    onChange?.(parsed);
  };

  return (
    <div className={className ?? "w-full"}>
      <Popover open={open} onOpenChange={setOpen}>
        <InputGroup className="h-11 rounded-xl border-border/60 bg-card/60">
          <InputGroupInput
            value={inputValue}
            onChange={(event) => handleInputChange(event.target.value)}
            onBlur={handleInputBlur}
            placeholder="mm/aaaa"
            disabled={disabled}
            className="h-11 px-3 font-medium"
          />
          <InputGroupAddon align="inline-end">
            <PopoverTrigger asChild>
              <InputGroupButton
                variant="ghost"
                size="icon-sm"
                disabled={disabled}
                aria-label="Abrir calendário"
              >
                <CalendarDaysIcon className="size-4 text-muted-foreground" />
              </InputGroupButton>
            </PopoverTrigger>
          </InputGroupAddon>
        </InputGroup>
        <PopoverContent className="w-auto rounded-2xl border-border/60 p-0">
          <Calendar
            mode="single"
            month={displayMonth}
            selected={value}
            onMonthChange={(month) => setDisplayMonth(normalizeMonth(month))}
            onSelect={(date) => {
              if (!date) return;
              const normalized = normalizeMonth(date);
              setDisplayMonth(normalized);
              setInputValue(formatCompetencia(normalized));
              onChange?.(normalized);
              setOpen(false);
            }}
            locale={ptBR}
            captionLayout="dropdown"
            startMonth={new Date(2000, 0, 1)}
            endMonth={new Date(new Date().getFullYear() + 20, 11, 1)}
            initialFocus
          />
          <div className="border-t border-border/60 p-3">
            <Button
              type="button"
              variant="outline"
              className="w-full rounded-xl"
              onClick={() => {
                const normalized = normalizeMonth(displayMonth);
                setInputValue(formatCompetencia(normalized));
                onChange?.(normalized);
                setOpen(false);
              }}
            >
              Usar {format(displayMonth, "MM/yyyy")}
            </Button>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}
