"use client";

import type { Role } from "@abase/shared-types";

import { useAuth } from "@/hooks/use-auth";

export function usePermissions() {
  const { user, ...auth } = useAuth();
  const roles = user?.roles ?? [];

  return {
    ...auth,
    user,
    role: user?.primary_role,
    roles,
    hasRole: (role: Role) => roles.includes(role),
    hasAnyRole: (nextRoles: Role[]) => nextRoles.some((role) => roles.includes(role)),
  };
}
