"use client";

import { FileIcon, FileTextIcon, UploadCloudIcon } from "lucide-react";
import { useDropzone, type Accept } from "react-dropzone";

import { cn } from "@/lib/utils";

type FileUploadDropzoneProps = {
  accept?: Accept;
  maxSize?: number;
  onUpload?: (file: File) => void;
  onUploadMany?: (files: File[]) => void;
  isProcessing?: boolean;
  disabled?: boolean;
  className?: string;
  emptyTitle?: string;
  emptyDescription?: string;
  file?: File | null;
  files?: File[];
  multiple?: boolean;
};

export default function FileUploadDropzone({
  accept,
  maxSize = 10 * 1024 * 1024,
  onUpload,
  onUploadMany,
  isProcessing,
  disabled,
  className,
  emptyTitle = "Arraste um arquivo ou clique para selecionar",
  emptyDescription,
  file,
  files,
  multiple = false,
}: FileUploadDropzoneProps) {
  const { acceptedFiles, getInputProps, getRootProps, isDragActive } = useDropzone({
    accept,
    maxSize,
    multiple,
    disabled: disabled || isProcessing,
    onDropAccepted: (files) => {
      if (multiple) {
        onUploadMany?.(files);
        return;
      }
      const [file] = files;
      if (file) onUpload?.(file);
    },
  });

  const selectedFiles = files ?? (multiple ? acceptedFiles : []);
  const selectedFile = file ?? (!multiple ? acceptedFiles[0] : undefined);
  const isTextUpload = Object.values(accept ?? {}).some((extensions) => extensions?.includes(".txt"));

  return (
    <div
      {...getRootProps()}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center gap-4 rounded-3xl border border-dashed border-border/70 bg-card/60 px-6 py-10 text-center transition hover:border-primary/70 hover:bg-card",
        isDragActive && "border-primary bg-primary/5",
        isProcessing && "cursor-wait opacity-70",
        disabled && !isProcessing && "cursor-not-allowed opacity-60 hover:border-border/70 hover:bg-card/60",
        className,
      )}
    >
      <input {...getInputProps()} />
      {multiple ? (
        selectedFiles.length ? (
          <>
            {isTextUpload ? (
              <FileTextIcon className="size-8 text-primary" />
            ) : (
              <FileIcon className="size-8 text-primary" />
            )}
            <div>
              <p className="font-semibold text-foreground">
                {selectedFiles.length} arquivo(s) selecionado(s)
              </p>
              <div className="mt-2 space-y-1 text-sm text-muted-foreground">
                {selectedFiles.slice(0, 4).map((selected) => (
                  <p key={`${selected.name}-${selected.size}`}>{selected.name}</p>
                ))}
                {selectedFiles.length > 4 ? (
                  <p>+ {selectedFiles.length - 4} arquivo(s)</p>
                ) : null}
              </div>
            </div>
          </>
        ) : (
          <>
            <UploadCloudIcon className="size-8 text-primary" />
            <div>
              <p className="font-semibold text-foreground">{emptyTitle}</p>
              <p className="text-sm text-muted-foreground">
                {emptyDescription ??
                  `Limite de ${(maxSize / 1024 / 1024).toFixed(0)} MB por arquivo`}
              </p>
            </div>
          </>
        )
      ) : selectedFile ? (
        <>
          {isTextUpload ? (
            <FileTextIcon className="size-8 text-primary" />
          ) : (
            <FileIcon className="size-8 text-primary" />
          )}
          <div>
            <p className="font-semibold text-foreground">{selectedFile.name}</p>
            <p className="text-sm text-muted-foreground">
              {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
            </p>
          </div>
        </>
      ) : (
        <>
          <UploadCloudIcon className="size-8 text-primary" />
          <div>
            <p className="font-semibold text-foreground">
              {emptyTitle}
            </p>
            <p className="text-sm text-muted-foreground">
              {emptyDescription ??
                `Limite de ${(maxSize / 1024 / 1024).toFixed(0)} MB por arquivo`}
            </p>
          </div>
        </>
      )}
    </div>
  );
}
