import type { Meta, StoryObj } from '@storybook/react-vite';
import React from 'react';
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
  Avatar,
  Badge,
  Chip,
  Code,
  Snippet,
  Image,
  Skeleton,
  Progress,
  CircularProgress,
  Pagination,
  User,
} from '@heroui/react';

const meta: Meta = {
  title: 'HeroUI/Data Display/Table',
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj;

export const TableExamples: Story = {
  render: () => (
    <div className="w-full space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Basic Table</h3>
        <Table aria-label="Example static collection table">
          <TableHeader>
            <TableColumn>NAME</TableColumn>
            <TableColumn>ROLE</TableColumn>
            <TableColumn>STATUS</TableColumn>
          </TableHeader>
          <TableBody>
            <TableRow key="1">
              <TableCell>Tony Reichert</TableCell>
              <TableCell>CEO</TableCell>
              <TableCell>Active</TableCell>
            </TableRow>
            <TableRow key="2">
              <TableCell>Zoey Lang</TableCell>
              <TableCell>Technical Lead</TableCell>
              <TableCell>Paused</TableCell>
            </TableRow>
            <TableRow key="3">
              <TableCell>Jane Fisher</TableCell>
              <TableCell>Senior Developer</TableCell>
              <TableCell>Active</TableCell>
            </TableRow>
            <TableRow key="4">
              <TableCell>William Howard</TableCell>
              <TableCell>Community Manager</TableCell>
              <TableCell>Vacation</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Table with Custom Cells</h3>
        <Table aria-label="Example table with custom cells">
          <TableHeader>
            <TableColumn>USER</TableColumn>
            <TableColumn>ROLE</TableColumn>
            <TableColumn>STATUS</TableColumn>
          </TableHeader>
          <TableBody>
            <TableRow key="1">
              <TableCell>
                <User
                  name="Tony Reichert"
                  description="tony@example.com"
                  avatarProps={{ src: 'https://i.pravatar.cc/150?u=a042581f4e29026024d' }}
                />
              </TableCell>
              <TableCell>CEO</TableCell>
              <TableCell>
                <Chip color="success" size="sm" variant="flat">Active</Chip>
              </TableCell>
            </TableRow>
            <TableRow key="2">
              <TableCell>
                <User
                  name="Zoey Lang"
                  description="zoey@example.com"
                  avatarProps={{ src: 'https://i.pravatar.cc/150?u=a042581f4e29026704d' }}
                />
              </TableCell>
              <TableCell>Technical Lead</TableCell>
              <TableCell>
                <Chip color="warning" size="sm" variant="flat">Paused</Chip>
              </TableCell>
            </TableRow>
            <TableRow key="3">
              <TableCell>
                <User
                  name="Jane Fisher"
                  description="jane@example.com"
                  avatarProps={{ src: 'https://i.pravatar.cc/150?u=a04258114e29026702d' }}
                />
              </TableCell>
              <TableCell>Senior Developer</TableCell>
              <TableCell>
                <Chip color="success" size="sm" variant="flat">Active</Chip>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Table with Selection</h3>
        <Table
          aria-label="Example table with selection"
          selectionMode="multiple"
          defaultSelectedKeys={['2', '4']}
        >
          <TableHeader>
            <TableColumn>NAME</TableColumn>
            <TableColumn>ROLE</TableColumn>
            <TableColumn>STATUS</TableColumn>
          </TableHeader>
          <TableBody>
            <TableRow key="1">
              <TableCell>Tony Reichert</TableCell>
              <TableCell>CEO</TableCell>
              <TableCell>Active</TableCell>
            </TableRow>
            <TableRow key="2">
              <TableCell>Zoey Lang</TableCell>
              <TableCell>Technical Lead</TableCell>
              <TableCell>Paused</TableCell>
            </TableRow>
            <TableRow key="3">
              <TableCell>Jane Fisher</TableCell>
              <TableCell>Senior Developer</TableCell>
              <TableCell>Active</TableCell>
            </TableRow>
            <TableRow key="4">
              <TableCell>William Howard</TableCell>
              <TableCell>Community Manager</TableCell>
              <TableCell>Vacation</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </section>
    </div>
  ),
};

export const AvatarExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Avatar Sizes</h3>
        <div className="flex gap-4 items-center">
          <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" size="sm" />
          <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" size="md" />
          <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" size="lg" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Avatar with Initials</h3>
        <div className="flex gap-4">
          <Avatar name="Jane Doe" />
          <Avatar name="John Smith" />
          <Avatar name="AB" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Avatar Colors</h3>
        <div className="flex gap-4">
          <Avatar name="D" color="default" />
          <Avatar name="P" color="primary" />
          <Avatar name="S" color="secondary" />
          <Avatar name="Su" color="success" />
          <Avatar name="W" color="warning" />
          <Avatar name="Da" color="danger" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Avatar Radius</h3>
        <div className="flex gap-4">
          <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" radius="none" />
          <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" radius="sm" />
          <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" radius="md" />
          <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" radius="lg" />
          <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" radius="full" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Avatar Group</h3>
        <div className="flex -space-x-2">
          <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" />
          <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026704d" />
          <Avatar src="https://i.pravatar.cc/150?u=a04258114e29026702d" />
          <Avatar src="https://i.pravatar.cc/150?u=a048581f4e29026701d" />
          <Avatar name="+5" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Avatar with Badge</h3>
        <div className="flex gap-4">
          <Badge content="" color="success" shape="circle" placement="bottom-right">
            <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" />
          </Badge>
          <Badge content="5" color="danger" shape="circle">
            <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" />
          </Badge>
        </div>
      </section>
    </div>
  ),
};

export const BadgeExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Badge Colors</h3>
        <div className="flex gap-4">
          <Badge content="5" color="default">
            <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" />
          </Badge>
          <Badge content="5" color="primary">
            <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" />
          </Badge>
          <Badge content="5" color="secondary">
            <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" />
          </Badge>
          <Badge content="5" color="success">
            <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" />
          </Badge>
          <Badge content="5" color="warning">
            <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" />
          </Badge>
          <Badge content="5" color="danger">
            <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" />
          </Badge>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Badge Placements</h3>
        <div className="flex gap-8">
          <Badge content="5" placement="top-right">
            <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" />
          </Badge>
          <Badge content="5" placement="bottom-right">
            <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" />
          </Badge>
          <Badge content="5" placement="top-left">
            <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" />
          </Badge>
          <Badge content="5" placement="bottom-left">
            <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" />
          </Badge>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Badge Shapes</h3>
        <div className="flex gap-4">
          <Badge content="5" shape="rectangle">
            <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" />
          </Badge>
          <Badge content="5" shape="circle">
            <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" />
          </Badge>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Badge as Dot</h3>
        <div className="flex gap-4">
          <Badge content="" color="success" shape="circle" placement="bottom-right">
            <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" />
          </Badge>
          <Badge content="" color="danger" shape="circle" placement="bottom-right">
            <Avatar src="https://i.pravatar.cc/150?u=a042581f4e29026024d" />
          </Badge>
        </div>
      </section>
    </div>
  ),
};

export const ChipExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Chip Colors</h3>
        <div className="flex flex-wrap gap-2">
          <Chip color="default">Default</Chip>
          <Chip color="primary">Primary</Chip>
          <Chip color="secondary">Secondary</Chip>
          <Chip color="success">Success</Chip>
          <Chip color="warning">Warning</Chip>
          <Chip color="danger">Danger</Chip>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Chip Variants</h3>
        <div className="flex flex-wrap gap-2">
          <Chip variant="solid" color="primary">Solid</Chip>
          <Chip variant="bordered" color="primary">Bordered</Chip>
          <Chip variant="light" color="primary">Light</Chip>
          <Chip variant="flat" color="primary">Flat</Chip>
          <Chip variant="faded" color="primary">Faded</Chip>
          <Chip variant="shadow" color="primary">Shadow</Chip>
          <Chip variant="dot" color="primary">Dot</Chip>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Chip Sizes</h3>
        <div className="flex items-center gap-2">
          <Chip size="sm" color="primary">Small</Chip>
          <Chip size="md" color="primary">Medium</Chip>
          <Chip size="lg" color="primary">Large</Chip>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Chip with Avatar</h3>
        <div className="flex gap-2">
          <Chip
            avatar={<Avatar name="JW" src="https://i.pravatar.cc/150?u=a042581f4e29026024d" />}
          >
            Jane Wilson
          </Chip>
          <Chip
            avatar={<Avatar name="JS" src="https://i.pravatar.cc/150?u=a042581f4e29026704d" />}
            color="secondary"
          >
            John Smith
          </Chip>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Closeable Chip</h3>
        <div className="flex gap-2">
          <Chip onClose={() => console.log('close')}>Closeable</Chip>
          <Chip onClose={() => console.log('close')} color="primary">Primary</Chip>
          <Chip onClose={() => console.log('close')} color="danger">Danger</Chip>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Chip with Icons</h3>
        <div className="flex gap-2">
          <Chip startContent={<span>✓</span>} color="success">Verified</Chip>
          <Chip startContent={<span>★</span>} color="warning">Premium</Chip>
          <Chip endContent={<span>→</span>} color="primary">Next</Chip>
        </div>
      </section>
    </div>
  ),
};

export const CodeExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Inline Code</h3>
        <div className="space-y-2">
          <p>Use <Code>npm install</Code> to install packages</p>
          <p>The <Code color="primary">const</Code> keyword declares a constant</p>
          <p>Press <Code color="warning">Ctrl + C</Code> to copy</p>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Code Colors</h3>
        <div className="flex flex-wrap gap-2">
          <Code color="default">Default</Code>
          <Code color="primary">Primary</Code>
          <Code color="secondary">Secondary</Code>
          <Code color="success">Success</Code>
          <Code color="warning">Warning</Code>
          <Code color="danger">Danger</Code>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Code Sizes</h3>
        <div className="flex items-center gap-2">
          <Code size="sm">Small</Code>
          <Code size="md">Medium</Code>
          <Code size="lg">Large</Code>
        </div>
      </section>
    </div>
  ),
};

export const SnippetExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Basic Snippet</h3>
        <Snippet>npm install @heroui/react</Snippet>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Snippet Colors</h3>
        <div className="space-y-3">
          <Snippet color="default">npm install</Snippet>
          <Snippet color="primary">git clone repository</Snippet>
          <Snippet color="secondary">docker run container</Snippet>
          <Snippet color="success">yarn install</Snippet>
          <Snippet color="warning">rm -rf node_modules</Snippet>
          <Snippet color="danger">sudo rm -rf /</Snippet>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Multi-line Snippet</h3>
        <Snippet>
          {`npm install @heroui/react
npm install framer-motion
npm install tailwindcss`}
        </Snippet>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Hide Symbol</h3>
        <Snippet hideSymbol>npm install @heroui/react</Snippet>
      </section>
    </div>
  ),
};

export const ImageExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Basic Image</h3>
        <Image
          width={300}
          alt="Example image"
          src="https://nextui.org/images/hero-card-complete.jpeg"
        />
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Image with Loading</h3>
        <Image
          width={300}
          alt="Example image"
          src="https://nextui.org/images/card-example-4.jpeg"
          isLoading
        />
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Zoomed Image</h3>
        <Image
          width={300}
          alt="Example image"
          src="https://nextui.org/images/card-example-5.jpeg"
          isZoomed
        />
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Blurred Image</h3>
        <Image
          width={300}
          alt="Example image"
          src="https://nextui.org/images/card-example-6.jpeg"
          isBlurred
        />
      </section>
    </div>
  ),
};

export const SkeletonExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Basic Skeleton</h3>
        <div className="space-y-3">
          <Skeleton className="rounded-lg">
            <div className="h-24 rounded-lg bg-default-300"></div>
          </Skeleton>
          <div className="space-y-2">
            <Skeleton className="w-3/5 rounded-lg">
              <div className="h-3 w-3/5 rounded-lg bg-default-200"></div>
            </Skeleton>
            <Skeleton className="w-4/5 rounded-lg">
              <div className="h-3 w-4/5 rounded-lg bg-default-200"></div>
            </Skeleton>
            <Skeleton className="w-2/5 rounded-lg">
              <div className="h-3 w-2/5 rounded-lg bg-default-300"></div>
            </Skeleton>
          </div>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Card Skeleton</h3>
        <div className="max-w-[300px] w-full flex items-center gap-3">
          <div>
            <Skeleton className="flex rounded-full w-12 h-12" />
          </div>
          <div className="w-full flex flex-col gap-2">
            <Skeleton className="h-3 w-3/5 rounded-lg" />
            <Skeleton className="h-3 w-4/5 rounded-lg" />
          </div>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Loading State</h3>
        {(() => {
          const [isLoaded, setIsLoaded] = React.useState(false);

          React.useEffect(() => {
            setTimeout(() => setIsLoaded(true), 2000);
          }, []);

          return (
            <div className="max-w-[300px]">
              <Skeleton isLoaded={isLoaded} className="rounded-lg">
                <div className="h-24 rounded-lg bg-secondary"></div>
              </Skeleton>
              <div className="space-y-3 mt-3">
                <Skeleton isLoaded={isLoaded} className="w-3/5 rounded-lg">
                  <div className="h-3 w-3/5 rounded-lg bg-secondary"></div>
                </Skeleton>
                <Skeleton isLoaded={isLoaded} className="w-4/5 rounded-lg">
                  <div className="h-3 w-4/5 rounded-lg bg-secondary-300"></div>
                </Skeleton>
              </div>
            </div>
          );
        })()}
      </section>
    </div>
  ),
};

export const ProgressExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Progress Colors</h3>
        <div className="space-y-4">
          <Progress value={65} color="default" />
          <Progress value={65} color="primary" />
          <Progress value={65} color="secondary" />
          <Progress value={65} color="success" />
          <Progress value={65} color="warning" />
          <Progress value={65} color="danger" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Progress Sizes</h3>
        <div className="space-y-4">
          <Progress value={65} size="sm" color="primary" />
          <Progress value={65} size="md" color="primary" />
          <Progress value={65} size="lg" color="primary" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Progress with Label</h3>
        <Progress
          label="Downloading..."
          value={65}
          color="primary"
          showValueLabel={true}
        />
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Circular Progress</h3>
        <div className="flex gap-4">
          <CircularProgress value={65} color="primary" />
          <CircularProgress value={75} color="secondary" />
          <CircularProgress value={85} color="success" />
          <CircularProgress value={95} color="warning" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Circular Progress with Label</h3>
        <CircularProgress
          value={65}
          color="primary"
          showValueLabel={true}
          label="Loading"
        />
      </section>
    </div>
  ),
};

export const PaginationExamples: Story = {
  render: () => (
    <div className="w-full max-w-2xl space-y-8">
      <section>
        <h3 className="text-lg font-semibold mb-4">Basic Pagination</h3>
        <Pagination total={10} initialPage={1} />
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Pagination Colors</h3>
        <div className="space-y-4">
          <Pagination total={5} initialPage={1} color="primary" />
          <Pagination total={5} initialPage={1} color="secondary" />
          <Pagination total={5} initialPage={1} color="success" />
          <Pagination total={5} initialPage={1} color="warning" />
          <Pagination total={5} initialPage={1} color="danger" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Pagination Sizes</h3>
        <div className="space-y-4">
          <Pagination total={5} initialPage={1} size="sm" />
          <Pagination total={5} initialPage={1} size="md" />
          <Pagination total={5} initialPage={1} size="lg" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Pagination Variants</h3>
        <div className="space-y-4">
          <Pagination total={5} variant="flat" color="primary" />
          <Pagination total={5} variant="bordered" color="primary" />
          <Pagination total={5} variant="light" color="primary" />
          <Pagination total={5} variant="faded" color="primary" />
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-4">Controlled Pagination</h3>
        {(() => {
          const [currentPage, setCurrentPage] = React.useState(1);

          return (
            <div className="flex flex-col gap-4">
              <p className="text-small text-default-500">Current page: {currentPage}</p>
              <Pagination
                total={10}
                color="primary"
                page={currentPage}
                onChange={setCurrentPage}
              />
            </div>
          );
        })()}
      </section>
    </div>
  ),
};
