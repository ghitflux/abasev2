import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AdminOverrideConfirmDialog from "./admin-override-confirm-dialog";

describe("AdminOverrideConfirmDialog", () => {
  it("deixa o fechamento sob controle do chamador apos confirmar", async () => {
    const user = userEvent.setup();
    const onOpenChange = jest.fn();
    const onConfirm = jest.fn().mockResolvedValue(undefined);

    render(
      <AdminOverrideConfirmDialog
        open
        onOpenChange={onOpenChange}
        title="Salvar override"
        description="Descricao"
        onConfirm={onConfirm}
      />,
    );

    await user.type(
      screen.getByPlaceholderText(
        "Descreva o motivo da alteração administrativa.",
      ),
      "Motivo válido para salvar.",
    );
    await user.click(
      screen.getByRole("checkbox", { name: /confirmo que esta alteração/i }),
    );
    await user.click(screen.getByRole("button", { name: "Salvar alteração" }));

    await waitFor(() =>
      expect(onConfirm).toHaveBeenCalledWith("Motivo válido para salvar."),
    );
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });
});
