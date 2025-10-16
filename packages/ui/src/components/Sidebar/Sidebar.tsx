'use client';

import React, { useState } from 'react';
import { Button, Divider, Avatar } from '@heroui/react';
import { cn } from '../../utils/cn';
import {
  PlusIcon,
  ChatBubbleIcon,
  LayersIcon,
  ComponentInstanceIcon,
  StarIcon,
  HomeIcon,
} from '@radix-ui/react-icons';

export interface SidebarItem {
  id: string;
  label: string;
  icon?: React.ReactNode;
  href?: string;
  onClick?: () => void;
  badge?: string | number;
}

export interface SidebarSection {
  title?: string;
  items: SidebarItem[];
}

export interface SidebarProps {
  sections?: SidebarSection[];
  favorites?: SidebarItem[];
  recents?: SidebarItem[];
  className?: string;
  logo?: React.ReactNode;
  user?: {
    name: string;
    avatar?: string;
    email?: string;
  };
  onNewChat?: () => void;
}

export function Sidebar({
  sections = [],
  favorites = [],
  recents = [],
  className,
  logo,
  user,
  onNewChat,
}: SidebarProps) {
  const [activeItem, setActiveItem] = useState<string | null>(null);

  const handleItemClick = (item: SidebarItem) => {
    setActiveItem(item.id);
    if (item.onClick) {
      item.onClick();
    }
  };

  return (
    <aside
      className={cn(
        'flex h-screen w-64 flex-col bg-content1 border-r border-divider',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4">
        {logo || (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <span className="text-white font-bold text-sm">C</span>
            </div>
            <span className="font-semibold text-foreground">Claude</span>
          </div>
        )}
      </div>

      {/* New Chat Button */}
      {onNewChat && (
        <div className="px-3 mb-2">
          <Button
            fullWidth
            color="default"
            variant="flat"
            startContent={<PlusIcon className="w-4 h-4" />}
            onPress={onNewChat}
            className="justify-start"
          >
            Novo bate-papo
          </Button>
        </div>
      )}

      {/* Main Sections */}
      <nav className="flex-1 overflow-y-auto px-3 space-y-1">
        {sections.map((section, idx) => (
          <div key={idx}>
            {section.items.map((item) => (
              <Button
                key={item.id}
                fullWidth
                variant={activeItem === item.id ? 'flat' : 'light'}
                color={activeItem === item.id ? 'primary' : 'default'}
                startContent={item.icon}
                onPress={() => handleItemClick(item)}
                className={cn(
                  'justify-start mb-1',
                  activeItem === item.id && 'bg-default-100'
                )}
              >
                <span className="flex-1 text-left truncate">{item.label}</span>
                {item.badge && (
                  <span className="text-xs bg-default-200 px-2 py-0.5 rounded-full">
                    {item.badge}
                  </span>
                )}
              </Button>
            ))}
          </div>
        ))}

        {/* Favorites Section */}
        {favorites.length > 0 && (
          <div className="py-2">
            <p className="text-xs font-semibold text-default-500 px-3 mb-2">
              Favoritos
            </p>
            {favorites.map((item) => (
              <Button
                key={item.id}
                fullWidth
                variant="light"
                startContent={
                  item.icon || <StarIcon className="w-4 h-4" />
                }
                onPress={() => handleItemClick(item)}
                className="justify-start mb-1 text-sm"
              >
                <span className="flex-1 text-left truncate">{item.label}</span>
              </Button>
            ))}
          </div>
        )}

        {/* Recents Section */}
        {recents.length > 0 && (
          <div className="py-2">
            <p className="text-xs font-semibold text-default-500 px-3 mb-2">
              Recentes
            </p>
            {recents.map((item) => (
              <Button
                key={item.id}
                fullWidth
                variant="light"
                onPress={() => handleItemClick(item)}
                className="justify-start mb-1 text-sm h-auto py-2"
              >
                <span className="flex-1 text-left line-clamp-2 text-default-600">
                  {item.label}
                </span>
              </Button>
            ))}
          </div>
        )}
      </nav>

      {/* Footer / User Info */}
      {user && (
        <>
          <Divider />
          <div className="p-3">
            <Button
              fullWidth
              variant="light"
              className="justify-start h-auto py-2"
            >
              <Avatar
                size="sm"
                src={user.avatar}
                name={user.name}
                className="flex-shrink-0"
              />
              <div className="flex-1 text-left ml-2">
                <p className="text-sm font-medium">{user.name}</p>
                {user.email && (
                  <p className="text-xs text-default-500">{user.email}</p>
                )}
              </div>
            </Button>
          </div>
        </>
      )}
    </aside>
  );
}

// Export compound components
Sidebar.displayName = 'Sidebar';
