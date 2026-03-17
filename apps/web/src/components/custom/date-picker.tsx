"use client";

import * as React from "react";
import { format, isValid, parse } from "date-fns";
import { ptBR } from "date-fns/locale";
import { CalendarIcon } from "lucide-react";

import { maskDate } from "@/lib/masks";
import { cn } from "@/lib/utils";
import { Calendar } from "@/components/ui/calendar";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

type DatePickerProps = {
  value?: Date;
  onChange?: (date?: Date) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
};

const DATE_INPUT_FORMAT = "dd/MM/yyyy";
const DATE_INPUT_REGEX = /^\d{2}\/\d{2}\/\d{4}$/;

function formatInputValue(value?: Date) {
  return value ? format(value, DATE_INPUT_FORMAT) : "";
}

function parseInputValue(value: string) {
  if (!DATE_INPUT_REGEX.test(value.trim())) {
    return null;
  }

  const parsed = parse(value, DATE_INPUT_FORMAT, new Date(), { locale: ptBR });
  if (!isValid(parsed)) {
    return null;
  }

  return new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate());
}

export default function DatePicker({
  value,
  onChange,
  placeholder = "dd/mm/aaaa",
  disabled,
  className,
}: DatePickerProps) {
  const [open, setOpen] = React.useState(false);
  const [inputValue, setInputValue] = React.useState(formatInputValue(value));

  React.useEffect(() => {
    setInputValue(formatInputValue(value));
  }, [value]);

  const handleInputChange = (nextValue: string) => {
    const maskedValue = maskDate(nextValue);
    setInputValue(maskedValue);

    if (!maskedValue.trim()) {
      onChange?.(undefined);
      return;
    }

    const parsed = parseInputValue(maskedValue);
    if (parsed) {
      onChange?.(parsed);
    }
  };

  const handleInputBlur = () => {
    if (!inputValue.trim()) {
      setInputValue("");
      onChange?.(undefined);
      return;
    }

    const parsed = parseInputValue(inputValue);
    if (!parsed) {
      setInputValue(formatInputValue(value));
      return;
    }

    setInputValue(formatInputValue(parsed));
    onChange?.(parsed);
  };

  return (
    <div className={cn("w-full", className)}>
      <Popover open={open} onOpenChange={setOpen}>
        <InputGroup className="h-11 rounded-xl border-border/60 bg-card/60">
          <InputGroupInput
            value={inputValue}
            onChange={(event) => handleInputChange(event.target.value)}
            onBlur={handleInputBlur}
            placeholder={placeholder}
            disabled={disabled}
            className={cn("h-11 px-3 font-medium", !inputValue && "text-muted-foreground")}
          />
          <InputGroupAddon align="inline-end">
            <PopoverTrigger asChild>
              <InputGroupButton
                variant="ghost"
                size="icon-sm"
                disabled={disabled}
                aria-label="Abrir calendário"
              >
                <CalendarIcon className="size-4 text-muted-foreground" />
              </InputGroupButton>
            </PopoverTrigger>
          </InputGroupAddon>
        </InputGroup>
        <PopoverContent className="w-auto rounded-2xl border-border/60 p-0">
          <Calendar
            mode="single"
            selected={value}
            onSelect={(date) => {
              onChange?.(date);
              setInputValue(formatInputValue(date));
              setOpen(false);
            }}
            locale={ptBR}
            captionLayout="dropdown"
            startMonth={new Date(1900, 0, 1)}
            endMonth={new Date(new Date().getFullYear() + 20, 11, 31)}
            initialFocus
          />
        </PopoverContent>
      </Popover>
    </div>
  );
}
