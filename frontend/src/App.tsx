import { HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ClientProvider } from './context/ClientProvider'
import { AnalyticsPage } from './pages/Analytics'
import { Dashboard } from './pages/Dashboard'
import { Operations } from './pages/Operations'
import { PerformancePage } from './pages/Performance'
import { StatementPage } from './pages/Statement'

export function App() {
  return (
    <ClientProvider>
      <HashRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="extrato" element={<StatementPage />} />
            <Route path="rentabilidade" element={<PerformancePage />} />
            <Route path="analise" element={<AnalyticsPage />} />
            <Route path="operacoes" element={<Operations />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </HashRouter>
    </ClientProvider>
  )
}
