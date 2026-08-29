import { cn } from '@/lib/utils'

/**
 * Prototype .code — the mono footer block of a panel. Either a CLI line
 * (`command` + `output`) or raw preformatted content via children.
 */
export function CodeBlock({
  command,
  output,
  children,
  className,
  style,
}: {
  command?: string
  output?: string
  children?: React.ReactNode
  className?: string
  style?: React.CSSProperties
}) {
  return (
    <div className={cn('code', className)} style={style}>
      {command != null && (
        <>
          <span className="k">$</span> {command}
          {'\n'}
        </>
      )}
      {output != null && <span className="s">{output}</span>}
      {children}
    </div>
  )
}
