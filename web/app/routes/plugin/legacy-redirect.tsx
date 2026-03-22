import { Navigate, useLocation } from 'react-router'

function PluginLegacyRedirect() {
  const location = useLocation()
  const nextPath = location.pathname.replace(/^\/plugin\b/, '/plugins')
  return <Navigate to={`${nextPath}${location.search}${location.hash}`} replace />
}

export default PluginLegacyRedirect
