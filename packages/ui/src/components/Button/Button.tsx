import React from 'react';
import { Button as HeroButton, ButtonProps as HeroButtonProps } from '@heroui/react';

import { cn } from '../../utils';

export interface ButtonProps extends HeroButtonProps {
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ children, loading, leftIcon, rightIcon, disabled, className, ...props }, ref) => {
    return (
      <HeroButton
        ref={ref}
        disabled={disabled || loading}
        className={cn(
          'font-medium transition-all duration-200',
          'hover:scale-[1.02] active:scale-[0.98]',
          className,
        )}
        {...props}
      >
        {loading ? (
          <span className="flex items-center gap-2">
            <span className="animate-spin h-4 w-4 rounded-full border-2 border-current border-t-transparent" />
            Processando...
          </span>
        ) : (
          <>
            {leftIcon && <span className="mr-2">{leftIcon}</span>}
            {children}
            {rightIcon && <span className="ml-2">{rightIcon}</span>}
          </>
        )}
      </HeroButton>
    );
  },
);

Button.displayName = 'Button';
