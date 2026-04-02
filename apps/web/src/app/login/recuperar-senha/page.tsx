import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import AgentManualResetForm from "@/components/auth/agent-manual-reset-form";
import { AUTH_COOKIES } from "@/lib/auth/constants";
import { deserializeUser } from "@/lib/auth/session";
import { resolvePostLoginPath } from "@/lib/navigation";

export default async function AgentManualResetPage() {
  const cookieStore = await cookies();
  const hasSession = Boolean(
    cookieStore.get(AUTH_COOKIES.accessToken)?.value ||
      cookieStore.get(AUTH_COOKIES.refreshToken)?.value,
  );
  const user = deserializeUser(cookieStore.get(AUTH_COOKIES.user)?.value);

  if (hasSession && user) {
    redirect(resolvePostLoginPath("/dashboard", user.roles, user.primary_role));
  }

  return <AgentManualResetForm />;
}
