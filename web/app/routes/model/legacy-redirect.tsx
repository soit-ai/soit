import { Navigate, useLocation } from 'react-router'

function ModelLegacyRedirect() {
  const location = useLocation()
  const nextPath = location.pathname.replace(/^\/model\b/, '/models')
  return <Navigate to={`${nextPath}${location.search}${location.hash}`} replace />
}

export default ModelLegacyRedirect
