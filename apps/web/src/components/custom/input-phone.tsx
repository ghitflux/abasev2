"use client";

import * as React from "react";

import { maskPhone } from "@/lib/masks";
import { Input } from "@/components/ui/input";

type InputPhoneProps = Omit<
  React.ComponentProps<typeof Input>,
  "value" | "onChange"
> & {
  value?: string;
  onChange?: (value: string) => void;
};

export default function InputPhone({
  value = "",
  onChange,
  ...props
}: InputPhoneProps) {
  const [internalValue, setInternalValue] = React.useState(maskPhone(value));

  React.useEffect(() => {
    setInternalValue(maskPhone(value));
  }, [value]);

  return (
    <Input
      {...props}
      value={internalValue}
      inputMode="numeric"
      onChange={(event) => {
        const nextValue = maskPhone(event.target.value);
        setInternalValue(nextValue);
        onChange?.(nextValue);
      }}
    />
  );
}
