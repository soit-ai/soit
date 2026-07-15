import { useMemo, type ReactNode } from 'react'

import { flexRender, getCoreRowModel, useReactTable, type ColumnDef } from '@tanstack/react-table'

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'

export interface BoxDataTableColumn<T> {
  id: string
  header: ReactNode
  className?: string
  cellClassName?: string
  render: (row: T) => ReactNode
}

interface BoxDataTableProps<T extends { id: string }> {
  columns: BoxDataTableColumn<T>[]
  rows: T[]
  emptyMessage?: ReactNode
  className?: string
  onRowClick?: (row: T) => void
  getRowClassName?: (row: T) => string | undefined
}

export function BoxDataTable<T extends { id: string }>({
  columns,
  rows,
  emptyMessage,
  className,
  onRowClick,
  getRowClassName,
}: BoxDataTableProps<T>) {
  const tableColumns = useMemo<ColumnDef<T>[]>(
    () =>
      columns.map((column) => ({
        id: column.id,
        header: () => column.header,
        cell: ({ row }) => column.render(row.original),
      })),
    [columns],
  )
  const columnConfig = useMemo(() => new Map(columns.map((column) => [column.id, column])), [columns])
  const table = useReactTable({
    data: rows,
    columns: tableColumns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id,
  })
  const leafColumnCount = table.getAllLeafColumns().length

  return (
    <div className={cn('min-w-0 w-full max-w-full overflow-x-auto rounded-lg border border-border bg-panel shadow-sm', className)}>
      <Table className="w-max min-w-full">
        <TableHeader className="bg-muted/60">
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id} className="hover:bg-muted/60">
              {headerGroup.headers.map((header) => {
                const config = columnConfig.get(header.column.id)

                return (
                  <TableHead
                    key={header.id}
                    colSpan={header.colSpan}
                    className={cn('h-10 px-5 text-xs font-semibold text-muted-foreground', config?.className)}
                  >
                    {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                )
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.length ? table.getRowModel().rows.map((row) => (
            <TableRow
              key={row.id}
              className={cn(
                'h-[62px] border-border/70 hover:bg-primary/5',
                onRowClick && 'cursor-pointer',
                getRowClassName?.(row.original),
              )}
              onClick={() => onRowClick?.(row.original)}
            >
              {row.getVisibleCells().map((cell) => {
                const config = columnConfig.get(cell.column.id)

                return (
                  <TableCell key={cell.id} className={cn('px-5 py-3 text-sm text-foreground/80', config?.cellClassName)}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                )
              })}
            </TableRow>
          )) : (
            <TableRow>
              <TableCell colSpan={leafColumnCount} className="h-28 text-center text-sm text-muted-foreground">
                {emptyMessage}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
