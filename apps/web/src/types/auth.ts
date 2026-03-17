import type { Role } from "@abase/shared-types";

export type UserRole = Role;

export type AuthUser = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  primary_role: UserRole;
  roles: UserRole[];
};
