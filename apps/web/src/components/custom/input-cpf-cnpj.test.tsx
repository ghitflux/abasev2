import { render, screen } from "@testing-library/react";

import InputCpfCnpj from "./input-cpf-cnpj";

describe("InputCpfCnpj", () => {
  it("nao marca o campo como invalido por checksum", () => {
    render(<InputCpfCnpj value="11111111111" />);

    const input = screen.getByRole("textbox");

    expect(input).toHaveValue("111.111.111-11");
    expect(input).not.toHaveAttribute("aria-invalid", "true");
  });
});
