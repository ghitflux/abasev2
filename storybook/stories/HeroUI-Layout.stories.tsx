import type { Meta, StoryObj } from '@storybook/react-vite';
import React from 'react';
import {
  Card,
  CardHeader,
  CardBody,
  CardFooter,
  Divider,
  Spacer,
  Navbar,
  NavbarBrand,
  NavbarContent,
  NavbarItem,
  NavbarMenu,
  NavbarMenuItem,
  NavbarMenuToggle,
  Link,
  Button,
  Tabs,
  Tab,
  Accordion,
  AccordionItem,
  Breadcrumbs,
  BreadcrumbItem,
} from '@heroui/react';

const meta: Meta = {
  title: 'HeroUI/Layout & Navigation/Cards',
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj;

export const CardVariants: Story = {
  render: () => (
    <div className="w-full max-w-4xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Card Shadows</h3>
        <div className="grid grid-cols-3 gap-4">
          <Card shadow="none">
            <CardBody>
              <p className="text-sm">Shadow: None</p>
            </CardBody>
          </Card>
          <Card shadow="sm">
            <CardBody>
              <p className="text-sm">Shadow: Small</p>
            </CardBody>
          </Card>
          <Card shadow="md">
            <CardBody>
              <p className="text-sm">Shadow: Medium</p>
            </CardBody>
          </Card>
          <Card shadow="lg">
            <CardBody>
              <p className="text-sm">Shadow: Large</p>
            </CardBody>
          </Card>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Card with Sections</h3>
        <div className="grid grid-cols-2 gap-4">
          <Card className="max-w-[400px]">
            <CardHeader className="flex gap-3">
              <div className="flex flex-col">
                <p className="text-md font-semibold">Card Title</p>
                <p className="text-small text-default-500">Card Subtitle</p>
              </div>
            </CardHeader>
            <Divider />
            <CardBody>
              <p className="text-sm">
                This is the card body content. You can put any content here.
              </p>
            </CardBody>
            <Divider />
            <CardFooter>
              <Button size="sm" color="primary">Action</Button>
            </CardFooter>
          </Card>

          <Card className="max-w-[400px]">
            <CardHeader>
              <h4 className="font-semibold">Simple Card</h4>
            </CardHeader>
            <CardBody>
              <p className="text-sm text-default-500">
                Card without dividers and with simple footer
              </p>
            </CardBody>
            <CardFooter className="gap-2">
              <Button size="sm" variant="light">Cancel</Button>
              <Button size="sm" color="primary">Save</Button>
            </CardFooter>
          </Card>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Card Variants</h3>
        <div className="grid grid-cols-3 gap-4">
          <Card>
            <CardBody>
              <p className="text-sm font-semibold mb-1">Default</p>
              <p className="text-xs text-default-500">Default card variant</p>
            </CardBody>
          </Card>
          <Card variant="bordered">
            <CardBody>
              <p className="text-sm font-semibold mb-1">Bordered</p>
              <p className="text-xs text-default-500">Card with border</p>
            </CardBody>
          </Card>
          <Card variant="flat">
            <CardBody>
              <p className="text-sm font-semibold mb-1">Flat</p>
              <p className="text-xs text-default-500">Flat card variant</p>
            </CardBody>
          </Card>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Hoverable & Pressable Cards</h3>
        <div className="grid grid-cols-2 gap-4">
          <Card isHoverable isPressable onPress={() => alert('Card pressed!')}>
            <CardBody>
              <p className="text-sm font-semibold mb-1">Hoverable & Pressable</p>
              <p className="text-xs text-default-500">Click me!</p>
            </CardBody>
          </Card>
          <Card isFooterBlurred className="h-[200px]">
            <CardHeader className="absolute z-10 top-1 flex-col !items-start">
              <p className="text-tiny text-white/60 uppercase font-bold">Card with Image</p>
              <h4 className="text-white font-medium text-large">Background Image</h4>
            </CardHeader>
            <div className="absolute inset-0 bg-gradient-to-br from-primary-500 to-secondary-500" />
            <CardFooter className="absolute bg-black/40 bottom-0 z-10 border-t-1 border-default-600 dark:border-default-100">
              <div className="flex flex-grow gap-2 items-center">
                <div className="flex flex-col">
                  <p className="text-tiny text-white/60">Footer Content</p>
                </div>
              </div>
              <Button radius="full" size="sm">Action</Button>
            </CardFooter>
          </Card>
        </div>
      </section>
    </div>
  ),
};

export const DividerExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Horizontal Divider</h3>
        <Card>
          <CardBody>
            <p>Content above</p>
            <Divider className="my-4" />
            <p>Content below</p>
          </CardBody>
        </Card>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Vertical Divider</h3>
        <div className="flex h-20 items-center">
          <div className="px-4">Left content</div>
          <Divider orientation="vertical" />
          <div className="px-4">Right content</div>
        </div>
      </section>
    </div>
  ),
};

export const SpacerExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Spacer Usage</h3>
        <Card>
          <CardBody>
            <p>First element</p>
            <Spacer y={4} />
            <p>Second element (16px space above)</p>
            <Spacer y={8} />
            <p>Third element (32px space above)</p>
          </CardBody>
        </Card>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Horizontal Spacer</h3>
        <div className="flex">
          <Button>Button 1</Button>
          <Spacer x={4} />
          <Button>Button 2</Button>
        </div>
      </section>
    </div>
  ),
};

export const NavbarExamples: Story = {
  render: () => (
    <div className="w-full space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Basic Navbar</h3>
        <Navbar>
          <NavbarBrand>
            <p className="font-bold text-inherit">ABASE</p>
          </NavbarBrand>
          <NavbarContent className="hidden sm:flex gap-4" justify="center">
            <NavbarItem>
              <Link color="foreground" href="#">
                Features
              </Link>
            </NavbarItem>
            <NavbarItem isActive>
              <Link href="#" aria-current="page">
                Customers
              </Link>
            </NavbarItem>
            <NavbarItem>
              <Link color="foreground" href="#">
                Integrations
              </Link>
            </NavbarItem>
          </NavbarContent>
          <NavbarContent justify="end">
            <NavbarItem className="hidden lg:flex">
              <Link href="#">Login</Link>
            </NavbarItem>
            <NavbarItem>
              <Button as={Link} color="primary" href="#" variant="flat">
                Sign Up
              </Button>
            </NavbarItem>
          </NavbarContent>
        </Navbar>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Navbar with Menu Toggle</h3>
        {(() => {
          const [isMenuOpen, setIsMenuOpen] = React.useState(false);
          const menuItems = ['Profile', 'Dashboard', 'Activity', 'Analytics', 'System', 'Deployments', 'Settings', 'Log Out'];

          return (
            <Navbar onMenuOpenChange={setIsMenuOpen}>
              <NavbarContent>
                <NavbarMenuToggle aria-label={isMenuOpen ? 'Close menu' : 'Open menu'} className="sm:hidden" />
                <NavbarBrand>
                  <p className="font-bold text-inherit">ABASE</p>
                </NavbarBrand>
              </NavbarContent>

              <NavbarContent className="hidden sm:flex gap-4" justify="center">
                <NavbarItem>
                  <Link color="foreground" href="#">Features</Link>
                </NavbarItem>
                <NavbarItem isActive>
                  <Link href="#" aria-current="page" color="primary">Customers</Link>
                </NavbarItem>
                <NavbarItem>
                  <Link color="foreground" href="#">Integrations</Link>
                </NavbarItem>
              </NavbarContent>

              <NavbarContent justify="end">
                <NavbarItem>
                  <Button as={Link} color="primary" href="#" variant="flat">Sign Up</Button>
                </NavbarItem>
              </NavbarContent>

              <NavbarMenu>
                {menuItems.map((item, index) => (
                  <NavbarMenuItem key={`${item}-${index}`}>
                    <Link
                      color={index === menuItems.length - 1 ? 'danger' : 'foreground'}
                      className="w-full"
                      href="#"
                      size="lg"
                    >
                      {item}
                    </Link>
                  </NavbarMenuItem>
                ))}
              </NavbarMenu>
            </Navbar>
          );
        })()}
      </section>
    </div>
  ),
};

export const TabsExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Basic Tabs</h3>
        <Tabs aria-label="Options">
          <Tab key="photos" title="Photos">
            <Card>
              <CardBody>
                Photos content goes here
              </CardBody>
            </Card>
          </Tab>
          <Tab key="music" title="Music">
            <Card>
              <CardBody>
                Music content goes here
              </CardBody>
            </Card>
          </Tab>
          <Tab key="videos" title="Videos">
            <Card>
              <CardBody>
                Videos content goes here
              </CardBody>
            </Card>
          </Tab>
        </Tabs>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Tabs with Colors</h3>
        <div className="space-y-4">
          <Tabs aria-label="Options" color="primary">
            <Tab key="tab1" title="Primary">Content 1</Tab>
            <Tab key="tab2" title="Tab 2">Content 2</Tab>
            <Tab key="tab3" title="Tab 3">Content 3</Tab>
          </Tabs>
          <Tabs aria-label="Options" color="secondary">
            <Tab key="tab1" title="Secondary">Content 1</Tab>
            <Tab key="tab2" title="Tab 2">Content 2</Tab>
            <Tab key="tab3" title="Tab 3">Content 3</Tab>
          </Tabs>
          <Tabs aria-label="Options" color="success">
            <Tab key="tab1" title="Success">Content 1</Tab>
            <Tab key="tab2" title="Tab 2">Content 2</Tab>
            <Tab key="tab3" title="Tab 3">Content 3</Tab>
          </Tabs>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Tabs Variants</h3>
        <div className="space-y-4">
          <Tabs aria-label="Options" variant="solid">
            <Tab key="tab1" title="Solid">Content 1</Tab>
            <Tab key="tab2" title="Tab 2">Content 2</Tab>
          </Tabs>
          <Tabs aria-label="Options" variant="underlined">
            <Tab key="tab1" title="Underlined">Content 1</Tab>
            <Tab key="tab2" title="Tab 2">Content 2</Tab>
          </Tabs>
          <Tabs aria-label="Options" variant="bordered">
            <Tab key="tab1" title="Bordered">Content 1</Tab>
            <Tab key="tab2" title="Tab 2">Content 2</Tab>
          </Tabs>
          <Tabs aria-label="Options" variant="light">
            <Tab key="tab1" title="Light">Content 1</Tab>
            <Tab key="tab2" title="Tab 2">Content 2</Tab>
          </Tabs>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Vertical Tabs</h3>
        <Tabs aria-label="Options" placement="start" isVertical>
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

      <section>
        <h3 className="text-lg font-semibold mb-4">Disabled Tab</h3>
        <Tabs aria-label="Options">
          <Tab key="tab1" title="Enabled">Content 1</Tab>
          <Tab key="tab2" title="Disabled" isDisabled>Content 2</Tab>
          <Tab key="tab3" title="Enabled">Content 3</Tab>
        </Tabs>
      </section>
    </div>
  ),
};

export const AccordionExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Basic Accordion</h3>
        <Accordion>
          <AccordionItem key="1" aria-label="Accordion 1" title="Accordion 1">
            Content for accordion item 1. This content is collapsible.
          </AccordionItem>
          <AccordionItem key="2" aria-label="Accordion 2" title="Accordion 2">
            Content for accordion item 2. This content is collapsible.
          </AccordionItem>
          <AccordionItem key="3" aria-label="Accordion 3" title="Accordion 3">
            Content for accordion item 3. This content is collapsible.
          </AccordionItem>
        </Accordion>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Accordion Variants</h3>
        <div className="space-y-4">
          <Accordion variant="light">
            <AccordionItem title="Light Variant">Content here</AccordionItem>
          </Accordion>
          <Accordion variant="shadow">
            <AccordionItem title="Shadow Variant">Content here</AccordionItem>
          </Accordion>
          <Accordion variant="bordered">
            <AccordionItem title="Bordered Variant">Content here</AccordionItem>
          </Accordion>
          <Accordion variant="splitted">
            <AccordionItem title="Splitted Item 1">Content 1</AccordionItem>
            <AccordionItem title="Splitted Item 2">Content 2</AccordionItem>
          </Accordion>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Multiple Selection</h3>
        <Accordion selectionMode="multiple">
          <AccordionItem key="1" title="Item 1">Content 1</AccordionItem>
          <AccordionItem key="2" title="Item 2">Content 2</AccordionItem>
          <AccordionItem key="3" title="Item 3">Content 3</AccordionItem>
        </Accordion>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">With Subtitle</h3>
        <Accordion>
          <AccordionItem
            key="1"
            aria-label="Item 1"
            title="Item 1"
            subtitle="Press to expand"
          >
            Content for item 1
          </AccordionItem>
          <AccordionItem
            key="2"
            aria-label="Item 2"
            title="Item 2"
            subtitle="More information"
          >
            Content for item 2
          </AccordionItem>
        </Accordion>
      </section>
    </div>
  ),
};

export const BreadcrumbsExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Basic Breadcrumbs</h3>
        <Breadcrumbs>
          <BreadcrumbItem>Home</BreadcrumbItem>
          <BreadcrumbItem>Products</BreadcrumbItem>
          <BreadcrumbItem>Electronics</BreadcrumbItem>
          <BreadcrumbItem>Laptops</BreadcrumbItem>
        </Breadcrumbs>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Breadcrumbs Variants</h3>
        <div className="space-y-4">
          <Breadcrumbs variant="solid">
            <BreadcrumbItem>Home</BreadcrumbItem>
            <BreadcrumbItem>Docs</BreadcrumbItem>
            <BreadcrumbItem>Solid</BreadcrumbItem>
          </Breadcrumbs>
          <Breadcrumbs variant="bordered">
            <BreadcrumbItem>Home</BreadcrumbItem>
            <BreadcrumbItem>Docs</BreadcrumbItem>
            <BreadcrumbItem>Bordered</BreadcrumbItem>
          </Breadcrumbs>
          <Breadcrumbs variant="light">
            <BreadcrumbItem>Home</BreadcrumbItem>
            <BreadcrumbItem>Docs</BreadcrumbItem>
            <BreadcrumbItem>Light</BreadcrumbItem>
          </Breadcrumbs>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">With Custom Separator</h3>
        <Breadcrumbs separator="›">
          <BreadcrumbItem>Home</BreadcrumbItem>
          <BreadcrumbItem>Products</BreadcrumbItem>
          <BreadcrumbItem>Current Page</BreadcrumbItem>
        </Breadcrumbs>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Disabled Item</h3>
        <Breadcrumbs>
          <BreadcrumbItem>Home</BreadcrumbItem>
          <BreadcrumbItem isDisabled>Disabled</BreadcrumbItem>
          <BreadcrumbItem>Current</BreadcrumbItem>
        </Breadcrumbs>
      </section>
    </div>
  ),
};
