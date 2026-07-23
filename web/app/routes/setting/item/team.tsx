import { useTranslation } from '@/i18n'
import { useEffect, useState } from 'react'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Separator } from '@/components/ui/separator'
import { toast } from '@/hooks/use-toast'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Users, Building, Shield, MoreVertical, Trash2, UserPlus } from 'lucide-react'
import { addWorkspaceMember, getCurrentUser, getWorkspace, listWorkspaceMembers, removeWorkspaceMember, updateWorkspace, updateWorkspaceMemberRole } from '@/services/identity-service'
import { useQuery } from '@/hooks/use-query'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'

function Page() {
  const { t } = useTranslation()
  
  const industryOptions = [
    { value: 'tech', label: t('system.settings.team.industries.tech') },
    { value: 'finance', label: t('system.settings.team.industries.finance') },
    { value: 'education', label: t('system.settings.team.industries.education') },
    { value: 'healthcare', label: t('system.settings.team.industries.healthcare') },
    { value: 'manufacturing', label: t('system.settings.team.industries.manufacturing') },
    { value: 'other', label: t('system.settings.team.industries.other') },
  ]

  const sizeOptions = [
    { value: '1-9', label: t('system.settings.team.sizes.small') },
    { value: '10-50', label: t('system.settings.team.sizes.medium') },
    { value: '51-200', label: t('system.settings.team.sizes.large') },
    { value: '201-500', label: t('system.settings.team.sizes.enterprise') },
    { value: '500+', label: t('system.settings.team.sizes.extraLarge') },
  ]

  const roleLabels = {
    admin: t('system.settings.team.roles.admin'),
    member: t('system.settings.team.roles.member'),
    guest: t('system.settings.team.roles.guest'),
  }

  const statusLabels = {
    active: t('system.settings.team.status.active'),
    inactive: t('system.settings.team.status.offline'),
  }

  // Team basic info.
  const [teamInfo, setTeamInfo] = useState({
    name: '',
    description: '',
    avatar: '',
    website: '',
    industry: 'tech',
    size: '10-50',
  })
  
  // Team members.
  const [members, setMembers] = useState<Array<{ id: string, name: string, email: string, role: string, avatar: string, status: string }>>([])
  
  // Team permission settings.
  const [permissions, setPermissions] = useState({
    allowMemberInvite: true,
    allowMemberRemove: false,
    allowFileSharing: true,
    allowExternalAccess: false,
    allowProjectCreation: true,
    requireAdminApproval: true
  })

  const [addMemberOpen, setAddMemberOpen] = useState(false)
  const [newMemberId, setNewMemberId] = useState('')
  const [newMemberRole, setNewMemberRole] = useState<'admin' | 'member' | 'guest'>('member')

  const { data: currentUser } = useQuery({
    queryKey: ['current-user'],
    queryFn: () => getCurrentUser(),
  })

  const workspaceId = currentUser?.workspace_id || ''

  const roleToWorkspaceRole = (role: string) => {
    if (role === 'admin') return 'admin'
    if (role === 'member') return 'dev'
    return 'viewer'
  }

  const workspaceRoleToRole = (role: string) => {
    if (role === 'owner' || role === 'admin') return 'admin'
    if (role === 'dev') return 'member'
    return 'guest'
  }

  useEffect(() => {
    if (!workspaceId) {
      return
    }
    getWorkspace(workspaceId)
      .then((workspace) => {
        const metadata = workspace.metadata || {}
        setTeamInfo((prev) => ({
          ...prev,
          name: workspace.name || prev.name,
          description: workspace.description || prev.description,
          avatar: metadata.avatar || '',
          website: metadata.website || '',
          industry: metadata.industry || prev.industry,
          size: metadata.size || prev.size,
        }))
        if (metadata.permissions) {
          setPermissions((prev) => ({ ...prev, ...metadata.permissions }))
        }
      })
      .catch(() => {})
  }, [workspaceId])

  useEffect(() => {
    if (!workspaceId) {
      return
    }
    listWorkspaceMembers(workspaceId)
      .then((data) => {
        setMembers(
          data.map((member) => ({
            id: member.user_id,
            name: member.name || member.email,
            email: member.email,
            role: workspaceRoleToRole(member.role),
            avatar: '',
            status: member.status === 'active' ? 'active' : 'inactive',
          }))
        )
      })
      .catch(() => {})
  }, [workspaceId])
  
  // Handle team info changes.
  const handleTeamInfoChange = (field: string, value: string) => {
    setTeamInfo(prev => ({
      ...prev,
      [field]: value
    }))
  }
  
  // Handle permission changes.
  const handlePermissionChange = (field: string, value: boolean) => {
    setPermissions(prev => ({
      ...prev,
      [field]: value
    }))
  }
  
  // Save team info.
  const handleSaveTeamInfo = () => {
    if (!workspaceId) {
      return
    }
    updateWorkspace(workspaceId, {
      name: teamInfo.name,
      description: teamInfo.description,
      metadata: {
        avatar: teamInfo.avatar,
        website: teamInfo.website,
        industry: teamInfo.industry,
        size: teamInfo.size,
      },
    })
      .then(() => {
        toast({
          title: t('system.settings.team.toast.savedTitle'),
          description: t('system.settings.team.toast.teamUpdated'),
        })
      })
      .catch(() => {})
  }
  
  // Save permission settings.
  const handleSavePermissions = () => {
    if (!workspaceId) {
      return
    }
    updateWorkspace(workspaceId, {
      metadata: {
        permissions,
      },
    })
      .then(() => {
        toast({
          title: t('system.settings.team.toast.savedTitle'),
          description: t('system.settings.team.toast.permissionsUpdated'),
        })
      })
      .catch(() => {})
  }
  
  // Add a new member.
  const handleAddMember = () => {
    setAddMemberOpen(true)
  }
  
  // Remove a member.
  const handleRemoveMember = (id: string) => {
    if (!workspaceId) {
      return
    }
    removeWorkspaceMember(workspaceId, id)
      .then(() => {
        setMembers(prev => prev.filter(member => member.id !== id))
        toast({
          title: t('system.settings.team.toast.memberRemoved'),
          description: t('system.settings.team.toast.memberRemovedDescription'),
        })
      })
      .catch(() => {})
  }
  
  // Change member role.
  const handleChangeRole = (id: string, role: string) => {
    if (!workspaceId) {
      return
    }
    updateWorkspaceMemberRole(workspaceId, id, roleToWorkspaceRole(role))
      .then(() => {
        setMembers(prev => prev.map(member => 
          member.id === id ? { ...member, role } : member
        ))
        toast({
          title: t('system.settings.team.toast.roleUpdated'),
          description: t('system.settings.team.toast.roleUpdatedDescription'),
        })
      })
      .catch(() => {})
  }

  const handleConfirmAddMember = () => {
    if (!workspaceId || !newMemberId) {
      return
    }
    addWorkspaceMember(workspaceId, { user_id: newMemberId, role: roleToWorkspaceRole(newMemberRole) })
      .then(() => {
        setAddMemberOpen(false)
        setNewMemberId('')
        setNewMemberRole('member')
        return listWorkspaceMembers(workspaceId)
      })
      .then((data) => {
        setMembers(
          data.map((member) => ({
            id: member.user_id,
            name: member.name || member.email,
            email: member.email,
            role: workspaceRoleToRole(member.role),
            avatar: '',
            status: member.status === 'active' ? 'active' : 'inactive',
          }))
        )
        toast({
          title: t('system.settings.team.toast.inviteSent'),
          description: t('system.settings.team.toast.inviteDescription'),
        })
      })
      .catch(() => {})
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold tracking-tight">{t('system.settings.team.title')}</h3>
          <p className="text-sm text-muted-foreground mt-1">{t('system.settings.team.description')}</p>
        </div>
        <Button onClick={handleAddMember}>
          <UserPlus className="mr-2 h-4 w-4" />
          {t('system.settings.team.actions.addMember')}
        </Button>
      </div>

      <Tabs defaultValue="members" className="w-full">
        <TabsList className="mb-4 grid w-full max-w-md grid-cols-3">
          <TabsTrigger value="members">
            <Users className="mr-2 h-4 w-4" />
            {t('system.settings.team.tabs.members')}
          </TabsTrigger>
          <TabsTrigger value="info">
            <Building className="mr-2 h-4 w-4" />
            {t('system.settings.team.tabs.info')}
          </TabsTrigger>
          <TabsTrigger value="permissions">
            <Shield className="mr-2 h-4 w-4" />
            {t('system.settings.team.tabs.permissions')}
          </TabsTrigger>
        </TabsList>
        
        {/* Team members tab */}
        <TabsContent value="members">
          <Card>
            <CardHeader>
              <CardTitle>{t('system.settings.team.members.title')}</CardTitle>
              <CardDescription>{t('system.settings.team.members.description')}</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('system.settings.team.members.columns.member')}</TableHead>
                    <TableHead>{t('system.settings.team.members.columns.email')}</TableHead>
                    <TableHead>{t('system.settings.team.members.columns.role')}</TableHead>
                    <TableHead>{t('system.settings.team.members.columns.status')}</TableHead>
                    <TableHead className="text-right">{t('system.settings.team.members.columns.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {members.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                        No workspace members returned by the server.
                      </TableCell>
                    </TableRow>
                  ) : members.map(member => (
                    <TableRow key={member.id}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <Avatar className="h-8 w-8">
                            <AvatarImage src={member.avatar || ''} />
                            <AvatarFallback>{member.name.charAt(0)}</AvatarFallback>
                          </Avatar>
                          <span>{member.name}</span>
                        </div>
                      </TableCell>
                      <TableCell>{member.email}</TableCell>
                      <TableCell>
                        <Badge variant={member.role === 'admin' ? 'default' : 
                                    member.role === 'member' ? 'secondary' : 'outline'}>
                          {roleLabels[member.role as keyof typeof roleLabels]}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className={`h-2 w-2 rounded-full ${member.status === 'active' ? 'bg-green-500' : 'bg-gray-300'}`} />
                          <span>{statusLabels[member.status as keyof typeof statusLabels]}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon">
                              <MoreVertical className="h-4 w-4" />
                              <span className="sr-only">{t('system.settings.team.members.actions.openMenu')}</span>
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleChangeRole(member.id, 'admin')}>
                              <Shield className="mr-2 h-4 w-4" />
                              {t('system.settings.team.members.actions.makeAdmin')}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleChangeRole(member.id, 'member')}>
                              <Users className="mr-2 h-4 w-4" />
                              {t('system.settings.team.members.actions.makeMember')}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleChangeRole(member.id, 'guest')}>
                              <Users className="mr-2 h-4 w-4" />
                              {t('system.settings.team.members.actions.makeGuest')}
                            </DropdownMenuItem>
                            <Separator className="my-2" />
                            <DropdownMenuItem 
                              onClick={() => handleRemoveMember(member.id)}
                              className="text-red-600 focus:text-red-600"
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              {t('system.settings.team.members.actions.remove')}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* Team info tab */}
        <TabsContent value="info">
          <Card>
            <CardHeader>
              <CardTitle>{t('system.settings.team.info.title')}</CardTitle>
              <CardDescription>{t('system.settings.team.info.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex flex-col md:flex-row gap-6">
                <div className="flex flex-col items-center gap-4">
                  <Avatar className="h-24 w-24">
                    <AvatarImage src={teamInfo.avatar || ''} />
                    <AvatarFallback className="text-2xl">{teamInfo.name.charAt(0)}</AvatarFallback>
                  </Avatar>
                </div>
                <div className="flex-1 space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="teamName">{t('system.settings.team.info.fields.name')}</Label>
                      <Input 
                        id="teamName" 
                        value={teamInfo.name} 
                        onChange={(e) => handleTeamInfoChange('name', e.target.value)} 
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="website">{t('system.settings.team.info.fields.website')}</Label>
                      <Input 
                        id="website" 
                        value={teamInfo.website} 
                        onChange={(e) => handleTeamInfoChange('website', e.target.value)} 
                      />
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="industry">{t('system.settings.team.info.fields.industry')}</Label>
                      <Select 
                        value={teamInfo.industry} 
                        onValueChange={(value) => handleTeamInfoChange('industry', value)}
                      >
                        <SelectTrigger id="industry">
                          <SelectValue placeholder={t('system.settings.team.info.placeholders.industry')} />
                        </SelectTrigger>
                        <SelectContent>
                          {industryOptions.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="size">{t('system.settings.team.info.fields.size')}</Label>
                      <Select 
                        value={teamInfo.size} 
                        onValueChange={(value) => handleTeamInfoChange('size', value)}
                      >
                        <SelectTrigger id="size">
                          <SelectValue placeholder={t('system.settings.team.info.placeholders.size')} />
                        </SelectTrigger>
                        <SelectContent>
                          {sizeOptions.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="description">{t('system.settings.team.info.fields.description')}</Label>
                    <Textarea 
                      id="description" 
                      value={teamInfo.description} 
                      onChange={(e) => handleTeamInfoChange('description', e.target.value)} 
                      rows={4}
                    />
                  </div>
                </div>
              </div>
            </CardContent>
            <CardFooter className="flex justify-end">
              <Button onClick={handleSaveTeamInfo}>{t('system.settings.team.actions.saveTeamInfo')}</Button>
            </CardFooter>
          </Card>
        </TabsContent>
        
        {/* Permissions tab */}
        <TabsContent value="permissions">
          <Card>
            <CardHeader>
              <CardTitle>{t('system.settings.team.permissions.title')}</CardTitle>
              <CardDescription>{t('system.settings.team.permissions.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label htmlFor="allowMemberInvite">{t('system.settings.team.permissions.allowMemberInvite.label')}</Label>
                    <p className="text-sm text-muted-foreground">{t('system.settings.team.permissions.allowMemberInvite.description')}</p>
                  </div>
                  <Switch 
                    id="allowMemberInvite" 
                    checked={permissions.allowMemberInvite}
                    onCheckedChange={(checked) => handlePermissionChange('allowMemberInvite', checked)}
                  />
                </div>
                
                <Separator />
                
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label htmlFor="allowMemberRemove">{t('system.settings.team.permissions.allowMemberRemove.label')}</Label>
                    <p className="text-sm text-muted-foreground">{t('system.settings.team.permissions.allowMemberRemove.description')}</p>
                  </div>
                  <Switch 
                    id="allowMemberRemove" 
                    checked={permissions.allowMemberRemove}
                    onCheckedChange={(checked) => handlePermissionChange('allowMemberRemove', checked)}
                  />
                </div>
                
                <Separator />
                
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label htmlFor="allowFileSharing">{t('system.settings.team.permissions.allowFileSharing.label')}</Label>
                    <p className="text-sm text-muted-foreground">{t('system.settings.team.permissions.allowFileSharing.description')}</p>
                  </div>
                  <Switch 
                    id="allowFileSharing" 
                    checked={permissions.allowFileSharing}
                    onCheckedChange={(checked) => handlePermissionChange('allowFileSharing', checked)}
                  />
                </div>
                
                <Separator />
                
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label htmlFor="allowExternalAccess">{t('system.settings.team.permissions.allowExternalAccess.label')}</Label>
                    <p className="text-sm text-muted-foreground">{t('system.settings.team.permissions.allowExternalAccess.description')}</p>
                  </div>
                  <Switch 
                    id="allowExternalAccess" 
                    checked={permissions.allowExternalAccess}
                    onCheckedChange={(checked) => handlePermissionChange('allowExternalAccess', checked)}
                  />
                </div>
                
                <Separator />
                
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label htmlFor="allowProjectCreation">{t('system.settings.team.permissions.allowProjectCreation.label')}</Label>
                    <p className="text-sm text-muted-foreground">{t('system.settings.team.permissions.allowProjectCreation.description')}</p>
                  </div>
                  <Switch 
                    id="allowProjectCreation" 
                    checked={permissions.allowProjectCreation}
                    onCheckedChange={(checked) => handlePermissionChange('allowProjectCreation', checked)}
                  />
                </div>
                
                <Separator />
                
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label htmlFor="requireAdminApproval">{t('system.settings.team.permissions.requireAdminApproval.label')}</Label>
                    <p className="text-sm text-muted-foreground">{t('system.settings.team.permissions.requireAdminApproval.description')}</p>
                  </div>
                  <Switch 
                    id="requireAdminApproval" 
                    checked={permissions.requireAdminApproval}
                    onCheckedChange={(checked) => handlePermissionChange('requireAdminApproval', checked)}
                  />
                </div>
              </div>
            </CardContent>
            <CardFooter className="flex justify-end">
              <Button onClick={handleSavePermissions}>{t('system.settings.team.actions.savePermissions')}</Button>
            </CardFooter>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={addMemberOpen} onOpenChange={setAddMemberOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('system.settings.team.actions.addMember')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="member-id">{t('system.settings.team.members.columns.member')}</Label>
              <Input
                id="member-id"
                value={newMemberId}
                onChange={(e) => setNewMemberId(e.target.value)}
                placeholder={t('system.settings.team.members.columns.member')}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="member-role">{t('system.settings.team.members.columns.role')}</Label>
              <Select value={newMemberRole} onValueChange={(value) => setNewMemberRole(value as 'admin' | 'member' | 'guest')}>
                <SelectTrigger id="member-role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">{roleLabels.admin}</SelectItem>
                  <SelectItem value="member">{roleLabels.member}</SelectItem>
                  <SelectItem value="guest">{roleLabels.guest}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddMemberOpen(false)}>
              {t('common.operation.cancel')}
            </Button>
            <Button onClick={handleConfirmAddMember}>
              {t('common.operation.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default Page
