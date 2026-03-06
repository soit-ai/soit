import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Pagination, PaginationContent, PaginationEllipsis, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from '@/components/ui/pagination'
import { ErrorResolvedBadge } from './log-badge'
import { Info, CheckCircle2 } from 'lucide-react'
import { useTranslation } from '@/i18n'

type Error = {
  id: string
  timestamp: string
  errorCode: string
  message: string
  source: string
  resolved: boolean
}

type ErrorTableProps = {
  errors: Error[]
  isLoading: boolean
}

export function ErrorTable({ errors, isLoading }: ErrorTableProps) {
  const { t } = useTranslation()

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle>{t('bot.log.errors.title')}</CardTitle>
        <CardDescription>{t('bot.log.errors.description')}</CardDescription>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[400px]">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('bot.log.errors.columns.time')}</TableHead>
                <TableHead>{t('bot.log.errors.columns.code')}</TableHead>
                <TableHead>{t('bot.log.errors.columns.message')}</TableHead>
                <TableHead>{t('bot.log.errors.columns.source')}</TableHead>
                <TableHead>{t('bot.log.errors.columns.status')}</TableHead>
                <TableHead>{t('bot.log.errors.columns.actions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-4">{t('bot.log.errors.loading')}</TableCell>
                </TableRow>
              ) : errors.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-4">{t('bot.log.errors.empty')}</TableCell>
                </TableRow>
              ) : (
                errors.map((error) => (
                  <TableRow key={error.id}>
                    <TableCell>{error.timestamp}</TableCell>
                    <TableCell className="font-mono">{error.errorCode}</TableCell>
                    <TableCell>{error.message}</TableCell>
                    <TableCell>{error.source}</TableCell>
                    <TableCell><ErrorResolvedBadge resolved={error.resolved} /></TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button variant="ghost" size="sm" className="h-8 px-2">
                          <Info className="h-4 w-4" />
                        </Button>
                        {!error.resolved && (
                          <Button variant="ghost" size="sm" className="h-8 px-2">
                            <CheckCircle2 className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
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
