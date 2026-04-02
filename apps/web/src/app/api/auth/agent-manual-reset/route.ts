import { NextResponse } from "next/server";

import { resetAgentPasswordManuallyWithBackend } from "@/lib/auth/backend";

export async function POST(request: Request) {
  try {
    const { email, password, passwordConfirmation } = await request.json();
    const payload = await resetAgentPasswordManuallyWithBackend(
      email,
      password,
      passwordConfirmation,
    );
    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json(
      {
        message: error instanceof Error ? error.message : "Falha ao atualizar a senha.",
      },
      { status: 400 },
    );
  }
}
