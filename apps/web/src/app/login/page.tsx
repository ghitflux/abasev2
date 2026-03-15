import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import LoginForm from "@/components/auth/login-form";
import { AUTH_COOKIES } from "@/lib/auth/constants";
import { resolvePostLoginPath } from "@/lib/navigation";
import { deserializeUser } from "@/lib/auth/session";

type LoginPageProps = {
  searchParams?: Promise<{ next?: string }>;
};

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = searchParams ? await searchParams : undefined;
  const cookieStore = await cookies();
  const hasSession = Boolean(
    cookieStore.get(AUTH_COOKIES.accessToken)?.value ||
      cookieStore.get(AUTH_COOKIES.refreshToken)?.value,
  );
  const user = deserializeUser(cookieStore.get(AUTH_COOKIES.user)?.value);

  if (hasSession && user) {
    redirect(resolvePostLoginPath(params?.next, user.roles, user.primary_role));
  }

  return <LoginForm next={params?.next ?? "/dashboard"} />;
}
