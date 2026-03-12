import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import FileUploadDropzone from "./file-upload-dropzone";

describe("FileUploadDropzone", () => {
  it("aceita arquivo .txt", async () => {
    const user = userEvent.setup();
    const onUpload = jest.fn();
    const { container } = render(
      <FileUploadDropzone
        accept={{ "text/plain": [".txt"] }}
        onUpload={onUpload}
        emptyTitle="Importar retorno"
      />,
    );

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["conteudo"], "retorno.txt", { type: "text/plain" });

    await user.upload(input, file);

    expect(onUpload).toHaveBeenCalledWith(file);
  });

  it("rejeita formato inválido", async () => {
    const user = userEvent.setup();
    const onUpload = jest.fn();
    const { container } = render(
      <FileUploadDropzone
        accept={{ "text/plain": [".txt"] }}
        onUpload={onUpload}
        emptyTitle="Importar retorno"
      />,
    );

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["id,valor"], "retorno.csv", { type: "text/csv" });

    await user.upload(input, file);

    expect(onUpload).not.toHaveBeenCalled();
  });

  it("aceita qualquer tipo de arquivo quando accept nao e informado", async () => {
    const user = userEvent.setup();
    const onUpload = jest.fn();
    const { container } = render(<FileUploadDropzone onUpload={onUpload} emptyTitle="Anexar" />);

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["zip"], "documento.zip", { type: "application/zip" });

    await user.upload(input, file);

    expect(onUpload).toHaveBeenCalledWith(file);
  });

  it("mantem o arquivo controlado visivel ao remount do passo", () => {
    const file = new File(["conteudo"], "comprovante.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });

    render(<FileUploadDropzone file={file} emptyTitle="Anexar" />);

    expect(screen.getByText("comprovante.docx")).toBeInTheDocument();
  });
});
