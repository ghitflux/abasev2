import type { Meta, StoryObj } from '@storybook/react-vite';
import React, { useState } from 'react';
import { FileUpload, useToast } from '@abase/ui';

const meta: Meta<typeof FileUpload> = {
  title: 'Components/FileUpload',
  component: FileUpload,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof FileUpload>;

export const Default: Story = {
  render: function DefaultStory() {
    const { addToast } = useToast();
    const [file, setFile] = useState<File | null>(null);

    return (
      <FileUpload
        onFileSelect={(selectedFile) => {
          setFile(selectedFile);
          addToast({
            type: 'success',
            title: 'Arquivo selecionado',
            description: `${selectedFile.name} (${(selectedFile.size / 1024).toFixed(2)} KB)`,
          });
        }}
        onFileRemove={() => {
          setFile(null);
          addToast({ type: 'info', title: 'Arquivo removido' });
        }}
        currentFile={file}
      />
    );
  },
};

export const WithProgress: Story = {
  render: function WithProgressStory() {
    const { addToast } = useToast();
    const [file, setFile] = useState<File | null>(null);
    const [progress, setProgress] = useState(0);
    const [isUploading, setIsUploading] = useState(false);

    const simulateUpload = (selectedFile: File) => {
      setFile(selectedFile);
      setIsUploading(true);
      setProgress(0);

      const interval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 100) {
            clearInterval(interval);
            setIsUploading(false);
            addToast({ type: 'success', title: 'Upload concluído!' });
            return 100;
          }
          return prev + 10;
        });
      }, 300);
    };

    return (
      <FileUpload
        onFileSelect={simulateUpload}
        onFileRemove={() => {
          setFile(null);
          setProgress(0);
        }}
        currentFile={file}
        uploadProgress={progress}
        isUploading={isUploading}
      />
    );
  },
};

export const ImagesOnly: Story = {
  render: function ImagesOnlyStory() {
    const { addToast } = useToast();
    const [file, setFile] = useState<File | null>(null);

    return (
      <FileUpload
        accept="image/*"
        maxSize={5}
        placeholder="Arraste uma imagem aqui ou clique para selecionar"
        onFileSelect={(selectedFile) => {
          setFile(selectedFile);
          addToast({ type: 'success', title: 'Imagem selecionada', description: selectedFile.name });
        }}
        onFileRemove={() => setFile(null)}
        currentFile={file}
      />
    );
  },
};

export const PDFOnly: Story = {
  render: function PDFOnlyStory() {
    const { addToast } = useToast();
    const [file, setFile] = useState<File | null>(null);

    return (
      <FileUpload
        accept=".pdf,application/pdf"
        maxSize={10}
        placeholder="Selecione um arquivo PDF (máx. 10MB)"
        onFileSelect={(selectedFile) => {
          setFile(selectedFile);
          addToast({ type: 'success', title: 'PDF selecionado', description: selectedFile.name });
        }}
        onFileRemove={() => setFile(null)}
        currentFile={file}
      />
    );
  },
};

export const DocumentsOnly: Story = {
  render: function DocumentsOnlyStory() {
    const { addToast } = useToast();
    const [file, setFile] = useState<File | null>(null);

    return (
      <FileUpload
        accept=".pdf,.doc,.docx,.xls,.xlsx,.txt"
        maxSize={15}
        placeholder="Documentos: PDF, Word, Excel, TXT"
        onFileSelect={(selectedFile) => {
          setFile(selectedFile);
          addToast({ type: 'success', title: 'Documento selecionado', description: selectedFile.name });
        }}
        onFileRemove={() => setFile(null)}
        currentFile={file}
      />
    );
  },
};

export const SmallFileSize: Story = {
  render: function SmallFileSizeStory() {
    const { addToast } = useToast();
    const [file, setFile] = useState<File | null>(null);

    return (
      <FileUpload
        maxSize={1}
        placeholder="Tamanho máximo: 1MB"
        onFileSelect={(selectedFile) => {
          setFile(selectedFile);
          addToast({ type: 'success', title: 'Arquivo selecionado', description: selectedFile.name });
        }}
        onFileRemove={() => setFile(null)}
        currentFile={file}
      />
    );
  },
};

export const WithError: Story = {
  render: function WithErrorStory() {
    const [file, setFile] = useState<File | null>(null);

    return (
      <FileUpload
        onFileSelect={(selectedFile) => setFile(selectedFile)}
        onFileRemove={() => setFile(null)}
        currentFile={file}
        error="Erro ao fazer upload. Tente novamente."
      />
    );
  },
};

export const Disabled: Story = {
  args: {
    disabled: true,
    placeholder: 'Upload desabilitado',
    onFileSelect: () => {},
  },
};

export const WithCustomPlaceholder: Story = {
  render: function WithCustomPlaceholderStory() {
    const { addToast } = useToast();
    const [file, setFile] = useState<File | null>(null);

    return (
      <FileUpload
        placeholder="📁 Clique aqui para anexar seu comprovante de residência"
        onFileSelect={(selectedFile) => {
          setFile(selectedFile);
          addToast({ type: 'success', title: 'Comprovante anexado!' });
        }}
        onFileRemove={() => setFile(null)}
        currentFile={file}
      />
    );
  },
};

export const MultipleUploads: Story = {
  render: function MultipleUploadsStory() {
    const { addToast } = useToast();
    const [file1, setFile1] = useState<File | null>(null);
    const [file2, setFile2] = useState<File | null>(null);
    const [file3, setFile3] = useState<File | null>(null);

    return (
      <div className="space-y-4">
        <div>
          <h3 className="text-sm font-medium mb-2">RG (frente e verso)</h3>
          <FileUpload
            accept="image/*,.pdf"
            placeholder="Anexe seu RG"
            onFileSelect={(file) => {
              setFile1(file);
              addToast({ type: 'success', title: 'RG anexado' });
            }}
            onFileRemove={() => setFile1(null)}
            currentFile={file1}
          />
        </div>

        <div>
          <h3 className="text-sm font-medium mb-2">CPF</h3>
          <FileUpload
            accept="image/*,.pdf"
            placeholder="Anexe seu CPF"
            onFileSelect={(file) => {
              setFile2(file);
              addToast({ type: 'success', title: 'CPF anexado' });
            }}
            onFileRemove={() => setFile2(null)}
            currentFile={file2}
          />
        </div>

        <div>
          <h3 className="text-sm font-medium mb-2">Comprovante de Residência</h3>
          <FileUpload
            accept="image/*,.pdf"
            placeholder="Anexe comprovante de residência"
            onFileSelect={(file) => {
              setFile3(file);
              addToast({ type: 'success', title: 'Comprovante anexado' });
            }}
            onFileRemove={() => setFile3(null)}
            currentFile={file3}
          />
        </div>
      </div>
    );
  },
};
