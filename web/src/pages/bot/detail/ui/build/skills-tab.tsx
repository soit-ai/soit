import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Volume2, Mic, Upload, FileText, Image, Code, Globe, Sliders } from 'lucide-react'
import { useTranslation } from '@/i18n'

interface SkillsTabProps {
  skills: {
    textToSpeech: boolean
    speechToText: boolean
    fileUpload: boolean
    documentReference: boolean
    imageGeneration: boolean
    codeInterpreter: boolean
    internetAccess: boolean
    customization: boolean
  }
  handleSkillToggle: (skill: keyof SkillsTabProps['skills']) => void
}

export const SkillsTab: React.FC<SkillsTabProps> = ({
  skills,
  handleSkillToggle
}) => {
  const { t } = useTranslation()

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('bot.build.skills.title')}</CardTitle>
        <CardDescription>{t('bot.build.skills.description')}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Text to speech */}
          <div 
            className={`flex items-start space-x-4 rounded-md border p-4 cursor-pointer ${skills.textToSpeech ? 'border-primary bg-primary/5' : ''}`}
            onClick={() => handleSkillToggle('textToSpeech')}
          >
            <div className="p-2 rounded-full bg-primary/10">
              <Volume2 className="h-5 w-5 text-primary" />
            </div>
            <div className="flex-1 space-y-1">
              <div className="flex items-center justify-between">
                <h4 className="font-medium">{t('bot.build.skills.textToSpeech.title')}</h4>
                <Switch 
                  checked={skills.textToSpeech} 
                  onCheckedChange={handleSkillToggle.bind(null, 'textToSpeech')}
                  className="cursor-pointer"
                  onClick={(event) => {
                    // Prevent event bubbling so the card click handler does not fire.
                    event.stopPropagation();
                  }}
                />
              </div>
              <p className="text-sm text-muted-foreground">{t('bot.build.skills.textToSpeech.description')}</p>
              {skills.textToSpeech && (
                <div className="mt-2 pt-2 border-t" onClick={(event) => event.stopPropagation()}>
                  <Label className="text-xs mb-1 block">{t('bot.build.skills.textToSpeech.settingsTitle')}</Label>
                  <Select defaultValue="zh-CN">
                    <SelectTrigger>
                      <SelectValue placeholder={t('bot.build.skills.textToSpeech.languagePlaceholder')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="zh-CN">{t('bot.build.skills.textToSpeech.languages.zhCN')}</SelectItem>
                      <SelectItem value="en-US">{t('bot.build.skills.textToSpeech.languages.enUS')}</SelectItem>
                      <SelectItem value="ja-JP">{t('bot.build.skills.textToSpeech.languages.jaJP')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          </div>
          
          {/* Speech to text */}
          <div 
            className={`flex items-start space-x-4 rounded-md border p-4 cursor-pointer ${skills.speechToText ? 'border-primary bg-primary/5' : ''}`}
            onClick={() => handleSkillToggle('speechToText')}
          >
            <div className="p-2 rounded-full bg-primary/10">
              <Mic className="h-5 w-5 text-primary" />
            </div>
            <div className="flex-1 space-y-1">
              <div className="flex items-center justify-between">
                <h4 className="font-medium">{t('bot.build.skills.speechToText.title')}</h4>
                <Switch 
                  checked={skills.speechToText} 
                  onCheckedChange={handleSkillToggle.bind(null, 'speechToText')}
                  className="cursor-pointer"
                  onClick={(event) => {
                    // Prevent event bubbling so the card click handler does not fire.
                    event.stopPropagation();
                  }}
                />
              </div>
              <p className="text-sm text-muted-foreground">{t('bot.build.skills.speechToText.description')}</p>
            </div>
          </div>
          
          {/* File upload */}
          <div 
            className={`flex items-start space-x-4 rounded-md border p-4 cursor-pointer ${skills.fileUpload ? 'border-primary bg-primary/5' : ''}`}
            onClick={() => handleSkillToggle('fileUpload')}
          >
            <div className="p-2 rounded-full bg-primary/10">
              <Upload className="h-5 w-5 text-primary" />
            </div>
            <div className="flex-1 space-y-1">
              <div className="flex items-center justify-between">
                <h4 className="font-medium">{t('bot.build.skills.fileUpload.title')}</h4>
                <Switch 
                  checked={skills.fileUpload} 
                  onCheckedChange={handleSkillToggle.bind(null, 'fileUpload')}
                  className="cursor-pointer"
                  onClick={(event) => {
                    // Prevent event bubbling so the card click handler does not fire.
                    event.stopPropagation();
                  }}
                />
              </div>
              <p className="text-sm text-muted-foreground">{t('bot.build.skills.fileUpload.description')}</p>
              {skills.fileUpload && (
                <div className="mt-2 pt-2 border-t" onClick={(event) => event.stopPropagation()}>
                  <Label className="text-xs mb-1 block">{t('bot.build.skills.fileUpload.fileTypes')}</Label>
                  <div className="flex flex-wrap gap-1 mt-1">
                    <Badge variant="outline">.pdf</Badge>
                    <Badge variant="outline">.docx</Badge>
                    <Badge variant="outline">.txt</Badge>
                    <Badge variant="outline">.csv</Badge>
                    <Badge variant="outline">.xlsx</Badge>
                  </div>
                </div>
              )}
            </div>
          </div>
          
          {/* Document citations */}
          <div 
            className={`flex items-start space-x-4 rounded-md border p-4 cursor-pointer ${skills.documentReference ? 'border-primary bg-primary/5' : ''}`}
            onClick={() => handleSkillToggle('documentReference')}
          >
            <div className="p-2 rounded-full bg-primary/10">
              <FileText className="h-5 w-5 text-primary" />
            </div>
            <div className="flex-1 space-y-1">
              <div className="flex items-center justify-between">
                <h4 className="font-medium">{t('bot.build.skills.documentReference.title')}</h4>
                <Switch 
                  checked={skills.documentReference} 
                  onCheckedChange={handleSkillToggle.bind(null, 'documentReference')}
                  className="cursor-pointer"
                  onClick={(event) => {
                    // Prevent event bubbling so the card click handler does not fire.
                    event.stopPropagation();
                  }}
                />
              </div>
              <p className="text-sm text-muted-foreground">{t('bot.build.skills.documentReference.description')}</p>
            </div>
          </div>
          
          {/* Image generation */}
          <div 
            className={`flex items-start space-x-4 rounded-md border p-4 cursor-pointer ${skills.imageGeneration ? 'border-primary bg-primary/5' : ''}`}
            onClick={() => handleSkillToggle('imageGeneration')}
          >
            <div className="p-2 rounded-full bg-primary/10">
              <Image className="h-5 w-5 text-primary" />
            </div>
            <div className="flex-1 space-y-1">
              <div className="flex items-center justify-between">
                <h4 className="font-medium">{t('bot.build.skills.imageGeneration.title')}</h4>
                <Switch 
                  checked={skills.imageGeneration} 
                  onCheckedChange={handleSkillToggle.bind(null, 'imageGeneration')}
                  className="cursor-pointer"
                  onClick={(event) => {
                    // Prevent event bubbling so the card click handler does not fire.
                    event.stopPropagation();
                  }}
                />
              </div>
              <p className="text-sm text-muted-foreground">{t('bot.build.skills.imageGeneration.description')}</p>
              {skills.imageGeneration && (
                <div className="mt-2 pt-2 border-t" onClick={(event) => event.stopPropagation()}>
                  <Label className="text-xs mb-1 block">{t('bot.build.skills.imageGeneration.modelLabel')}</Label>
                  <Select defaultValue="dall-e-3">
                    <SelectTrigger>
                      <SelectValue placeholder={t('bot.build.skills.imageGeneration.modelPlaceholder')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="dall-e-3">DALL-E 3</SelectItem>
                      <SelectItem value="stable-diffusion">Stable Diffusion</SelectItem>
                      <SelectItem value="midjourney">Midjourney</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          </div>
          
          {/* Code interpreter */}
          <div 
            className={`flex items-start space-x-4 rounded-md border p-4 cursor-pointer ${skills.codeInterpreter ? 'border-primary bg-primary/5' : ''}`}
            onClick={() => handleSkillToggle('codeInterpreter')}
          >
            <div className="p-2 rounded-full bg-primary/10">
              <Code className="h-5 w-5 text-primary" />
            </div>
            <div className="flex-1 space-y-1">
              <div className="flex items-center justify-between">
                <h4 className="font-medium">{t('bot.build.skills.codeInterpreter.title')}</h4>
                <Switch 
                  checked={skills.codeInterpreter} 
                  onCheckedChange={handleSkillToggle.bind(null, 'codeInterpreter')}
                  className="cursor-pointer"
                  onClick={(event) => {
                    // Prevent event bubbling so the card click handler does not fire.
                    event.stopPropagation();
                  }}
                />
              </div>
              <p className="text-sm text-muted-foreground">{t('bot.build.skills.codeInterpreter.description')}</p>
            </div>
          </div>
          
          {/* Internet access */}
          <div 
            className={`flex items-start space-x-4 rounded-md border p-4 cursor-pointer ${skills.internetAccess ? 'border-primary bg-primary/5' : ''}`}
            onClick={() => handleSkillToggle('internetAccess')}
          >
            <div className="p-2 rounded-full bg-primary/10">
              <Globe className="h-5 w-5 text-primary" />
            </div>
            <div className="flex-1 space-y-1">
              <div className="flex items-center justify-between">
                <h4 className="font-medium">{t('bot.build.skills.internetAccess.title')}</h4>
                <Switch 
                  checked={skills.internetAccess} 
                  onCheckedChange={handleSkillToggle.bind(null, 'internetAccess')}
                  className="cursor-pointer"
                  onClick={(event) => {
                    // Prevent event bubbling so the card click handler does not fire.
                    event.stopPropagation();
                  }}
                />
              </div>
              <p className="text-sm text-muted-foreground">{t('bot.build.skills.internetAccess.description')}</p>
            </div>
          </div>
          
          {/* Custom appearance */}
          <div 
            className={`flex items-start space-x-4 rounded-md border p-4 cursor-pointer ${skills.customization ? 'border-primary bg-primary/5' : ''}`}
            onClick={() => handleSkillToggle('customization')}
          >
            <div className="p-2 rounded-full bg-primary/10">
              <Sliders className="h-5 w-5 text-primary" />
            </div>
            <div className="flex-1 space-y-1">
              <div className="flex items-center justify-between">
                <h4 className="font-medium">{t('bot.build.skills.customization.title')}</h4>
                <Switch 
                  checked={skills.customization} 
                  onCheckedChange={handleSkillToggle.bind(null, 'customization')}
                  className="cursor-pointer"
                  onClick={(event) => {
                    // Prevent event bubbling so the card click handler does not fire.
                    event.stopPropagation();
                  }}
                />
              </div>
              <p className="text-sm text-muted-foreground">{t('bot.build.skills.customization.description')}</p>
              {skills.customization && (
                <div className="mt-2 pt-2 border-t space-y-2" onClick={(event) => event.stopPropagation()}>
                  <div>
                    <Label className="text-xs mb-1 block">{t('bot.build.skills.customization.themeColor')}</Label>
                    <div className="flex space-x-2 mt-1">
                      <div className="w-6 h-6 rounded-full bg-blue-500 cursor-pointer ring-2 ring-offset-2 ring-blue-500" />
                      <div className="w-6 h-6 rounded-full bg-green-500 cursor-pointer" />
                      <div className="w-6 h-6 rounded-full bg-purple-500 cursor-pointer" />
                      <div className="w-6 h-6 rounded-full bg-red-500 cursor-pointer" />
                      <div className="w-6 h-6 rounded-full bg-gray-500 cursor-pointer" />
                    </div>
                  </div>
                  <div>
                    <Label className="text-xs mb-1 block">{t('bot.build.skills.customization.avatarLabel')}</Label>
                    <div className="flex items-center space-x-2 mt-1">
                      <Avatar className="h-8 w-8">
                        <AvatarImage src="/bot-avatar.png" alt={t('bot.build.skills.customization.avatarAlt')} />
                        <AvatarFallback>AI</AvatarFallback>
                      </Avatar>
                      <Button variant="outline" size="sm">{t('bot.build.skills.customization.changeAvatar')}</Button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default SkillsTab
