import { Navigate, useLocation } from 'react-router'

function SystemLegacyRedirect() {
  const location = useLocation()
  const nextPath = location.pathname.replace(/^\/system\b/, '/observability')
  return <Navigate to={`${nextPath}${location.search}${location.hash}`} replace />
}

export default SystemLegacyRedirect
