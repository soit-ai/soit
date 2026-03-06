import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { PlusCircle, Settings2, Trash2, Save, X, HelpCircle } from 'lucide-react'

// 变量类型枚举
export enum VariableType {
  STRING = 'string',
  NUMBER = 'number',
  BOOLEAN = 'boolean',
  ARRAY = 'array',
  OBJECT = 'object'
}

// 变量接口
export interface Variable {
  key: string
  value: string
  description: string
  type: VariableType
}

// 新变量默认值
export const DEFAULT_VARIABLE: Variable = {
  key: '',
  value: '',
  description: '',
  type: VariableType.STRING
}

interface VariablesTabProps {
  variables: Variable[]
  newVariable: Variable
  setNewVariable: (variable: Variable) => void
  editingVariableIndex: number | null
  handleAddVariable: () => void
  handleEditVariable: (index: number) => void
  handleUpdateVariable: () => void
  handleDeleteVariable: (index: number) => void
  handleCancelEdit: () => void
}

export const VariablesTab: React.FC<VariablesTabProps> = ({
  variables,
  newVariable,
  setNewVariable,
  editingVariableIndex,
  handleAddVariable,
  handleEditVariable,
  handleUpdateVariable,
  handleDeleteVariable,
  handleCancelEdit
}) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Variable Management</CardTitle>
        <CardDescription>Add variables that can be used in prompts</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-5">
          {/* Variable Add Form */}
          <div className="rounded-lg border bg-card p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center">
                <h3 className="text-sm font-medium">Add New Variable</h3>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-6 w-6 ml-1">
                        <HelpCircle className="h-3.5 w-3.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="right" className="max-w-80">
                      <p>Variables can be used in prompts using the format {'{variable_name}'}. For example: "Hello, my name is {'{name}'}"</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              {editingVariableIndex !== null && (
                <Badge variant="outline" className="text-xs bg-primary/5">Edit Mode</Badge>
              )}
            </div>
            
            <div className="grid grid-cols-12 gap-3">
              <div className="col-span-12 sm:col-span-3">
                <div className="flex items-center justify-between mb-1.5">
                  <Label htmlFor="variable-key" className="text-xs">Variable Name</Label>
                  <span className="text-[10px] text-muted-foreground">{'{'}variable_name{'}'}</span>
                </div>
                <Input 
                  id="variable-key"
                  placeholder="name"
                  value={newVariable.key}
                  onChange={(e) => setNewVariable({...newVariable, key: e.target.value})}
                  className="font-mono text-sm h-9"
                />
              </div>
              <div className="col-span-12 sm:col-span-2">
                <Label htmlFor="variable-type" className="text-xs block mb-1.5">Type</Label>
                <Select 
                  value={newVariable.type} 
                  onValueChange={(value) => setNewVariable({...newVariable, type: value as VariableType})}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue placeholder="Select Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={VariableType.STRING}>String</SelectItem>
                    <SelectItem value={VariableType.NUMBER}>Number</SelectItem>
                    <SelectItem value={VariableType.BOOLEAN}>Boolean</SelectItem>
                    <SelectItem value={VariableType.ARRAY}>Array</SelectItem>
                    <SelectItem value={VariableType.OBJECT}>Object</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="col-span-12 sm:col-span-3">
                <Label htmlFor="variable-value" className="text-xs block mb-1.5">Default Value</Label>
                <Input 
                  id="variable-value"
                  placeholder="John"
                  value={newVariable.value}
                  onChange={(e) => setNewVariable({...newVariable, value: e.target.value})}
                  className="font-mono text-sm h-9"
                />
              </div>
              <div className="col-span-12 sm:col-span-2">
                <Label htmlFor="variable-description" className="text-xs block mb-1.5">Description</Label>
                <Input 
                  id="variable-description"
                  placeholder="User's name"
                  value={newVariable.description}
                  onChange={(e) => setNewVariable({...newVariable, description: e.target.value})}
                  className="h-9"
                />
              </div>
              <div className="col-span-12 sm:col-span-2 flex items-end">
                {editingVariableIndex !== null ? (
                  <div className="flex space-x-1 w-full">
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button 
                            onClick={handleUpdateVariable} 
                            size="sm" 
                            className="flex-1 h-9"
                            disabled={!newVariable.key.trim()}
                          >
                            <Save className="h-4 w-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent side="top">
                          <p>Save Changes</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button 
                            onClick={handleCancelEdit} 
                            variant="outline" 
                            size="sm"
                            className="h-9"
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent side="top">
                          <p>Cancel Edit</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                ) : (
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button 
                          onClick={handleAddVariable} 
                          className="w-full h-9"
                          disabled={!newVariable.key.trim()}
                        >
                          <PlusCircle className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent side="top">
                        <p>Add Variable</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                )}
              </div>
            </div>
          </div>
          
          {/* Variable List */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium">Variable List</h3>
              <span className="text-xs text-muted-foreground">
                Total: {variables.length} variables
              </span>
            </div>
            
            <div className="rounded-lg border overflow-hidden">
              <div className="grid grid-cols-12 gap-2 px-3 py-2 bg-muted/50 font-medium text-xs">
                <div className="col-span-3">Variable Name</div>
                <div className="col-span-2">Type</div>
                <div className="col-span-2">Default Value</div>
                <div className="col-span-3">Description</div>
                <div className="col-span-2 text-center">Actions</div>
              </div>
              
              <ScrollArea className="h-[240px]">
                {variables.length > 0 ? (
                  <div className="divide-y">
                    {variables.map((variable, index) => (
                      <div 
                        key={index} 
                        className={`grid grid-cols-12 gap-2 px-3 py-2.5 hover:bg-muted/30 text-sm transition-colors ${editingVariableIndex === index ? 'bg-primary/5' : ''}`}
                      >
                        <div className="col-span-3 font-mono flex items-center text-xs overflow-hidden">
                          <Badge variant="outline" className="mr-1.5 text-[10px] px-1 py-0 h-4 bg-primary/5 shrink-0">Var</Badge>
                          <span className="truncate">{variable.key}</span>
                        </div>
                        <div className="col-span-2 flex items-center text-xs overflow-hidden">
                          <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 shrink-0">
                            {variable.type === VariableType.STRING && 'String'}
                            {variable.type === VariableType.NUMBER && 'Number'}
                            {variable.type === VariableType.BOOLEAN && 'Boolean'}
                            {variable.type === VariableType.ARRAY && 'Array'}
                            {variable.type === VariableType.OBJECT && 'Object'}
                          </Badge>
                        </div>
                        <div className="col-span-2 font-mono flex items-center text-xs overflow-hidden">
                          <span className="truncate">{variable.value || <span className="text-muted-foreground italic">No default value</span>}</span>
                        </div>
                        <div className="col-span-3 flex items-center text-xs overflow-hidden">
                          <span className="truncate">{variable.description || <span className="text-muted-foreground italic">No description</span>}</span>
                        </div>
                        <div className="col-span-2 flex items-center justify-center space-x-1">
                          <TooltipProvider>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button 
                                  onClick={() => handleEditVariable(index)} 
                                  variant="ghost" 
                                  size="icon"
                                  className="h-7 w-7"
                                >
                                  <Settings2 className="h-3.5 w-3.5" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent side="top">
                                <p>Edit Variable</p>
                              </TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                          
                          <TooltipProvider>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button 
                                  onClick={() => handleDeleteVariable(index)} 
                                  variant="ghost" 
                                  size="icon"
                                  className="h-7 w-7 text-destructive hover:text-destructive hover:bg-destructive/10"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent side="top">
                                <p>Delete Variable</p>
                              </TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center p-8 text-sm text-muted-foreground">
                    <div className="rounded-full bg-muted/50 p-3 mb-2">
                      <PlusCircle className="h-5 w-5 text-muted-foreground" />
                    </div>
                    <p>No variables yet, please add variables</p>
                  </div>
                )}
              </ScrollArea>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default VariablesTab
