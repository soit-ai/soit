import { GalleryVerticalEnd } from 'lucide-react'

import { Link } from '@/components/ui/link'
import logoIcon from '@/assets/logo-m.png'

type AuthShellProps = {
  children: React.ReactNode
}

const panelItems = ['Agents', 'Knowledge', 'Runtime']

export function AuthShell({ children }: AuthShellProps) {
  return (
    <div className="grid min-h-svh bg-[linear-gradient(180deg,#f8fafc_0%,#f1f5f9_100%)] lg:grid-cols-2 dark:bg-[linear-gradient(180deg,#020617_0%,#0f172a_100%)]">
      <div className="flex flex-col gap-6 p-6 md:p-10">
        <div className="flex justify-center md:justify-start">
          <Link to="/" className="inline-flex items-center gap-3 font-medium text-slate-950 dark:text-white">
            <div className="flex items-center justify-center rounded-md text-white  dark:text-slate-950">
              {/* <GalleryVerticalEnd className="h-4 w-4" /> */}
              <img src={logoIcon} alt="logo" className="size-14" />
            </div>
            <span className="text-2xl font-bold">SOIT AI</span>
          </Link>
        </div>

        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-sm rounded-lg border border-slate-200/80 bg-white px-6 py-7 shadow-none dark:border-slate-800 dark:bg-slate-900 md:px-7 md:py-8">
            {children}
          </div>
        </div>
      </div>

      <div className="relative hidden overflow-hidden border-l border-slate-200/70 bg-[linear-gradient(145deg,rgba(241,245,249,0.98)_0%,rgba(226,232,240,0.94)_52%,rgba(224,242,254,0.92)_100%)] lg:block dark:border-slate-800 dark:bg-[linear-gradient(145deg,rgba(15,23,42,0.98)_0%,rgba(15,23,42,0.94)_52%,rgba(8,47,73,0.92)_100%)]">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(56,189,248,0.14),transparent_26%),radial-gradient(circle_at_78%_18%,rgba(14,165,233,0.12),transparent_24%),linear-gradient(rgba(15,23,42,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(15,23,42,0.04)_1px,transparent_1px)] [background-size:auto,auto,32px_32px,32px_32px] dark:bg-[radial-gradient(circle_at_20%_20%,rgba(56,189,248,0.18),transparent_26%),radial-gradient(circle_at_78%_18%,rgba(45,212,191,0.14),transparent_24%),linear-gradient(rgba(255,255,255,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.04)_1px,transparent_1px)]" />
        <div className="relative flex h-full flex-col justify-between p-8 xl:p-10">
          <div className="max-w-sm space-y-3 pt-4">
            <div className="text-[10px] font-medium uppercase tracking-[0.24em] text-sky-700 dark:text-cyan-100/75">
              Workspace Access
            </div>
            <h2 className="text-3xl font-semibold tracking-tight text-slate-950 dark:text-white">
              Enter SOIT with a cleaner sign-in surface.
            </h2>
            <p className="text-sm leading-6 text-slate-600 dark:text-slate-300">
              Keep the original split-page structure, but make the experience calmer and more consistent.
            </p>
          </div>

          <div className="grid gap-2.5 sm:grid-cols-3">
            {panelItems.map((item) => (
              <div
                key={item}
                className="rounded-md border border-slate-200/80 bg-white/75 px-3 py-3 text-xs font-medium text-slate-700 backdrop-blur-sm dark:border-white/10 dark:bg-white/8 dark:text-white"
              >
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
