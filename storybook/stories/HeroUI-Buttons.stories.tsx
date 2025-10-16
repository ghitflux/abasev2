import type { Meta, StoryObj } from '@storybook/react-vite';
import React from 'react';
import { Button, ButtonGroup } from '@heroui/react';

const meta: Meta<typeof Button> = {
  title: 'HeroUI/Actions/Button',
  component: Button,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    color: {
      control: 'select',
      options: ['default', 'primary', 'secondary', 'success', 'warning', 'danger'],
    },
    variant: {
      control: 'select',
      options: ['solid', 'bordered', 'light', 'flat', 'faded', 'shadow', 'ghost'],
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
    },
    radius: {
      control: 'select',
      options: ['none', 'sm', 'md', 'lg', 'full'],
    },
    isDisabled: {
      control: 'boolean',
    },
    isLoading: {
      control: 'boolean',
    },
  },
};

export default meta;
type Story = StoryObj<typeof Button>;

export const Default: Story = {
  args: {
    children: 'Button',
  },
};

export const Colors: Story = {
  render: () => (
    <div className="flex flex-wrap gap-4">
      <Button color="default">Default</Button>
      <Button color="primary">Primary (Verde Neon)</Button>
      <Button color="secondary">Secondary (Roxo)</Button>
      <Button color="success">Success</Button>
      <Button color="warning">Warning</Button>
      <Button color="danger">Danger</Button>
    </div>
  ),
};

export const Variants: Story = {
  render: () => (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap gap-4">
        <Button variant="solid" color="primary">Solid</Button>
        <Button variant="bordered" color="primary">Bordered</Button>
        <Button variant="light" color="primary">Light</Button>
        <Button variant="flat" color="primary">Flat</Button>
        <Button variant="faded" color="primary">Faded</Button>
        <Button variant="shadow" color="primary">Shadow</Button>
        <Button variant="ghost" color="primary">Ghost</Button>
      </div>

      <div className="flex flex-wrap gap-4">
        <Button variant="solid" color="secondary">Solid</Button>
        <Button variant="bordered" color="secondary">Bordered</Button>
        <Button variant="light" color="secondary">Light</Button>
        <Button variant="flat" color="secondary">Flat</Button>
        <Button variant="faded" color="secondary">Faded</Button>
        <Button variant="shadow" color="secondary">Shadow</Button>
        <Button variant="ghost" color="secondary">Ghost</Button>
      </div>
    </div>
  ),
};

export const Sizes: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-4">
      <Button size="sm" color="primary">Small</Button>
      <Button size="md" color="primary">Medium</Button>
      <Button size="lg" color="primary">Large</Button>
    </div>
  ),
};

export const Radius: Story = {
  render: () => (
    <div className="flex flex-wrap gap-4">
      <Button radius="none" color="primary">None</Button>
      <Button radius="sm" color="primary">Small</Button>
      <Button radius="md" color="primary">Medium</Button>
      <Button radius="lg" color="primary">Large</Button>
      <Button radius="full" color="primary">Full</Button>
    </div>
  ),
};

export const LoadingState: Story = {
  render: () => (
    <div className="flex flex-wrap gap-4">
      <Button color="primary">Normal</Button>
      <Button color="primary" isLoading>Loading</Button>
      <Button color="primary" isLoading spinner={<div>⏳</div>}>Custom Spinner</Button>
    </div>
  ),
};

export const DisabledState: Story = {
  render: () => (
    <div className="flex flex-wrap gap-4">
      <Button color="primary" isDisabled>Disabled Solid</Button>
      <Button color="primary" variant="bordered" isDisabled>Disabled Bordered</Button>
      <Button color="primary" variant="flat" isDisabled>Disabled Flat</Button>
    </div>
  ),
};

export const WithIcons: Story = {
  render: () => (
    <div className="flex flex-wrap gap-4">
      <Button color="primary" startContent={<span>📧</span>}>
        Email
      </Button>
      <Button color="success" endContent={<span>→</span>}>
        Next
      </Button>
      <Button color="danger" startContent={<span>🗑️</span>} endContent={<span>×</span>}>
        Delete
      </Button>
      <Button isIconOnly color="primary" aria-label="Like">
        ❤️
      </Button>
    </div>
  ),
};

export const FullWidth: Story = {
  render: () => (
    <div className="w-full max-w-md space-y-4">
      <Button color="primary" fullWidth>Full Width Button</Button>
      <Button color="secondary" variant="bordered" fullWidth>Full Width Bordered</Button>
    </div>
  ),
};

export const WithPressHandlers: Story = {
  render: () => {
    const [count, setCount] = React.useState(0);

    return (
      <div className="flex flex-col gap-4 items-center">
        <p className="text-default-500">Click count: {count}</p>
        <Button
          color="primary"
          onPress={() => setCount(count + 1)}
        >
          Click me
        </Button>
      </div>
    );
  },
};

export const ButtonGroupExample: Story = {
  render: () => (
    <div className="flex flex-col gap-6">
      <ButtonGroup>
        <Button>One</Button>
        <Button>Two</Button>
        <Button>Three</Button>
      </ButtonGroup>

      <ButtonGroup color="primary">
        <Button>Save</Button>
        <Button>Edit</Button>
        <Button>Delete</Button>
      </ButtonGroup>

      <ButtonGroup variant="bordered">
        <Button>Left</Button>
        <Button>Center</Button>
        <Button>Right</Button>
      </ButtonGroup>
    </div>
  ),
};

export const AllCombinations: Story = {
  render: () => (
    <div className="space-y-8 p-4">
      <section>
        <h3 className="text-lg font-semibold mb-4">Primary (Verde Neon #00ff18)</h3>
        <div className="flex flex-wrap gap-3">
          <Button color="primary" variant="solid">Solid</Button>
          <Button color="primary" variant="bordered">Bordered</Button>
          <Button color="primary" variant="light">Light</Button>
          <Button color="primary" variant="flat">Flat</Button>
          <Button color="primary" variant="faded">Faded</Button>
          <Button color="primary" variant="shadow">Shadow</Button>
          <Button color="primary" variant="ghost">Ghost</Button>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Secondary (Roxo #7828c8)</h3>
        <div className="flex flex-wrap gap-3">
          <Button color="secondary" variant="solid">Solid</Button>
          <Button color="secondary" variant="bordered">Bordered</Button>
          <Button color="secondary" variant="light">Light</Button>
          <Button color="secondary" variant="flat">Flat</Button>
          <Button color="secondary" variant="faded">Faded</Button>
          <Button color="secondary" variant="shadow">Shadow</Button>
          <Button color="secondary" variant="ghost">Ghost</Button>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Success</h3>
        <div className="flex flex-wrap gap-3">
          <Button color="success" variant="solid">Solid</Button>
          <Button color="success" variant="bordered">Bordered</Button>
          <Button color="success" variant="light">Light</Button>
          <Button color="success" variant="flat">Flat</Button>
          <Button color="success" variant="faded">Faded</Button>
          <Button color="success" variant="shadow">Shadow</Button>
          <Button color="success" variant="ghost">Ghost</Button>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Warning</h3>
        <div className="flex flex-wrap gap-3">
          <Button color="warning" variant="solid">Solid</Button>
          <Button color="warning" variant="bordered">Bordered</Button>
          <Button color="warning" variant="light">Light</Button>
          <Button color="warning" variant="flat">Flat</Button>
          <Button color="warning" variant="faded">Faded</Button>
          <Button color="warning" variant="shadow">Shadow</Button>
          <Button color="warning" variant="ghost">Ghost</Button>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Danger</h3>
        <div className="flex flex-wrap gap-3">
          <Button color="danger" variant="solid">Solid</Button>
          <Button color="danger" variant="bordered">Bordered</Button>
          <Button color="danger" variant="light">Light</Button>
          <Button color="danger" variant="flat">Flat</Button>
          <Button color="danger" variant="faded">Faded</Button>
          <Button color="danger" variant="shadow">Shadow</Button>
          <Button color="danger" variant="ghost">Ghost</Button>
        </div>
      </section>
    </div>
  ),
};
