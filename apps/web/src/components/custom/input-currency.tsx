"use client";

import * as React from "react";

import { maskCurrency, unmaskCurrency } from "@/lib/masks";
import { Input } from "@/components/ui/input";

type InputCurrencyProps = {
  value?: number | null;
  onChange?: (value: number | null) => void;
  className?: string;
  placeholder?: string;
  disabled?: boolean;
};

export default function InputCurrency({
  value,
  onChange,
  className,
  placeholder = "R$ 0,00",
  disabled = false,
}: InputCurrencyProps) {
  const [displayValue, setDisplayValue] = React.useState(
    value ? maskCurrency(value) : "",
  );

  React.useEffect(() => {
    setDisplayValue(value ? maskCurrency(value) : "");
  }, [value]);

  return (
    <Input
      value={displayValue}
      className={className}
      inputMode="numeric"
      placeholder={placeholder}
      disabled={disabled}
      onChange={(event) => {
        const cents = unmaskCurrency(event.target.value);
        setDisplayValue(cents ? maskCurrency(cents) : "");
        onChange?.(cents || null);
      }}
    />
  );
}
