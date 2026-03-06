import React from 'react'
import { useTranslation } from 'react-i18next'
import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Separator } from '@/components/ui/separator'
import { PlusIcon, SearchIcon, Trash2Icon, AlertCircleIcon, FileTextIcon, TagIcon, UploadIcon, DownloadIcon, RefreshCwIcon } from 'lucide-react'
import { useNavLayout } from '@/components/layout/nav-layout'

// 敏感词分类
const WORD_CATEGORIES = [
  { id: 'politics', name: '政治' },
  { id: 'violence', name: '暴力' },
  { id: 'discrimination', name: '歧视' },
  { id: 'obscenity', name: '淫秽' },
  { id: 'personal', name: '个人信息' },
  { id: 'custom', name: '自定义' },
]

// 敏感词类型
interface SensitiveWord {
  id: string
  word: string
  category: string
  action: 'block' | 'warn' | 'log'
  enabled: boolean
}

// 敏感词分类类型
interface WordCategory {
  category: string
  label: string
  count: number
  active: boolean
}

// 模拟敏感词数据
const mockSensitiveWords: SensitiveWord[] = [
  { id: 'word-001', word: '敏感词1', category: 'politics', action: 'block', enabled: true },
  { id: 'word-002', word: '敏感词2', category: 'violence', action: 'log', enabled: true },
  { id: 'word-003', word: '敏感词3', category: 'discrimination', action: 'warn', enabled: true },
  { id: 'word-004', word: '敏感词4', category: 'custom', action: 'block', enabled: true },
  { id: 'word-005', word: '敏感词5', category: 'politics', action: 'warn', enabled: true },
  { id: 'word-006', word: '敏感词6', category: 'violence', action: 'log', enabled: false },
  { id: 'word-007', word: '敏感词7', category: 'discrimination', action: 'block', enabled: true },
  { id: 'word-008', word: '敏感词8', category: 'custom', action: 'warn', enabled: false },
  { id: 'word-009', word: '敏感词9', category: 'discrimination', action: 'warn', enabled: true },
  { id: 'word-010', word: '敏感词10', category: 'obscenity', action: 'block', enabled: true },
]

// 敏感词项组件
interface SensitiveWordItemProps {
  word: SensitiveWord
  onToggle: (id: string) => void
  onDelete: (id: string) => void
  onChangeAction: (id: string, action: 'block' | 'warn' | 'log') => void
}

function SensitiveWordItem({ word, onToggle, onDelete, onChangeAction }: SensitiveWordItemProps) {
  // 根据分类获取徽章样式
  const getCategoryBadge = (category: string) => {
    switch (category) {
      case 'politics':
        return <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">政治</Badge>
      case 'violence':
        return <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">暴力</Badge>
      case 'discrimination':
        return <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">歧视</Badge>
      case 'obscenity':
        return <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200">色情</Badge>
      case 'personal':
        return <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">个人信息</Badge>
      case 'custom':
        return <Badge variant="outline" className="bg-gray-50 text-gray-700 border-gray-200">自定义</Badge>
      default:
        return <Badge variant="outline">{category}</Badge>
    }
  }

  return (
    <TableRow className={!word.enabled ? 'opacity-60' : ''}>
      <TableCell>
        <Switch 
          checked={word.enabled} 
          onCheckedChange={() => onToggle(word.id)}
        />
      </TableCell>
      <TableCell className="font-medium">{word.word}</TableCell>
      <TableCell>{getCategoryBadge(word.category)}</TableCell>
      <TableCell>
        <Select defaultValue={word.action} onValueChange={(value) => onChangeAction(word.id, value as 'block' | 'warn' | 'log')}>
          <SelectTrigger className="w-[120px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="block">拦截</SelectItem>
            <SelectItem value="replace">替换</SelectItem>
            <SelectItem value="warn">警告</SelectItem>
          </SelectContent>
        </Select>
      </TableCell>
      <TableCell>
        <Button variant="ghost" size="icon" onClick={() => onDelete(word.id)}>
          <Trash2Icon className="h-4 w-4" />
        </Button>
      </TableCell>
    </TableRow>
  )
}

// 敏感词标签组件
interface CategoryTagProps {
  category: string
  label: string
  count: number
  active: boolean
  onClick: (category: string) => void
}

function CategoryTag({ category, label, count, active, onClick }: CategoryTagProps) {
  return (
    <div 
      className={`flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer hover:bg-accent ${
        active ? 'bg-accent' : ''
      }`}
      onClick={() => onClick(category)}
    >
      <TagIcon className="h-4 w-4" />
      <span>{label}</span>
      <Badge variant="secondary" className="ml-auto">
        {count}
      </Badge>
    </div>
  )
}

interface SensitiveWordsManagerProps {
  subTab?: string | null;
}

function BoxHeader({ title, description, onRefresh }: { title: string; description: string; onRefresh?: () => void }) {
  return (
    <div className="flex flex-1 justify-between">
      <div>
        <h3 className="text-lg font-bold">{title}</h3>
        <p className="text-sm text-muted-foreground mt-1">{description}</p>
      </div>
      {onRefresh && (
        <Button variant="outline" size="sm" onClick={onRefresh}>
          <RefreshCwIcon className="h-4 w-4 mr-2" />
          刷新
        </Button>
      )}
    </div>
  )
}

export function SensitiveWordsManager({ subTab = null }: SensitiveWordsManagerProps) {
  const { t } = useTranslation()
  const [words, setWords] = useState<SensitiveWord[]>(mockSensitiveWords)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [newWord, setNewWord] = useState('')
  const [newCategory, setNewCategory] = useState('custom')
  const [newAction, setNewAction] = useState<'block' | 'warn' | 'log'>('block')
  const { setHeaderContent } = useNavLayout()
  
  // 设置头部内容
  useEffect(() => {
    setHeaderContent(
      <BoxHeader 
        title="敏感词管理" 
        description="管理敏感词库和过滤规则" 
        onRefresh={() => {
          // 刷新数据的逻辑
          console.log('Refreshing sensitive words data...')
        }}
      />
    )
    return () => setHeaderContent(null)
  }, [setHeaderContent])

  // 根据分类和搜索筛选敏感词
  const filteredWords = words.filter(word => {
    const matchesCategory = selectedCategory === 'all' || word.category === selectedCategory
    const matchesSearch = word.word.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesCategory && matchesSearch
  })

  // 根据分类获取敏感词数量
  const getCategoryCount = (category: string): number => {
    if (category === 'all') return words.length
    return words.filter(word => word.category === category).length
  }
  
  // 添加敏感词
  const addNewWord = () => {
    if (!newWord.trim()) return
    
    const id = `word-${Date.now()}`
    const wordObj: SensitiveWord = {
      id,
      word: newWord,
      category: newCategory,
      action: newAction,
      enabled: true
    }
    
    setWords([wordObj, ...words])
    setNewWord('')
  }
  
  // 删除敏感词
  const deleteWord = (id: string) => {
    setWords(words.filter(word => word.id !== id))
  }
  
  // 切换敏感词状态
  const toggleWordStatus = (id: string) => {
    setWords(words.map(word => {
      if (word.id === id) {
        return { ...word, enabled: !word.enabled }
      }
      return word
    }))
  }
  
  // 修改敏感词处理方式
  const changeWordAction = (id: string, action: 'block' | 'warn' | 'log') => {
    setWords(words.map(word => {
      if (word.id === id) {
        return { ...word, action }
      }
      return word
    }))
  }
  
  // 根据子标签页显示不同内容
  const renderSubTabContent = () => {
    switch (subTab) {
      case 'custom-words':
        return (
          <Card className="w-full">
            <CardHeader>
              <CardTitle>自定义敏感词管理</CardTitle>
              <CardDescription>管理自定义的敏感词列表和处理方式</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <Input 
                    placeholder="添加新敏感词" 
                    value={newWord} 
                    onChange={(e) => setNewWord(e.target.value)} 
                    className="flex-1"
                  />
                  <Select value={newAction} onValueChange={(value: string) => setNewAction(value as 'block' | 'warn' | 'log')}>
                    <SelectTrigger className="w-[120px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="block">拦截</SelectItem>
                      <SelectItem value="warn">警告</SelectItem>
                      <SelectItem value="log">记录</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button onClick={addNewWord}>添加</Button>
                </div>
                
                <div className="border rounded-md">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>敏感词</TableHead>
                        <TableHead>处理方式</TableHead>
                        <TableHead>操作</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {words
                        .filter(word => word.category === 'custom')
                        .map((word, index) => (
                          <TableRow key={index}>
                            <TableCell>{word.word}</TableCell>
                            <TableCell>
                              <Badge variant={word.action === 'block' ? 'destructive' : 
                                word.action === 'warn' ? 'outline' : 'secondary'}>
                                {word.action === 'block' ? '拦截' : 
                                 word.action === 'warn' ? '警告' : '记录'}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                <Button 
                                  variant="ghost" 
                                  size="icon" 
                                  onClick={() => deleteWord(word.id)}
                                >
                                  <Trash2Icon className="h-4 w-4" />
                                </Button>
                                <Select 
                                  defaultValue={word.action} 
                                  onValueChange={(value) => changeWordAction(word.id, value as 'block' | 'warn' | 'log')}
                                >
                                  <SelectTrigger className="w-[100px] h-8">
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="block">拦截</SelectItem>
                                    <SelectItem value="warn">警告</SelectItem>
                                    <SelectItem value="log">记录</SelectItem>
                                  </SelectContent>
                                </Select>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))
                      }
                    </TableBody>
                  </Table>
                </div>
              </div>
            </CardContent>
          </Card>
        )
      case 'system-words':
        return (
          <Card className="w-full">
            <CardHeader>
              <CardTitle>系统敏感词配置</CardTitle>
              <CardDescription>管理系统预设的敏感词列表和处理方式</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label>启用系统敏感词检测</Label>
                  <Switch checked={true} />
                </div>
                <Separator />
                
                <div className="space-y-2">
                  <Label>敏感词类别</Label>
                  <div className="grid grid-cols-2 gap-2">
                    {['政治', '暴力', '色情', '歧视', '毒品', '赌博'].map((category) => (
                      <div key={category} className="flex items-center space-x-2">
                        <Checkbox id={category} checked={true} />
                        <Label htmlFor={category}>{category}</Label>
                      </div>
                    ))}
                  </div>
                </div>
                
                <div className="space-y-2">
                  <Label>处理方式</Label>
                  <RadioGroup defaultValue="warn">
                    <div className="flex items-center space-x-2">
                      <RadioGroupItem value="block" id="block" />
                      <Label htmlFor="block">拦截所有匹配内容</Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <RadioGroupItem value="warn" id="warn" />
                      <Label htmlFor="warn">显示警告但允许继续</Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <RadioGroupItem value="log" id="log" />
                      <Label htmlFor="log">仅记录不干预</Label>
                    </div>
                  </RadioGroup>
                </div>
              </div>
            </CardContent>
          </Card>
        )
      case 'export-import':
        return (
          <Card className="w-full">
            <CardHeader>
              <CardTitle>导入导出</CardTitle>
              <CardDescription>导入或导出敏感词列表</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                <div className="space-y-2">
                  <h3 className="text-lg font-medium">导出敏感词列表</h3>
                  <p className="text-sm text-muted-foreground">将当前所有敏感词导出为CSV或JSON格式</p>
                  <div className="flex gap-2 mt-2">
                    <Button variant="outline">导出为CSV</Button>
                    <Button variant="outline">导出为JSON</Button>
                  </div>
                </div>
                
                <Separator />
                
                <div className="space-y-2">
                  <h3 className="text-lg font-medium">导入敏感词列表</h3>
                  <p className="text-sm text-muted-foreground">从CSV或JSON文件导入敏感词列表</p>
                  <div className="grid w-full max-w-sm items-center gap-1.5">
                    <Label htmlFor="file">上传文件</Label>
                    <Input id="file" type="file" />
                  </div>
                  <Button className="mt-2">开始导入</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )
      default:
        return null
    }
  }
  
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* 左侧分类列表 */}
        <Card className="md:col-span-1">
          <CardHeader>
            <CardTitle>分类</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <CategoryTag
              key="all"
              category="all"
              label="全部"
              count={getCategoryCount('all')}
              active={selectedCategory === 'all'}
              onClick={() => setSelectedCategory('all')}
            />
            
            {WORD_CATEGORIES.map(category => (
              <CategoryTag
                key={category.id}
                category={category.id}
                label={category.name}
                count={getCategoryCount(category.id)}
                active={selectedCategory === category.id}
                onClick={() => setSelectedCategory(category.id)}
              />
            ))}
          </CardContent>
        </Card>

        {/* 右侧敏感词列表 */}
        <Card className="md:col-span-3">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle>敏感词列表</CardTitle>
              <Badge variant="outline">
                {filteredWords.length} 个敏感词
              </Badge>
            </div>
            <CardDescription>
              管理系统中的敏感词，设置处理方式
            </CardDescription>
            
            <div className="flex w-full items-center space-x-2 mt-4">
              <div className="relative flex-1">
                <SearchIcon className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  type="search"
                  placeholder="搜索敏感词..."
                  className="pl-8"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>
          </CardHeader>
          
          <CardContent>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[60px]">状态</TableHead>
                    <TableHead>敏感词</TableHead>
                    <TableHead>分类</TableHead>
                    <TableHead>处理方式</TableHead>
                    <TableHead className="w-[60px]">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredWords.length > 0 ? (
                    filteredWords.map((word) => (
                      <SensitiveWordItem 
                        key={word.id} 
                        word={word} 
                        onToggle={toggleWordStatus}
                        onDelete={deleteWord}
                        onChangeAction={changeWordAction}
                      />
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={5} className="h-24 text-center">
                        没有找到符合条件的敏感词
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
          
          <Separator />
          
          <CardFooter className="pt-4">
            <div className="flex w-full items-end gap-2">
              <div className="flex-1">
                <Label htmlFor="new-word" className="mb-2 block">
                  添加新敏感词
                </Label>
                <Input
                  id="new-word"
                  placeholder="输入敏感词..."
                  value={newWord}
                  onChange={(e) => setNewWord(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="new-category" className="mb-2 block">
                  分类
                </Label>
                <Select value={newCategory} onValueChange={(value: string) => setNewCategory(value)}>
                  <SelectTrigger id="new-category" className="w-[120px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {WORD_CATEGORIES.map(category => (
                      <SelectItem key={category.id} value={category.id}>
                        {category.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label htmlFor="new-action" className="mb-2 block">
                  处理方式
                </Label>
                <Select value={newAction} onValueChange={(value: string) => setNewAction(value as 'block' | 'warn' | 'log')}>
                  <SelectTrigger id="new-action" className="w-[120px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="block">拦截</SelectItem>
                    <SelectItem value="warn">警告</SelectItem>
                    <SelectItem value="log">记录</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={addNewWord}>
                <PlusIcon className="h-4 w-4 mr-2" />
                添加
              </Button>
            </div>
          </CardFooter>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>敏感词规则设置</CardTitle>
          <CardDescription>
            配置敏感词检测和处理的全局规则
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileTextIcon className="h-4 w-4" />
              <Label>启用敏感词检测</Label>
            </div>
            <Switch defaultChecked />
          </div>
          
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileTextIcon className="h-4 w-4" />
              <Label>检测用户输入</Label>
            </div>
            <Switch defaultChecked />
          </div>
          
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileTextIcon className="h-4 w-4" />
              <Label>检测AI输出</Label>
            </div>
            <Switch defaultChecked />
          </div>
          
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileTextIcon className="h-4 w-4" />
              <Label>记录敏感词触发事件</Label>
            </div>
            <Switch defaultChecked />
          </div>
          
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileTextIcon className="h-4 w-4" />
              <Label>启用模糊匹配</Label>
            </div>
            <Switch />
          </div>
        </CardContent>
        <CardFooter className="flex justify-end gap-2">
          <Button variant="outline">重置默认值</Button>
          <Button>保存设置</Button>
        </CardFooter>
      </Card>
    </div>
  )
}
