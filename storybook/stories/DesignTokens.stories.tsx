import type { Meta, StoryObj } from '@storybook/react-vite';
import React from 'react';
import { Card, CardBody } from '@heroui/react';

const meta: Meta = {
  title: 'Foundations/Design Tokens',
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj;

export const ThemeOverview: Story = {
  render: () => (
    <div className="space-y-8">
      <section>
        <h2 className="text-2xl font-bold mb-4">ABASE Theme - Verde/Neon</h2>
        <p className="text-default-600 mb-6">
          Tema customizado com cores verde neon (#00ff18) como primária e roxo (#7828c8) como secundária.
          Suporte completo para light e dark mode com variantes 50-900.
        </p>

        <div className="grid grid-cols-2 gap-6">
          <Card>
            <CardBody className="p-6">
              <h3 className="text-lg font-semibold mb-3">🎨 Cor Primária</h3>
              <div className="flex items-center gap-3 mb-2">
                <div className="w-12 h-12 rounded-lg bg-primary" />
                <div>
                  <p className="font-semibold">Verde Neon</p>
                  <code className="text-xs">#00ff18</code>
                </div>
              </div>
              <p className="text-sm text-default-500">
                Usada para ações principais, destaques e elementos interativos importantes.
              </p>
            </CardBody>
          </Card>

          <Card>
            <CardBody className="p-6">
              <h3 className="text-lg font-semibold mb-3">🎨 Cor Secundária</h3>
              <div className="flex items-center gap-3 mb-2">
                <div className="w-12 h-12 rounded-lg bg-secondary" />
                <div>
                  <p className="font-semibold">Roxo</p>
                  <code className="text-xs">#7828c8</code>
                </div>
              </div>
              <p className="text-sm text-default-500">
                Usada para ações secundárias, elementos de suporte e variações visuais.
              </p>
            </CardBody>
          </Card>
        </div>
      </section>
    </div>
  ),
};

export const Colors: Story = {
  render: () => (
    <div className="space-y-8">
      <section>
        <h2 className="text-2xl font-bold mb-4">Cores do Sistema</h2>

        <h3 className="text-lg font-semibold mb-3 mt-6">Primary - Verde Neon (#00ff18)</h3>
        <div className="grid grid-cols-5 gap-4">
          {[50, 100, 200, 300, 400, 500, 600, 700, 800, 900].map((shade) => (
            <div key={shade} className="space-y-2">
              <div className={`h-20 rounded-lg bg-primary-${shade} border border-default-200`} />
              <p className="text-xs text-default-600">primary-{shade}</p>
              {shade === 500 && <p className="text-xs font-semibold text-primary">DEFAULT</p>}
            </div>
          ))}
        </div>

        <h3 className="text-lg font-semibold mb-3 mt-6">Secondary - Roxo (#7828c8)</h3>
        <div className="grid grid-cols-5 gap-4">
          {[50, 100, 200, 300, 400, 500, 600, 700, 800, 900].map((shade) => (
            <div key={shade} className="space-y-2">
              <div className={`h-20 rounded-lg bg-secondary-${shade}`} />
              <p className="text-xs text-default-600">secondary-{shade}</p>
              {shade === 500 && <p className="text-xs font-semibold text-secondary">DEFAULT</p>}
            </div>
          ))}
        </div>

        <h3 className="text-lg font-semibold mb-3 mt-6">Success</h3>
        <div className="grid grid-cols-5 gap-4">
          {[50, 100, 200, 300, 400, 500, 600, 700, 800, 900].map((shade) => (
            <div key={shade} className="space-y-2">
              <div className={`h-20 rounded-lg bg-success-${shade}`} />
              <p className="text-xs text-default-600">success-{shade}</p>
            </div>
          ))}
        </div>

        <h3 className="text-lg font-semibold mb-3 mt-6">Warning</h3>
        <div className="grid grid-cols-5 gap-4">
          {[50, 100, 200, 300, 400, 500, 600, 700, 800, 900].map((shade) => (
            <div key={shade} className="space-y-2">
              <div className={`h-20 rounded-lg bg-warning-${shade}`} />
              <p className="text-xs text-default-600">warning-{shade}</p>
            </div>
          ))}
        </div>

        <h3 className="text-lg font-semibold mb-3 mt-6">Danger</h3>
        <div className="grid grid-cols-5 gap-4">
          {[50, 100, 200, 300, 400, 500, 600, 700, 800, 900].map((shade) => (
            <div key={shade} className="space-y-2">
              <div className={`h-20 rounded-lg bg-danger-${shade}`} />
              <p className="text-xs text-default-600">danger-{shade}</p>
            </div>
          ))}
        </div>

        <h3 className="text-lg font-semibold mb-3 mt-6">Default (Neutral)</h3>
        <div className="grid grid-cols-5 gap-4">
          {[50, 100, 200, 300, 400, 500, 600, 700, 800, 900].map((shade) => (
            <div key={shade} className="space-y-2">
              <div className={`h-20 rounded-lg bg-default-${shade} border border-default-200`} />
              <p className="text-xs text-default-600">default-{shade}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  ),
};

export const Typography: Story = {
  render: () => (
    <div className="space-y-8">
      <section>
        <h2 className="text-2xl font-bold mb-6">Tipografia</h2>

        <div className="space-y-6">
          <div className="border-b border-default-200 pb-4">
            <h1 className="text-4xl font-bold mb-2">Heading 1</h1>
            <code className="text-xs text-default-500">text-4xl font-bold</code>
          </div>

          <div className="border-b border-default-200 pb-4">
            <h2 className="text-3xl font-bold mb-2">Heading 2</h2>
            <code className="text-xs text-default-500">text-3xl font-bold</code>
          </div>

          <div className="border-b border-default-200 pb-4">
            <h3 className="text-2xl font-semibold mb-2">Heading 3</h3>
            <code className="text-xs text-default-500">text-2xl font-semibold</code>
          </div>

          <div className="border-b border-default-200 pb-4">
            <h4 className="text-xl font-semibold mb-2">Heading 4</h4>
            <code className="text-xs text-default-500">text-xl font-semibold</code>
          </div>

          <div className="border-b border-default-200 pb-4">
            <h5 className="text-lg font-medium mb-2">Heading 5</h5>
            <code className="text-xs text-default-500">text-lg font-medium</code>
          </div>

          <div className="border-b border-default-200 pb-4">
            <p className="text-base mb-2">Body - Texto padrão do sistema</p>
            <code className="text-xs text-default-500">text-base</code>
          </div>

          <div className="border-b border-default-200 pb-4">
            <p className="text-sm mb-2">Small - Texto secundário</p>
            <code className="text-xs text-default-500">text-sm</code>
          </div>

          <div className="border-b border-default-200 pb-4">
            <p className="text-xs mb-2">Extra Small - Labels e hints</p>
            <code className="text-xs text-default-500">text-xs</code>
          </div>
        </div>
      </section>

      <section className="mt-8">
        <h3 className="text-xl font-semibold mb-4">Pesos de Fonte</h3>
        <div className="space-y-3">
          <p className="font-thin">Thin (100) - font-thin</p>
          <p className="font-light">Light (300) - font-light</p>
          <p className="font-normal">Normal (400) - font-normal</p>
          <p className="font-medium">Medium (500) - font-medium</p>
          <p className="font-semibold">Semibold (600) - font-semibold</p>
          <p className="font-bold">Bold (700) - font-bold</p>
          <p className="font-extrabold">Extrabold (800) - font-extrabold</p>
        </div>
      </section>
    </div>
  ),
};

export const Spacing: Story = {
  render: () => (
    <div className="space-y-8">
      <section>
        <h2 className="text-2xl font-bold mb-6">Espaçamentos</h2>

        <div className="space-y-4">
          {[0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24].map((size) => (
            <div key={size} className="flex items-center gap-4">
              <div className="w-16 text-sm text-default-600">{size * 4}px</div>
              <div className={`h-8 bg-primary-500 rounded`} style={{ width: `${size * 4}px` }} />
              <code className="text-xs text-default-500">p-{size} / m-{size} / gap-{size}</code>
            </div>
          ))}
        </div>
      </section>
    </div>
  ),
};

export const BorderRadius: Story = {
  render: () => (
    <div className="space-y-8">
      <section>
        <h2 className="text-2xl font-bold mb-6">Border Radius</h2>

        <div className="grid grid-cols-3 gap-6">
          <div className="space-y-2">
            <div className="h-20 bg-primary-500 rounded-none" />
            <p className="text-sm">None - rounded-none</p>
            <code className="text-xs text-default-500">0px</code>
          </div>

          <div className="space-y-2">
            <div className="h-20 bg-primary-500 rounded-sm" />
            <p className="text-sm">Small - rounded-sm</p>
            <code className="text-xs text-default-500">2px</code>
          </div>

          <div className="space-y-2">
            <div className="h-20 bg-primary-500 rounded" />
            <p className="text-sm">Default - rounded</p>
            <code className="text-xs text-default-500">4px</code>
          </div>

          <div className="space-y-2">
            <div className="h-20 bg-primary-500 rounded-md" />
            <p className="text-sm">Medium - rounded-md</p>
            <code className="text-xs text-default-500">6px</code>
          </div>

          <div className="space-y-2">
            <div className="h-20 bg-primary-500 rounded-lg" />
            <p className="text-sm">Large - rounded-lg</p>
            <code className="text-xs text-default-500">8px</code>
          </div>

          <div className="space-y-2">
            <div className="h-20 bg-primary-500 rounded-xl" />
            <p className="text-sm">XL - rounded-xl</p>
            <code className="text-xs text-default-500">12px</code>
          </div>

          <div className="space-y-2">
            <div className="h-20 bg-primary-500 rounded-2xl" />
            <p className="text-sm">2XL - rounded-2xl</p>
            <code className="text-xs text-default-500">16px</code>
          </div>

          <div className="space-y-2">
            <div className="h-20 bg-primary-500 rounded-3xl" />
            <p className="text-sm">3XL - rounded-3xl</p>
            <code className="text-xs text-default-500">24px</code>
          </div>

          <div className="space-y-2">
            <div className="h-20 w-20 bg-primary-500 rounded-full" />
            <p className="text-sm">Full - rounded-full</p>
            <code className="text-xs text-default-500">9999px</code>
          </div>
        </div>
      </section>
    </div>
  ),
};

export const Shadows: Story = {
  render: () => (
    <div className="space-y-8">
      <section>
        <h2 className="text-2xl font-bold mb-6">Sombras</h2>

        <div className="grid grid-cols-3 gap-8">
          <Card className="shadow-sm">
            <CardBody className="p-6">
              <p className="font-medium mb-2">Small</p>
              <code className="text-xs text-default-500">shadow-sm</code>
            </CardBody>
          </Card>

          <Card className="shadow">
            <CardBody className="p-6">
              <p className="font-medium mb-2">Default</p>
              <code className="text-xs text-default-500">shadow</code>
            </CardBody>
          </Card>

          <Card className="shadow-md">
            <CardBody className="p-6">
              <p className="font-medium mb-2">Medium</p>
              <code className="text-xs text-default-500">shadow-md</code>
            </CardBody>
          </Card>

          <Card className="shadow-lg">
            <CardBody className="p-6">
              <p className="font-medium mb-2">Large</p>
              <code className="text-xs text-default-500">shadow-lg</code>
            </CardBody>
          </Card>

          <Card className="shadow-xl">
            <CardBody className="p-6">
              <p className="font-medium mb-2">Extra Large</p>
              <code className="text-xs text-default-500">shadow-xl</code>
            </CardBody>
          </Card>

          <Card className="shadow-2xl">
            <CardBody className="p-6">
              <p className="font-medium mb-2">2XL</p>
              <code className="text-xs text-default-500">shadow-2xl</code>
            </CardBody>
          </Card>
        </div>
      </section>
    </div>
  ),
};

export const Borders: Story = {
  render: () => (
    <div className="space-y-8">
      <section>
        <h2 className="text-2xl font-bold mb-6">Bordas</h2>

        <h3 className="text-lg font-semibold mb-4">Espessuras</h3>
        <div className="space-y-4">
          <div className="border border-default-200 p-4 rounded-lg">
            <code className="text-sm">border (1px)</code>
          </div>
          <div className="border-2 border-default-200 p-4 rounded-lg">
            <code className="text-sm">border-2 (2px)</code>
          </div>
          <div className="border-4 border-default-200 p-4 rounded-lg">
            <code className="text-sm">border-4 (4px)</code>
          </div>
          <div className="border-8 border-default-200 p-4 rounded-lg">
            <code className="text-sm">border-8 (8px)</code>
          </div>
        </div>

        <h3 className="text-lg font-semibold mb-4 mt-6">Cores de Borda</h3>
        <div className="grid grid-cols-3 gap-4">
          <div className="border-2 border-default-200 p-4 rounded-lg">
            <code className="text-sm">border-default-200</code>
          </div>
          <div className="border-2 border-primary-500 p-4 rounded-lg">
            <code className="text-sm">border-primary-500</code>
          </div>
          <div className="border-2 border-success-500 p-4 rounded-lg">
            <code className="text-sm">border-success-500</code>
          </div>
          <div className="border-2 border-warning-500 p-4 rounded-lg">
            <code className="text-sm">border-warning-500</code>
          </div>
          <div className="border-2 border-danger-500 p-4 rounded-lg">
            <code className="text-sm">border-danger-500</code>
          </div>
        </div>
      </section>
    </div>
  ),
};

export const Cards: Story = {
  render: () => (
    <div className="space-y-8">
      <section>
        <h2 className="text-2xl font-bold mb-6">Cards</h2>

        <div className="grid grid-cols-2 gap-6">
          <Card>
            <CardBody className="p-6">
              <h3 className="font-semibold mb-2">Card Padrão</h3>
              <p className="text-sm text-default-600">Card básico sem customização</p>
            </CardBody>
          </Card>

          <Card className="border border-default-200">
            <CardBody className="p-6">
              <h3 className="font-semibold mb-2">Card com Borda</h3>
              <p className="text-sm text-default-600">Card com borda visível</p>
            </CardBody>
          </Card>

          <Card className="shadow-lg">
            <CardBody className="p-6">
              <h3 className="font-semibold mb-2">Card com Shadow Large</h3>
              <p className="text-sm text-default-600">Sombra mais pronunciada</p>
            </CardBody>
          </Card>

          <Card className="bg-primary-50 border-2 border-primary-200">
            <CardBody className="p-6">
              <h3 className="font-semibold text-primary-700 mb-2">Card Colorido</h3>
              <p className="text-sm text-primary-600">Com background e borda colorida</p>
            </CardBody>
          </Card>
        </div>
      </section>
    </div>
  ),
};

export const Tables: Story = {
  render: () => (
    <div className="space-y-8">
      <section>
        <h2 className="text-2xl font-bold mb-6">Tabelas</h2>

        <div className="rounded-lg border border-default-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-default-100">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-semibold text-default-700">Nome</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-default-700">Email</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-default-700">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-default-200">
              <tr className="hover:bg-default-50">
                <td className="px-4 py-3 text-sm">João Silva</td>
                <td className="px-4 py-3 text-sm text-default-600">joao@example.com</td>
                <td className="px-4 py-3"><span className="text-success text-sm">Ativo</span></td>
              </tr>
              <tr className="hover:bg-default-50">
                <td className="px-4 py-3 text-sm">Maria Santos</td>
                <td className="px-4 py-3 text-sm text-default-600">maria@example.com</td>
                <td className="px-4 py-3"><span className="text-success text-sm">Ativo</span></td>
              </tr>
              <tr className="hover:bg-default-50">
                <td className="px-4 py-3 text-sm">Pedro Costa</td>
                <td className="px-4 py-3 text-sm text-default-600">pedro@example.com</td>
                <td className="px-4 py-3"><span className="text-danger text-sm">Inativo</span></td>
              </tr>
            </tbody>
          </table>
        </div>

        <p className="text-sm text-default-600 mt-4">
          Classes utilizadas: <code>bg-default-100</code>, <code>divide-y divide-default-200</code>, <code>hover:bg-default-50</code>
        </p>
      </section>
    </div>
  ),
};
