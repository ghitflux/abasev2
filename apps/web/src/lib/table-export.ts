"use client";

import { toast } from "sonner";

export type TableExportColumn<T> = {
  header: string;
  value: (row: T) => string | number;
};

function downloadFile(filename: string, content: string, contentType: string) {
  const blob = new Blob([content], { type: contentType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function exportAsSeparatedText<T>(
  filename: string,
  columns: TableExportColumn<T>[],
  rows: T[],
  separator: string,
) {
  const header = columns.map((column) => column.header).join(separator);
  const lines = rows.map((row) =>
    columns
      .map((column) => String(column.value(row) ?? "").replaceAll(separator, " "))
      .join(separator),
  );

  downloadFile(
    filename,
    [header, ...lines].join("\n"),
    "application/vnd.ms-excel;charset=utf-8",
  );
}

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function exportAsPrintableHtml<T>(
  title: string,
  columns: TableExportColumn<T>[],
  rows: T[],
) {
  const escapedTitle = escapeHtml(title);
  const headers = columns.map((column) => `<th>${escapeHtml(column.header)}</th>`).join("");
  const body = rows
    .map(
      (row) =>
        `<tr>${columns
          .map((column) => `<td>${escapeHtml(String(column.value(row) ?? "-"))}</td>`)
          .join("")}</tr>`,
    )
    .join("");
  const html = `
    <html lang="pt-BR">
      <head>
        <title>${escapedTitle}</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 24px; color: #111827; }
          h1 { margin: 0 0 16px; font-size: 22px; }
          table { width: 100%; border-collapse: collapse; }
          th, td { border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; font-size: 12px; }
          th { background: #f3f4f6; text-transform: uppercase; letter-spacing: 0.04em; }
        </style>
      </head>
      <body>
        <h1>${escapedTitle}</h1>
        <table>
          <thead><tr>${headers}</tr></thead>
          <tbody>${body}</tbody>
        </table>
      </body>
    </html>
  `;

  const iframe = document.createElement("iframe");
  iframe.setAttribute("aria-hidden", "true");
  iframe.style.position = "fixed";
  iframe.style.right = "0";
  iframe.style.bottom = "0";
  iframe.style.width = "0";
  iframe.style.height = "0";
  iframe.style.border = "0";
  iframe.style.opacity = "0";
  iframe.style.pointerEvents = "none";

  document.body.appendChild(iframe);

  const cleanup = () => {
    window.setTimeout(() => {
      iframe.remove();
    }, 0);
  };

  const printWindow = iframe.contentWindow;
  const printDocument = printWindow?.document;

  if (!printWindow || !printDocument) {
    cleanup();
    toast.error("Nao foi possivel preparar a visualizacao para PDF.");
    return;
  }

  try {
    printDocument.open();
    printDocument.write(html);
    printDocument.close();

    const triggerPrint = () => {
      try {
        printWindow.focus();
        printWindow.print();
      } catch {
        toast.error("Nao foi possivel gerar a visualizacao para PDF.");
      } finally {
        window.setTimeout(cleanup, 1500);
      }
    };

    printWindow.addEventListener("afterprint", cleanup, { once: true });
    window.setTimeout(triggerPrint, 150);
  } catch {
    cleanup();
    toast.error("Nao foi possivel gerar a visualizacao para PDF.");
  }
}

export function exportRows<T>(
  format: "csv" | "pdf" | "excel",
  title: string,
  filenameBase: string,
  columns: TableExportColumn<T>[],
  rows: T[],
) {
  if (format === "pdf") {
    exportAsPrintableHtml(title, columns, rows);
    return;
  }

  const separator = format === "csv" ? ";" : "\t";
  const extension = format === "csv" ? "csv" : "xls";
  exportAsSeparatedText(`${filenameBase}.${extension}`, columns, rows, separator);
}
