"use client";

import { CheckIcon, ChevronsUpDownIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export type SelectOption = {
  value: string;
  label: string;
};

type SearchableSelectProps = {
  options: SelectOption[];
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyLabel?: string;
  className?: string;
};

export default function SearchableSelect({
  options,
  value,
  onChange,
  placeholder = "Selecione uma opção",
  searchPlaceholder = "Buscar...",
  emptyLabel = "Nenhum resultado encontrado.",
  className,
}: SearchableSelectProps) {
  const selected = options.find((option) => option.value === value);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          className={cn(
            "w-full justify-between rounded-xl border-border/60 bg-card/60",
            !selected && "text-muted-foreground",
            className,
          )}
        >
          {selected?.label ?? placeholder}
          <ChevronsUpDownIcon className="size-4 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] rounded-2xl border-border/60 p-0">
        <Command>
          <CommandInput placeholder={searchPlaceholder} />
          <CommandList>
            <CommandEmpty>{emptyLabel}</CommandEmpty>
            <CommandGroup>
              {options.map((option) => (
                <CommandItem
                  key={option.value}
                  value={`${option.label} ${option.value}`}
                  onSelect={() => onChange?.(option.value)}
                >
                  <CheckIcon
                    className={cn(
                      "size-4",
                      option.value === value ? "opacity-100" : "opacity-0",
                    )}
                  />
                  {option.label}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
