import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Switch } from '@/components/ui/switch'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { MoreHorizontal, Eye, Download, RefreshCw, CheckCircle2, XCircle } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import type { Chunk } from './types'

interface ChunkTableProps {
  chunks: (Chunk & { documentId: string; documentTitle: string; documentType: string })[]
  selectedChunks: string[]
  chunkSwitch: Record<string, boolean>
  onChunkSelect: (chunkId: string) => void
  onSelectAll: () => void
  onSwitchChange: (chunkId: string, value: boolean) => void
  onChunkEdit: (chunk: Chunk) => void
  onViewDetail: (chunk: Chunk) => void
}

export function ChunkTable({
  chunks,
  selectedChunks,
  chunkSwitch,
  onChunkSelect,
  onSelectAll,
  onSwitchChange,
  onChunkEdit,
  onViewDetail,
}: ChunkTableProps) {
  return (
    <div className="overflow-x-auto">
      <Table className="border-0">
        <TableHeader>
          <TableRow>
            <TableHead className="w-[40px]">
              <Checkbox
                checked={selectedChunks.length === chunks.length && chunks.length > 0}
                onCheckedChange={onSelectAll}
              />
            </TableHead>
            <TableHead className="w-[100px]">Chunk ID</TableHead>
            <TableHead>Content</TableHead>
            <TableHead className="w-[100px]">Tokens</TableHead>
            <TableHead className="w-[100px]">Vectorized</TableHead>
            <TableHead className="w-[100px]">Indexed</TableHead>
            <TableHead className="w-[150px]">Position</TableHead>
            <TableHead className="w-[100px]">Actions</TableHead>
            <TableHead className="w-[80px]">Switch</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {chunks.map((chunk) => (
            <TableRow key={chunk.id}>
              <TableCell>
                <Checkbox
                  checked={selectedChunks.includes(chunk.id)}
                  onCheckedChange={() => onChunkSelect(chunk.id)}
                />
              </TableCell>
              <TableCell className="font-medium">
                {chunk.id}
              </TableCell>
              <TableCell>
                <div
                  className="max-w-[400px] line-clamp-2 cursor-pointer text-primary hover:text-primary hover:underline transition-colors"
                  onClick={() => onChunkEdit(chunk)}
                >
                  {chunk.content}
                </div>
              </TableCell>
              <TableCell>
                <Badge variant="outline">{chunk.tokens}</Badge>
              </TableCell>
              <TableCell>
                {chunk.vectorized ? (
                  <Badge variant="default" className="bg-success">
                    <CheckCircle2 className="mr-1 h-3 w-3" />
                    Completed
                  </Badge>
                ) : (
                  <Badge variant="outline">
                    <XCircle className="mr-1 h-3 w-3" />
                    Pending
                  </Badge>
                )}
              </TableCell>
              <TableCell>
                {chunk.indexed ? (
                  <Badge variant="default" className="bg-success">
                    <CheckCircle2 className="mr-1 h-3 w-3" />
                    Completed
                  </Badge>
                ) : (
                  <Badge variant="outline">
                    <XCircle className="mr-1 h-3 w-3" />
                    Pending
                  </Badge>
                )}
              </TableCell>
              <TableCell>
                <span className="text-sm text-muted-foreground">
                  {chunk.metadata.startIndex} - {chunk.metadata.endIndex}
                </span>
              </TableCell>
              <TableCell>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button variant="ghost" size="sm" onClick={() => onViewDetail(chunk)}>
                        <RefreshCw className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>Rechunk</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </TableCell>
              <TableCell>
                <Switch
                  checked={chunkSwitch[chunk.id] ?? true}
                  onCheckedChange={v => onSwitchChange(chunk.id, v)}
                />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
} 