import { Routes, Route, Navigate } from 'react-router-dom';
import AppLayout from './components/layout/AppLayout';
import DashboardPage from './pages/DashboardPage';
import ConveniosPage from './pages/ConveniosPage';
import ContractTypePage from './pages/ContractTypePage';
import AuditPage from './pages/AuditPage';
import RecordsPage from './pages/RecordsPage';
import SetupPage from './pages/SetupPage';

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/setup" element={<SetupPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/convenios" element={<ConveniosPage />} />
        <Route path="/calidad" element={<ContractTypePage />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="/records" element={<RecordsPage />} />
      </Route>
    </Routes>
  );
}
