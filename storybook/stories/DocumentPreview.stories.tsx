import type { Meta, StoryObj } from '@storybook/react-vite';
import React from 'react';
import { DocumentPreview } from '@abase/ui';

const meta: Meta<typeof DocumentPreview> = {
  title: 'Components/DocumentPreview',
  component: DocumentPreview,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof DocumentPreview>;

export const PDFDocument: Story = {
  args: {
    url: 'https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf',
    type: 'pdf',
    title: 'Contrato de Associação',
  },
};

export const ImageDocument: Story = {
  args: {
    url: 'https://via.placeholder.com/600x400',
    type: 'image',
    title: 'Comprovante de Residência',
  },
};

export const WithActions: Story = {
  args: {
    url: 'https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf',
    type: 'pdf',
    title: 'Documento Oficial',
    onDownload: () => alert('Baixando documento...'),
    onPrint: () => alert('Imprimindo documento...'),
  },
};
