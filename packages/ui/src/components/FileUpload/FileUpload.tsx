"use client";

import React, { useCallback, useState } from 'react';
import { Button, Card, CardBody, Progress } from '@heroui/react';
import { cn } from '../../utils/cn';

export interface FileUploadProps {
  onFileSelect: (file: File) => void;
  onFileRemove?: () => void;
  accept?: string;
  maxSize?: number; // in MB
  multiple?: boolean;
  disabled?: boolean;
  className?: string;
  placeholder?: string;
  currentFile?: File | null;
  uploadProgress?: number;
  isUploading?: boolean;
  error?: string;
}

export function FileUpload({
  onFileSelect,
  onFileRemove,
  accept = "*/*",
  maxSize = 10,
  multiple = false,
  disabled = false,
  className,
  placeholder = "Arraste e solte um arquivo aqui ou clique para selecionar",
  currentFile,
  uploadProgress,
  isUploading = false,
  error,
}: FileUploadProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [internalError, setInternalError] = useState<string>("");

  const validateFile = useCallback((file: File): string | null => {
    // Check file size
    if (file.size > maxSize * 1024 * 1024) {
      return `Arquivo muito grande. Tamanho máximo: ${maxSize}MB`;
    }

    // Check file type if accept is specified
    if (accept !== "*/*") {
      const acceptedTypes = accept.split(',').map(type => type.trim());
      const fileType = file.type;
      const fileName = file.name.toLowerCase();
      
      const isAccepted = acceptedTypes.some(type => {
        if (type.startsWith('.')) {
          // Extension check
          return fileName.endsWith(type.toLowerCase());
        } else if (type.includes('*')) {
          // MIME type with wildcard
          const baseType = type.split('/')[0];
          return fileType.startsWith(baseType);
        } else {
          // Exact MIME type
          return fileType === type;
        }
      });

      if (!isAccepted) {
        return `Tipo de arquivo não permitido. Tipos aceitos: ${accept}`;
      }
    }

    return null;
  }, [accept, maxSize]);

  const handleFileSelect = useCallback((file: File) => {
    const validationError = validateFile(file);
    if (validationError) {
      setInternalError(validationError);
      return;
    }

    setInternalError("");
    onFileSelect(file);
  }, [validateFile, onFileSelect]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);

    if (disabled) return;

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      const file = files[0];
      handleFileSelect(file);
    }
  }, [disabled, handleFileSelect]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) {
      setIsDragOver(true);
    }
  }, [disabled]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleFileInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const file = files[0];
      handleFileSelect(file);
    }
  }, [handleFileSelect]);

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const displayError = error || internalError;

  return (
    <div className={cn("w-full", className)}>
      <Card
        className={cn(
          "border-2 border-dashed transition-colors",
          isDragOver && !disabled && "border-primary bg-primary-50",
          disabled && "opacity-50 cursor-not-allowed",
          displayError && "border-danger",
          !displayError && !isDragOver && "border-default-300"
        )}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        <CardBody className="p-6">
          <div className="flex flex-col items-center justify-center text-center space-y-4">
            {/* Upload Icon */}
            <div className="text-4xl text-default-400">
              {isUploading ? (
                <div className="animate-spin">⏳</div>
              ) : (
                <svg
                  className="w-12 h-12 mx-auto"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
              )}
            </div>

            {/* Content */}
            <div className="space-y-2">
              <p className="text-sm text-default-600">
                {placeholder}
              </p>
              
              {!multiple && (
                <p className="text-xs text-default-400">
                  Tamanho máximo: {maxSize}MB
                </p>
              )}
            </div>

            {/* File Input */}
            <input
              type="file"
              accept={accept}
              multiple={multiple}
              onChange={handleFileInputChange}
              disabled={disabled}
              className="hidden"
              id="file-upload-input"
            />

            {/* Upload Button */}
            <Button
              as="label"
              htmlFor="file-upload-input"
              color="primary"
              variant="bordered"
              size="sm"
              disabled={disabled || isUploading}
              className="cursor-pointer"
            >
              {isUploading ? "Enviando..." : "Selecionar Arquivo"}
            </Button>

            {/* Current File Display */}
            {currentFile && (
              <div className="w-full mt-4 p-3 bg-default-100 rounded-lg">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <div className="text-sm">
                      <p className="font-medium text-default-700">
                        {currentFile.name}
                      </p>
                      <p className="text-xs text-default-500">
                        {formatFileSize(currentFile.size)}
                      </p>
                    </div>
                  </div>
                  
                  {onFileRemove && (
                    <Button
                      size="sm"
                      variant="light"
                      color="danger"
                      onPress={onFileRemove}
                      disabled={isUploading}
                    >
                      Remover
                    </Button>
                  )}
                </div>

                {/* Upload Progress */}
                {isUploading && uploadProgress !== undefined && (
                  <div className="mt-2">
                    <Progress
                      value={uploadProgress}
                      color="primary"
                      size="sm"
                      className="w-full"
                    />
                    <p className="text-xs text-default-500 mt-1">
                      {uploadProgress}% concluído
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Error Display */}
            {displayError && (
              <div className="w-full mt-2 p-2 bg-danger-50 border border-danger-200 rounded text-sm text-danger-600">
                {displayError}
              </div>
            )}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
