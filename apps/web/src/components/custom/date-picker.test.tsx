import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import DatePicker from "./date-picker";

describe("DatePicker", () => {
  it("aplica mascara de data enquanto o usuario digita", async () => {
    const user = userEvent.setup();

    render(<DatePicker />);

    const input = screen.getByPlaceholderText("dd/mm/aaaa");
    await user.type(input, "11031990");

    expect(input).toHaveValue("11/03/1990");
  });
});
