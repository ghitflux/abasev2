"use client";

import * as React from "react";

import { maskCEP } from "@/lib/masks";
import { Input } from "@/components/ui/input";

export type ViaCepAddress = {
  cep: string;
  logradouro: string;
  complemento: string;
  bairro: string;
  localidade: string;
  uf: string;
  erro?: boolean;
};

type InputCepProps = Omit<
  React.ComponentProps<typeof Input>,
  "value" | "onChange"
> & {
  value?: string;
  onChange?: (value: string) => void;
  onAddressResolved?: (address: ViaCepAddress | null) => void;
};

export default function InputCep({
  value = "",
  onChange,
  onAddressResolved,
  ...props
}: InputCepProps) {
  const [internalValue, setInternalValue] = React.useState(maskCEP(value));

  React.useEffect(() => {
    setInternalValue(maskCEP(value));
  }, [value]);

  React.useEffect(() => {
    const cep = internalValue.replace(/\D/g, "");
    if (cep.length !== 8) return;

    let active = true;

    fetch(`https://viacep.com.br/ws/${cep}/json/`)
      .then((response) => response.json())
      .then((data: ViaCepAddress) => {
        if (!active) return;
        onAddressResolved?.(data.erro ? null : data);
      })
      .catch(() => {
        if (!active) return;
        onAddressResolved?.(null);
      });

    return () => {
      active = false;
    };
  }, [internalValue, onAddressResolved]);

  return (
    <Input
      {...props}
      value={internalValue}
      inputMode="numeric"
      onChange={(event) => {
        const nextValue = maskCEP(event.target.value);
        setInternalValue(nextValue);
        onChange?.(nextValue);
      }}
    />
  );
}
