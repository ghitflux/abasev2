import React from 'react';
import type { Preview } from '@storybook/react-vite';
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
      options: {
        light: { name: 'light', value: '#ffffff' },
        dark: { name: 'dark', value: '#000000' },
        gray: { name: 'gray', value: '#f5f5f5' }
      }
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

  initialGlobals: {
    backgrounds: {
      value: 'light'
    }
  }
};

export default preview;
