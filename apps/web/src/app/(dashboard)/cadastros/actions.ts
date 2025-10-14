"use server";

export async function submitCadastro(id: number) {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/api/v1/cadastros/cadastros/${id}/submit`,
    {
      method: "POST",
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error("Falha ao submeter cadastro");
  }

  return response.json();
}
