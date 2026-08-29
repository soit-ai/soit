/**
 * Dev kitchen sink — renders the console-skinned shared primitives side by
 * side for visual comparison against the v13 prototype. Not linked from any
 * navigation; open /v2/_kitchen directly. Sample copy is intentionally
 * hardcoded English (this screen is a development aid, not product UI).
 */
import { useState } from 'react'

import {
  ConsoleButton,
  ConsoleTabs,
  FilterChip,
  FilterSearch,
  KindChip,
  Pager,
  Seg,
  StatTile,
  StatTileGrid,
  StatusChip,
  Workbench,
  WorkbenchPanel,
} from '../components'
import {
  Badge,
  Button,
  Checkbox,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
} from '../components/ui'

export default function ConsoleKitchen() {
  const [range, setRange] = useState<'1h' | '24h' | '7d' | '30d'>('24h')
  const [tab, setTab] = useState<'library' | 'exceptions' | 'recycle'>('library')

  return (
    <Workbench
      title="Kitchen sink"
      description="Console-skinned shared primitives vs prototype forms. Dev aid, not product UI."
      actions={
        <>
          <Seg options={['1h', '24h', '7d', '30d'] as const} value={range} onChange={setRange} />
          <ConsoleButton>Export</ConsoleButton>
          <ConsoleButton variant="primary">New agent</ConsoleButton>
        </>
      }
      tiles={
        <StatTileGrid>
          <StatTile label="Runs · 24h" value="1,284" delta={{ direction: 'up', label: '+4.1%' }} sub="vs previous" />
          <StatTile label="Policy pass" value="96.4%" delta={{ direction: 'flat', label: '0.0%' }} />
          <StatTile label="Blocked" value="15" delta={{ direction: 'down', label: '-3' }} />
          <StatTile label="Spend" value="—" na />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            { id: 'library', label: 'Library', count: 6 },
            { id: 'exceptions', label: 'Exceptions', count: 2 },
            { id: 'recycle', label: 'Recycle bin' },
          ]}
          value={tab}
          onChange={setTab}
        />
      }
      filters={
        <>
          <FilterChip active count="1,284">All</FilterChip>
          <FilterChip count="1,238">Pass</FilterChip>
          <FilterChip count="31">Degraded</FilterChip>
          <FilterChip>Has audit</FilterChip>
          <FilterSearch placeholder="Filter by run id, tool, artifact…" />
        </>
      }
    >
      <div className="stack">
        <WorkbenchPanel title="Shared table (BoxDataTable base)" hint="prototype density via skin">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Run</TableHead>
                <TableHead>Subject</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="num text-right">Cost</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell><span className="runid">run_01J9KD84QF</span></TableCell>
                <TableCell><KindChip kind="agent" label="support-triage" /></TableCell>
                <TableCell><StatusChip status="pass" /></TableCell>
                <TableCell className="num text-right">$0.041</TableCell>
              </TableRow>
              <TableRow>
                <TableCell><span className="runid">run_01J9KD7Q2M</span></TableCell>
                <TableCell><KindChip kind="workflow" label="ticket-escalation" /></TableCell>
                <TableCell><StatusChip status="degraded" /></TableCell>
                <TableCell className="num text-right">$0.118</TableCell>
              </TableRow>
              <TableRow>
                <TableCell><span className="runid">run_01J9KD5N8B</span></TableCell>
                <TableCell><KindChip kind="knowledge" label="product-docs" /></TableCell>
                <TableCell><StatusChip status="running" /></TableCell>
                <TableCell className="num text-right">—</TableCell>
              </TableRow>
            </TableBody>
          </Table>
          <Pager summary="3 of 1,284 runs" onPrev={() => {}} onNext={() => {}} prevDisabled />
        </WorkbenchPanel>

        <WorkbenchPanel title="Shared form controls" hint="input / select / switch / checkbox">
          <div className="flex flex-wrap items-end gap-4 p-3.5">
            <div className="grid gap-1.5">
              <Label htmlFor="k-name">Agent name</Label>
              <Input id="k-name" placeholder="support-triage" className="w-56" />
            </div>
            <div className="grid gap-1.5">
              <Label>Model</Label>
              <Select defaultValue="gpt">
                <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="gpt">Primary GPT</SelectItem>
                  <SelectItem value="claude">Claude Main</SelectItem>
                  <SelectItem value="llama">OpenRouter Llama</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <label className="flex items-center gap-2 text-xs">
              <Switch defaultChecked /> Enabled
            </label>
            <label className="flex items-center gap-2 text-xs">
              <Checkbox defaultChecked /> Require approval
            </label>
            <Badge>chip-badge</Badge>
          </div>
          <div className="grid gap-1.5 p-3.5 pt-0">
            <Label htmlFor="k-notes">System prompt</Label>
            <Textarea id="k-notes" defaultValue="You are a support triage agent." className="max-w-xl" />
          </div>
        </WorkbenchPanel>

        <WorkbenchPanel title="Shared buttons / overlays / tabs">
          <div className="flex flex-wrap items-center gap-2 p-3.5">
            <Button>Primary</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive">Destructive</Button>
            <Dialog>
              <DialogTrigger render={<Button variant="outline" />}>Open dialog</DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create schedule</DialogTitle>
                  <DialogDescription>Runs are recorded as governed evidence.</DialogDescription>
                </DialogHeader>
                <div className="grid gap-1.5">
                  <Label htmlFor="k-cron">Cron</Label>
                  <Input id="k-cron" defaultValue="0 2 * * *" />
                </div>
                <DialogFooter showCloseButton>
                  <Button>Create</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button variant="ghost" />}>Menu ▾</DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                <DropdownMenuLabel>Actions</DropdownMenuLabel>
                <DropdownMenuItem>Replay run</DropdownMenuItem>
                <DropdownMenuItem>Open trace</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem variant="destructive">Redrive dead-letter</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <div className="p-3.5 pt-0">
            <Tabs defaultValue="a">
              <TabsList>
                <TabsTrigger value="a">Versions <span className="mono">12</span></TabsTrigger>
                <TabsTrigger value="b">Releases <span className="mono">3</span></TabsTrigger>
                <TabsTrigger value="c">Rollback</TabsTrigger>
              </TabsList>
              <TabsContent value="a" className="dim">Shared Tabs restyled to the prototype underline strip.</TabsContent>
              <TabsContent value="b" className="dim">Release list goes here.</TabsContent>
              <TabsContent value="c" className="dim">Rollback panel goes here.</TabsContent>
            </Tabs>
          </div>
        </WorkbenchPanel>
      </div>
    </Workbench>
  )
}
