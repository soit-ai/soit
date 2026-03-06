import React, { useEffect, useState } from 'react'
import { useTranslation } from '@/i18n'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { useNavLayout } from '@/components/layout/nav-layout'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { LockIcon, KeyIcon, ShieldIcon, ClockIcon, PlusIcon, TrashIcon, RefreshCwIcon, UserIcon, ServerIcon } from 'lucide-react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

// Mock API key data.
const mockApiKeys = [
  { id: 'key-001', name: 'Development', key: 'sk-dev-xxxxxxxxxxxx', status: 'active', created: '2025-05-01', lastUsed: '2025-05-31', permissions: ['read', 'write'] },
  { id: 'key-002', name: 'Staging', key: 'sk-test-xxxxxxxxxxxx', status: 'active', created: '2025-05-10', lastUsed: '2025-05-30', permissions: ['read'] },
  { id: 'key-003', name: 'Production', key: 'sk-prod-xxxxxxxxxxxx', status: 'inactive', created: '2025-05-15', lastUsed: '2025-05-20', permissions: ['read', 'write', 'admin'] },
]

// Mock IP allowlist data.
const mockIpWhitelist = [
  { id: 'ip-001', ip: '192.168.1.1', description: 'Office network', created: '2025-05-01' },
  { id: 'ip-002', ip: '10.0.0.1/24', description: 'Dev servers', created: '2025-05-10' },
  { id: 'ip-003', ip: '203.0.113.0/24', description: 'Partner network', created: '2025-05-15' },
]

function BoxHeader({ title, description, onRefresh }: { title: string; description: string; onRefresh?: () => void }) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-1 justify-between">
      <div>
        <h3 className="text-lg font-bold">{title}</h3>
        <p className="text-sm text-muted-foreground mt-1">{description}</p>
      </div>
      {onRefresh && (
        <Button variant="outline" size="sm" onClick={onRefresh}>
          <RefreshCwIcon className="h-4 w-4 mr-2" />
          {t('safe.accessControl.actions.refresh')}
        </Button>
      )}
    </div>
  )
}

interface AccessControlProps {
  subTab?: string | null
}

export function AccessControl({ subTab = null }: AccessControlProps) {
  const { t } = useTranslation()
  const [apiKeys, setApiKeys] = useState(mockApiKeys)
  const [ipWhitelist, setIpWhitelist] = useState(mockIpWhitelist)
  const [newKeyName, setNewKeyName] = useState('')
  const [newKeyPermission, setNewKeyPermission] = useState('read')
  const [newIp, setNewIp] = useState('')
  const [newIpDescription, setNewIpDescription] = useState('')
  const { setHeaderContent } = useNavLayout()

  // Set header content.
  useEffect(() => {
    setHeaderContent(
      <BoxHeader
        title={t('safe.accessControl.header.title')}
        description={t('safe.accessControl.header.description')}
      />
    )
    return () => setHeaderContent(null)
  }, [setHeaderContent, t])

  // Add API key.
  const handleAddApiKey = () => {
    if (!newKeyName.trim()) return

    const newKey = {
      id: `key-${Date.now()}`,
      name: newKeyName.trim(),
      key: `sk-${Math.random().toString(36).substring(2, 10)}-${Math.random().toString(36).substring(2, 10)}`,
      status: 'active',
      created: new Date().toISOString().split('T')[0],
      lastUsed: new Date().toISOString().split('T')[0],
      permissions: [newKeyPermission],
    }

    setApiKeys([...apiKeys, newKey])
    setNewKeyName('')
  }

  // Delete API key.
  const handleDeleteApiKey = (id: string) => {
    setApiKeys(apiKeys.filter((key) => key.id !== id))
  }

  // Add IP allowlist entry.
  const handleAddIpWhitelist = () => {
    if (!newIp.trim()) return

    const newIpEntry = {
      id: `ip-${Date.now()}`,
      ip: newIp.trim(),
      description: newIpDescription.trim(),
      created: new Date().toISOString().split('T')[0],
    }

    setIpWhitelist([...ipWhitelist, newIpEntry])
    setNewIp('')
    setNewIpDescription('')
  }

  // Delete IP allowlist entry.
  const handleDeleteIpWhitelist = (id: string) => {
    setIpWhitelist(ipWhitelist.filter((entry) => entry.id !== id))
  }

  return (
    <div className="space-y-6">
      {/* API key management. */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <KeyIcon className="h-5 w-5 text-primary" />
              <CardTitle>{t('safe.accessControl.apiKeys.title')}</CardTitle>
            </div>
            <Button variant="outline" size="sm">
              <RefreshCwIcon className="h-4 w-4 mr-2" />
              {t('safe.accessControl.actions.refresh')}
            </Button>
          </div>
          <CardDescription>{t('safe.accessControl.apiKeys.description')}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('safe.accessControl.apiKeys.table.name')}</TableHead>
                  <TableHead>{t('safe.accessControl.apiKeys.table.key')}</TableHead>
                  <TableHead>{t('safe.accessControl.apiKeys.table.status')}</TableHead>
                  <TableHead>{t('safe.accessControl.apiKeys.table.permissions')}</TableHead>
                  <TableHead>{t('safe.accessControl.apiKeys.table.created')}</TableHead>
                  <TableHead>{t('safe.accessControl.apiKeys.table.lastUsed')}</TableHead>
                  <TableHead className="text-right">{t('safe.accessControl.apiKeys.table.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {apiKeys.map((key) => (
                  <TableRow key={key.id}>
                    <TableCell className="font-medium">{key.name}</TableCell>
                    <TableCell>
                      <code className="bg-muted px-1 py-0.5 rounded text-sm">{key.key.substring(0, 8)}...</code>
                    </TableCell>
                    <TableCell>
                      {key.status === 'active' ? (
                        <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                          {t('safe.accessControl.apiKeys.status.active')}
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="bg-gray-50 text-gray-700 border-gray-200">
                          {t('safe.accessControl.apiKeys.status.inactive')}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {key.permissions.includes('read') && (
                          <Badge variant="secondary" className="text-xs">
                            {t('safe.accessControl.apiKeys.permissions.read')}
                          </Badge>
                        )}
                        {key.permissions.includes('write') && (
                          <Badge variant="secondary" className="text-xs">
                            {t('safe.accessControl.apiKeys.permissions.write')}
                          </Badge>
                        )}
                        {key.permissions.includes('admin') && (
                          <Badge variant="secondary" className="text-xs">
                            {t('safe.accessControl.apiKeys.permissions.admin')}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>{key.created}</TableCell>
                    <TableCell>{key.lastUsed}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="icon" onClick={() => handleDeleteApiKey(key.id)}>
                        <TrashIcon className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div className="mt-4 flex items-end gap-2">
            <div className="flex-1">
              <Label htmlFor="new-key-name" className="mb-2 block">
                {t('safe.accessControl.apiKeys.fields.name')}
              </Label>
              <Input
                id="new-key-name"
                placeholder={t('safe.accessControl.apiKeys.placeholders.name')}
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="new-key-permission" className="mb-2 block">
                {t('safe.accessControl.apiKeys.fields.permission')}
              </Label>
              <Select value={newKeyPermission} onValueChange={setNewKeyPermission}>
                <SelectTrigger id="new-key-permission" className="w-[120px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="read">{t('safe.accessControl.apiKeys.permissions.readOnly')}</SelectItem>
                  <SelectItem value="write">{t('safe.accessControl.apiKeys.permissions.readWrite')}</SelectItem>
                  <SelectItem value="admin">{t('safe.accessControl.apiKeys.permissions.admin')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button onClick={handleAddApiKey}>
              <PlusIcon className="h-4 w-4 mr-2" />
              {t('safe.accessControl.apiKeys.actions.create')}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* IP allowlist. */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <ServerIcon className="h-5 w-5 text-primary" />
            <CardTitle>{t('safe.accessControl.ipWhitelist.title')}</CardTitle>
          </div>
          <CardDescription>{t('safe.accessControl.ipWhitelist.description')}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('safe.accessControl.ipWhitelist.table.ip')}</TableHead>
                  <TableHead>{t('safe.accessControl.ipWhitelist.table.description')}</TableHead>
                  <TableHead>{t('safe.accessControl.ipWhitelist.table.created')}</TableHead>
                  <TableHead className="text-right">{t('safe.accessControl.ipWhitelist.table.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {ipWhitelist.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="font-medium">
                      <code className="bg-muted px-1 py-0.5 rounded text-sm">{entry.ip}</code>
                    </TableCell>
                    <TableCell>{entry.description}</TableCell>
                    <TableCell>{entry.created}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="icon" onClick={() => handleDeleteIpWhitelist(entry.id)}>
                        <TrashIcon className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div className="mt-4 flex items-end gap-2">
            <div>
              <Label htmlFor="new-ip" className="mb-2 block">
                {t('safe.accessControl.ipWhitelist.fields.ip')}
              </Label>
              <Input
                id="new-ip"
                placeholder={t('safe.accessControl.ipWhitelist.placeholders.ip')}
                value={newIp}
                onChange={(e) => setNewIp(e.target.value)}
              />
            </div>
            <div className="flex-1">
              <Label htmlFor="new-ip-description" className="mb-2 block">
                {t('safe.accessControl.ipWhitelist.fields.description')}
              </Label>
              <Input
                id="new-ip-description"
                placeholder={t('safe.accessControl.ipWhitelist.placeholders.description')}
                value={newIpDescription}
                onChange={(e) => setNewIpDescription(e.target.value)}
              />
            </div>
            <Button onClick={handleAddIpWhitelist}>
              <PlusIcon className="h-4 w-4 mr-2" />
              {t('safe.accessControl.ipWhitelist.actions.add')}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Access control settings. */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <ShieldIcon className="h-5 w-5 text-primary" />
            <CardTitle>{t('safe.accessControl.settings.title')}</CardTitle>
          </div>
          <CardDescription>{t('safe.accessControl.settings.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <LockIcon className="h-4 w-4" />
              <Label>{t('safe.accessControl.settings.apiKeyAuth')}</Label>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ServerIcon className="h-4 w-4" />
              <Label>{t('safe.accessControl.settings.ipAllowlist')}</Label>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ClockIcon className="h-4 w-4" />
              <Label>{t('safe.accessControl.settings.rateLimit')}</Label>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <UserIcon className="h-4 w-4" />
              <Label>{t('safe.accessControl.settings.userAuth')}</Label>
            </div>
            <Switch defaultChecked />
          </div>
        </CardContent>
        <CardFooter className="flex justify-end gap-2">
          <Button variant="outline">{t('safe.accessControl.actions.reset')}</Button>
          <Button>{t('safe.accessControl.actions.save')}</Button>
        </CardFooter>
      </Card>
    </div>
  )
}
