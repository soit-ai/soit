import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Copy } from 'lucide-react'

interface ApiKeyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  apiKey: string;
}

export function ApiKeyDialog({ open, onOpenChange, apiKey }: ApiKeyDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>API 密钥</DialogTitle>
          <DialogDescription>
            请妥善保管您的 API 密钥，不要泄露给他人。
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="api-key-display">API 密钥</Label>
            <div className="flex items-center space-x-2">
              <Input 
                id="api-key-display" 
                type="password" 
                value={apiKey || '••••••••••••••••••••••••••••••'} 
                readOnly 
              />
              <Button variant="outline" size="icon">
                <Copy className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="regenerate-key">重新生成密钥</Label>
            <p className="text-sm text-muted-foreground">重新生成密钥将使当前密钥失效，所有使用旧密钥的应用需要更新。</p>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button variant="destructive">重新生成密钥</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
