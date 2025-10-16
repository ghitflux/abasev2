import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import type { StorybookConfig } from '@storybook/react-vite';
import { mergeConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';

const require = createRequire(import.meta.url);

const config: StorybookConfig = {
  stories: ['../stories/**/*.stories.@(js|jsx|ts|tsx|mdx)'],
  addons: [
    getAbsolutePath("@storybook/addon-a11y"),
    getAbsolutePath("@storybook/addon-themes"),
    getAbsolutePath("@storybook/addon-docs")
  ],
  framework: {
    name: getAbsolutePath("@storybook/react-vite"),
    options: {},
  },
  typescript: {
    reactDocgen: 'react-docgen-typescript',
    reactDocgenTypescriptOptions: {
      shouldExtractLiteralValuesFromEnum: true,
      propFilter: (prop) => (prop.parent ? !/node_modules/.test(prop.parent.fileName) : true),
    },
  },
  core: {
    disableTelemetry: true,
  },
  async viteFinal(config) {
    return mergeConfig(config, {
      plugins: [react(), tailwindcss()],
    });
  },
};

export default config;

function getAbsolutePath(value: string): any {
  return dirname(require.resolve(join(value, "package.json")));
}
