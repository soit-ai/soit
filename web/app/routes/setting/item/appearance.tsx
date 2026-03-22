import { useTranslation } from '@/i18n'
import { useState } from 'react'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { toast } from '@/hooks/use-toast'
import { Sun, Moon, Laptop, Palette, Layout, Type, Check } from 'lucide-react'
function Page() {
  const { t } = useTranslation()
  const [theme, setTheme] = useState('system')
  const [fontSize, setFontSize] = useState('medium')
  const [colorScheme, setColorScheme] = useState('default')
  const [sidebarPosition, setSidebarPosition] = useState('left')
  const [compactMode, setCompactMode] = useState(false)
  const [animationsEnabled, setAnimationsEnabled] = useState(true)
  const [borderRadius, setBorderRadius] = useState('medium')
  
  // 主题选项
  const themeOptions = [
    { value: 'light', label: '浅色', icon: Sun },
    { value: 'dark', label: '深色', icon: Moon },
    { value: 'system', label: '跟随系统', icon: Laptop },
  ]
  
  // 字体大小选项
  const fontSizeOptions = [
    { value: 'small', label: '小' },
    { value: 'medium', label: '中' },
    { value: 'large', label: '大' },
    { value: 'x-large', label: '超大' },
  ]
  
  // 颜色方案选项
  const colorSchemeOptions = [
    { value: 'default', label: '默认' },
    { value: 'blue', label: '蓝色' },
    { value: 'green', label: '绿色' },
    { value: 'purple', label: '紫色' },
    { value: 'orange', label: '橙色' },
  ]
  
  // 圆角大小选项
  const borderRadiusOptions = [
    { value: 'none', label: '无' },
    { value: 'small', label: '小' },
    { value: 'medium', label: '中' },
    { value: 'large', label: '大' },
  ]
  
  // 保存外观设置
  const handleSaveAppearance = () => {
    // 这里应该有API调用来保存设置
    console.log('保存外观设置', {
      theme,
      fontSize,
      colorScheme,
      sidebarPosition,
      compactMode,
      animationsEnabled,
      borderRadius
    })
    
    toast({
      title: '已保存',
      description: '外观设置已更新',
    })
  }
  
  // 重置为默认设置
  const handleResetDefaults = () => {
    setTheme('system')
    setFontSize('medium')
    setColorScheme('default')
    setSidebarPosition('left')
    setCompactMode(false)
    setAnimationsEnabled(true)
    setBorderRadius('medium')
    
    toast({
      title: '已重置',
      description: '外观设置已恢复默认',
    })
  }
  
  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold tracking-tight">外观设置</h3>
          <p className="text-sm text-muted-foreground mt-1">自定义界面外观和显示偏好</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleResetDefaults}>恢复默认</Button>
          <Button onClick={handleSaveAppearance}>保存设置</Button>
        </div>
      </div>

      <Tabs defaultValue="theme" className="w-full">
        <TabsList className="mb-4 grid w-full max-w-md grid-cols-3">
          <TabsTrigger value="theme">主题</TabsTrigger>
          <TabsTrigger value="layout">布局</TabsTrigger>
          <TabsTrigger value="typography">排版</TabsTrigger>
        </TabsList>
        
        {/* 主题标签页 */}
        <TabsContent value="theme">
          <div className="grid gap-6">
            <Card>
              <CardHeader>
                <CardTitle>主题模式</CardTitle>
                <CardDescription>选择您喜欢的主题模式</CardDescription>
              </CardHeader>
              <CardContent>
                <RadioGroup
                  value={theme}
                  onValueChange={setTheme}
                  className="grid grid-cols-3 gap-4"
                >
                  {themeOptions.map((option) => (
                    <div key={option.value}>
                      <RadioGroupItem
                        value={option.value}
                        id={`theme-${option.value}`}
                        className="peer sr-only"
                      />
                      <Label
                        htmlFor={`theme-${option.value}`}
                        className="flex flex-col items-center justify-between rounded-md border-2 border-muted bg-popover p-4 hover:bg-accent hover:text-accent-foreground peer-data-[state=checked]:border-primary [&:has([data-state=checked])]:border-primary"
                      >
                        <option.icon className="mb-3 h-6 w-6" />
                        {option.label}
                      </Label>
                    </div>
                  ))}
                </RadioGroup>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader>
                <CardTitle>颜色方案</CardTitle>
                <CardDescription>选择应用的主色调</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4">
                  <div className="grid grid-cols-5 gap-4">
                    {colorSchemeOptions.map((option) => (
                      <div 
                        key={option.value} 
                        className={`flex h-10 items-center justify-center rounded-md border-2 cursor-pointer ${colorScheme === option.value ? 'border-primary' : 'border-muted'}`}
                        onClick={() => setColorScheme(option.value)}
                      >
                        <div className="flex items-center gap-2">
                          <div className={`h-4 w-4 rounded-full bg-${option.value === 'default' ? 'primary' : option.value}-500`}></div>
                          <span>{option.label}</span>
                          {colorScheme === option.value && <Check className="h-4 w-4 ml-1" />}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader>
                <CardTitle>圆角</CardTitle>
                <CardDescription>调整界面元素的圆角大小</CardDescription>
              </CardHeader>
              <CardContent>
                <Select value={borderRadius} onValueChange={setBorderRadius}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择圆角大小" />
                  </SelectTrigger>
                  <SelectContent>
                    {borderRadiusOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                
                <div className="mt-4 grid grid-cols-4 gap-4">
                  {borderRadiusOptions.map((option) => (
                    <div 
                      key={option.value} 
                      className={`h-16 border-2 ${borderRadius === option.value ? 'border-primary' : 'border-muted'} ${option.value === 'none' ? 'rounded-none' : option.value === 'small' ? 'rounded-sm' : option.value === 'medium' ? 'rounded-md' : 'rounded-lg'}`}
                    ></div>
                  ))}
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader>
                <CardTitle>动画效果</CardTitle>
                <CardDescription>控制界面动画效果</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>启用动画效果</Label>
                    <p className="text-sm text-muted-foreground">
                      控制界面过渡和动画效果
                    </p>
                  </div>
                  <Switch
                    checked={animationsEnabled}
                    onCheckedChange={setAnimationsEnabled}
                  />
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
        
        {/* 布局标签页 */}
        <TabsContent value="layout">
          <Card>
            <CardHeader>
              <CardTitle>布局偏好</CardTitle>
              <CardDescription>自定义应用的布局和显示方式</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <h3 className="text-lg font-medium">侧边栏位置</h3>
                <RadioGroup
                  value={sidebarPosition}
                  onValueChange={setSidebarPosition}
                  className="grid grid-cols-2 gap-4"
                >
                  <div>
                    <RadioGroupItem
                      value="left"
                      id="sidebar-left"
                      className="peer sr-only"
                    />
                    <Label
                      htmlFor="sidebar-left"
                      className="flex flex-col items-center justify-between rounded-md border-2 border-muted bg-popover p-4 hover:bg-accent hover:text-accent-foreground peer-data-[state=checked]:border-primary [&:has([data-state=checked])]:border-primary"
                    >
                      <Layout className="mb-3 h-6 w-6" />
                      左侧
                    </Label>
                  </div>
                  <div>
                    <RadioGroupItem
                      value="right"
                      id="sidebar-right"
                      className="peer sr-only"
                    />
                    <Label
                      htmlFor="sidebar-right"
                      className="flex flex-col items-center justify-between rounded-md border-2 border-muted bg-popover p-4 hover:bg-accent hover:text-accent-foreground peer-data-[state=checked]:border-primary [&:has([data-state=checked])]:border-primary"
                    >
                      <Layout className="mb-3 h-6 w-6" style={{ transform: 'scaleX(-1)' }} />
                      右侧
                    </Label>
                  </div>
                </RadioGroup>
              </div>
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>紧凑模式</Label>
                  <p className="text-sm text-muted-foreground">
                    减小界面元素间距，显示更多内容
                  </p>
                </div>
                <Switch
                  checked={compactMode}
                  onCheckedChange={setCompactMode}
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* 排版标签页 */}
        <TabsContent value="typography">
          <Card>
            <CardHeader>
              <CardTitle>字体设置</CardTitle>
              <CardDescription>调整文字大小和显示方式</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <h3 className="text-lg font-medium">字体大小</h3>
                <RadioGroup
                  value={fontSize}
                  onValueChange={setFontSize}
                  className="grid grid-cols-4 gap-4"
                >
                  {fontSizeOptions.map((option) => (
                    <div key={option.value}>
                      <RadioGroupItem
                        value={option.value}
                        id={`font-${option.value}`}
                        className="peer sr-only"
                      />
                      <Label
                        htmlFor={`font-${option.value}`}
                        className="flex flex-col items-center justify-between rounded-md border-2 border-muted bg-popover p-4 hover:bg-accent hover:text-accent-foreground peer-data-[state=checked]:border-primary [&:has([data-state=checked])]:border-primary"
                      >
                        <Type className={`mb-3 ${option.value === 'small' ? 'h-4 w-4' : option.value === 'medium' ? 'h-5 w-5' : option.value === 'large' ? 'h-6 w-6' : 'h-7 w-7'}`} />
                        {option.label}
                      </Label>
                    </div>
                  ))}
                </RadioGroup>
              </div>
              
              <div className="space-y-2">
                <h3 className="text-lg font-medium">预览</h3>
                <div className={`p-4 border rounded-md ${fontSize === 'small' ? 'text-sm' : fontSize === 'medium' ? 'text-base' : fontSize === 'large' ? 'text-lg' : 'text-xl'}`}>
                  <h4 className="font-bold mb-2">标题示例</h4>
                  <p>这是一段示例文本，用于展示不同字体大小的效果。调整上方的字体大小设置，可以看到此处文本大小的变化。</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default Page
