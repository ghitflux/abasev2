import type { Meta, StoryObj } from '@storybook/react-vite';
import React from 'react';
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  useDisclosure,
  Button,
  Dropdown,
  DropdownTrigger,
  DropdownMenu,
  DropdownItem,
  DropdownSection,
  Popover,
  PopoverTrigger,
  PopoverContent,
  Tooltip,
  Spinner,
} from '@heroui/react';

const meta: Meta = {
  title: 'HeroUI/Overlay & Feedback/Modal',
  parameters: {
    layout: 'centered',
  },
};

export default meta;
type Story = StoryObj;

export const ModalExamples: Story = {
  render: () => {
    const { isOpen, onOpen, onOpenChange } = useDisclosure();
    const { isOpen: isOpen2, onOpen: onOpen2, onOpenChange: onOpenChange2 } = useDisclosure();
    const { isOpen: isOpen3, onOpen: onOpen3, onOpenChange: onOpenChange3 } = useDisclosure();

    return (
      <div className="flex flex-wrap gap-4 p-8">
        <section className="w-full space-y-4">
          <h3 className="text-lg font-semibold">Basic Modal</h3>
          <Button onPress={onOpen} color="primary">Open Modal</Button>
          <Modal isOpen={isOpen} onOpenChange={onOpenChange}>
            <ModalContent>
              {(onClose) => (
                <>
                  <ModalHeader className="flex flex-col gap-1">Modal Title</ModalHeader>
                  <ModalBody>
                    <p>
                      Lorem ipsum dolor sit amet, consectetur adipiscing elit.
                      Nullam pulvinar risus non risus hendrerit venenatis.
                    </p>
                    <p>
                      Pellentesque sit amet hendrerit risus, sed porttitor quam.
                    </p>
                  </ModalBody>
                  <ModalFooter>
                    <Button color="danger" variant="light" onPress={onClose}>
                      Close
                    </Button>
                    <Button color="primary" onPress={onClose}>
                      Action
                    </Button>
                  </ModalFooter>
                </>
              )}
            </ModalContent>
          </Modal>

          <h3 className="text-lg font-semibold mt-8">Modal Sizes</h3>
          <div className="flex gap-2">
            <Button onPress={onOpen2} size="sm">Small Modal</Button>
            <Button onPress={onOpen3} size="sm">Large Modal</Button>
          </div>
          <Modal size="sm" isOpen={isOpen2} onOpenChange={onOpenChange2}>
            <ModalContent>
              {(onClose) => (
                <>
                  <ModalHeader>Small Modal</ModalHeader>
                  <ModalBody>
                    <p>This is a small modal.</p>
                  </ModalBody>
                  <ModalFooter>
                    <Button onPress={onClose}>Close</Button>
                  </ModalFooter>
                </>
              )}
            </ModalContent>
          </Modal>

          <Modal size="5xl" isOpen={isOpen3} onOpenChange={onOpenChange3}>
            <ModalContent>
              {(onClose) => (
                <>
                  <ModalHeader>Large Modal</ModalHeader>
                  <ModalBody>
                    <p>This is a large modal with more content space.</p>
                  </ModalBody>
                  <ModalFooter>
                    <Button onPress={onClose}>Close</Button>
                  </ModalFooter>
                </>
              )}
            </ModalContent>
          </Modal>
        </section>
      </div>
    );
  },
};

export const ModalPlacements: Story = {
  render: () => {
    const placements = ['center', 'top', 'bottom', 'top-center', 'bottom-center'] as const;
    const [placement, setPlacement] = React.useState<typeof placements[number]>('center');
    const { isOpen, onOpen, onOpenChange } = useDisclosure();

    return (
      <div className="flex flex-col gap-4 p-8">
        <h3 className="text-lg font-semibold">Modal Placements</h3>
        <div className="flex flex-wrap gap-2">
          {placements.map((p) => (
            <Button
              key={p}
              size="sm"
              onPress={() => {
                setPlacement(p);
                onOpen();
              }}
            >
              {p}
            </Button>
          ))}
        </div>
        <Modal placement={placement} isOpen={isOpen} onOpenChange={onOpenChange}>
          <ModalContent>
            {(onClose) => (
              <>
                <ModalHeader>Modal at {placement}</ModalHeader>
                <ModalBody>
                  <p>This modal is positioned at: {placement}</p>
                </ModalBody>
                <ModalFooter>
                  <Button onPress={onClose}>Close</Button>
                </ModalFooter>
              </>
            )}
          </ModalContent>
        </Modal>
      </div>
    );
  },
};

export const ModalScrollBehavior: Story = {
  render: () => {
    const { isOpen, onOpen, onOpenChange } = useDisclosure();
    const { isOpen: isOpen2, onOpen: onOpen2, onOpenChange: onOpenChange2 } = useDisclosure();

    return (
      <div className="flex flex-col gap-4 p-8">
        <h3 className="text-lg font-semibold">Scroll Behavior</h3>
        <div className="flex gap-2">
          <Button onPress={onOpen}>Inside (default)</Button>
          <Button onPress={onOpen2}>Outside</Button>
        </div>

        <Modal scrollBehavior="inside" isOpen={isOpen} onOpenChange={onOpenChange}>
          <ModalContent>
            {(onClose) => (
              <>
                <ModalHeader>Scroll Inside</ModalHeader>
                <ModalBody>
                  {Array.from({ length: 20 }).map((_, i) => (
                    <p key={i}>
                      Lorem ipsum dolor sit amet, consectetur adipiscing elit. Line {i + 1}
                    </p>
                  ))}
                </ModalBody>
                <ModalFooter>
                  <Button onPress={onClose}>Close</Button>
                </ModalFooter>
              </>
            )}
          </ModalContent>
        </Modal>

        <Modal scrollBehavior="outside" isOpen={isOpen2} onOpenChange={onOpenChange2}>
          <ModalContent>
            {(onClose) => (
              <>
                <ModalHeader>Scroll Outside</ModalHeader>
                <ModalBody>
                  {Array.from({ length: 20 }).map((_, i) => (
                    <p key={i}>
                      Lorem ipsum dolor sit amet, consectetur adipiscing elit. Line {i + 1}
                    </p>
                  ))}
                </ModalBody>
                <ModalFooter>
                  <Button onPress={onClose}>Close</Button>
                </ModalFooter>
              </>
            )}
          </ModalContent>
        </Modal>
      </div>
    );
  },
};

export const DropdownExamples: Story = {
  render: () => (
    <div className="flex flex-col gap-8 p-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Basic Dropdown</h3>
        <Dropdown>
          <DropdownTrigger>
            <Button variant="bordered">Open Menu</Button>
          </DropdownTrigger>
          <DropdownMenu aria-label="Static Actions">
            <DropdownItem key="new">New file</DropdownItem>
            <DropdownItem key="copy">Copy link</DropdownItem>
            <DropdownItem key="edit">Edit file</DropdownItem>
            <DropdownItem key="delete" className="text-danger" color="danger">
              Delete file
            </DropdownItem>
          </DropdownMenu>
        </Dropdown>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Dropdown with Sections</h3>
        <Dropdown>
          <DropdownTrigger>
            <Button variant="bordered">Actions</Button>
          </DropdownTrigger>
          <DropdownMenu aria-label="Actions with sections">
            <DropdownSection title="Actions" showDivider>
              <DropdownItem key="new">New file</DropdownItem>
              <DropdownItem key="copy">Copy link</DropdownItem>
            </DropdownSection>
            <DropdownSection title="Danger zone">
              <DropdownItem key="delete" color="danger">Delete file</DropdownItem>
            </DropdownSection>
          </DropdownMenu>
        </Dropdown>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Dropdown with Icons</h3>
        <Dropdown>
          <DropdownTrigger>
            <Button variant="bordered">Menu</Button>
          </DropdownTrigger>
          <DropdownMenu aria-label="Menu with icons">
            <DropdownItem key="new" startContent={<span>➕</span>}>
              New file
            </DropdownItem>
            <DropdownItem key="copy" startContent={<span>📋</span>}>
              Copy link
            </DropdownItem>
            <DropdownItem key="edit" startContent={<span>✏️</span>}>
              Edit file
            </DropdownItem>
            <DropdownItem key="delete" startContent={<span>🗑️</span>} color="danger">
              Delete file
            </DropdownItem>
          </DropdownMenu>
        </Dropdown>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Dropdown with Selection</h3>
        {(() => {
          const [selectedKeys, setSelectedKeys] = React.useState(new Set(['text']));

          return (
            <div className="flex flex-col gap-2">
              <Dropdown>
                <DropdownTrigger>
                  <Button variant="bordered">
                    {selectedKeys.has('text') ? 'Text' : selectedKeys.has('number') ? 'Number' : 'Date'}
                  </Button>
                </DropdownTrigger>
                <DropdownMenu
                  aria-label="Selection"
                  selectionMode="single"
                  selectedKeys={selectedKeys}
                  onSelectionChange={setSelectedKeys as any}
                >
                  <DropdownItem key="text">Text</DropdownItem>
                  <DropdownItem key="number">Number</DropdownItem>
                  <DropdownItem key="date">Date</DropdownItem>
                </DropdownMenu>
              </Dropdown>
              <p className="text-sm text-default-500">Selected: {Array.from(selectedKeys).join(', ')}</p>
            </div>
          );
        })()}
      </section>
    </div>
  ),
};

export const PopoverExamples: Story = {
  render: () => (
    <div className="flex flex-col gap-8 p-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Basic Popover</h3>
        <Popover placement="bottom">
          <PopoverTrigger>
            <Button>Open Popover</Button>
          </PopoverTrigger>
          <PopoverContent>
            <div className="px-1 py-2">
              <div className="text-small font-bold">Popover Content</div>
              <div className="text-tiny">This is the popover content</div>
            </div>
          </PopoverContent>
        </Popover>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Popover Placements</h3>
        <div className="flex flex-wrap gap-2">
          <Popover placement="top">
            <PopoverTrigger>
              <Button size="sm">Top</Button>
            </PopoverTrigger>
            <PopoverContent>
              <div className="px-1 py-2">Top placement</div>
            </PopoverContent>
          </Popover>

          <Popover placement="bottom">
            <PopoverTrigger>
              <Button size="sm">Bottom</Button>
            </PopoverTrigger>
            <PopoverContent>
              <div className="px-1 py-2">Bottom placement</div>
            </PopoverContent>
          </Popover>

          <Popover placement="left">
            <PopoverTrigger>
              <Button size="sm">Left</Button>
            </PopoverTrigger>
            <PopoverContent>
              <div className="px-1 py-2">Left placement</div>
            </PopoverContent>
          </Popover>

          <Popover placement="right">
            <PopoverTrigger>
              <Button size="sm">Right</Button>
            </PopoverTrigger>
            <PopoverContent>
              <div className="px-1 py-2">Right placement</div>
            </PopoverContent>
          </Popover>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Popover with Arrow</h3>
        <Popover showArrow placement="bottom">
          <PopoverTrigger>
            <Button>With Arrow</Button>
          </PopoverTrigger>
          <PopoverContent>
            <div className="px-1 py-2">
              <div className="text-small font-bold">Arrow Popover</div>
              <div className="text-tiny">This popover has an arrow</div>
            </div>
          </PopoverContent>
        </Popover>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Popover Colors</h3>
        <div className="flex flex-wrap gap-2">
          <Popover color="default">
            <PopoverTrigger>
              <Button size="sm">Default</Button>
            </PopoverTrigger>
            <PopoverContent>
              <div className="px-1 py-2">Default color</div>
            </PopoverContent>
          </Popover>

          <Popover color="primary">
            <PopoverTrigger>
              <Button size="sm" color="primary">Primary</Button>
            </PopoverTrigger>
            <PopoverContent>
              <div className="px-1 py-2">Primary color</div>
            </PopoverContent>
          </Popover>

          <Popover color="secondary">
            <PopoverTrigger>
              <Button size="sm" color="secondary">Secondary</Button>
            </PopoverTrigger>
            <PopoverContent>
              <div className="px-1 py-2">Secondary color</div>
            </PopoverContent>
          </Popover>

          <Popover color="success">
            <PopoverTrigger>
              <Button size="sm" color="success">Success</Button>
            </PopoverTrigger>
            <PopoverContent>
              <div className="px-1 py-2">Success color</div>
            </PopoverContent>
          </Popover>

          <Popover color="warning">
            <PopoverTrigger>
              <Button size="sm" color="warning">Warning</Button>
            </PopoverTrigger>
            <PopoverContent>
              <div className="px-1 py-2">Warning color</div>
            </PopoverContent>
          </Popover>

          <Popover color="danger">
            <PopoverTrigger>
              <Button size="sm" color="danger">Danger</Button>
            </PopoverTrigger>
            <PopoverContent>
              <div className="px-1 py-2">Danger color</div>
            </PopoverContent>
          </Popover>
        </div>
      </section>
    </div>
  ),
};

export const TooltipExamples: Story = {
  render: () => (
    <div className="flex flex-col gap-8 p-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Basic Tooltip</h3>
        <div className="flex gap-4">
          <Tooltip content="I am a tooltip">
            <Button>Hover me</Button>
          </Tooltip>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Tooltip Colors</h3>
        <div className="flex flex-wrap gap-2">
          <Tooltip content="Default tooltip">
            <Button size="sm">Default</Button>
          </Tooltip>
          <Tooltip content="Primary tooltip" color="primary">
            <Button size="sm" color="primary">Primary</Button>
          </Tooltip>
          <Tooltip content="Secondary tooltip" color="secondary">
            <Button size="sm" color="secondary">Secondary</Button>
          </Tooltip>
          <Tooltip content="Success tooltip" color="success">
            <Button size="sm" color="success">Success</Button>
          </Tooltip>
          <Tooltip content="Warning tooltip" color="warning">
            <Button size="sm" color="warning">Warning</Button>
          </Tooltip>
          <Tooltip content="Danger tooltip" color="danger">
            <Button size="sm" color="danger">Danger</Button>
          </Tooltip>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Tooltip Placements</h3>
        <div className="flex flex-wrap gap-2">
          <Tooltip content="Top" placement="top">
            <Button size="sm">Top</Button>
          </Tooltip>
          <Tooltip content="Bottom" placement="bottom">
            <Button size="sm">Bottom</Button>
          </Tooltip>
          <Tooltip content="Left" placement="left">
            <Button size="sm">Left</Button>
          </Tooltip>
          <Tooltip content="Right" placement="right">
            <Button size="sm">Right</Button>
          </Tooltip>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Tooltip with Delay</h3>
        <Tooltip content="This tooltip has a delay" delay={1000}>
          <Button>Hover (1s delay)</Button>
        </Tooltip>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Tooltip with Arrow</h3>
        <Tooltip content="Tooltip with arrow" showArrow>
          <Button>With Arrow</Button>
        </Tooltip>
      </section>
    </div>
  ),
};

export const SpinnerExamples: Story = {
  render: () => (
    <div className="flex flex-col gap-8 p-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Spinner Sizes</h3>
        <div className="flex items-center gap-4">
          <Spinner size="sm" />
          <Spinner size="md" />
          <Spinner size="lg" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Spinner Colors</h3>
        <div className="flex flex-wrap gap-4">
          <Spinner color="default" />
          <Spinner color="primary" />
          <Spinner color="secondary" />
          <Spinner color="success" />
          <Spinner color="warning" />
          <Spinner color="danger" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Spinner with Label</h3>
        <div className="flex flex-col gap-4">
          <Spinner label="Loading..." />
          <Spinner label="Please wait" color="primary" />
          <Spinner label="Processing" color="success" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Spinner in Button</h3>
        <div className="flex gap-2">
          <Button isLoading color="primary">
            Loading
          </Button>
          <Button isLoading color="secondary" variant="bordered">
            Processing
          </Button>
        </div>
      </section>
    </div>
  ),
};
