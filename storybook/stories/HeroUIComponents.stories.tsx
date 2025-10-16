import type { Meta, StoryObj } from '@storybook/react-vite';
import React from 'react';
import {
  Button,
  Card,
  CardHeader,
  CardBody,
  CardFooter,
  Input,
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  useDisclosure,
  Dropdown,
  DropdownTrigger,
  DropdownMenu,
  DropdownItem,
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
  Tabs,
  Tab,
  Chip,
  Avatar,
  Badge,
  Checkbox,
  Radio,
  RadioGroup,
  Switch,
  Select,
  SelectItem,
  Slider,
  Progress,
  Spinner,
  Tooltip,
  Popover,
  PopoverTrigger,
  PopoverContent,
  Navbar,
  NavbarBrand,
  NavbarContent,
  NavbarItem,
  Accordion,
  AccordionItem,
  Pagination,
  Breadcrumbs,
  BreadcrumbItem,
} from '@heroui/react';

const meta: Meta = {
  title: 'HeroUI/Components Overview',
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj;

export const AllComponents: Story = {
  render: () => (
    <div className="space-y-12 p-4">
      {/* Buttons */}
      <section>
        <h2 className="text-2xl font-bold mb-4">Buttons</h2>
        <div className="flex flex-wrap gap-4">
          <Button color="default">Default</Button>
          <Button color="primary">Primary</Button>
          <Button color="secondary">Secondary</Button>
          <Button color="success">Success</Button>
          <Button color="warning">Warning</Button>
          <Button color="danger">Danger</Button>
        </div>
        <div className="flex flex-wrap gap-4 mt-4">
          <Button variant="solid" color="primary">Solid</Button>
          <Button variant="bordered" color="primary">Bordered</Button>
          <Button variant="light" color="primary">Light</Button>
          <Button variant="flat" color="primary">Flat</Button>
          <Button variant="faded" color="primary">Faded</Button>
          <Button variant="shadow" color="primary">Shadow</Button>
          <Button variant="ghost" color="primary">Ghost</Button>
        </div>
      </section>

      {/* Cards */}
      <section>
        <h2 className="text-2xl font-bold mb-4">Cards</h2>
        <div className="grid grid-cols-3 gap-4">
          <Card>
            <CardHeader>
              <h4 className="font-semibold">Card Header</h4>
            </CardHeader>
            <CardBody>
              <p className="text-small text-default-500">Card body content goes here</p>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <h4 className="font-semibold mb-2">Simple Card</h4>
              <p className="text-small text-default-500">Without header or footer</p>
            </CardBody>
          </Card>
          <Card>
            <CardHeader>
              <h4 className="font-semibold">With Footer</h4>
            </CardHeader>
            <CardBody>
              <p className="text-small text-default-500">Card content</p>
            </CardBody>
            <CardFooter>
              <Button size="sm" color="primary">Action</Button>
            </CardFooter>
          </Card>
        </div>
      </section>

      {/* Inputs */}
      <section>
        <h2 className="text-2xl font-bold mb-4">Inputs</h2>
        <div className="grid grid-cols-2 gap-4">
          <Input label="Name" placeholder="Enter your name" />
          <Input label="Email" type="email" placeholder="Enter your email" />
          <Input label="Password" type="password" placeholder="Enter your password" />
          <Input
            label="Disabled"
            placeholder="Disabled input"
            isDisabled
          />
        </div>
      </section>

      {/* Select */}
      <section>
        <h2 className="text-2xl font-bold mb-4">Select</h2>
        <div className="grid grid-cols-2 gap-4">
          <Select label="Select an option" placeholder="Choose one">
            <SelectItem key="option1">Option 1</SelectItem>
            <SelectItem key="option2">Option 2</SelectItem>
            <SelectItem key="option3">Option 3</SelectItem>
          </Select>
          <Select label="With default" placeholder="Choose one" defaultSelectedKeys={['option2']}>
            <SelectItem key="option1">Option 1</SelectItem>
            <SelectItem key="option2">Option 2</SelectItem>
            <SelectItem key="option3">Option 3</SelectItem>
          </Select>
        </div>
      </section>

      {/* Checkbox, Radio, Switch */}
      <section>
        <h2 className="text-2xl font-bold mb-4">Form Controls</h2>
        <div className="flex gap-8">
          <div className="space-y-2">
            <p className="text-sm font-semibold mb-2">Checkboxes</p>
            <Checkbox defaultSelected>Option 1</Checkbox>
            <Checkbox>Option 2</Checkbox>
            <Checkbox isDisabled>Disabled</Checkbox>
          </div>
          <div className="space-y-2">
            <p className="text-sm font-semibold mb-2">Radio</p>
            <RadioGroup defaultValue="1">
              <Radio value="1">Option 1</Radio>
              <Radio value="2">Option 2</Radio>
              <Radio value="3">Option 3</Radio>
            </RadioGroup>
          </div>
          <div className="space-y-4">
            <p className="text-sm font-semibold mb-2">Switch</p>
            <Switch defaultSelected>Enabled</Switch>
            <Switch>Disabled</Switch>
          </div>
        </div>
      </section>

      {/* Slider & Progress */}
      <section>
        <h2 className="text-2xl font-bold mb-4">Slider & Progress</h2>
        <div className="space-y-6">
          <div>
            <p className="text-sm mb-2">Slider</p>
            <Slider
              label="Volume"
              step={1}
              minValue={0}
              maxValue={100}
              defaultValue={50}
              className="max-w-md"
            />
          </div>
          <div>
            <p className="text-sm mb-2">Progress</p>
            <Progress value={65} className="max-w-md" color="primary" />
          </div>
        </div>
      </section>

      {/* Chips & Badges */}
      <section>
        <h2 className="text-2xl font-bold mb-4">Chips & Badges</h2>
        <div className="flex gap-4 items-center">
          <Chip color="default">Default</Chip>
          <Chip color="primary">Primary</Chip>
          <Chip color="secondary">Secondary</Chip>
          <Chip color="success">Success</Chip>
          <Chip color="warning">Warning</Chip>
          <Chip color="danger">Danger</Chip>
          <Badge content="5" color="danger">
            <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" />
          </Badge>
        </div>
      </section>

      {/* Avatars */}
      <section>
        <h2 className="text-2xl font-bold mb-4">Avatars</h2>
        <div className="flex gap-4 items-center">
          <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" size="sm" />
          <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" size="md" />
          <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" size="lg" />
          <Avatar name="JD" color="primary" />
          <Avatar name="AB" color="secondary" />
        </div>
      </section>

      {/* Table */}
      <section>
        <h2 className="text-2xl font-bold mb-4">Table</h2>
        <Table aria-label="Example table">
          <TableHeader>
            <TableColumn>NAME</TableColumn>
            <TableColumn>ROLE</TableColumn>
            <TableColumn>STATUS</TableColumn>
          </TableHeader>
          <TableBody>
            <TableRow key="1">
              <TableCell>John Doe</TableCell>
              <TableCell>Developer</TableCell>
              <TableCell>
                <Chip color="success" size="sm">Active</Chip>
              </TableCell>
            </TableRow>
            <TableRow key="2">
              <TableCell>Jane Smith</TableCell>
              <TableCell>Designer</TableCell>
              <TableCell>
                <Chip color="success" size="sm">Active</Chip>
              </TableCell>
            </TableRow>
            <TableRow key="3">
              <TableCell>Bob Johnson</TableCell>
              <TableCell>Manager</TableCell>
              <TableCell>
                <Chip color="warning" size="sm">Away</Chip>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </section>

      {/* Tabs */}
      <section>
        <h2 className="text-2xl font-bold mb-4">Tabs</h2>
        <Tabs aria-label="Options">
          <Tab key="photos" title="Photos">
            <Card>
              <CardBody>Photos content</CardBody>
            </Card>
          </Tab>
          <Tab key="music" title="Music">
            <Card>
              <CardBody>Music content</CardBody>
            </Card>
          </Tab>
          <Tab key="videos" title="Videos">
            <Card>
              <CardBody>Videos content</CardBody>
            </Card>
          </Tab>
        </Tabs>
      </section>

      {/* Accordion */}
      <section>
        <h2 className="text-2xl font-bold mb-4">Accordion</h2>
        <Accordion>
          <AccordionItem key="1" aria-label="Accordion 1" title="Accordion 1">
            Content for accordion 1
          </AccordionItem>
          <AccordionItem key="2" aria-label="Accordion 2" title="Accordion 2">
            Content for accordion 2
          </AccordionItem>
          <AccordionItem key="3" aria-label="Accordion 3" title="Accordion 3">
            Content for accordion 3
          </AccordionItem>
        </Accordion>
      </section>

      {/* Pagination */}
      <section>
        <h2 className="text-2xl font-bold mb-4">Pagination</h2>
        <Pagination total={10} initialPage={1} />
      </section>

      {/* Breadcrumbs */}
      <section>
        <h2 className="text-2xl font-bold mb-4">Breadcrumbs</h2>
        <Breadcrumbs>
          <BreadcrumbItem>Home</BreadcrumbItem>
          <BreadcrumbItem>Products</BreadcrumbItem>
          <BreadcrumbItem>Category</BreadcrumbItem>
          <BreadcrumbItem>Item</BreadcrumbItem>
        </Breadcrumbs>
      </section>

      {/* Spinner */}
      <section>
        <h2 className="text-2xl font-bold mb-4">Spinner</h2>
        <div className="flex gap-4">
          <Spinner size="sm" />
          <Spinner size="md" />
          <Spinner size="lg" />
          <Spinner color="primary" />
          <Spinner color="secondary" />
          <Spinner color="success" />
        </div>
      </section>

      {/* Tooltip */}
      <section>
        <h2 className="text-2xl font-bold mb-4">Tooltip</h2>
        <div className="flex gap-4">
          <Tooltip content="Tooltip on top">
            <Button>Hover me</Button>
          </Tooltip>
          <Tooltip content="Tooltip with color" color="primary">
            <Button color="primary">Primary tooltip</Button>
          </Tooltip>
        </div>
      </section>
    </div>
  ),
};

export const ModalExample: Story = {
  render: function ModalStory() {
    const { isOpen, onOpen, onOpenChange } = useDisclosure();

    return (
      <div>
        <Button onPress={onOpen} color="primary">Open Modal</Button>
        <Modal isOpen={isOpen} onOpenChange={onOpenChange}>
          <ModalContent>
            {(onClose) => (
              <>
                <ModalHeader className="flex flex-col gap-1">Modal Title</ModalHeader>
                <ModalBody>
                  <p>This is the modal body content.</p>
                  <p>You can put any content here.</p>
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
      </div>
    );
  },
};

export const DropdownExample: Story = {
  render: () => (
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
  ),
};

export const PopoverExample: Story = {
  render: () => (
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
  ),
};
