"use client";

import * as React from "react";

import { maskPixKey } from "@/lib/masks";
import { Input } from "@/components/ui/input";

type InputPixKeyProps = Omit<
  React.ComponentProps<typeof Input>,
  "value" | "onChange"
> & {
  value?: string;
  onChange?: (value: string) => void;
};

export default function InputPixKey({
  value = "",
  onChange,
  ...props
}: InputPixKeyProps) {
  const [internalValue, setInternalValue] = React.useState(maskPixKey(value));

  React.useEffect(() => {
    setInternalValue(maskPixKey(value));
  }, [value]);

  return (
    <Input
      {...props}
      value={internalValue}
      onChange={(event) => {
        const nextValue = maskPixKey(event.target.value);
        setInternalValue(nextValue);
        onChange?.(nextValue);
      }}
    />
  );
}
