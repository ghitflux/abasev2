import type { Meta, StoryObj } from '@storybook/react-vite';
import React from 'react';
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
  Button,
  Chip,
  User,
  Avatar,
  Tooltip,
  Pagination,
  Input,
  Dropdown,
  DropdownTrigger,
  DropdownMenu,
  DropdownItem,
} from '@heroui/react';
import { MagnifyingGlassIcon as Search, EllipsisVerticalIcon as MoreVertical, PencilIcon as Edit, TrashIcon as Trash, EyeIcon as Eye, ArrowDownTrayIcon as Download } from '@heroicons/react/24/outline';

const meta: Meta = {
  title: 'Advanced/Tables',
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj;

// Sample Data
const users = [
  {
    id: 1,
    name: 'Tony Reichert',
    role: 'CEO',
    team: 'Management',
    status: 'active',
    age: 29,
    avatar: 'https://i.pravatar.cc/150?u=a042581f4e29026024d',
    email: 'tony.reichert@example.com',
  },
  {
    id: 2,
    name: 'Zoey Lang',
    role: 'Technical Lead',
    team: 'Development',
    status: 'paused',
    age: 25,
    avatar: 'https://i.pravatar.cc/150?u=a042581f4e29026704d',
    email: 'zoey.lang@example.com',
  },
  {
    id: 3,
    name: 'Jane Fisher',
    role: 'Senior Developer',
    team: 'Development',
    status: 'active',
    age: 22,
    avatar: 'https://i.pravatar.cc/150?u=a04258114e29026702d',
    email: 'jane.fisher@example.com',
  },
  {
    id: 4,
    name: 'William Howard',
    role: 'Community Manager',
    team: 'Marketing',
    status: 'vacation',
    age: 28,
    avatar: 'https://i.pravatar.cc/150?u=a048581f4e29026701d',
    email: 'william.howard@example.com',
  },
  {
    id: 5,
    name: 'Kristen Copper',
    role: 'Sales Manager',
    team: 'Sales',
    status: 'active',
    age: 24,
    avatar: 'https://i.pravatar.cc/150?u=a092581d4ef9026700d',
    email: 'kristen.copper@example.com',
  },
];

const statusColorMap: Record<string, 'success' | 'danger' | 'warning'> = {
  active: 'success',
  paused: 'danger',
  vacation: 'warning',
};

export const CompleteDataTable: Story = {
  render: () => {
    const [filterValue, setFilterValue] = React.useState('');
    const [selectedKeys, setSelectedKeys] = React.useState<Set<string>>(new Set());
    const [page, setPage] = React.useState(1);
    const rowsPerPage = 4;

    const filteredItems = React.useMemo(() => {
      return users.filter((user) =>
        user.name.toLowerCase().includes(filterValue.toLowerCase())
      );
    }, [filterValue]);

    const items = React.useMemo(() => {
      const start = (page - 1) * rowsPerPage;
      const end = start + rowsPerPage;
      return filteredItems.slice(start, end);
    }, [page, filteredItems]);

    const pages = Math.ceil(filteredItems.length / rowsPerPage);

    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <Input
            className="w-full max-w-[44%]"
            placeholder="Search by name..."
            value={filterValue}
            onValueChange={setFilterValue}
            startContent={<Search className="text-default-400" />}
          />
          <div className="flex gap-2">
            <Button color="primary" startContent={<Download />}>
              Export
            </Button>
            <Button color="primary">Add New</Button>
          </div>
        </div>

        <div className="text-small text-default-400">
          Total {users.length} users
        </div>

        <Table
          aria-label="Example table with custom cells"
          selectionMode="multiple"
          selectedKeys={selectedKeys}
          onSelectionChange={setSelectedKeys as any}
        >
          <TableHeader>
            <TableColumn>NAME</TableColumn>
            <TableColumn>ROLE</TableColumn>
            <TableColumn>STATUS</TableColumn>
            <TableColumn align="center">ACTIONS</TableColumn>
          </TableHeader>
          <TableBody items={items}>
            {(item) => (
              <TableRow key={item.id}>
                <TableCell>
                  <User
                    name={item.name}
                    description={item.email}
                    avatarProps={{ src: item.avatar }}
                  />
                </TableCell>
                <TableCell>
                  <div className="flex flex-col">
                    <p className="text-bold text-small">{item.role}</p>
                    <p className="text-tiny text-default-400">{item.team}</p>
                  </div>
                </TableCell>
                <TableCell>
                  <Chip
                    color={statusColorMap[item.status]}
                    size="sm"
                    variant="flat"
                  >
                    {item.status}
                  </Chip>
                </TableCell>
                <TableCell>
                  <div className="flex items-center justify-center gap-2">
                    <Tooltip content="Details">
                      <Button
                        isIconOnly
                        size="sm"
                        variant="light"
                      >
                        <Eye className="w-4 h-4" />
                      </Button>
                    </Tooltip>
                    <Tooltip content="Edit">
                      <Button
                        isIconOnly
                        size="sm"
                        variant="light"
                      >
                        <Edit className="w-4 h-4" />
                      </Button>
                    </Tooltip>
                    <Tooltip content="Delete" color="danger">
                      <Button
                        isIconOnly
                        size="sm"
                        variant="light"
                        color="danger"
                      >
                        <Trash className="w-4 h-4" />
                      </Button>
                    </Tooltip>
                  </div>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>

        <div className="flex justify-between items-center">
          <span className="text-small text-default-400">
            {selectedKeys === 'all'
              ? 'All items selected'
              : `${selectedKeys.size} of ${filteredItems.length} selected`}
          </span>
          <Pagination
            isCompact
            showControls
            showShadow
            color="primary"
            page={page}
            total={pages}
            onChange={setPage}
          />
        </div>
      </div>
    );
  },
};

export const SortableTable: Story = {
  render: () => {
    const [sortDescriptor, setSortDescriptor] = React.useState<{
      column: string;
      direction: 'ascending' | 'descending';
    }>({
      column: 'name',
      direction: 'ascending',
    });

    const sortedItems = React.useMemo(() => {
      return [...users].sort((a, b) => {
        const first = a[sortDescriptor.column as keyof typeof a];
        const second = b[sortDescriptor.column as keyof typeof b];
        const cmp = first < second ? -1 : first > second ? 1 : 0;

        return sortDescriptor.direction === 'descending' ? -cmp : cmp;
      });
    }, [sortDescriptor]);

    return (
      <Table
        aria-label="Example table with sorting"
        sortDescriptor={sortDescriptor as any}
        onSortChange={setSortDescriptor as any}
      >
        <TableHeader>
          <TableColumn key="name" allowsSorting>NAME</TableColumn>
          <TableColumn key="role" allowsSorting>ROLE</TableColumn>
          <TableColumn key="status" allowsSorting>STATUS</TableColumn>
          <TableColumn key="age" allowsSorting>AGE</TableColumn>
        </TableHeader>
        <TableBody items={sortedItems}>
          {(item) => (
            <TableRow key={item.id}>
              <TableCell>{item.name}</TableCell>
              <TableCell>{item.role}</TableCell>
              <TableCell>
                <Chip color={statusColorMap[item.status]} size="sm" variant="flat">
                  {item.status}
                </Chip>
              </TableCell>
              <TableCell>{item.age}</TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    );
  },
};

export const EmptyState: Story = {
  render: () => (
    <Table aria-label="Example empty table">
      <TableHeader>
        <TableColumn>NAME</TableColumn>
        <TableColumn>ROLE</TableColumn>
        <TableColumn>STATUS</TableColumn>
      </TableHeader>
      <TableBody emptyContent={'No rows to display.'}>
        {[]}
      </TableBody>
    </Table>
  ),
};

export const LoadingState: Story = {
  render: () => (
    <Table aria-label="Example table with loading state">
      <TableHeader>
        <TableColumn>NAME</TableColumn>
        <TableColumn>ROLE</TableColumn>
        <TableColumn>STATUS</TableColumn>
      </TableHeader>
      <TableBody
        items={[]}
        loadingContent={'Loading...'}
        loadingState="loading"
      >
        {[]}
      </TableBody>
    </Table>
  ),
};

export const WithDropdownActions: Story = {
  render: () => (
    <Table aria-label="Example table with dropdown actions">
      <TableHeader>
        <TableColumn>NAME</TableColumn>
        <TableColumn>ROLE</TableColumn>
        <TableColumn>STATUS</TableColumn>
        <TableColumn align="end">ACTIONS</TableColumn>
      </TableHeader>
      <TableBody items={users.slice(0, 3)}>
        {(item) => (
          <TableRow key={item.id}>
            <TableCell>
              <User
                name={item.name}
                description={item.email}
                avatarProps={{ src: item.avatar }}
              />
            </TableCell>
            <TableCell>{item.role}</TableCell>
            <TableCell>
              <Chip color={statusColorMap[item.status]} size="sm" variant="flat">
                {item.status}
              </Chip>
            </TableCell>
            <TableCell>
              <div className="flex justify-end">
                <Dropdown>
                  <DropdownTrigger>
                    <Button isIconOnly size="sm" variant="light">
                      <MoreVertical className="w-4 h-4" />
                    </Button>
                  </DropdownTrigger>
                  <DropdownMenu>
                    <DropdownItem>View</DropdownItem>
                    <DropdownItem>Edit</DropdownItem>
                    <DropdownItem className="text-danger" color="danger">
                      Delete
                    </DropdownItem>
                  </DropdownMenu>
                </Dropdown>
              </div>
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  ),
};

export const CompactTable: Story = {
  render: () => (
    <Table
      aria-label="Compact table"
      isCompact
      removeWrapper
    >
      <TableHeader>
        <TableColumn>NAME</TableColumn>
        <TableColumn>ROLE</TableColumn>
        <TableColumn>STATUS</TableColumn>
      </TableHeader>
      <TableBody items={users}>
        {(item) => (
          <TableRow key={item.id}>
            <TableCell>{item.name}</TableCell>
            <TableCell>{item.role}</TableCell>
            <TableCell>
              <Chip color={statusColorMap[item.status]} size="sm" variant="dot">
                {item.status}
              </Chip>
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  ),
};
