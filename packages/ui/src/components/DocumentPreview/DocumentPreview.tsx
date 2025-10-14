"use client";

import React, { useState, useRef, useEffect } from 'react';
import { Button, Card, CardBody, Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, useDisclosure } from '@heroui/react';
import { cn } from '../../utils/cn';

export interface DocumentPreviewProps {
  file: File | string; // File object or URL
  fileName?: string;
  fileType?: string;
  fileSize?: number;
  className?: string;
  showDownload?: boolean;
  showFullscreen?: boolean;
  maxWidth?: string;
  maxHeight?: string;
  onDownload?: () => void;
  onRemove?: () => void;
}

export function DocumentPreview({
  file,
  fileName,
  fileType,
  fileSize,
  className,
  showDownload = true,
  showFullscreen = true,
  maxWidth = "300px",
  maxHeight = "400px",
  onDownload,
  onRemove,
}: DocumentPreviewProps) {
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [isImage, setIsImage] = useState(false);
  const [isPdf, setIsPdf] = useState(false);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Determine file info
  const getFileInfo = () => {
    if (typeof file === 'string') {
      // URL provided
      const url = file;
      const name = fileName || url.split('/').pop() || 'documento';
      const type = fileType || getFileTypeFromUrl(url);
      return { url, name, type };
    } else {
      // File object provided
      const url = URL.createObjectURL(file);
      const name = fileName || file.name;
      const type = fileType || file.type;
      return { url, name, type };
    }
  };

  const getFileTypeFromUrl = (url: string): string => {
    const extension = url.split('.').pop()?.toLowerCase();
    const mimeTypes: Record<string, string> = {
      'pdf': 'application/pdf',
      'jpg': 'image/jpeg',
      'jpeg': 'image/jpeg',
      'png': 'image/png',
      'gif': 'image/gif',
      'webp': 'image/webp',
      'svg': 'image/svg+xml',
      'doc': 'application/msword',
      'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'xls': 'application/vnd.ms-excel',
      'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    };
    return mimeTypes[extension || ''] || 'application/octet-stream';
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getFileIcon = (type: string): React.ReactNode => {
    if (type.startsWith('image/')) {
      return (
        <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 20 20">
          <path
            fillRule="evenodd"
            d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z"
            clipRule="evenodd"
          />
        </svg>
      );
    } else if (type === 'application/pdf') {
      return (
        <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 20 20">
          <path
            fillRule="evenodd"
            d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z"
            clipRule="evenodd"
          />
        </svg>
      );
    } else {
      return (
        <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 20 20">
          <path
            fillRule="evenodd"
            d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"
            clipRule="evenodd"
          />
        </svg>
      );
    }
  };

  useEffect(() => {
    const { url, type } = getFileInfo();
    
    setIsImage(type.startsWith('image/'));
    setIsPdf(type === 'application/pdf');
    setPreviewUrl(url);
    setIsLoading(false);

    return () => {
      if (typeof file !== 'string' && url.startsWith('blob:')) {
        URL.revokeObjectURL(url);
      }
    };
  }, [file]);

  const handleDownload = () => {
    if (onDownload) {
      onDownload();
    } else {
      const link = document.createElement('a');
      link.href = previewUrl;
      link.download = getFileInfo().name;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  const renderPreview = () => {
    if (isLoading) {
      return (
        <div className="flex items-center justify-center h-48">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </div>
      );
    }

    if (error) {
      return (
        <div className="flex flex-col items-center justify-center h-48 text-danger">
          <svg className="w-12 h-12 mb-2" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
              clipRule="evenodd"
            />
          </svg>
          <p className="text-sm">{error}</p>
        </div>
      );
    }

    if (isImage) {
      return (
        <img
          src={previewUrl}
          alt={getFileInfo().name}
          className="w-full h-full object-contain"
          onError={() => setError('Erro ao carregar imagem')}
        />
      );
    }

    if (isPdf) {
      return (
        <iframe
          src={previewUrl}
          className="w-full h-full border-0"
          title={getFileInfo().name}
          onError={() => setError('Erro ao carregar PDF')}
        />
      );
    }

    // Generic file preview
    return (
      <div className="flex flex-col items-center justify-center h-48 text-default-500">
        {getFileIcon(getFileInfo().type)}
        <p className="text-sm mt-2 text-center px-2">
          {getFileInfo().name}
        </p>
        {fileSize && (
          <p className="text-xs text-default-400 mt-1">
            {formatFileSize(fileSize)}
          </p>
        )}
      </div>
    );
  };

  return (
    <>
      <Card className={cn("w-full", className)}>
        <CardBody className="p-0">
          <div
            className="relative overflow-hidden"
            style={{ maxWidth, maxHeight }}
          >
            {renderPreview()}
            
            {/* Overlay Actions */}
            <div className="absolute top-2 right-2 flex space-x-1">
              {showFullscreen && (
                <Button
                  size="sm"
                  variant="flat"
                  color="default"
                  isIconOnly
                  onPress={onOpen}
                  className="bg-white/80 backdrop-blur-sm"
                >
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fillRule="evenodd"
                      d="M3 4a1 1 0 011-1h4a1 1 0 010 2H6.414l2.293 2.293a1 1 0 01-1.414 1.414L5 6.414V8a1 1 0 01-2 0V4zm9 1a1 1 0 010-2h4a1 1 0 011 1v4a1 1 0 01-2 0V6.414l-2.293 2.293a1 1 0 11-1.414-1.414L13.586 5H12zm-9 7a1 1 0 012 0v1.586l2.293-2.293a1 1 0 111.414 1.414L6.414 15H8a1 1 0 010 2H4a1 1 0 01-1-1v-4zm13-1a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 010-2h1.586l-2.293-2.293a1 1 0 111.414-1.414L15 13.586V12a1 1 0 011-1z"
                      clipRule="evenodd"
                    />
                  </svg>
                </Button>
              )}
              
              {onRemove && (
                <Button
                  size="sm"
                  variant="flat"
                  color="danger"
                  isIconOnly
                  onPress={onRemove}
                  className="bg-white/80 backdrop-blur-sm"
                >
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fillRule="evenodd"
                      d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                      clipRule="evenodd"
                    />
                  </svg>
                </Button>
              )}
            </div>
          </div>
          
          {/* File Info */}
          <div className="p-3 border-t border-default-200">
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-default-900 truncate">
                  {getFileInfo().name}
                </p>
                {fileSize && (
                  <p className="text-xs text-default-500">
                    {formatFileSize(fileSize)}
                  </p>
                )}
              </div>
              
              {showDownload && (
                <Button
                  size="sm"
                  variant="light"
                  color="primary"
                  onPress={handleDownload}
                >
                  Download
                </Button>
              )}
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Fullscreen Modal */}
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        size="5xl"
        scrollBehavior="inside"
      >
        <ModalContent>
          <ModalHeader className="flex flex-col gap-1">
            {getFileInfo().name}
          </ModalHeader>
          <ModalBody>
            <div className="w-full h-96">
              {renderPreview()}
            </div>
          </ModalBody>
          <ModalFooter>
            <Button color="danger" variant="light" onPress={onClose}>
              Fechar
            </Button>
            {showDownload && (
              <Button color="primary" onPress={handleDownload}>
                Download
              </Button>
            )}
          </ModalFooter>
        </ModalContent>
      </Modal>
    </>
  );
}
