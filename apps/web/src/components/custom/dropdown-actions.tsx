"use client";

import { MoreHorizontalIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

type DropdownActionItem = {
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
  onClick: () => void;
  variant?: "default" | "destructive";
  disabled?: boolean;
};

type DropdownActionsProps = {
  items: DropdownActionItem[];
};

export default function DropdownActions({ items }: DropdownActionsProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="rounded-full">
          <MoreHorizontalIcon className="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="rounded-xl">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <DropdownMenuItem
              key={item.label}
              disabled={item.disabled}
              variant={item.variant}
              onClick={item.onClick}
            >
              {Icon ? <Icon className="size-4" /> : null}
              {item.label}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
