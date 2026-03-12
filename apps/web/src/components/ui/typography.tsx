import { cn } from "@/lib/utils";

export function H1({ className, ...props }: React.ComponentProps<"h1">) {
  return <h1 className={cn("text-3xl font-semibold tracking-tight text-foreground sm:text-4xl", className)} {...props} />;
}

export function H2({ className, ...props }: React.ComponentProps<"h2">) {
  return <h2 className={cn("text-2xl font-semibold tracking-tight text-foreground", className)} {...props} />;
}

export function Lead({ className, ...props }: React.ComponentProps<"p">) {
  return <p className={cn("text-base text-muted-foreground sm:text-lg", className)} {...props} />;
}

export function Muted({ className, ...props }: React.ComponentProps<"p">) {
  return <p className={cn("text-sm text-muted-foreground", className)} {...props} />;
}
