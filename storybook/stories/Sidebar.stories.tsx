import type { Meta, StoryObj } from '@storybook/react-vite';
import React from 'react';
import { Sidebar } from '@abase/ui';
import {
  ChatBubbleIcon,
  LayersIcon,
  ComponentInstanceIcon,
  HomeIcon,
  GearIcon,
  ReaderIcon,
} from '@radix-ui/react-icons';

const meta: Meta<typeof Sidebar> = {
  title: 'Components/Sidebar',
  component: Sidebar,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof Sidebar>;

export const ClaudeStyle: Story = {
  args: {
    logo: (
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
          <span className="text-white font-bold text-sm">C</span>
        </div>
        <span className="font-semibold text-foreground">Claude</span>
      </div>
    ),
    onNewChat: () => alert('Novo chat!'),
    sections: [
      {
        items: [
          {
            id: 'conversas',
            label: 'Conversas',
            icon: <ChatBubbleIcon className="w-4 h-4" />,
          },
          {
            id: 'projetos',
            label: 'Projetos',
            icon: <LayersIcon className="w-4 h-4" />,
          },
          {
            id: 'artefatos',
            label: 'Artefatos',
            icon: <ComponentInstanceIcon className="w-4 h-4" />,
          },
        ],
      },
    ],
    favorites: [
      {
        id: 'fav1',
        label: 'Dev Python | Abase',
      },
      {
        id: 'fav2',
        label: 'Família Venâncio',
      },
      {
        id: 'fav3',
        label: 'Dev Ruby',
      },
    ],
    recents: [
      {
        id: 'rec1',
        label: 'Abase V2 project planning',
      },
      {
        id: 'rec2',
        label: 'Mobile app development strategy',
      },
      {
        id: 'rec3',
        label: 'Casual greeting',
      },
      {
        id: 'rec4',
        label: 'Weekly consumption cost calculator implementation',
      },
      {
        id: 'rec5',
        label: 'Cardápio Familiar para Home Office',
      },
      {
        id: 'rec6',
        label: 'Ruby on Rails vs Django for SaaS Startups',
      },
      {
        id: 'rec7',
        label: 'Lovable Software Project Complete Guide',
      },
      {
        id: 'rec8',
        label: 'API NFe Xml',
      },
    ],
  },
};

export const WithUser: Story = {
  args: {
    ...ClaudeStyle.args,
    user: {
      name: 'João Silva',
      email: 'joao@example.com',
      avatar: 'https://i.pravatar.cc/150?u=user1',
    },
  },
};

export const SimpleMenu: Story = {
  args: {
    logo: (
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
          <span className="text-white font-bold text-sm">A</span>
        </div>
        <span className="font-semibold text-foreground">ABASE</span>
      </div>
    ),
    sections: [
      {
        items: [
          {
            id: 'home',
            label: 'Início',
            icon: <HomeIcon className="w-4 h-4" />,
          },
          {
            id: 'cadastros',
            label: 'Cadastros',
            icon: <ReaderIcon className="w-4 h-4" />,
            badge: '12',
          },
          {
            id: 'analise',
            label: 'Análise',
            icon: <LayersIcon className="w-4 h-4" />,
            badge: '5',
          },
          {
            id: 'tesouraria',
            label: 'Tesouraria',
            icon: <ComponentInstanceIcon className="w-4 h-4" />,
            badge: '3',
          },
          {
            id: 'config',
            label: 'Configurações',
            icon: <GearIcon className="w-4 h-4" />,
          },
        ],
      },
    ],
    user: {
      name: 'Admin',
      email: 'admin@abase.com.br',
      avatar: 'https://i.pravatar.cc/150?u=admin',
    },
  },
};

export const WithMultipleSections: Story = {
  args: {
    sections: [
      {
        title: 'Principal',
        items: [
          {
            id: 'home',
            label: 'Início',
            icon: <HomeIcon className="w-4 h-4" />,
          },
          {
            id: 'projetos',
            label: 'Projetos',
            icon: <LayersIcon className="w-4 h-4" />,
          },
        ],
      },
      {
        title: 'Gestão',
        items: [
          {
            id: 'cadastros',
            label: 'Cadastros',
            icon: <ReaderIcon className="w-4 h-4" />,
          },
          {
            id: 'analise',
            label: 'Análise',
            icon: <ComponentInstanceIcon className="w-4 h-4" />,
          },
        ],
      },
    ],
    user: {
      name: 'Maria Santos',
      avatar: 'https://i.pravatar.cc/150?u=user2',
    },
  },
};

export const WithCustomStyling: Story = {
  args: {
    ...ClaudeStyle.args,
    className: 'border-r-4 border-primary',
  },
};

export const Minimal: Story = {
  args: {
    sections: [
      {
        items: [
          {
            id: 'item1',
            label: 'Item 1',
          },
          {
            id: 'item2',
            label: 'Item 2',
          },
          {
            id: 'item3',
            label: 'Item 3',
          },
        ],
      },
    ],
  },
};
