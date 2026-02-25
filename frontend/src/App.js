import { useState, useEffect, createContext, useContext } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "@/components/Layout";
import UploadPage from "@/pages/UploadPage";
import IdentityPage from "@/pages/IdentityPage";
import ProcessingPage from "@/pages/ProcessingPage";
import DashboardPage from "@/pages/DashboardPage";
import AccountsPage from "@/pages/AccountsPage";
import LineagePage from "@/pages/LineagePage";
import ExclusionsPage from "@/pages/ExclusionsPage";
import ExportPage from "@/pages/ExportPage";
import { Toaster } from "@/components/ui/sonner";

// Session Context
export const SessionCtx = createContext(null);
export const useAppSession = () => useContext(SessionCtx);

function App() {
  const [sessionId, setSessionId] = useState(() => localStorage.getItem('revstrux_session') || null);
  const [sessionStatus, setSessionStatus] = useState('');

  useEffect(() => {
    if (sessionId) localStorage.setItem('revstrux_session', sessionId);
    else localStorage.removeItem('revstrux_session');
  }, [sessionId]);

  const ctx = { sessionId, setSessionId, sessionStatus, setSessionStatus };

  return (
    <SessionCtx.Provider value={ctx}>
      <BrowserRouter>
        <Layout sessionId={sessionId} sessionStatus={sessionStatus}>
          <Routes>
            <Route path="/" element={<Navigate to="/upload" replace />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/identity" element={<IdentityPage />} />
            <Route path="/processing" element={<ProcessingPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/accounts" element={<AccountsPage />} />
            <Route path="/accounts/:rsxId" element={<LineagePage />} />
            <Route path="/exclusions" element={<ExclusionsPage />} />
            <Route path="/export" element={<ExportPage />} />
          </Routes>
        </Layout>
        <Toaster position="top-right" richColors />
      </BrowserRouter>
    </SessionCtx.Provider>
  );
}

export default App;
