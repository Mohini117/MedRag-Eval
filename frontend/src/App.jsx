import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import NavBar from './components/layout/NavBar'
import QueryRunner    from './pages/QueryRunner'
import BenchmarkResults from './pages/BenchmarkResults'
import ScoreHeatmap   from './pages/ScoreHeatmap'
import FailureExplorer from './pages/FailureExplorer'
import TraceViewer    from './pages/TraceViewer'

export default function App() {
  return (
    <BrowserRouter>
      <NavBar />
      <Routes>
        <Route path="/"        element={<QueryRunner />} />
        <Route path="/benchmark" element={<BenchmarkResults />} />
        <Route path="/heatmap" element={<ScoreHeatmap />} />
        <Route path="/failure" element={<FailureExplorer />} />
        <Route path="/trace"   element={<TraceViewer />} />
        <Route path="*"        element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
