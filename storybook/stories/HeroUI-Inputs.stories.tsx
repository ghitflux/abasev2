import type { Meta, StoryObj } from '@storybook/react-vite';
import React from 'react';
import {
  Input,
  Textarea,
  Checkbox,
  CheckboxGroup,
  Radio,
  RadioGroup,
  Switch,
  Select,
  SelectItem,
  Slider,
} from '@heroui/react';

const meta: Meta = {
  title: 'HeroUI/Inputs & Forms/Input',
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj;

export const InputVariants: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-6">
      <section>
        <h3 className="text-lg font-semibold mb-4">Variants</h3>
        <div className="space-y-4">
          <Input variant="flat" label="Flat" placeholder="Enter your text" />
          <Input variant="bordered" label="Bordered" placeholder="Enter your text" />
          <Input variant="faded" label="Faded" placeholder="Enter your text" />
          <Input variant="underlined" label="Underlined" placeholder="Enter your text" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Colors</h3>
        <div className="space-y-4">
          <Input color="default" variant="bordered" label="Default" placeholder="Default color" />
          <Input color="primary" variant="bordered" label="Primary" placeholder="Primary color" />
          <Input color="secondary" variant="bordered" label="Secondary" placeholder="Secondary color" />
          <Input color="success" variant="bordered" label="Success" placeholder="Success color" />
          <Input color="warning" variant="bordered" label="Warning" placeholder="Warning color" />
          <Input color="danger" variant="bordered" label="Danger" placeholder="Danger color" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Sizes</h3>
        <div className="space-y-4">
          <Input size="sm" label="Small" placeholder="Small input" />
          <Input size="md" label="Medium" placeholder="Medium input" />
          <Input size="lg" label="Large" placeholder="Large input" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Types</h3>
        <div className="space-y-4">
          <Input type="text" label="Text" placeholder="Enter text" />
          <Input type="email" label="Email" placeholder="you@example.com" />
          <Input type="password" label="Password" placeholder="Enter password" />
          <Input type="number" label="Number" placeholder="Enter number" />
          <Input type="url" label="URL" placeholder="https://example.com" />
          <Input type="search" label="Search" placeholder="Search..." />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">With Icons</h3>
        <div className="space-y-4">
          <Input
            label="Email"
            placeholder="you@example.com"
            startContent={<span className="text-default-400">📧</span>}
          />
          <Input
            label="Price"
            placeholder="0.00"
            startContent={<span className="text-default-400">$</span>}
            endContent={<span className="text-default-400">USD</span>}
          />
          <Input
            label="Website"
            placeholder="example.com"
            startContent={<span className="text-default-400">https://</span>}
          />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">States</h3>
        <div className="space-y-4">
          <Input label="Default" placeholder="Default state" />
          <Input label="Disabled" placeholder="Disabled state" isDisabled />
          <Input label="Read Only" placeholder="Read only" isReadOnly value="Cannot edit this" />
          <Input label="Required" placeholder="Required field" isRequired />
          <Input
            label="With Error"
            placeholder="Invalid input"
            isInvalid
            errorMessage="Please enter a valid value"
          />
          <Input
            label="With Description"
            placeholder="Enter your name"
            description="We'll never share your name with anyone else."
          />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Label Placements</h3>
        <div className="space-y-4">
          <Input label="Inside" placeholder="Label inside" labelPlacement="inside" />
          <Input label="Outside" placeholder="Label outside" labelPlacement="outside" />
          <Input label="Outside Left" placeholder="Label outside-left" labelPlacement="outside-left" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Clearable</h3>
        <Input
          label="Search"
          placeholder="Type to search..."
          isClearable
          onClear={() => console.log('input cleared')}
        />
      </section>
    </div>
  ),
};

export const TextareaExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-6">
      <section>
        <h3 className="text-lg font-semibold mb-4">Textarea Variants</h3>
        <div className="space-y-4">
          <Textarea variant="flat" label="Flat" placeholder="Enter your description" />
          <Textarea variant="bordered" label="Bordered" placeholder="Enter your description" />
          <Textarea variant="faded" label="Faded" placeholder="Enter your description" />
          <Textarea variant="underlined" label="Underlined" placeholder="Enter your description" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Textarea with Min Rows</h3>
        <Textarea
          label="Description"
          placeholder="Enter your description"
          minRows={3}
        />
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Textarea with Max Rows</h3>
        <Textarea
          label="Bio"
          placeholder="Enter your bio"
          maxRows={5}
        />
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Disabled Textarea</h3>
        <Textarea
          label="Disabled"
          placeholder="This is disabled"
          isDisabled
        />
      </section>
    </div>
  ),
};

export const CheckboxExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Checkbox Sizes</h3>
        <div className="flex gap-4">
          <Checkbox size="sm">Small</Checkbox>
          <Checkbox size="md">Medium</Checkbox>
          <Checkbox size="lg">Large</Checkbox>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Checkbox Colors</h3>
        <div className="flex flex-col gap-3">
          <Checkbox color="default" defaultSelected>Default</Checkbox>
          <Checkbox color="primary" defaultSelected>Primary (Verde Neon)</Checkbox>
          <Checkbox color="secondary" defaultSelected>Secondary (Roxo)</Checkbox>
          <Checkbox color="success" defaultSelected>Success</Checkbox>
          <Checkbox color="warning" defaultSelected>Warning</Checkbox>
          <Checkbox color="danger" defaultSelected>Danger</Checkbox>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Checkbox States</h3>
        <div className="flex flex-col gap-3">
          <Checkbox>Unchecked</Checkbox>
          <Checkbox defaultSelected>Checked</Checkbox>
          <Checkbox isDisabled>Disabled</Checkbox>
          <Checkbox isDisabled defaultSelected>Disabled Checked</Checkbox>
          <Checkbox isInvalid>Invalid</Checkbox>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Checkbox Group</h3>
        <CheckboxGroup
          label="Select features"
          color="primary"
          defaultValue={['feature1']}
        >
          <Checkbox value="feature1">Feature 1</Checkbox>
          <Checkbox value="feature2">Feature 2</Checkbox>
          <Checkbox value="feature3">Feature 3</Checkbox>
          <Checkbox value="feature4">Feature 4</Checkbox>
        </CheckboxGroup>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Controlled Checkbox</h3>
        {(() => {
          const [isSelected, setIsSelected] = React.useState(false);
          return (
            <div className="flex flex-col gap-3">
              <Checkbox
                isSelected={isSelected}
                onValueChange={setIsSelected}
                color="primary"
              >
                {isSelected ? 'Checked' : 'Unchecked'}
              </Checkbox>
              <p className="text-sm text-default-500">Selected: {isSelected ? 'true' : 'false'}</p>
            </div>
          );
        })()}
      </section>
    </div>
  ),
};

export const RadioExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Radio Sizes</h3>
        <RadioGroup defaultValue="md">
          <Radio value="sm" size="sm">Small</Radio>
          <Radio value="md" size="md">Medium</Radio>
          <Radio value="lg" size="lg">Large</Radio>
        </RadioGroup>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Radio Colors</h3>
        <div className="space-y-6">
          <RadioGroup label="Select color" defaultValue="primary">
            <Radio value="default" color="default">Default</Radio>
            <Radio value="primary" color="primary">Primary (Verde Neon)</Radio>
            <Radio value="secondary" color="secondary">Secondary (Roxo)</Radio>
            <Radio value="success" color="success">Success</Radio>
            <Radio value="warning" color="warning">Warning</Radio>
            <Radio value="danger" color="danger">Danger</Radio>
          </RadioGroup>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Radio Orientation</h3>
        <RadioGroup label="Select option" orientation="horizontal" defaultValue="option1">
          <Radio value="option1">Option 1</Radio>
          <Radio value="option2">Option 2</Radio>
          <Radio value="option3">Option 3</Radio>
        </RadioGroup>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Disabled Radio</h3>
        <RadioGroup label="Select option" defaultValue="option1">
          <Radio value="option1">Option 1</Radio>
          <Radio value="option2" isDisabled>Option 2 (Disabled)</Radio>
          <Radio value="option3">Option 3</Radio>
        </RadioGroup>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Radio with Description</h3>
        <RadioGroup label="Select plan" description="Choose your subscription plan">
          <Radio value="free" description="Basic features">Free</Radio>
          <Radio value="pro" description="Advanced features">Pro</Radio>
          <Radio value="enterprise" description="All features">Enterprise</Radio>
        </RadioGroup>
      </section>
    </div>
  ),
};

export const SwitchExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Switch Sizes</h3>
        <div className="flex gap-6">
          <Switch size="sm">Small</Switch>
          <Switch size="md">Medium</Switch>
          <Switch size="lg">Large</Switch>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Switch Colors</h3>
        <div className="flex flex-col gap-3">
          <Switch color="default" defaultSelected>Default</Switch>
          <Switch color="primary" defaultSelected>Primary (Verde Neon)</Switch>
          <Switch color="secondary" defaultSelected>Secondary (Roxo)</Switch>
          <Switch color="success" defaultSelected>Success</Switch>
          <Switch color="warning" defaultSelected>Warning</Switch>
          <Switch color="danger" defaultSelected>Danger</Switch>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Switch States</h3>
        <div className="flex flex-col gap-3">
          <Switch>Off</Switch>
          <Switch defaultSelected>On</Switch>
          <Switch isDisabled>Disabled Off</Switch>
          <Switch isDisabled defaultSelected>Disabled On</Switch>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Controlled Switch</h3>
        {(() => {
          const [isSelected, setIsSelected] = React.useState(false);
          return (
            <div className="flex flex-col gap-3">
              <Switch
                isSelected={isSelected}
                onValueChange={setIsSelected}
                color="primary"
              >
                {isSelected ? 'Enabled' : 'Disabled'}
              </Switch>
              <p className="text-sm text-default-500">Status: {isSelected ? 'ON' : 'OFF'}</p>
            </div>
          );
        })()}
      </section>
    </div>
  ),
};

export const SelectExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Select Variants</h3>
        <div className="space-y-4">
          <Select variant="flat" label="Flat" placeholder="Select an option">
            <SelectItem key="option1">Option 1</SelectItem>
            <SelectItem key="option2">Option 2</SelectItem>
            <SelectItem key="option3">Option 3</SelectItem>
          </Select>
          <Select variant="bordered" label="Bordered" placeholder="Select an option">
            <SelectItem key="option1">Option 1</SelectItem>
            <SelectItem key="option2">Option 2</SelectItem>
            <SelectItem key="option3">Option 3</SelectItem>
          </Select>
          <Select variant="faded" label="Faded" placeholder="Select an option">
            <SelectItem key="option1">Option 1</SelectItem>
            <SelectItem key="option2">Option 2</SelectItem>
            <SelectItem key="option3">Option 3</SelectItem>
          </Select>
          <Select variant="underlined" label="Underlined" placeholder="Select an option">
            <SelectItem key="option1">Option 1</SelectItem>
            <SelectItem key="option2">Option 2</SelectItem>
            <SelectItem key="option3">Option 3</SelectItem>
          </Select>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Select Colors</h3>
        <div className="space-y-4">
          <Select color="primary" variant="bordered" label="Primary" placeholder="Select">
            <SelectItem key="1">Option 1</SelectItem>
            <SelectItem key="2">Option 2</SelectItem>
          </Select>
          <Select color="secondary" variant="bordered" label="Secondary" placeholder="Select">
            <SelectItem key="1">Option 1</SelectItem>
            <SelectItem key="2">Option 2</SelectItem>
          </Select>
          <Select color="success" variant="bordered" label="Success" placeholder="Select">
            <SelectItem key="1">Option 1</SelectItem>
            <SelectItem key="2">Option 2</SelectItem>
          </Select>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Multiple Selection</h3>
        <Select
          label="Select multiple"
          placeholder="Choose multiple options"
          selectionMode="multiple"
          variant="bordered"
        >
          <SelectItem key="option1">Option 1</SelectItem>
          <SelectItem key="option2">Option 2</SelectItem>
          <SelectItem key="option3">Option 3</SelectItem>
          <SelectItem key="option4">Option 4</SelectItem>
        </Select>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">With Description</h3>
        <Select
          label="Select country"
          placeholder="Choose a country"
          description="Select your country of residence"
          variant="bordered"
        >
          <SelectItem key="br">Brazil</SelectItem>
          <SelectItem key="us">United States</SelectItem>
          <SelectItem key="uk">United Kingdom</SelectItem>
          <SelectItem key="fr">France</SelectItem>
        </Select>
      </section>
    </div>
  ),
};

export const SliderExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Slider Sizes</h3>
        <div className="space-y-6">
          <Slider size="sm" label="Small" defaultValue={50} className="max-w-md" />
          <Slider size="md" label="Medium" defaultValue={50} className="max-w-md" />
          <Slider size="lg" label="Large" defaultValue={50} className="max-w-md" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Slider Colors</h3>
        <div className="space-y-6">
          <Slider color="primary" label="Primary" defaultValue={50} className="max-w-md" />
          <Slider color="secondary" label="Secondary" defaultValue={50} className="max-w-md" />
          <Slider color="success" label="Success" defaultValue={50} className="max-w-md" />
          <Slider color="warning" label="Warning" defaultValue={50} className="max-w-md" />
          <Slider color="danger" label="Danger" defaultValue={50} className="max-w-md" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Slider with Steps</h3>
        <Slider
          label="Volume"
          step={10}
          minValue={0}
          maxValue={100}
          defaultValue={50}
          marks={[
            { value: 0, label: '0%' },
            { value: 50, label: '50%' },
            { value: 100, label: '100%' },
          ]}
          className="max-w-md"
        />
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Vertical Slider</h3>
        <Slider
          orientation="vertical"
          label="Volume"
          defaultValue={50}
          className="h-64"
        />
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Range Slider</h3>
        <Slider
          label="Price Range"
          step={50}
          minValue={0}
          maxValue={1000}
          defaultValue={[200, 800]}
          formatOptions={{ style: 'currency', currency: 'USD' }}
          className="max-w-md"
        />
      </section>
    </div>
  ),
};
