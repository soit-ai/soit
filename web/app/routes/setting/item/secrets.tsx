import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from '@/i18n'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { toast } from 'sonner'
import { Copy, Plus, RefreshCw, ShieldCheck, Trash2 } from 'lucide-react'
import {
  listSecrets,
  createSecret,
  updateSecret,
  deleteSecret,
  testSecret,
  type Secret,
} from '@/services/secrets-service'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'

type SecretFormState = {
  name: string
  description: string
  value: string
}

const emptyForm = (): SecretFormState => ({
  name: '',
  description: '',
  value: '',
})

function Page() {
  const { t } = useTranslation()
  const [secrets, setSecrets] = useState<Secret[]>([])
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [activeSecret, setActiveSecret] = useState<Secret | null>(null)
  const [form, setForm] = useState<SecretFormState>(() => emptyForm())

  const fetchSecrets = async () => {
    try {
      setLoading(true)
      const data = await listSecrets({ limit: 200, offset: 0 })
      setSecrets(data || [])
    } catch (error) {
      toast.error(t('system.settings.secrets.toast.fetchError'))
      console.error('Failed to fetch secrets:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSecrets()
  }, [])

  const openCreate = () => {
    setForm(emptyForm())
    setActiveSecret(null)
    setCreateOpen(true)
  }

  const openEdit = (secret: Secret) => {
    setActiveSecret(secret)
    setForm({
      name: secret.name,
      description: secret.description || '',
      value: '',
    })
    setEditOpen(true)
  }

  const openDelete = (secret: Secret) => {
    setActiveSecret(secret)
    setDeleteOpen(true)
  }

  const handleCopy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value)
      toast.success(t('system.settings.secrets.toast.copySuccess'))
    } catch (error) {
      toast.error(t('system.settings.secrets.toast.copyError'))
      console.error('Failed to copy secret ref:', error)
    }
  }

  const handleTest = async (secret: Secret) => {
    try {
      await testSecret(secret.id)
      toast.success(t('system.settings.secrets.toast.testSuccess'))
    } catch (error) {
      toast.error(t('system.settings.secrets.toast.testError'))
      console.error('Failed to test secret:', error)
    }
  }

  const handleCreate = async () => {
    if (!form.name.trim() || !form.value.trim()) {
      toast.error(t('system.settings.secrets.toast.validationError'))
      return
    }
    try {
      await createSecret({
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        value: form.value,
      })
      toast.success(t('system.settings.secrets.toast.createSuccess'))
      setCreateOpen(false)
      setForm(emptyForm())
      fetchSecrets()
    } catch (error) {
      toast.error(t('system.settings.secrets.toast.createError'))
      console.error('Failed to create secret:', error)
    }
  }

  const handleUpdate = async () => {
    if (!activeSecret) return
    if (!form.name.trim()) {
      toast.error(t('system.settings.secrets.toast.validationError'))
      return
    }
    try {
      await updateSecret(activeSecret.id, {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        value: form.value.trim() ? form.value : undefined,
      })
      toast.success(t('system.settings.secrets.toast.updateSuccess'))
      setEditOpen(false)
      setActiveSecret(null)
      setForm(emptyForm())
      fetchSecrets()
    } catch (error) {
      toast.error(t('system.settings.secrets.toast.updateError'))
      console.error('Failed to update secret:', error)
    }
  }

  const handleDelete = async () => {
    if (!activeSecret) return
    try {
      await deleteSecret(activeSecret.id)
      toast.success(t('system.settings.secrets.toast.deleteSuccess'))
      setDeleteOpen(false)
      setActiveSecret(null)
      fetchSecrets()
    } catch (error) {
      toast.error(t('system.settings.secrets.toast.deleteError'))
      console.error('Failed to delete secret:', error)
    }
  }

  const rows = useMemo(() => {
    if (!searchQuery.trim()) return secrets
    const keyword = searchQuery.trim().toLowerCase()
    return secrets.filter((secret) => {
      return (
        secret.name.toLowerCase().includes(keyword) ||
        secret.secret_ref.toLowerCase().includes(keyword) ||
        (secret.description || '').toLowerCase().includes(keyword)
      )
    })
  }, [secrets, searchQuery])

  const formatTimestamp = (value?: string | null) => {
    if (!value) return '-'
    return formatDateTime(isoToZonedDate(value))
  }

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t('system.settings.secrets.title')}</CardTitle>
              <CardDescription>{t('system.settings.secrets.description')}</CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder={t('system.settings.secrets.searchPlaceholder')}
                className="hidden h-8 w-[220px] lg:block"
              />
              <Button variant="outline" size="sm" onClick={fetchSecrets} disabled={loading}>
                <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                {t('system.settings.secrets.actions.refresh')}
              </Button>
              <Button size="sm" onClick={openCreate}>
                <Plus className="mr-2 h-4 w-4" />
                {t('system.settings.secrets.actions.create')}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {rows.length === 0 && (
            <div className="text-sm text-muted-foreground">{t('system.settings.secrets.empty')}</div>
          )}
          {rows.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('system.settings.secrets.table.name')}</TableHead>
                  <TableHead>{t('system.settings.secrets.table.ref')}</TableHead>
                  <TableHead>{t('system.settings.secrets.table.description')}</TableHead>
                  <TableHead>{t('system.settings.secrets.table.updatedAt')}</TableHead>
                  <TableHead className="text-right">{t('system.settings.secrets.table.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((secret) => (
                  <TableRow key={secret.id}>
                    <TableCell className="font-medium">{secret.name}</TableCell>
                    <TableCell className="font-mono text-xs">{secret.secret_ref}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{secret.description || '-'}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{formatTimestamp(secret.updated_at)}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button variant="ghost" size="sm" onClick={() => handleCopy(secret.secret_ref)}>
                          <Copy className="mr-1 h-4 w-4" />
                          {t('system.settings.secrets.actions.copy')}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleTest(secret)}>
                          <ShieldCheck className="mr-1 h-4 w-4" />
                          {t('system.settings.secrets.actions.test')}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => openEdit(secret)}>
                          {t('system.settings.secrets.actions.edit')}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => openDelete(secret)}>
                          <Trash2 className="mr-1 h-4 w-4 text-destructive" />
                          {t('system.settings.secrets.actions.delete')}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('system.settings.secrets.create.title')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{t('system.settings.secrets.form.name')}</Label>
              <Input value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label>{t('system.settings.secrets.form.description')}</Label>
              <Input value={form.description} onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label>{t('system.settings.secrets.form.value')}</Label>
              <Input
                type="password"
                value={form.value}
                onChange={(event) => setForm((prev) => ({ ...prev, value: event.target.value }))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              {t('system.settings.secrets.actions.cancel')}
            </Button>
            <Button onClick={handleCreate}>{t('system.settings.secrets.actions.confirm')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('system.settings.secrets.edit.title')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{t('system.settings.secrets.form.name')}</Label>
              <Input value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label>{t('system.settings.secrets.form.description')}</Label>
              <Input value={form.description} onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label>{t('system.settings.secrets.form.rotateValue')}</Label>
              <Input
                type="password"
                value={form.value}
                onChange={(event) => setForm((prev) => ({ ...prev, value: event.target.value }))}
                placeholder={t('system.settings.secrets.form.rotatePlaceholder')}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              {t('system.settings.secrets.actions.cancel')}
            </Button>
            <Button onClick={handleUpdate}>{t('system.settings.secrets.actions.confirm')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('system.settings.secrets.delete.title')}</DialogTitle>
          </DialogHeader>
          <div className="text-sm text-muted-foreground">
            {t('system.settings.secrets.delete.description', { name: activeSecret?.name || '' })}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              {t('system.settings.secrets.actions.cancel')}
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              {t('system.settings.secrets.actions.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default Page
