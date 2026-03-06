import React, { useEffect, useState } from 'react'
import { useTranslation } from '@/i18n'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Slider } from '@/components/ui/slider'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { EyeOffIcon, LockIcon, RefreshCwIcon, SaveIcon, ShieldIcon, TrashIcon } from 'lucide-react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useNavLayout } from '@/components/layout/nav-layout'

// Mock privacy rule data
const mockPrivacyRules = [
  { id: 'rule-001', name: 'Personal identifiers', type: 'pii', action: 'mask', enabled: true },
  { id: 'rule-002', name: 'Credit card number', type: 'financial', action: 'block', enabled: true },
  { id: 'rule-003', name: 'Phone number', type: 'contact', action: 'mask', enabled: true },
  { id: 'rule-004', name: 'Email address', type: 'contact', action: 'mask', enabled: false },
  { id: 'rule-005', name: 'Address data', type: 'location', action: 'mask', enabled: true },
]

interface PrivacyProtectionProps {
  subTab?: string | null
}

function BoxHeader({
  title,
  description,
  onRefresh,
  refreshLabel,
}: {
  title: string
  description: string
  onRefresh?: () => void
  refreshLabel?: string
}) {
  return (
    <div className="flex flex-1 justify-between">
      <div>
        <h3 className="text-lg font-bold">{title}</h3>
        <p className="text-sm text-muted-foreground mt-1">{description}</p>
      </div>
      {onRefresh && (
        <Button variant="outline" size="sm" onClick={onRefresh}>
          <RefreshCwIcon className="h-4 w-4 mr-2" />
          {refreshLabel}
        </Button>
      )}
    </div>
  )
}

export function PrivacyProtection({ subTab = null }: PrivacyProtectionProps) {
  const { t } = useTranslation()
  const { setHeaderContent } = useNavLayout()
  const [privacyRules, setPrivacyRules] = useState(mockPrivacyRules)
  const [newRuleName, setNewRuleName] = useState('')
  const [newRuleType, setNewRuleType] = useState('pii')
  const [newRuleAction, setNewRuleAction] = useState('mask')
  const [maskingLevel, setMaskingLevel] = useState(80)

  useEffect(() => {
    setHeaderContent(
      <BoxHeader
        title={t('safe.privacyProtection.header.title')}
        description={t('safe.privacyProtection.header.description')}
        refreshLabel={t('safe.privacyProtection.header.refresh')}
        onRefresh={() => console.log('Refreshing privacy protection rules...')}
      />
    )
    return () => setHeaderContent(null)
  }, [setHeaderContent, t])

  const renderSubTabContent = () => {
    switch (subTab) {
      case 'data-masking':
        return (
          <Card className="w-full">
            <CardHeader>
              <CardTitle>{t('safe.privacyProtection.subTabs.dataMasking.title')}</CardTitle>
              <CardDescription>{t('safe.privacyProtection.subTabs.dataMasking.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <Label htmlFor="enable-masking">{t('safe.privacyProtection.subTabs.dataMasking.enable')}</Label>
                <Switch id="enable-masking" checked={true} />
              </div>

              <div className="space-y-2">
                <Label>{t('safe.privacyProtection.subTabs.dataMasking.levelLabel')}</Label>
                <div className="flex items-center gap-4">
                  <Slider
                    value={[maskingLevel]}
                    min={0}
                    max={100}
                    step={10}
                    onValueChange={(value) => setMaskingLevel(value[0])}
                    className="flex-1"
                  />
                  <span className="w-12 text-right">{maskingLevel}%</span>
                </div>
                <p className="text-sm text-muted-foreground">
                  {t('safe.privacyProtection.subTabs.dataMasking.levelHint')}
                </p>
              </div>

              <div className="space-y-2">
                <Label>{t('safe.privacyProtection.subTabs.dataMasking.fields.title')}</Label>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('safe.privacyProtection.subTabs.dataMasking.fields.table.field')}</TableHead>
                      <TableHead>{t('safe.privacyProtection.subTabs.dataMasking.fields.table.method')}</TableHead>
                      <TableHead>{t('safe.privacyProtection.subTabs.dataMasking.fields.table.status')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow>
                      <TableCell>{t('safe.privacyProtection.subTabs.dataMasking.fields.phone')}</TableCell>
                      <TableCell>{t('safe.privacyProtection.subTabs.dataMasking.methods.phone')}</TableCell>
                      <TableCell>
                        <Switch checked={true} />
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>{t('safe.privacyProtection.subTabs.dataMasking.fields.idNumber')}</TableCell>
                      <TableCell>{t('safe.privacyProtection.subTabs.dataMasking.methods.idNumber')}</TableCell>
                      <TableCell>
                        <Switch checked={true} />
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>{t('safe.privacyProtection.subTabs.dataMasking.fields.bankCard')}</TableCell>
                      <TableCell>{t('safe.privacyProtection.subTabs.dataMasking.methods.bankCard')}</TableCell>
                      <TableCell>
                        <Switch checked={true} />
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>{t('safe.privacyProtection.subTabs.dataMasking.fields.email')}</TableCell>
                      <TableCell>{t('safe.privacyProtection.subTabs.dataMasking.methods.email')}</TableCell>
                      <TableCell>
                        <Switch checked={true} />
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>{t('safe.privacyProtection.subTabs.dataMasking.fields.address')}</TableCell>
                      <TableCell>{t('safe.privacyProtection.subTabs.dataMasking.methods.address')}</TableCell>
                      <TableCell>
                        <Switch checked={true} />
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        )
      case 'encryption':
        return (
          <Card className="w-full">
            <CardHeader>
              <CardTitle>{t('safe.privacyProtection.subTabs.encryption.title')}</CardTitle>
              <CardDescription>{t('safe.privacyProtection.subTabs.encryption.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <Label htmlFor="enable-encryption">{t('safe.privacyProtection.subTabs.encryption.enable')}</Label>
                <Switch id="enable-encryption" checked={true} />
              </div>

              <div className="space-y-2">
                <Label>{t('safe.privacyProtection.subTabs.encryption.algorithmLabel')}</Label>
                <div className="grid grid-cols-2 gap-2">
                  <div className="flex items-center space-x-2">
                    <input type="radio" id="aes-256" name="algorithm" checked />
                    <Label htmlFor="aes-256">AES-256</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <input type="radio" id="rsa-2048" name="algorithm" />
                    <Label htmlFor="rsa-2048">RSA-2048</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <input type="radio" id="chacha20" name="algorithm" />
                    <Label htmlFor="chacha20">ChaCha20-Poly1305</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <input type="radio" id="sm4" name="algorithm" />
                    <Label htmlFor="sm4">{t('safe.privacyProtection.subTabs.encryption.algorithms.sm4')}</Label>
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <Label>{t('safe.privacyProtection.subTabs.encryption.keyManagement.title')}</Label>
                <div className="border rounded-md p-4 space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-medium">
                        {t('safe.privacyProtection.subTabs.encryption.keyManagement.primaryKey')}
                      </h4>
                      <p className="text-sm text-muted-foreground">
                        {t('safe.privacyProtection.subTabs.encryption.keyManagement.lastRotated', {
                          date: '2023-10-15',
                        })}
                      </p>
                    </div>
                    <Button variant="outline" size="sm">
                      <RefreshCwIcon className="h-4 w-4 mr-2" />
                      {t('safe.privacyProtection.subTabs.encryption.keyManagement.rotate')}
                    </Button>
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-medium">
                        {t('safe.privacyProtection.subTabs.encryption.keyManagement.backup')}
                      </h4>
                      <p className="text-sm text-muted-foreground">
                        {t('safe.privacyProtection.subTabs.encryption.keyManagement.autoBackup')}
                      </p>
                    </div>
                    <Button variant="outline" size="sm">
                      <SaveIcon className="h-4 w-4 mr-2" />
                      {t('safe.privacyProtection.subTabs.encryption.keyManagement.manualBackup')}
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )
      case 'access-control':
        return (
          <Card className="w-full">
            <CardHeader>
              <CardTitle>{t('safe.privacyProtection.subTabs.accessControl.title')}</CardTitle>
              <CardDescription>{t('safe.privacyProtection.subTabs.accessControl.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <Label htmlFor="enable-access-control">
                  {t('safe.privacyProtection.subTabs.accessControl.enable')}
                </Label>
                <Switch id="enable-access-control" checked={true} />
              </div>

              <div className="space-y-2">
                <Label>{t('safe.privacyProtection.subTabs.accessControl.policies.title')}</Label>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('safe.privacyProtection.subTabs.accessControl.policies.table.dataType')}</TableHead>
                      <TableHead>{t('safe.privacyProtection.subTabs.accessControl.policies.table.role')}</TableHead>
                      <TableHead>{t('safe.privacyProtection.subTabs.accessControl.policies.table.permission')}</TableHead>
                      <TableHead>{t('safe.privacyProtection.subTabs.accessControl.policies.table.status')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow>
                      <TableCell>{t('safe.privacyProtection.subTabs.accessControl.policies.dataType.pii')}</TableCell>
                      <TableCell>{t('safe.privacyProtection.subTabs.accessControl.policies.roles.admin')}</TableCell>
                      <TableCell>{t('safe.privacyProtection.subTabs.accessControl.policies.permissions.readWrite')}</TableCell>
                      <TableCell>
                        <Switch checked={true} />
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>{t('safe.privacyProtection.subTabs.accessControl.policies.dataType.pii')}</TableCell>
                      <TableCell>{t('safe.privacyProtection.subTabs.accessControl.policies.roles.user')}</TableCell>
                      <TableCell>{t('safe.privacyProtection.subTabs.accessControl.policies.permissions.none')}</TableCell>
                      <TableCell>
                        <Switch checked={true} />
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>{t('safe.privacyProtection.subTabs.accessControl.policies.dataType.payment')}</TableCell>
                      <TableCell>{t('safe.privacyProtection.subTabs.accessControl.policies.roles.finance')}</TableCell>
                      <TableCell>{t('safe.privacyProtection.subTabs.accessControl.policies.permissions.read')}</TableCell>
                      <TableCell>
                        <Switch checked={true} />
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>{t('safe.privacyProtection.subTabs.accessControl.policies.dataType.payment')}</TableCell>
                      <TableCell>{t('safe.privacyProtection.subTabs.accessControl.policies.roles.other')}</TableCell>
                      <TableCell>{t('safe.privacyProtection.subTabs.accessControl.policies.permissions.none')}</TableCell>
                      <TableCell>
                        <Switch checked={true} />
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>

              <div className="space-y-2">
                <Label>{t('safe.privacyProtection.subTabs.accessControl.audit.title')}</Label>
                <div className="flex items-center justify-between">
                  <p className="text-sm">{t('safe.privacyProtection.subTabs.accessControl.audit.items.record')}</p>
                  <Switch checked={true} />
                </div>
                <div className="flex items-center justify-between">
                  <p className="text-sm">{t('safe.privacyProtection.subTabs.accessControl.audit.items.alert')}</p>
                  <Switch checked={true} />
                </div>
                <div className="flex items-center justify-between">
                  <p className="text-sm">{t('safe.privacyProtection.subTabs.accessControl.audit.items.report')}</p>
                  <Switch checked={true} />
                </div>
              </div>
            </CardContent>
          </Card>
        )
      default:
        return null
    }
  }

  if (subTab) {
    return <div className="space-y-4">{renderSubTabContent()}</div>
  }

  const toggleRuleStatus = (id: string) => {
    setPrivacyRules(
      privacyRules.map((rule) => (rule.id === id ? { ...rule, enabled: !rule.enabled } : rule))
    )
  }

  const deleteRule = (id: string) => {
    setPrivacyRules(privacyRules.filter((rule) => rule.id !== id))
  }

  const addNewRule = () => {
    if (!newRuleName.trim()) return

    const newRule = {
      id: `rule-${Date.now()}`,
      name: newRuleName.trim(),
      type: newRuleType,
      action: newRuleAction,
      enabled: true,
    }

    setPrivacyRules([...privacyRules, newRule])
    setNewRuleName('')
  }

  const getRuleTypeDisplay = (type: string) => {
    switch (type) {
      case 'pii':
        return (
          <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
            {t('safe.privacyProtection.types.pii')}
          </Badge>
        )
      case 'financial':
        return (
          <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
            {t('safe.privacyProtection.types.financial')}
          </Badge>
        )
      case 'contact':
        return (
          <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200">
            {t('safe.privacyProtection.types.contact')}
          </Badge>
        )
      case 'location':
        return (
          <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
            {t('safe.privacyProtection.types.location')}
          </Badge>
        )
      default:
        return <Badge variant="outline">{t('safe.privacyProtection.types.other')}</Badge>
    }
  }

  const getRuleActionDisplay = (action: string) => {
    switch (action) {
      case 'mask':
        return <Badge>{t('safe.privacyProtection.actions.mask')}</Badge>
      case 'block':
        return <Badge variant="destructive">{t('safe.privacyProtection.actions.block')}</Badge>
      case 'warn':
        return <Badge variant="secondary">{t('safe.privacyProtection.actions.warn')}</Badge>
      default:
        return <Badge variant="outline">{t('safe.privacyProtection.actions.unknown')}</Badge>
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center gap-2">
            <ShieldIcon className="h-5 w-5 text-primary" />
            <CardTitle>{t('safe.privacyProtection.rules.title')}</CardTitle>
          </div>
          <CardDescription>{t('safe.privacyProtection.rules.description')}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('safe.privacyProtection.rules.table.name')}</TableHead>
                  <TableHead>{t('safe.privacyProtection.rules.table.type')}</TableHead>
                  <TableHead>{t('safe.privacyProtection.rules.table.action')}</TableHead>
                  <TableHead>{t('safe.privacyProtection.rules.table.status')}</TableHead>
                  <TableHead className="text-right">{t('safe.privacyProtection.rules.table.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {privacyRules.map((rule) => (
                  <TableRow key={rule.id}>
                    <TableCell className="font-medium">{rule.name}</TableCell>
                    <TableCell>{getRuleTypeDisplay(rule.type)}</TableCell>
                    <TableCell>{getRuleActionDisplay(rule.action)}</TableCell>
                    <TableCell>
                      <Switch checked={rule.enabled} onCheckedChange={() => toggleRuleStatus(rule.id)} />
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="icon" onClick={() => deleteRule(rule.id)}>
                        <TrashIcon className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div className="mt-4 grid grid-cols-4 gap-4">
            <div className="col-span-2">
              <Label htmlFor="new-rule-name" className="mb-2 block">
                {t('safe.privacyProtection.rules.newRule.nameLabel')}
              </Label>
              <Input
                id="new-rule-name"
                placeholder={t('safe.privacyProtection.rules.newRule.namePlaceholder')}
                value={newRuleName}
                onChange={(event) => setNewRuleName(event.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="new-rule-type" className="mb-2 block">
                {t('safe.privacyProtection.rules.newRule.typeLabel')}
              </Label>
              <select
                id="new-rule-type"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                value={newRuleType}
                onChange={(event) => setNewRuleType(event.target.value)}
              >
                <option value="pii">{t('safe.privacyProtection.types.pii')}</option>
                <option value="financial">{t('safe.privacyProtection.types.financial')}</option>
                <option value="contact">{t('safe.privacyProtection.types.contact')}</option>
                <option value="location">{t('safe.privacyProtection.types.location')}</option>
              </select>
            </div>
            <div>
              <Label htmlFor="new-rule-action" className="mb-2 block">
                {t('safe.privacyProtection.rules.newRule.actionLabel')}
              </Label>
              <select
                id="new-rule-action"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                value={newRuleAction}
                onChange={(event) => setNewRuleAction(event.target.value)}
              >
                <option value="mask">{t('safe.privacyProtection.actions.mask')}</option>
                <option value="block">{t('safe.privacyProtection.actions.block')}</option>
                <option value="warn">{t('safe.privacyProtection.actions.warn')}</option>
              </select>
            </div>
          </div>

          <div className="mt-4 flex justify-end">
            <Button onClick={addNewRule}>{t('safe.privacyProtection.rules.newRule.addButton')}</Button>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="rules" className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="rules">{t('safe.privacyProtection.tabs.rules')}</TabsTrigger>
          <TabsTrigger value="settings">{t('safe.privacyProtection.tabs.settings')}</TabsTrigger>
        </TabsList>

        <TabsContent value="rules">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <EyeOffIcon className="h-5 w-5 text-primary" />
                <CardTitle>{t('safe.privacyProtection.rules.title')}</CardTitle>
              </div>
              <CardDescription>{t('safe.privacyProtection.rules.description')}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('safe.privacyProtection.rules.table.name')}</TableHead>
                      <TableHead>{t('safe.privacyProtection.rules.table.type')}</TableHead>
                      <TableHead>{t('safe.privacyProtection.rules.table.action')}</TableHead>
                      <TableHead>{t('safe.privacyProtection.rules.table.status')}</TableHead>
                      <TableHead className="text-right">{t('safe.privacyProtection.rules.table.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {privacyRules.map((rule) => (
                      <TableRow key={rule.id}>
                        <TableCell className="font-medium">{rule.name}</TableCell>
                        <TableCell>{getRuleTypeDisplay(rule.type)}</TableCell>
                        <TableCell>{getRuleActionDisplay(rule.action)}</TableCell>
                        <TableCell>
                          <Switch checked={rule.enabled} onCheckedChange={() => toggleRuleStatus(rule.id)} />
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="icon" onClick={() => deleteRule(rule.id)}>
                            <TrashIcon className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              <div className="mt-4 grid grid-cols-4 gap-4">
                <div className="col-span-2">
                  <Label htmlFor="new-rule-name" className="mb-2 block">
                    {t('safe.privacyProtection.rules.newRule.nameLabel')}
                  </Label>
                  <Input
                    id="new-rule-name"
                    placeholder={t('safe.privacyProtection.rules.newRule.namePlaceholder')}
                    value={newRuleName}
                    onChange={(event) => setNewRuleName(event.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="new-rule-type" className="mb-2 block">
                    {t('safe.privacyProtection.rules.newRule.typeLabel')}
                  </Label>
                  <select
                    id="new-rule-type"
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                    value={newRuleType}
                    onChange={(event) => setNewRuleType(event.target.value)}
                  >
                    <option value="pii">{t('safe.privacyProtection.types.pii')}</option>
                    <option value="financial">{t('safe.privacyProtection.types.financial')}</option>
                    <option value="contact">{t('safe.privacyProtection.types.contact')}</option>
                    <option value="location">{t('safe.privacyProtection.types.location')}</option>
                  </select>
                </div>
                <div>
                  <Label htmlFor="new-rule-action" className="mb-2 block">
                    {t('safe.privacyProtection.rules.newRule.actionLabel')}
                  </Label>
                  <select
                    id="new-rule-action"
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                    value={newRuleAction}
                    onChange={(event) => setNewRuleAction(event.target.value)}
                  >
                    <option value="mask">{t('safe.privacyProtection.actions.mask')}</option>
                    <option value="block">{t('safe.privacyProtection.actions.block')}</option>
                    <option value="warn">{t('safe.privacyProtection.actions.warn')}</option>
                  </select>
                </div>
              </div>

              <div className="mt-4 flex justify-end">
                <Button onClick={addNewRule}>{t('safe.privacyProtection.rules.newRule.addButton')}</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="settings">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <ShieldIcon className="h-5 w-5 text-primary" />
                <CardTitle>{t('safe.privacyProtection.settings.title')}</CardTitle>
              </div>
              <CardDescription>{t('safe.privacyProtection.settings.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label>{t('safe.privacyProtection.settings.options.enable.label')}</Label>
                    <p className="text-sm text-muted-foreground">
                      {t('safe.privacyProtection.settings.options.enable.description')}
                    </p>
                  </div>
                  <Switch defaultChecked />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>{t('safe.privacyProtection.settings.options.detectPii.label')}</Label>
                    <p className="text-sm text-muted-foreground">
                      {t('safe.privacyProtection.settings.options.detectPii.description')}
                    </p>
                  </div>
                  <Switch defaultChecked />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>{t('safe.privacyProtection.settings.options.log.label')}</Label>
                    <p className="text-sm text-muted-foreground">
                      {t('safe.privacyProtection.settings.options.log.description')}
                    </p>
                  </div>
                  <Switch defaultChecked />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>{t('safe.privacyProtection.settings.options.alerts.label')}</Label>
                    <p className="text-sm text-muted-foreground">
                      {t('safe.privacyProtection.settings.options.alerts.description')}
                    </p>
                  </div>
                  <Switch defaultChecked />
                </div>
              </div>

              <div className="space-y-4 pt-4 border-t">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label>{t('safe.privacyProtection.settings.masking.label')}</Label>
                    <span className="text-sm">{maskingLevel}%</span>
                  </div>
                  <Slider
                    value={[maskingLevel]}
                    min={0}
                    max={100}
                    step={10}
                    onValueChange={(value) => setMaskingLevel(value[0])}
                    className="w-full"
                  />
                  <p className="text-sm text-muted-foreground mt-2">
                    {t('safe.privacyProtection.settings.masking.hint')}
                  </p>
                </div>
              </div>
            </CardContent>
            <CardFooter className="flex justify-end gap-2">
              <Button variant="outline">
                <RefreshCwIcon className="h-4 w-4 mr-2" />
                {t('safe.privacyProtection.settings.actions.reset')}
              </Button>
              <Button>
                <SaveIcon className="h-4 w-4 mr-2" />
                {t('safe.privacyProtection.settings.actions.save')}
              </Button>
            </CardFooter>
          </Card>

          <Card className="mt-4">
            <CardHeader>
              <div className="flex items-center gap-2">
                <LockIcon className="h-5 w-5 text-primary" />
                <CardTitle>{t('safe.privacyProtection.retention.title')}</CardTitle>
              </div>
              <CardDescription>{t('safe.privacyProtection.retention.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label>{t('safe.privacyProtection.retention.options.autoDelete.label')}</Label>
                  <p className="text-sm text-muted-foreground">
                    {t('safe.privacyProtection.retention.options.autoDelete.description')}
                  </p>
                </div>
                <Switch defaultChecked />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="retention-period" className="mb-2 block">
                    {t('safe.privacyProtection.retention.fields.period.label')}
                  </Label>
                  <select
                    id="retention-period"
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                    defaultValue="30"
                  >
                    <option value="7">{t('safe.privacyProtection.retention.fields.period.options.days7')}</option>
                    <option value="14">{t('safe.privacyProtection.retention.fields.period.options.days14')}</option>
                    <option value="30">{t('safe.privacyProtection.retention.fields.period.options.days30')}</option>
                    <option value="60">{t('safe.privacyProtection.retention.fields.period.options.days60')}</option>
                    <option value="90">{t('safe.privacyProtection.retention.fields.period.options.days90')}</option>
                  </select>
                </div>

                <div>
                  <Label htmlFor="deletion-method" className="mb-2 block">
                    {t('safe.privacyProtection.retention.fields.method.label')}
                  </Label>
                  <select
                    id="deletion-method"
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                    defaultValue="secure"
                  >
                    <option value="standard">
                      {t('safe.privacyProtection.retention.fields.method.options.standard')}
                    </option>
                    <option value="secure">{t('safe.privacyProtection.retention.fields.method.options.secure')}</option>
                    <option value="complete">
                      {t('safe.privacyProtection.retention.fields.method.options.complete')}
                    </option>
                  </select>
                </div>
              </div>
            </CardContent>
            <CardFooter className="flex justify-end gap-2">
              <Button variant="destructive">
                <TrashIcon className="h-4 w-4 mr-2" />
                {t('safe.privacyProtection.retention.actions.purge')}
              </Button>
            </CardFooter>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
