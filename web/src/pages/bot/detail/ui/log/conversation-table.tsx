import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Pagination, PaginationContent, PaginationEllipsis, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from '@/components/ui/pagination'
import { ConversationStatusBadge } from './log-badge'
import { useTranslation } from '@/i18n'

type Conversation = {
  id: string
  startTime: string
  endTime: string
  user: string
  messageCount: number
  status: 'completed' | 'error' | 'interrupted'
}

type ConversationTableProps = {
  conversations: Conversation[]
  isLoading: boolean
  currentPage: number
  setCurrentPage: (page: number) => void
}

export function ConversationTable({ 
  conversations, 
  isLoading, 
  currentPage, 
  setCurrentPage 
}: ConversationTableProps) {
  const { t } = useTranslation()

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle>{t('bot.log.conversations.title')}</CardTitle>
        <CardDescription>{t('bot.log.conversations.description')}</CardDescription>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[400px]">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('bot.log.conversations.columns.id')}</TableHead>
                <TableHead>{t('bot.log.conversations.columns.startTime')}</TableHead>
                <TableHead>{t('bot.log.conversations.columns.endTime')}</TableHead>
                <TableHead>{t('bot.log.conversations.columns.user')}</TableHead>
                <TableHead>{t('bot.log.conversations.columns.messageCount')}</TableHead>
                <TableHead>{t('bot.log.conversations.columns.status')}</TableHead>
                <TableHead>{t('bot.log.conversations.columns.actions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-4">{t('bot.log.conversations.loading')}</TableCell>
                </TableRow>
              ) : conversations.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-4">{t('bot.log.conversations.empty')}</TableCell>
                </TableRow>
              ) : (
                conversations.map((conversation) => (
                  <TableRow key={conversation.id}>
                    <TableCell className="font-mono text-xs">{conversation.id}</TableCell>
                    <TableCell>{conversation.startTime}</TableCell>
                    <TableCell>{conversation.endTime}</TableCell>
                    <TableCell>{conversation.user}</TableCell>
                    <TableCell>{conversation.messageCount}</TableCell>
                    <TableCell><ConversationStatusBadge status={conversation.status} /></TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm">{t('bot.log.conversations.viewDetails')}</Button>
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
              <PaginationPrevious href="#" onClick={() => setCurrentPage(Math.max(1, currentPage - 1))} />
            </PaginationItem>
            <PaginationItem>
              <PaginationLink href="#" isActive={currentPage === 1} onClick={() => setCurrentPage(1)}>1</PaginationLink>
            </PaginationItem>
            <PaginationItem>
              <PaginationLink href="#" isActive={currentPage === 2} onClick={() => setCurrentPage(2)}>2</PaginationLink>
            </PaginationItem>
            <PaginationItem>
              <PaginationLink href="#" isActive={currentPage === 3} onClick={() => setCurrentPage(3)}>3</PaginationLink>
            </PaginationItem>
            <PaginationItem>
              <PaginationEllipsis />
            </PaginationItem>
            <PaginationItem>
              <PaginationNext href="#" onClick={() => setCurrentPage(currentPage + 1)} />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      </CardFooter>
    </Card>
  )
}
