import type { Config } from 'tailwindcss';
import hero from '../../packages/ui/hero';
import { tailwindThemeExtend } from '../../packages/ui/tailwind-theme';

const config: Config = {
  content: [
    './src/**/*.{ts,tsx}',
    '../../packages/ui/src/**/*.{ts,tsx}',
    '../../packages/shared/src/**/*.{ts,tsx}',
    '../../node_modules/@heroui/theme/dist/**/*.{js,ts,jsx,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: tailwindThemeExtend,
  },
  plugins: [hero],
};

export default config;
