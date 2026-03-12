import LoginForm from "@/components/auth/login-form";

type LoginPageProps = {
  searchParams?: Promise<{ next?: string }>;
};

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = searchParams ? await searchParams : undefined;
  return <LoginForm next={params?.next ?? "/dashboard"} />;
}
