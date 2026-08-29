// The shared use-navigate hook already forwards the ?nosider embed flag on
// every navigation; the console must keep that behaviour, so this is a
// re-export under a console-local name rather than a copy.
export { useNavigate as useConsoleNavigate } from '@/hooks/use-navigate'
