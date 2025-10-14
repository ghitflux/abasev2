import React from 'react';
import { Control, Controller, FieldPath, FieldValues } from 'react-hook-form';
import { Checkbox, DatePicker, Input, Radio, RadioGroup, Select, SelectItem, Textarea } from '@heroui/react';

import { cn } from '../../utils';

interface FormFieldProps<T extends FieldValues> {
  control: Control<T>;
  name: FieldPath<T>;
  label?: string;
  placeholder?: string;
  type?:
    | 'text'
    | 'email'
    | 'password'
    | 'number'
    | 'textarea'
    | 'select'
    | 'date'
    | 'checkbox'
    | 'radio';
  options?: { value: string; label: string }[];
  required?: boolean;
  disabled?: boolean;
  className?: string;
  helperText?: string;
}

const HeroSelect = Select as any;
const HeroSelectItem = SelectItem as any;

export function FormField<T extends FieldValues>({
  control,
  name,
  label,
  placeholder,
  type = 'text',
  options,
  required,
  disabled,
  className,
  helperText,
}: FormFieldProps<T>) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState }) => {
        const error = fieldState.error;
        const baseProps = {
          ...field,
          label,
          placeholder,
          isRequired: required,
          isDisabled: disabled,
          errorMessage: error?.message,
          isInvalid: !!error,
          description: helperText,
          className: cn('w-full', className),
        };

        switch (type) {
          case 'textarea':
            return <Textarea {...baseProps} minRows={3} />;

          case 'select':
            return (
              <HeroSelect
                {...baseProps}
                selectedKeys={new Set(field.value ? [String(field.value)] : [])}
                onSelectionChange={(keys: any) => field.onChange(Array.from(keys)[0])}
              >
                {(options?.map((option) => (
                  <HeroSelectItem key={option.value}>{option.label}</HeroSelectItem>
                )) ?? null)}
              </HeroSelect>
            );

          case 'date':
            return <DatePicker {...baseProps} value={field.value as any} onChange={field.onChange} />;

          case 'checkbox':
            return (
              <Checkbox
                {...baseProps}
                isSelected={Boolean(field.value)}
                onValueChange={field.onChange}
              >
                {label}
              </Checkbox>
            );

          case 'radio':
            return (
              <RadioGroup {...baseProps} value={field.value} onValueChange={field.onChange}>
                {options?.map((option) => (
                  <Radio key={option.value} value={option.value}>
                    {option.label}
                  </Radio>
                ))}
              </RadioGroup>
            );

          default:
            return <Input {...baseProps} type={type} value={field.value ?? ''} onChange={field.onChange} />;
        }
      }}
    />
  );
}
