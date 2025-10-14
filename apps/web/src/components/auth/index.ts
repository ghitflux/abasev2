/**
 * Auth Components
 *
 * Componentes relacionados a autenticação e autorização
 */

export { ProtectedRoute, withAuth } from './ProtectedRoute';
export type { ProtectedRouteProps, Role } from './ProtectedRoute';

export { PermissionGate, usePermissions } from './PermissionGate';
export type { PermissionGateProps } from './PermissionGate';

export { UserMenu } from './UserMenu';
export type { UserMenuProps } from './UserMenu';
