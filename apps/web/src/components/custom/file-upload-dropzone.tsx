"use client";

import { FileIcon, FileTextIcon, UploadCloudIcon } from "lucide-react";
import { useDropzone, type Accept } from "react-dropzone";

import { cn } from "@/lib/utils";

type FileUploadDropzoneProps = {
  accept?: Accept;
  maxSize?: number;
  onUpload?: (file: File) => void;
  isProcessing?: boolean;
  disabled?: boolean;
  className?: string;
  emptyTitle?: string;
  emptyDescription?: string;
  file?: File | null;
};

export default function FileUploadDropzone({
  accept,
  maxSize = 10 * 1024 * 1024,
  onUpload,
  isProcessing,
  disabled,
  className,
  emptyTitle = "Arraste um arquivo ou clique para selecionar",
  emptyDescription,
  file,
}: FileUploadDropzoneProps) {
  const { acceptedFiles, getInputProps, getRootProps, isDragActive } = useDropzone({
    accept,
    maxSize,
    multiple: false,
    disabled: disabled || isProcessing,
    onDropAccepted: (files) => {
      const [file] = files;
      if (file) onUpload?.(file);
    },
  });

  const selectedFile = file ?? acceptedFiles[0];
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
      {selectedFile ? (
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
