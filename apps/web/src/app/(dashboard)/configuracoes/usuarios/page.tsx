"use client";

import * as React from "react";
import type { Role } from "@abase/shared-types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  KeyIcon,
  PencilIcon,
  SearchIcon,
  ShieldCheckIcon,
  UserCheckIcon,
  UserPlusIcon,
  Users2Icon,
  UserXIcon,
} from "lucide-react";
import { toast } from "sonner";

import type {
  AvailableRole,
  PaginatedMetaResponse,
  SystemUserAccessUpdatePayload,
  SystemUserCreatePayload,
  SystemUserListItem,
  SystemUserPasswordResetPayload,
  SystemUserPasswordResetResult,
  SystemUsersMeta,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { formatDateTime } from "@/lib/formatters";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { usePermissions } from "@/hooks/use-permissions";
import RoleGuard from "@/components/auth/role-guard";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { MetricCardSkeleton } from "@/components/shared/page-skeletons";
import StatsCard from "@/components/shared/stats-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";

type StatusFilter = "todos" | "ativos" | "inativos";

function AccessDialog({
  open,
  onOpenChange,
  selectedUser,
  availableRoles,
  isPending,
  onSave,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedUser: SystemUserListItem | null;
  availableRoles: AvailableRole[];
  isPending: boolean;
  onSave: (payload: SystemUserAccessUpdatePayload) => void;
}) {
  const [selectedRoles, setSelectedRoles] = React.useState<Role[]>([]);
  const [isActive, setIsActive] = React.useState(true);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (!selectedUser) return;
    setSelectedRoles(selectedUser.roles);
    setIsActive(selectedUser.is_active);
    setError("");
  }, [selectedUser]);

  if (!selectedUser) return null;

  const toggleRole = (role: Role, checked: boolean) => {
    setError("");
    setSelectedRoles((current) => {
      if (checked) {
        return current.includes(role) ? current : [...current, role];
      }

      return current.filter((item) => item !== role);
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Editar acesso</DialogTitle>
          <DialogDescription>
            Ajuste os perfis e o status de acesso do usuário interno.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          <Card className="rounded-2xl border-border/60 bg-card/60 py-4">
            <CardContent className="space-y-2 px-4">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-base font-semibold text-foreground">{selectedUser.full_name}</p>
                {selectedUser.is_current_user ? (
                  <Badge variant="outline">Sessão atual</Badge>
                ) : null}
              </div>
              <p className="text-sm text-muted-foreground">{selectedUser.email}</p>
            </CardContent>
          </Card>

          <div className="flex items-center justify-between rounded-2xl border border-border/60 bg-card/60 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-foreground">Usuário ativo</p>
              <p className="text-xs text-muted-foreground">
                Controle imediato de login para este acesso interno.
              </p>
            </div>
            <Switch
              checked={isActive}
              disabled={isPending || selectedUser.is_current_user}
              onCheckedChange={setIsActive}
            />
          </div>

          <div className="space-y-3">
            <div>
              <p className="text-sm font-medium text-foreground">Perfis liberados</p>
              <p className="text-xs text-muted-foreground">
                O usuário precisa manter pelo menos um perfil operacional.
              </p>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {availableRoles.map((roleOption) => {
                const isChecked = selectedRoles.includes(roleOption.codigo);
                const isLockedAdmin =
                  selectedUser.is_current_user &&
                  roleOption.codigo === "ADMIN" &&
                  isChecked;

                return (
                  <label
                    key={roleOption.codigo}
                    className="flex items-start gap-3 rounded-2xl border border-border/60 bg-card/60 px-4 py-3"
                  >
                    <Checkbox
                      checked={isChecked}
                      disabled={isPending || isLockedAdmin}
                      onCheckedChange={(checked) =>
                        toggleRole(roleOption.codigo, Boolean(checked))
                      }
                    />
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-foreground">{roleOption.nome}</p>
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                        {roleOption.codigo}
                      </p>
                    </div>
                  </label>
                );
              })}
            </div>
          </div>

          {selectedUser.is_current_user ? (
            <p className="text-xs text-muted-foreground">
              Sua sessão precisa continuar ativa e manter o perfil ADMIN.
            </p>
          ) : null}

          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            disabled={isPending}
            onClick={() => {
              if (!selectedRoles.length) {
                setError("Selecione ao menos um perfil para salvar.");
                return;
              }

              onSave({ roles: selectedRoles, is_active: isActive });
            }}
          >
            {isPending ? <Spinner /> : null}
            Salvar acesso
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CreateUserDialog({
  open,
  onOpenChange,
  availableRoles,
  isPending,
  onCreate,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  availableRoles: AvailableRole[];
  isPending: boolean;
  onCreate: (payload: SystemUserCreatePayload) => void;
}) {
  const [firstName, setFirstName] = React.useState("");
  const [lastName, setLastName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [selectedRoles, setSelectedRoles] = React.useState<Role[]>([]);
  const [password, setPassword] = React.useState("");
  const [passwordConfirm, setPasswordConfirm] = React.useState("");
  const [isActive, setIsActive] = React.useState(true);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (!open) {
      setFirstName("");
      setLastName("");
      setEmail("");
      setSelectedRoles([]);
      setPassword("");
      setPasswordConfirm("");
      setIsActive(true);
      setError("");
    }
  }, [open]);

  const toggleRole = (role: Role, checked: boolean) => {
    setError("");
    setSelectedRoles((current) => {
      if (checked) {
        return current.includes(role) ? current : [...current, role];
      }
      return current.filter((item) => item !== role);
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Novo usuário interno</DialogTitle>
          <DialogDescription>
            Cadastre o acesso operacional e defina uma senha temporária com troca obrigatória no
            primeiro login.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground" htmlFor="create-first-name">
                Nome
              </label>
              <Input
                id="create-first-name"
                value={firstName}
                onChange={(event) => {
                  setFirstName(event.target.value);
                  setError("");
                }}
                placeholder="Nome do usuário"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground" htmlFor="create-last-name">
                Sobrenome
              </label>
              <Input
                id="create-last-name"
                value={lastName}
                onChange={(event) => {
                  setLastName(event.target.value);
                  setError("");
                }}
                placeholder="Sobrenome do usuário"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground" htmlFor="create-email">
              E-mail
            </label>
            <Input
              id="create-email"
              type="email"
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
                setError("");
              }}
              placeholder="email@abase.com"
            />
          </div>

          <div className="space-y-3">
            <div>
              <p className="text-sm font-medium text-foreground">Perfis liberados</p>
              <p className="text-xs text-muted-foreground">
                Selecione ao menos um perfil permitido para o seu nível de acesso.
              </p>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {availableRoles.map((roleOption) => {
                const isChecked = selectedRoles.includes(roleOption.codigo);
                return (
                  <label
                    key={roleOption.codigo}
                    className="flex items-start gap-3 rounded-2xl border border-border/60 bg-card/60 px-4 py-3"
                  >
                    <Checkbox
                      checked={isChecked}
                      disabled={isPending}
                      onCheckedChange={(checked) =>
                        toggleRole(roleOption.codigo, Boolean(checked))
                      }
                    />
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-foreground">{roleOption.nome}</p>
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                        {roleOption.codigo}
                      </p>
                    </div>
                  </label>
                );
              })}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground" htmlFor="create-password">
                Senha temporária
              </label>
              <Input
                id="create-password"
                type="password"
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value);
                  setError("");
                }}
                placeholder="Digite a senha temporária"
              />
            </div>
            <div className="space-y-2">
              <label
                className="text-sm font-medium text-foreground"
                htmlFor="create-password-confirm"
              >
                Confirmar senha
              </label>
              <Input
                id="create-password-confirm"
                type="password"
                value={passwordConfirm}
                onChange={(event) => {
                  setPasswordConfirm(event.target.value);
                  setError("");
                }}
                placeholder="Repita a senha temporária"
              />
            </div>
          </div>

          <div className="flex items-center justify-between rounded-2xl border border-border/60 bg-card/60 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-foreground">Usuário ativo</p>
              <p className="text-xs text-muted-foreground">
                O acesso pode ser criado já desativado, se necessário.
              </p>
            </div>
            <Switch checked={isActive} disabled={isPending} onCheckedChange={setIsActive} />
          </div>

          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            disabled={isPending}
            onClick={() => {
              if (!firstName.trim() || !email.trim()) {
                setError("Preencha nome e e-mail do usuário.");
                return;
              }
              if (!selectedRoles.length) {
                setError("Selecione ao menos um perfil para o novo usuário.");
                return;
              }
              if (!password || !passwordConfirm) {
                setError("Preencha a senha temporária e a confirmação.");
                return;
              }
              if (password !== passwordConfirm) {
                setError("A confirmação da senha não confere.");
                return;
              }

              onCreate({
                email,
                first_name: firstName.trim(),
                last_name: lastName.trim(),
                roles: selectedRoles,
                password,
                password_confirm: passwordConfirm,
                is_active: isActive,
              });
            }}
          >
            {isPending ? <Spinner /> : <UserPlusIcon className="size-4" />}
            Criar usuário
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ResetPasswordDialog({
  open,
  onOpenChange,
  selectedUser,
  isPending,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedUser: SystemUserListItem | null;
  isPending: boolean;
  onConfirm: (payload: SystemUserPasswordResetPayload) => void;
}) {
  const [password, setPassword] = React.useState("");
  const [passwordConfirm, setPasswordConfirm] = React.useState("");
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (!open) {
      setPassword("");
      setPasswordConfirm("");
      setError("");
    }
  }, [open, selectedUser]);

  if (!selectedUser) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Definir nova senha</DialogTitle>
          <DialogDescription>
            Defina a nova senha do usuário. Ela será gravada com hash no banco e ficará válida
            imediatamente.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-3 rounded-2xl border border-border/60 bg-card/60 px-4 py-4">
            <p className="text-sm text-foreground">
              Usuário: <span className="font-medium">{selectedUser.full_name}</span>
            </p>
            <p className="text-sm text-muted-foreground">{selectedUser.email}</p>
          </div>

          <div className="space-y-3">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground" htmlFor="reset-password">
                Nova senha
              </label>
              <Input
                id="reset-password"
                type="password"
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value);
                  setError("");
                }}
                placeholder="Digite a nova senha"
              />
            </div>

            <div className="space-y-2">
              <label
                className="text-sm font-medium text-foreground"
                htmlFor="reset-password-confirm"
              >
                Confirmar nova senha
              </label>
              <Input
                id="reset-password-confirm"
                type="password"
                value={passwordConfirm}
                onChange={(event) => {
                  setPasswordConfirm(event.target.value);
                  setError("");
                }}
                placeholder="Repita a nova senha"
              />
            </div>
          </div>

          <p className="text-xs text-muted-foreground">
            A senha será armazenada com hash. A flag de troca pendente será removida após a
            atualização.
          </p>

          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            disabled={isPending}
            onClick={() => {
              if (!password || !passwordConfirm) {
                setError("Preencha a nova senha e a confirmação.");
                return;
              }

              if (password !== passwordConfirm) {
                setError("A confirmação da senha não confere.");
                return;
              }

              onConfirm({ password, password_confirm: passwordConfirm });
            }}
          >
            {isPending ? <Spinner /> : null}
            Salvar nova senha
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function UsuariosConfiguracoesPageContent() {
  const queryClient = useQueryClient();
  const { user, refresh } = usePermissions();
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState<StatusFilter>("todos");
  const [roleFilter, setRoleFilter] = React.useState<Role | "">("");
  const [createDialogOpen, setCreateDialogOpen] = React.useState(false);
  const [selectedUser, setSelectedUser] = React.useState<SystemUserListItem | null>(null);
  const [passwordUser, setPasswordUser] = React.useState<SystemUserListItem | null>(null);
  const debouncedSearch = useDebouncedValue(search, 300);

  const usersQuery = useQuery({
    queryKey: ["configuracoes-usuarios", page, debouncedSearch, statusFilter, roleFilter],
    queryFn: () =>
      apiFetch<PaginatedMetaResponse<SystemUserListItem, SystemUsersMeta>>(
        "configuracoes/usuarios",
        {
          query: {
            page,
            page_size: 20,
            search: debouncedSearch || undefined,
            role: roleFilter || undefined,
            is_active:
              statusFilter === "todos"
                ? undefined
                : statusFilter === "ativos"
                  ? true
                  : false,
          },
        },
      ),
  });

  const updateAccessMutation = useMutation({
    mutationFn: (payload: { userId: number; body: SystemUserAccessUpdatePayload }) =>
      apiFetch<SystemUserListItem>(`configuracoes/usuarios/${payload.userId}`, {
        method: "PATCH",
        body: payload.body,
      }),
    onSuccess: async (updatedUser) => {
      toast.success("Acesso atualizado com sucesso.");
      setSelectedUser(null);
      await queryClient.invalidateQueries({ queryKey: ["configuracoes-usuarios"] });

      if (updatedUser.id === user?.id) {
        await refresh();
      }
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao atualizar acesso.");
    },
  });

  const createUserMutation = useMutation({
    mutationFn: (payload: SystemUserCreatePayload) =>
      apiFetch<SystemUserListItem>("configuracoes/usuarios", {
        method: "POST",
        body: payload,
      }),
    onSuccess: async (createdUser) => {
      toast.success(`Usuário ${createdUser.full_name} criado com sucesso.`);
      setCreateDialogOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["configuracoes-usuarios"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao criar usuário.");
    },
  });

  const resetPasswordMutation = useMutation({
    mutationFn: (payload: { targetUser: SystemUserListItem; body: SystemUserPasswordResetPayload }) =>
      apiFetch<SystemUserPasswordResetResult>(
        `configuracoes/usuarios/${payload.targetUser.id}/resetar-senha`,
        {
          method: "POST",
          body: payload.body,
        },
      ),
    onSuccess: async (result, payload) => {
      setPasswordUser(null);
      toast.success(result.detail || `Senha atualizada para ${payload.targetUser.full_name}.`);
      await queryClient.invalidateQueries({ queryKey: ["configuracoes-usuarios"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao resetar senha.");
    },
  });

  const users = usersQuery.data?.results ?? [];
  const meta = usersQuery.data?.meta;
  const roleOptions = React.useMemo(
    () => usersQuery.data?.meta.available_roles ?? [],
    [usersQuery.data?.meta.available_roles],
  );
  const totalPages = Math.max(1, Math.ceil((usersQuery.data?.count ?? 0) / 20));

  const roleLabelMap = React.useMemo(
    () =>
      Object.fromEntries(roleOptions.map((roleOption) => [roleOption.codigo, roleOption.nome])),
    [roleOptions],
  );

  const columns = React.useMemo<DataTableColumn<SystemUserListItem>[]>(
    () => [
      {
        id: "usuario",
        header: "Usuário",
        cell: (row) => (
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-medium text-foreground">{row.full_name}</p>
              {row.is_current_user ? <Badge variant="outline">Sessão atual</Badge> : null}
            </div>
            <p className="text-xs text-muted-foreground">{row.email}</p>
          </div>
        ),
      },
      {
        id: "roles",
        header: "Perfis",
        cell: (row) => (
          <div className="flex flex-wrap gap-2">
            {row.roles.map((role) => (
              <Badge key={role} variant="outline">
                {roleLabelMap[role] ?? role}
              </Badge>
            ))}
          </div>
        ),
      },
      {
        id: "is_active",
        header: "Acesso",
        accessor: "is_active",
        cell: (row) => (
          <Badge
            className={
              row.is_active
                ? "bg-emerald-500/15 text-emerald-200"
                : "bg-amber-500/15 text-amber-200"
            }
          >
            {row.is_active ? "Ativo" : "Inativo"}
          </Badge>
        ),
      },
      {
        id: "must_set_password",
        header: "Senha",
        accessor: "must_set_password",
        cell: (row) => (
          <Badge
            className={
              row.must_set_password
                ? "bg-amber-500/15 text-amber-200"
                : "bg-sky-500/15 text-sky-200"
            }
          >
            {row.must_set_password ? "Troca pendente" : "Regular"}
          </Badge>
        ),
      },
      {
        id: "last_login",
        header: "Último login",
        accessor: "last_login",
        cell: (row) => formatDateTime(row.last_login),
      },
      {
        id: "acoes",
        header: "Ações",
        cell: (row) => (
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => setSelectedUser(row)}>
              <PencilIcon className="size-4" />
              Acesso
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPasswordUser(row)}
            >
              <KeyIcon className="size-4" />
              Resetar senha
            </Button>
          </div>
        ),
      },
    ],
    [roleLabelMap],
  );

  return (
    <div className="space-y-8">
      <section className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold text-foreground">Configurações de usuários</h1>
          <p className="max-w-3xl text-sm text-muted-foreground">
            Gestão centralizada dos acessos internos do sistema, com criação de usuários,
            atualização de perfis e definição direta de novas senhas.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="rounded-[1.5rem] border border-border/60 bg-card/60 px-4 py-3 text-sm text-muted-foreground">
            Usuário em sessão: <span className="font-medium text-foreground">{user?.full_name}</span>
          </div>
          <Button onClick={() => setCreateDialogOpen(true)}>
            <UserPlusIcon className="size-4" />
            Novo usuário
          </Button>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {usersQuery.isLoading && !usersQuery.data ? (
          Array.from({ length: 4 }).map((_, index) => <MetricCardSkeleton key={index} />)
        ) : (
          <>
            <StatsCard
              title="Usuários internos"
              value={String(meta?.total ?? 0)}
              delta={`${meta?.ativos ?? 0} com acesso ativo`}
              tone="neutral"
              icon={Users2Icon}
            />
            <StatsCard
              title="Acessos ativos"
              value={String(meta?.ativos ?? 0)}
              delta={`${Math.max((meta?.total ?? 0) - (meta?.ativos ?? 0), 0)} inativos`}
              tone="positive"
              icon={UserCheckIcon}
            />
            <StatsCard
              title="Administradores"
              value={String(meta?.admins ?? 0)}
              delta={`${Math.max((meta?.total ?? 0) - (meta?.admins ?? 0), 0)} demais perfis`}
              tone="neutral"
              icon={ShieldCheckIcon}
            />
            <StatsCard
              title="Troca de senha"
              value={String(meta?.troca_senha_pendente ?? 0)}
              delta={
                (meta?.troca_senha_pendente ?? 0) > 0
                  ? "Usuários aguardando troca obrigatória"
                  : "Sem pendências de credenciais"
              }
              tone={(meta?.troca_senha_pendente ?? 0) > 0 ? "warning" : "positive"}
              icon={UserXIcon}
            />
          </>
        )}
      </section>

      <section className="space-y-4 rounded-[1.75rem] border border-border/60 bg-card/70 p-5 shadow-xl shadow-black/20">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="relative w-full max-w-xl">
            <SearchIcon className="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              placeholder="Buscar por nome ou email..."
              className="rounded-2xl border-border/60 bg-card/60 pl-11"
            />
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              variant={statusFilter === "todos" ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setStatusFilter("todos");
                setPage(1);
              }}
            >
              Todos
            </Button>
            <Button
              variant={statusFilter === "ativos" ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setStatusFilter("ativos");
                setPage(1);
              }}
            >
              Ativos
            </Button>
            <Button
              variant={statusFilter === "inativos" ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setStatusFilter("inativos");
                setPage(1);
              }}
            >
              Inativos
            </Button>
          </div>
        </div>

        {roleOptions.length ? (
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
              Filtrar por perfil
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                variant={roleFilter === "" ? "default" : "outline"}
                size="sm"
                onClick={() => {
                  setRoleFilter("");
                  setPage(1);
                }}
              >
                Todos os perfis
              </Button>
              {roleOptions.map((roleOption) => (
                <Button
                  key={roleOption.codigo}
                  variant={roleFilter === roleOption.codigo ? "default" : "outline"}
                  size="sm"
                  onClick={() => {
                    setRoleFilter(roleOption.codigo);
                    setPage(1);
                  }}
                >
                  {roleOption.nome}
                </Button>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      {usersQuery.isError ? (
        <div className="flex flex-col gap-3 rounded-[1.75rem] border border-destructive/40 bg-card/60 px-6 py-8">
          <p className="text-sm text-destructive">
            {usersQuery.error instanceof Error
              ? usersQuery.error.message
              : "Nao foi possivel carregar os usuarios internos."}
          </p>
          <div>
            <Button variant="outline" onClick={() => void usersQuery.refetch()}>
              Tentar novamente
            </Button>
          </div>
        </div>
      ) : (
        <DataTable
          data={users}
          columns={columns}
          currentPage={page}
          totalPages={totalPages}
          onPageChange={setPage}
          emptyMessage="Nenhum usuário encontrado para os filtros informados."
          loading={usersQuery.isLoading}
          skeletonRows={6}
        />
      )}

      <CreateUserDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        availableRoles={roleOptions}
        isPending={createUserMutation.isPending}
        onCreate={(payload) => createUserMutation.mutate(payload)}
      />

      <AccessDialog
        open={Boolean(selectedUser)}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedUser(null);
          }
        }}
        selectedUser={selectedUser}
        availableRoles={roleOptions}
        isPending={updateAccessMutation.isPending}
        onSave={(payload) => {
          if (!selectedUser) return;
          updateAccessMutation.mutate({
            userId: selectedUser.id,
            body: payload,
          });
        }}
      />

      <ResetPasswordDialog
        open={Boolean(passwordUser)}
        onOpenChange={(open) => {
          if (!open) {
            setPasswordUser(null);
          }
        }}
        selectedUser={passwordUser}
        isPending={resetPasswordMutation.isPending}
        onConfirm={(payload) => {
          if (!passwordUser) return;
          resetPasswordMutation.mutate({
            targetUser: passwordUser,
            body: payload,
          });
        }}
      />
    </div>
  );
}

export default function UsuariosConfiguracoesPage() {
  return (
    <RoleGuard allow={["ADMIN", "COORDENADOR"]}>
      <UsuariosConfiguracoesPageContent />
    </RoleGuard>
  );
}
