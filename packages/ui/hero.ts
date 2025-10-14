import { heroui } from '@heroui/react';

const heroPlugin = heroui({
  themes: {
    light: {
      colors: {
        background: '#FFFFFF',
        foreground: '#11181C',
        primary: {
          DEFAULT: '#0072f5',
          foreground: '#FFFFFF',
        },
        focus: '#0072f5',
      },
    },
    dark: {
      colors: {
        background: '#000000',
        foreground: '#ECEDEE',
        primary: {
          DEFAULT: '#0072f5',
          foreground: '#FFFFFF',
        },
        focus: '#0072f5',
      },
    },
  },
});

export default heroPlugin;
