import type { Meta, StoryObj } from '@storybook/react-vite';
import React from 'react';
import {
  Calendar,
  DatePicker,
  DateInput,
  DateRangePicker,
} from '@heroui/react';
import { parseDate } from '@internationalized/date';

const meta: Meta = {
  title: 'HeroUI/Date & Time/Calendar',
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj;

export const CalendarExamples: Story = {
  render: () => (
    <div className="w-full max-w-4xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Basic Calendar</h3>
        <Calendar aria-label="Date" />
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Calendar with Default Value</h3>
        <Calendar
          aria-label="Date"
          defaultValue={parseDate('2024-03-15')}
        />
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Calendar Colors</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm mb-2">Primary</p>
            <Calendar color="primary" />
          </div>
          <div>
            <p className="text-sm mb-2">Secondary</p>
            <Calendar color="secondary" />
          </div>
          <div>
            <p className="text-sm mb-2">Success</p>
            <Calendar color="success" />
          </div>
          <div>
            <p className="text-sm mb-2">Warning</p>
            <Calendar color="warning" />
          </div>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Disabled Calendar</h3>
        <Calendar aria-label="Date" isDisabled />
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Controlled Calendar</h3>
        {(() => {
          const [value, setValue] = React.useState(parseDate('2024-03-15'));

          return (
            <div className="flex flex-col gap-4">
              <p className="text-sm text-default-500">
                Selected date: {value.toString()}
              </p>
              <Calendar
                aria-label="Date"
                value={value}
                onChange={setValue}
                color="primary"
              />
            </div>
          );
        })()}
      </section>
    </div>
  ),
};

export const DatePickerExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Basic DatePicker</h3>
        <DatePicker label="Birth date" />
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">DatePicker Variants</h3>
        <div className="space-y-4">
          <DatePicker label="Flat" variant="flat" />
          <DatePicker label="Bordered" variant="bordered" />
          <DatePicker label="Faded" variant="faded" />
          <DatePicker label="Underlined" variant="underlined" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">DatePicker Colors</h3>
        <div className="space-y-4">
          <DatePicker label="Primary" color="primary" variant="bordered" />
          <DatePicker label="Secondary" color="secondary" variant="bordered" />
          <DatePicker label="Success" color="success" variant="bordered" />
          <DatePicker label="Warning" color="warning" variant="bordered" />
          <DatePicker label="Danger" color="danger" variant="bordered" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">DatePicker with Default Value</h3>
        <DatePicker
          label="Event date"
          defaultValue={parseDate('2024-03-15')}
        />
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">DatePicker Sizes</h3>
        <div className="space-y-4">
          <DatePicker label="Small" size="sm" />
          <DatePicker label="Medium" size="md" />
          <DatePicker label="Large" size="lg" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">DatePicker States</h3>
        <div className="space-y-4">
          <DatePicker label="Disabled" isDisabled />
          <DatePicker label="Read Only" isReadOnly value={parseDate('2024-03-15')} />
          <DatePicker
            label="Required"
            isRequired
            description="This field is required"
          />
          <DatePicker
            label="With Error"
            isInvalid
            errorMessage="Please select a valid date"
          />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Controlled DatePicker</h3>
        {(() => {
          const [value, setValue] = React.useState(parseDate('2024-03-15'));

          return (
            <div className="flex flex-col gap-4">
              <p className="text-sm text-default-500">
                Selected: {value.toString()}
              </p>
              <DatePicker
                label="Select date"
                value={value}
                onChange={setValue}
                color="primary"
              />
            </div>
          );
        })()}
      </section>
    </div>
  ),
};

export const DateInputExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Basic DateInput</h3>
        <DateInput label="Birth date" />
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">DateInput Variants</h3>
        <div className="space-y-4">
          <DateInput label="Flat" variant="flat" />
          <DateInput label="Bordered" variant="bordered" />
          <DateInput label="Faded" variant="faded" />
          <DateInput label="Underlined" variant="underlined" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">DateInput Colors</h3>
        <div className="space-y-4">
          <DateInput label="Primary" color="primary" variant="bordered" />
          <DateInput label="Secondary" color="secondary" variant="bordered" />
          <DateInput label="Success" color="success" variant="bordered" />
          <DateInput label="Warning" color="warning" variant="bordered" />
          <DateInput label="Danger" color="danger" variant="bordered" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">DateInput with Default Value</h3>
        <DateInput
          label="Event date"
          defaultValue={parseDate('2024-03-15')}
        />
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">DateInput Sizes</h3>
        <div className="space-y-4">
          <DateInput label="Small" size="sm" />
          <DateInput label="Medium" size="md" />
          <DateInput label="Large" size="lg" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">DateInput States</h3>
        <div className="space-y-4">
          <DateInput label="Disabled" isDisabled />
          <DateInput label="Read Only" isReadOnly value={parseDate('2024-03-15')} />
          <DateInput
            label="Required"
            isRequired
            description="This field is required"
          />
          <DateInput
            label="With Error"
            isInvalid
            errorMessage="Please enter a valid date"
          />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Label Placements</h3>
        <div className="space-y-4">
          <DateInput label="Inside" labelPlacement="inside" />
          <DateInput label="Outside" labelPlacement="outside" />
          <DateInput label="Outside Left" labelPlacement="outside-left" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Controlled DateInput</h3>
        {(() => {
          const [value, setValue] = React.useState(parseDate('2024-03-15'));

          return (
            <div className="flex flex-col gap-4">
              <p className="text-sm text-default-500">
                Selected: {value.toString()}
              </p>
              <DateInput
                label="Select date"
                value={value}
                onChange={setValue}
                color="primary"
              />
            </div>
          );
        })()}
      </section>
    </div>
  ),
};

export const DateRangePickerExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Basic DateRangePicker</h3>
        <DateRangePicker label="Stay duration" />
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">DateRangePicker Variants</h3>
        <div className="space-y-4">
          <DateRangePicker label="Flat" variant="flat" />
          <DateRangePicker label="Bordered" variant="bordered" />
          <DateRangePicker label="Faded" variant="faded" />
          <DateRangePicker label="Underlined" variant="underlined" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">DateRangePicker Colors</h3>
        <div className="space-y-4">
          <DateRangePicker label="Primary" color="primary" variant="bordered" />
          <DateRangePicker label="Secondary" color="secondary" variant="bordered" />
          <DateRangePicker label="Success" color="success" variant="bordered" />
          <DateRangePicker label="Warning" color="warning" variant="bordered" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">DateRangePicker Sizes</h3>
        <div className="space-y-4">
          <DateRangePicker label="Small" size="sm" />
          <DateRangePicker label="Medium" size="md" />
          <DateRangePicker label="Large" size="lg" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">DateRangePicker States</h3>
        <div className="space-y-4">
          <DateRangePicker label="Disabled" isDisabled />
          <DateRangePicker label="Read Only" isReadOnly />
          <DateRangePicker
            label="Required"
            isRequired
            description="Please select a date range"
          />
          <DateRangePicker
            label="With Error"
            isInvalid
            errorMessage="Please select a valid date range"
          />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">With Description</h3>
        <DateRangePicker
          label="Event duration"
          description="Select start and end dates for your event"
          color="primary"
        />
      </section>
    </div>
  ),
};

export const AllDateTimeComponents: Story = {
  render: () => (
    <div className="w-full max-w-4xl space-y-12 p-4">
      <section>
        <h2 className="text-2xl font-bold mb-6">Calendar</h2>
        <div className="grid grid-cols-2 gap-8">
          <div>
            <h3 className="text-lg font-semibold mb-4">Default</h3>
            <Calendar aria-label="Date" />
          </div>
          <div>
            <h3 className="text-lg font-semibold mb-4">Primary Color</h3>
            <Calendar aria-label="Date" color="primary" />
          </div>
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold mb-6">DatePicker</h2>
        <div className="grid grid-cols-2 gap-4">
          <DatePicker label="Event date" variant="bordered" />
          <DatePicker label="Birth date" color="primary" variant="bordered" />
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold mb-6">DateInput</h2>
        <div className="grid grid-cols-2 gap-4">
          <DateInput label="Start date" variant="bordered" />
          <DateInput label="End date" color="primary" variant="bordered" />
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold mb-6">DateRangePicker</h2>
        <div className="space-y-4">
          <DateRangePicker label="Stay duration" variant="bordered" />
          <DateRangePicker
            label="Project timeline"
            color="primary"
            variant="bordered"
          />
        </div>
      </section>
    </div>
  ),
};
