"use client";

import * as React from "react";
import { Clock3Icon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";

type TimePickerProps = {
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
};

const HOURS = Array.from({ length: 24 }, (_, index) => index);
const MINUTES = Array.from({ length: 60 }, (_, index) => index);

function formatTime(value = "") {
  const digits = value.replace(/\D/g, "").slice(0, 4);
  if (digits.length <= 2) return digits;
  return `${digits.slice(0, 2)}:${digits.slice(2)}`;
}

function isValidTime(value = "") {
  if (!/^\d{2}:\d{2}$/.test(value)) return false;
  const [hours, minutes] = value.split(":").map(Number);
  return hours >= 0 && hours <= 23 && minutes >= 0 && minutes <= 59;
}

function padTimePart(value: number) {
  return String(value).padStart(2, "0");
}

function toTimeValue(hours: number, minutes: number) {
  return `${padTimePart(hours)}:${padTimePart(minutes)}`;
}

function resolveTimeParts(value = "") {
  if (isValidTime(value)) {
    const [hours, minutes] = value.split(":").map(Number);
    return { hours, minutes };
  }

  const now = new Date();
  return { hours: now.getHours(), minutes: now.getMinutes() };
}

type TimeColumnProps = {
  label: string;
  values: number[];
  selected: number;
  onSelect: (value: number) => void;
};

function TimeColumn({ label, values, selected, onSelect }: TimeColumnProps) {
  return (
    <div className="min-w-0">
      <div className="border-b border-border/60 px-3 py-2 text-xs font-medium uppercase tracking-[0.22em] text-muted-foreground">
        {label}
      </div>
      <ScrollArea className="h-56">
        <div className="space-y-1 p-2">
          {values.map((value) => {
            const active = value === selected;
            return (
              <button
                key={value}
                type="button"
                onClick={() => onSelect(value)}
                className={cn(
                  "w-full rounded-lg px-3 py-2 text-left text-sm font-medium tabular-nums transition-colors",
                  active
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-accent/70 hover:text-accent-foreground",
                )}
              >
                {padTimePart(value)}
              </button>
            );
          })}
        </div>
      </ScrollArea>
    </div>
  );
}

export default function TimePicker({
  value = "",
  onChange,
  placeholder = "00:00",
  className,
  disabled,
}: TimePickerProps) {
  const [open, setOpen] = React.useState(false);
  const [internalValue, setInternalValue] = React.useState(formatTime(value));
  const timeParts = resolveTimeParts(internalValue);

  React.useEffect(() => {
    setInternalValue(formatTime(value));
  }, [value]);

  const commitTime = (nextHours: number, nextMinutes: number, close = false) => {
    const nextValue = toTimeValue(nextHours, nextMinutes);
    setInternalValue(nextValue);
    onChange?.(nextValue);
    if (close) {
      setOpen(false);
    }
  };

  return (
    <div className={cn("w-full", className)}>
      <Popover open={open} onOpenChange={setOpen}>
        <InputGroup className="h-11 rounded-xl border-border/60 bg-card/60">
          <InputGroupInput
            value={internalValue}
            placeholder={placeholder}
            disabled={disabled}
            className="h-11 px-3 font-medium tabular-nums"
            inputMode="numeric"
            maxLength={5}
            aria-invalid={Boolean(internalValue) && !isValidTime(internalValue)}
            onChange={(event) => {
              const nextValue = formatTime(event.target.value);
              setInternalValue(nextValue);
              onChange?.(nextValue);
            }}
            onBlur={() => {
              if (!internalValue.trim()) {
                onChange?.("");
                return;
              }

              if (!isValidTime(internalValue)) {
                const fallbackValue = isValidTime(formatTime(value))
                  ? formatTime(value)
                  : "";
                setInternalValue(fallbackValue);
                onChange?.(fallbackValue);
              }
            }}
          />
          <InputGroupAddon align="inline-end">
            <PopoverTrigger asChild>
              <InputGroupButton
                variant="ghost"
                size="icon-sm"
                disabled={disabled}
                aria-label="Selecionar horário"
              >
                <Clock3Icon className="size-4 text-muted-foreground" />
              </InputGroupButton>
            </PopoverTrigger>
          </InputGroupAddon>
        </InputGroup>
        <PopoverContent className="w-[18rem] rounded-2xl border-border/60 p-0">
          <div className="grid grid-cols-2 divide-x divide-border/60">
            <TimeColumn
              label="Hora"
              values={HOURS}
              selected={timeParts.hours}
              onSelect={(nextHours) => commitTime(nextHours, timeParts.minutes)}
            />
            <TimeColumn
              label="Minuto"
              values={MINUTES}
              selected={timeParts.minutes}
              onSelect={(nextMinutes) =>
                commitTime(timeParts.hours, nextMinutes, true)
              }
            />
          </div>
          <div className="flex gap-2 border-t border-border/60 p-3">
            <Button
              type="button"
              variant="outline"
              className="flex-1 rounded-xl"
              onClick={() => {
                const now = new Date();
                commitTime(now.getHours(), now.getMinutes(), true);
              }}
            >
              Agora
            </Button>
            <Button
              type="button"
              variant="outline"
              className="rounded-xl"
              onClick={() => {
                setInternalValue("");
                onChange?.("");
                setOpen(false);
              }}
            >
              Limpar
            </Button>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}
