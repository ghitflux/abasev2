import React from 'react';
import type { Preview } from '@storybook/react';
import { HeroUIProvider } from '@heroui/system';
import { ToastProvider } from '@abase/ui';
import '../src/globals.css';

const preview: Preview = {
  parameters: {
    actions: { argTypesRegex: '^on[A-Z].*' },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/,
      },
    },
    layout: 'padded',
    backgrounds: {
      default: 'light',
      values: [
        { name: 'light', value: '#ffffff' },
        { name: 'dark', value: '#000000' },
        { name: 'gray', value: '#f5f5f5' },
      ],
    },
  },
  decorators: [
    (Story) => (
      <HeroUIProvider>
        <ToastProvider>
          <Story />
        </ToastProvider>
      </HeroUIProvider>
    ),
  ],
};

export default preview;
