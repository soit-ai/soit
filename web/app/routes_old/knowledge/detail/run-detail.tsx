import { Navigate, useParams } from 'react-router'

function Page() {
  const { runId } = useParams<{ knowledgeId: string; runId: string }>()

  if (!runId) {
    return <Navigate to="/observe/runs" replace />
  }

  return <Navigate to={`/observe/runs/${runId}`} replace />
}

export default Page
