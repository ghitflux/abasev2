import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { AUTH_COOKIES } from "@/lib/auth/constants";

export default async function HomePage() {
  const cookieStore = await cookies();
  if (cookieStore.get(AUTH_COOKIES.accessToken)?.value) {
    redirect("/dashboard");
  }

  redirect("/login");
}
