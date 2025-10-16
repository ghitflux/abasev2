import React, { useEffect } from 'react';
import type { Preview, Decorator } from '@storybook/react-vite';
import { HeroUIProvider } from '@heroui/system';
import { ToastProvider } from '@abase/ui';
import { withThemeByClassName } from '@storybook/addon-themes';
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
      disable: true,
    },
  },

  decorators: [
    withThemeByClassName({
      themes: {
        light: 'light',
        dark: 'dark',
      },
      defaultTheme: 'light',
    }) as Decorator,
    (Story, context) => {
      const theme = context.globals.theme || 'light';

      useEffect(() => {
        const root = document.documentElement;
        root.classList.remove('light', 'dark');
        root.classList.add(theme);
        root.style.colorScheme = theme;
      }, [theme]);

      return (
        <div className={`${theme} min-h-screen`}>
          <div className="bg-background text-foreground min-h-screen">
            <HeroUIProvider>
              <ToastProvider>
                <Story />
              </ToastProvider>
            </HeroUIProvider>
          </div>
        </div>
      );
    },
  ],
};

export default preview;
