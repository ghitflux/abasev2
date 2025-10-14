import type { Config } from 'tailwindcss';
import hero from '../packages/ui/hero';
import { tailwindThemeExtend } from '../packages/ui/tailwind-theme';

const config: Config = {
  content: [
    './stories/**/*.{js,jsx,ts,tsx,mdx}',
    './src/**/*.{js,jsx,ts,tsx}',
    '../apps/web/src/**/*.{ts,tsx}',
    '../packages/ui/src/**/*.{ts,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: tailwindThemeExtend,
  },
  plugins: [hero],
};

export default config;
