import * as React from "react"
import { useState } from "react"
import { Settings2, InfoIcon } from "lucide-react"

import { useTranslation } from "@/i18n"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"

export interface ModelOptionProps {
  modelId?: string
  modelName?: string
  className?: string
  onOptionChange?: (option: ModelOptionValues) => void
}

export interface ModelOptionValues {
  temperature: number
  topP: number
  presencePenalty: number
  frequencyPenalty: number
  maxTokens: number
  responseFormat: string
  seed?: number
}

const defaultOption: ModelOptionValues = {
  temperature: 0.7,
  topP: 1,
  presencePenalty: 0,
  frequencyPenalty: 0,
  maxTokens: 0,
  responseFormat: "auto",
  seed: undefined
}

export function ModelOption({
  modelName,
  className,
  onOptionChange
}: ModelOptionProps) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [option, setOption] = useState<ModelOptionValues>(defaultOption)
  const title = modelName
    ? t("common.model.option.titleWithName", { name: modelName })
    : t("common.model.option.title")

  const handleOptionChange = <K extends keyof ModelOptionValues>(key: K, value: ModelOptionValues[K]) => {
    const newOption = { ...option, [key]: value }
    setOption(newOption)
    onOptionChange?.(newOption)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger render={<Button
          variant="outline"
          size="icon"
          className={cn("h-9 w-9", className)}
        >
          <Settings2 className="h-4 w-4" />
          <span className="sr-only">{t("common.model.option.srLabel")}</span>
        </Button>} />
      <PopoverContent className="w-[400px] p-0" align="end" sideOffset={5}>
        <Card className="border-none shadow-none">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{title}</CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            <div className="max-h-[60vh] overflow-y-auto pr-2 grid grid-cols-2 gap-4">
              <div>
                <div className="flex-1">
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <div className="flex items-center gap-1">
                      <Label htmlFor="temperature" className="text-sm font-medium">
                        {t("common.model.params.temperature")}
                      </Label>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger render={<InfoIcon className="h-3.5 w-3.5 text-muted-foreground cursor-help" />} />
                          <TooltipContent side="right" className="max-w-80">
                            <p>{t("common.model.params.temperatureTip")}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                    <Switch
                      id="temperature-switch"
                      checked={option.temperature !== 0}
                      onCheckedChange={(checked) => {
                        handleOptionChange("temperature", checked ? 0.7 : 0)
                      }}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <Slider
                      id="temperature"
                      min={0}
                      max={2}
                      step={0.1}
                      value={[option.temperature]}
                      onValueChange={(value) => handleOptionChange("temperature", Array.isArray(value) ? value[0] : value)}
                      className="flex-1"
                      disabled={option.temperature === 0}
                    />
                    <Input
                      type="number"
                      className="w-16 h-7 text-xs"
                      min={0}
                      max={2}
                      step={0.1}
                      value={option.temperature}
                      onChange={(e) => handleOptionChange("temperature", parseFloat(e.target.value) || 0)}
                      disabled={option.temperature === 0}
                    />
                  </div>
                </div>
              </div>

              <div>
                <div className="flex-1">
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <div className="flex items-center gap-1">
                      <Label htmlFor="top-p" className="text-sm font-medium">
                        {t("common.model.params.top_p")}
                      </Label>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger render={<InfoIcon className="h-3.5 w-3.5 text-muted-foreground cursor-help" />} />
                          <TooltipContent side="right" className="max-w-80">
                            <p>{t("common.model.params.top_pTip")}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                    <Switch
                      id="top-p-switch"
                      checked={option.topP !== 0}
                      onCheckedChange={(checked) => {
                        handleOptionChange("topP", checked ? 0.7 : 0)
                      }}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <Slider
                      id="top-p"
                      min={0}
                      max={1}
                      step={0.05}
                      value={[option.topP]}
                      onValueChange={(value) => handleOptionChange("topP", Array.isArray(value) ? value[0] : value)}
                      className="flex-1"
                      disabled={option.topP === 0}
                    />
                    <Input
                      type="number"
                      className="w-16 h-7 text-xs"
                      min={0}
                      max={1}
                      step={0.05}
                      value={option.topP}
                      onChange={(e) => handleOptionChange("topP", parseFloat(e.target.value) || 0)}
                      disabled={option.topP === 0}
                    />
                  </div>
                </div>
              </div>

              <div>
                <div className="flex-1">
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <div className="flex items-center gap-1">
                      <Label htmlFor="presence-penalty" className="text-sm font-medium">
                        {t("common.model.params.presence_penalty")}
                      </Label>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger render={<InfoIcon className="h-3.5 w-3.5 text-muted-foreground cursor-help" />} />
                          <TooltipContent side="right" className="max-w-80">
                            <p>{t("common.model.params.presence_penaltyTip")}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                    <Switch
                      id="presence-penalty-switch"
                      checked={option.presencePenalty !== 0}
                      onCheckedChange={(checked) => {
                        handleOptionChange("presencePenalty", checked ? 0.5 : 0)
                      }}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <Slider
                      id="presence-penalty"
                      min={-2}
                      max={2}
                      step={0.1}
                      value={[option.presencePenalty]}
                      onValueChange={(value) => handleOptionChange("presencePenalty", Array.isArray(value) ? value[0] : value)}
                      className="flex-1"
                      disabled={option.presencePenalty === 0}
                    />
                    <Input
                      type="number"
                      className="w-16 h-7 text-xs"
                      min={-2}
                      max={2}
                      step={0.1}
                      value={option.presencePenalty}
                      onChange={(e) => handleOptionChange("presencePenalty", parseFloat(e.target.value) || 0)}
                      disabled={option.presencePenalty === 0}
                    />
                  </div>
                </div>
              </div>

              <div>
                <div className="flex-1">
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <div className="flex items-center gap-1">
                      <Label htmlFor="frequency-penalty" className="text-sm font-medium">
                        {t("common.model.params.frequency_penalty")}
                      </Label>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger render={<InfoIcon className="h-3.5 w-3.5 text-muted-foreground cursor-help" />} />
                          <TooltipContent side="right" className="max-w-80">
                            <p>{t("common.model.params.frequency_penaltyTip")}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                    <Switch
                      id="frequency-penalty-switch"
                      checked={option.frequencyPenalty !== 0}
                      onCheckedChange={(checked) => {
                        handleOptionChange("frequencyPenalty", checked ? 0.5 : 0)
                      }}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <Slider
                      id="frequency-penalty"
                      min={-2}
                      max={2}
                      step={0.1}
                      value={[option.frequencyPenalty]}
                      onValueChange={(value) => handleOptionChange("frequencyPenalty", Array.isArray(value) ? value[0] : value)}
                      className="flex-1"
                      disabled={option.frequencyPenalty === 0}
                    />
                    <Input
                      type="number"
                      className="w-16 h-7 text-xs"
                      min={-2}
                      max={2}
                      step={0.1}
                      value={option.frequencyPenalty}
                      onChange={(e) => handleOptionChange("frequencyPenalty", parseFloat(e.target.value) || 0)}
                      disabled={option.frequencyPenalty === 0}
                    />
                  </div>
                </div>
              </div>

              <div>
                <div className="flex-1">
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <div className="flex items-center gap-1">
                      <Label htmlFor="max-tokens" className="text-sm font-medium">
                        {t("common.model.params.max_tokens")}
                      </Label>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger render={<InfoIcon className="h-3.5 w-3.5 text-muted-foreground cursor-help" />} />
                          <TooltipContent side="right" className="max-w-80">
                            <p>{t("common.model.params.max_tokensTip")}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                    <Switch
                      id="max-tokens-switch"
                      checked={option.maxTokens !== 0}
                      onCheckedChange={(checked) => {
                        handleOptionChange("maxTokens", checked ? 2048 : 0)
                      }}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <Slider
                      id="max-tokens"
                      min={0}
                      max={4096}
                      step={1}
                      value={[option.maxTokens]}
                      onValueChange={(value) => handleOptionChange("maxTokens", Array.isArray(value) ? value[0] : value)}
                      className="flex-1"
                      disabled={option.maxTokens === 0}
                    />
                    <Input
                      type="number"
                      className="w-16 h-7 text-xs"
                      min={0}
                      max={4096}
                      step={1}
                      value={option.maxTokens}
                      onChange={(e) => handleOptionChange("maxTokens", parseInt(e.target.value) || 0)}
                      disabled={option.maxTokens === 0}
                    />
                  </div>
                </div>
              </div>

              <div>
                <div className="flex-1">
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <div className="flex items-center gap-1">
                      <Label htmlFor="response-format" className="text-sm font-medium">
                        {t("common.model.params.response_format")}
                      </Label>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger render={<InfoIcon className="h-3.5 w-3.5 text-muted-foreground cursor-help" />} />
                          <TooltipContent side="right" className="max-w-80">
                            <p>{t("common.model.params.response_formatTip")}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                    <Switch
                      id="response-format-switch"
                      checked={option.responseFormat !== "auto"}
                      onCheckedChange={(checked) => {
                        handleOptionChange("responseFormat", checked ? "json_object" : "auto")
                      }}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <Select
                      value={option.responseFormat}
                      onValueChange={(value) => handleOptionChange("responseFormat", value)}
                      disabled={option.responseFormat === "auto"}
                    >
                      <SelectTrigger className="h-7 text-xs">
                        <SelectValue placeholder={t("common.model.params.response_formatPlaceholder")} />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="auto">{t("common.model.params.response_formatOptions.auto")}</SelectItem>
                        <SelectItem value="json_object">{t("common.model.params.response_formatOptions.json_object")}</SelectItem>
                        <SelectItem value="text">{t("common.model.params.response_formatOptions.text")}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>

              <div>
                <div className="flex-1">
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <div className="flex items-center gap-1">
                      <Label htmlFor="seed" className="text-sm font-medium">
                        {t("common.model.params.seed")}
                      </Label>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger render={<InfoIcon className="h-3.5 w-3.5 text-muted-foreground cursor-help" />} />
                          <TooltipContent side="right" className="max-w-80">
                            <p>{t("common.model.params.seedTip")}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                    <Switch
                      id="seed-switch"
                      checked={option.seed !== undefined}
                      onCheckedChange={(checked) => {
                        handleOptionChange("seed", checked ? 42 : undefined)
                      }}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <Input
                      type="number"
                      className="flex-1 h-7 text-xs"
                      min={0}
                      max={2147483647}
                      step={1}
                      value={option.seed === undefined ? "" : option.seed}
                      onChange={(e) => {
                        const value = e.target.value === "" ? undefined : parseInt(e.target.value, 10)
                        handleOptionChange("seed", value)
                      }}
                      disabled={option.seed === undefined}
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        if (option.seed !== undefined) {
                          const randomSeed = Math.floor(Math.random() * 2147483647)
                          handleOptionChange("seed", randomSeed)
                        }
                      }}
                      className="shrink-0 h-7 text-xs px-2"
                      disabled={option.seed === undefined}
                    >
                      {t("common.model.params.seedRandom")}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
          <CardFooter className="flex justify-end gap-2 pt-0 pb-3 px-4">
            <Button variant="outline" size="sm" onClick={() => setOpen(false)}>
              {t("common.operation.close")}
            </Button>
          </CardFooter>
        </Card>
      </PopoverContent>
    </Popover>
  )
}
