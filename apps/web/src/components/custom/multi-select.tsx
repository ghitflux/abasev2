"use client";

import { CheckIcon, ChevronDownIcon, XIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
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
import type { SelectOption } from "@/components/custom/searchable-select";

type MultiSelectProps = {
  options: SelectOption[];
  value?: string[];
  onChange?: (value: string[]) => void;
  placeholder?: string;
  className?: string;
};

export default function MultiSelect({
  options,
  value = [],
  onChange,
  placeholder = "Selecione",
  className,
}: MultiSelectProps) {
  const selectedOptions = options.filter((option) => value.includes(option.value));

  const toggleValue = (nextValue: string) => {
    if (value.includes(nextValue)) {
      onChange?.(value.filter((item) => item !== nextValue));
      return;
    }
    onChange?.([...value, nextValue]);
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className={cn(
            "min-h-10 w-full justify-between rounded-xl border-border/60 bg-card/60 px-3 py-2",
            className,
          )}
        >
          <div className="flex flex-1 flex-wrap gap-1">
            {selectedOptions.length > 0 ? (
              selectedOptions.map((option) => (
                <Badge key={option.value} variant="secondary" className="rounded-full">
                  {option.label}
                  <span
                    aria-hidden
                    className="ml-1 inline-flex cursor-pointer"
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      toggleValue(option.value);
                    }}
                  >
                    <XIcon className="size-3" />
                  </span>
                </Badge>
              ))
            ) : (
              <span className="text-muted-foreground">{placeholder}</span>
            )}
          </div>
          <ChevronDownIcon className="size-4 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] rounded-2xl border-border/60 p-0">
        <Command>
          <CommandInput placeholder="Buscar..." />
          <CommandList>
            <CommandEmpty>Nenhuma opção encontrada.</CommandEmpty>
            <CommandGroup>
              {options.map((option) => (
                <CommandItem
                  key={option.value}
                  value={`${option.label} ${option.value}`}
                  onSelect={() => toggleValue(option.value)}
                >
                  <CheckIcon
                    className={cn(
                      "size-4",
                      value.includes(option.value) ? "opacity-100" : "opacity-0",
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
