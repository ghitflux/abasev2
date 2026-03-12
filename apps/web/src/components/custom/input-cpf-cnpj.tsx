"use client";

import * as React from "react";

import { maskCPFCNPJ } from "@/lib/masks";
import { Input } from "@/components/ui/input";

type InputCpfCnpjProps = Omit<
  React.ComponentProps<typeof Input>,
  "value" | "onChange"
> & {
  value?: string;
  onChange?: (value: string) => void;
};

export default function InputCpfCnpj({
  value = "",
  onChange,
  ...props
}: InputCpfCnpjProps) {
  const [internalValue, setInternalValue] = React.useState(maskCPFCNPJ(value));

  React.useEffect(() => {
    setInternalValue(maskCPFCNPJ(value));
  }, [value]);

  return (
    <Input
      {...props}
      value={internalValue}
      inputMode="numeric"
      onChange={(event) => {
        const nextValue = maskCPFCNPJ(event.target.value);
        setInternalValue(nextValue);
        onChange?.(nextValue);
      }}
    />
  );
}
