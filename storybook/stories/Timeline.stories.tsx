import type { Meta, StoryObj } from '@storybook/react-vite';
import React from 'react';
import { Timeline, StatusTimeline, TimelineEvent } from '@abase/ui';
import { CheckCircle, Clock, XCircle, FileText } from 'lucide-react';

const meta: Meta<typeof Timeline> = {
  title: 'Components/Timeline',
  component: Timeline,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof Timeline>;

const sampleEvents: TimelineEvent[] = [
  {
    id: '1',
    title: 'Cadastro Criado',
    description: 'Novo cadastro foi iniciado no sistema',
    timestamp: new Date('2024-01-15T10:00:00'),
    status: 'completed',
    user: 'João Silva',
  },
  {
    id: '2',
    title: 'Documentos Enviados',
    description: 'Todos os documentos necessários foram anexados',
    timestamp: new Date('2024-01-15T14:30:00'),
    status: 'completed',
    user: 'João Silva',
  },
  {
    id: '3',
    title: 'Em Análise',
    description: 'Cadastro está sendo analisado pela equipe',
    timestamp: new Date('2024-01-16T09:00:00'),
    status: 'current',
    user: 'Maria Santos (Analista)',
  },
  {
    id: '4',
    title: 'Aprovação Final',
    description: 'Aguardando aprovação do gestor',
    timestamp: new Date('2024-01-17T00:00:00'),
    status: 'pending',
  },
];

export const Default: Story = {
  args: {
    events: sampleEvents,
  },
};

export const CompletedProcess: Story = {
  args: {
    events: [
      {
        id: '1',
        title: 'Cadastro Criado',
        description: 'Novo cadastro iniciado',
        timestamp: new Date('2024-01-15T10:00:00'),
        status: 'completed',
        user: 'João Silva',
      },
      {
        id: '2',
        title: 'Análise Aprovada',
        description: 'Cadastro aprovado pela equipe de análise',
        timestamp: new Date('2024-01-16T14:00:00'),
        status: 'completed',
        user: 'Maria Santos',
      },
      {
        id: '3',
        title: 'Pagamento Recebido',
        description: 'Pagamento confirmado no valor de R$ 150,00',
        timestamp: new Date('2024-01-17T10:30:00'),
        status: 'completed',
        user: 'Sistema',
      },
      {
        id: '4',
        title: 'Contrato Assinado',
        description: 'Contrato assinado digitalmente',
        timestamp: new Date('2024-01-18T16:00:00'),
        status: 'completed',
        user: 'João Silva',
      },
    ],
  },
};

export const WithError: Story = {
  args: {
    events: [
      {
        id: '1',
        title: 'Cadastro Criado',
        description: 'Novo cadastro iniciado',
        timestamp: new Date('2024-01-15T10:00:00'),
        status: 'completed',
      },
      {
        id: '2',
        title: 'Documentação Incompleta',
        description: 'Faltam documentos obrigatórios: RG e Comprovante de Residência',
        timestamp: new Date('2024-01-16T14:00:00'),
        status: 'error',
        user: 'Sistema',
      },
      {
        id: '3',
        title: 'Aguardando Correção',
        description: 'Associado foi notificado sobre os documentos faltantes',
        timestamp: new Date('2024-01-16T14:05:00'),
        status: 'pending',
      },
    ],
  },
};

export const WithCustomIcons: Story = {
  args: {
    events: [
      {
        id: '1',
        title: 'Aprovado',
        description: 'Cadastro aprovado com sucesso',
        timestamp: new Date('2024-01-15T10:00:00'),
        status: 'completed',
        icon: <CheckCircle size={16} className="text-white" />,
      },
      {
        id: '2',
        title: 'Em Processamento',
        description: 'Processando documentação',
        timestamp: new Date('2024-01-16T14:00:00'),
        status: 'current',
        icon: <Clock size={16} className="text-white" />,
      },
      {
        id: '3',
        title: 'Erro',
        description: 'Falha no processamento',
        timestamp: new Date('2024-01-17T09:00:00'),
        status: 'error',
        icon: <XCircle size={16} className="text-white" />,
      },
      {
        id: '4',
        title: 'Pendente',
        description: 'Aguardando documentos',
        timestamp: new Date('2024-01-18T00:00:00'),
        status: 'pending',
        icon: <FileText size={16} className="text-default-400" />,
      },
    ],
  },
};

export const CompactVariant: Story = {
  args: {
    events: sampleEvents,
    variant: 'compact',
  },
};

export const DetailedVariant: Story = {
  args: {
    events: [
      {
        id: '1',
        title: 'Cadastro Criado',
        description: 'Novo cadastro foi iniciado',
        timestamp: new Date('2024-01-15T10:00:00'),
        status: 'completed',
        user: 'João Silva',
        metadata: {
          'IP': '192.168.1.1',
          'Navegador': 'Chrome 120',
          'Tipo': 'Novo Associado',
        },
      },
      {
        id: '2',
        title: 'Documentos Enviados',
        description: 'Documentos anexados',
        timestamp: new Date('2024-01-15T14:30:00'),
        status: 'completed',
        user: 'João Silva',
        metadata: {
          'Documentos': '5 arquivos',
          'Tamanho Total': '2.5 MB',
        },
      },
    ],
    variant: 'detailed',
  },
};

export const WithoutTimestamps: Story = {
  args: {
    events: sampleEvents,
    showTimestamps: false,
  },
};

export const WithoutUsers: Story = {
  args: {
    events: sampleEvents,
    showUser: false,
  },
};

export const WithMaxHeight: Story = {
  args: {
    events: [
      ...sampleEvents,
      {
        id: '5',
        title: 'Evento 5',
        description: 'Descrição do evento 5',
        timestamp: new Date('2024-01-18T10:00:00'),
        status: 'pending',
      },
      {
        id: '6',
        title: 'Evento 6',
        description: 'Descrição do evento 6',
        timestamp: new Date('2024-01-19T10:00:00'),
        status: 'pending',
      },
    ],
    maxHeight: '400px',
  },
};

export const StatusTimelineRascunho: Story = {
  render: () => <StatusTimeline status="RASCUNHO" />,
};

export const StatusTimelineEmAnalise: Story = {
  render: () => <StatusTimeline status="EM_ANALISE" />,
};

export const StatusTimelineAprovado: Story = {
  render: () => <StatusTimeline status="APROVADO" />,
};

export const StatusTimelineConcluido: Story = {
  render: () => <StatusTimeline status="CONCLUIDO" />,
};

export const Empty: Story = {
  args: {
    events: [],
  },
};
