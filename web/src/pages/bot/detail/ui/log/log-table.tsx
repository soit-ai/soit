import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Pagination, PaginationContent, PaginationEllipsis, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from '@/components/ui/pagination'
import { LogTypeBadge } from './log-badge'
import { Info } from 'lucide-react'
import { useTranslation } from '@/i18n'

type Log = {
  id: string
  timestamp: string
  type: 'info' | 'warning' | 'error'
  message: string
  details: string
  sessionId?: string
}

type LogTableProps = {
  logs: Log[]
  isLoading: boolean
}

export function LogTable({ logs, isLoading }: LogTableProps) {
  const { t } = useTranslation()

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle>{t('bot.log.logs.title')}</CardTitle>
        <CardDescription>{t('bot.log.logs.description')}</CardDescription>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[400px]">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('bot.log.logs.columns.time')}</TableHead>
                <TableHead>{t('bot.log.logs.columns.type')}</TableHead>
                <TableHead>{t('bot.log.logs.columns.message')}</TableHead>
                <TableHead>{t('bot.log.logs.columns.sessionId')}</TableHead>
                <TableHead>{t('bot.log.logs.columns.actions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-4">{t('bot.log.logs.loading')}</TableCell>
                </TableRow>
              ) : logs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-4">{t('bot.log.logs.empty')}</TableCell>
                </TableRow>
              ) : (
                logs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell>{log.timestamp}</TableCell>
                    <TableCell><LogTypeBadge type={log.type} /></TableCell>
                    <TableCell>{log.message}</TableCell>
                    <TableCell className="font-mono text-xs">{log.sessionId || '-'}</TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm" className="h-8 px-2">
                        <Info className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </ScrollArea>
      </CardContent>
      <CardFooter>
        <Pagination>
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious href="#" />
            </PaginationItem>
            <PaginationItem>
              <PaginationLink href="#" isActive>1</PaginationLink>
            </PaginationItem>
            <PaginationItem>
              <PaginationLink href="#">2</PaginationLink>
            </PaginationItem>
            <PaginationItem>
              <PaginationLink href="#">3</PaginationLink>
            </PaginationItem>
            <PaginationItem>
              <PaginationEllipsis />
            </PaginationItem>
            <PaginationItem>
              <PaginationNext href="#" />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      </CardFooter>
    </Card>
  )
}
