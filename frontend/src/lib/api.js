import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const api = axios.create({ baseURL: API });

// Sessions
export const createSession = () => api.post('/sessions').then(r => r.data);
export const getSession = (sid) => api.get(`/sessions/${sid}`).then(r => r.data);
export const updateSettings = (sid, settings) => api.put(`/sessions/${sid}/settings`, settings).then(r => r.data);

// Upload
export const uploadFile = (sid, fileType, file) => {
    const fd = new FormData();
    fd.append('file', file);
    return api.post(`/sessions/${sid}/upload/${fileType}`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
    }).then(r => r.data);
};

// Validation
export const validateFiles = (sid) => api.post(`/sessions/${sid}/validate`).then(r => r.data);

// Identity
export const getIdentity = (sid) => api.get(`/sessions/${sid}/identity`).then(r => r.data);
export const identityDecide = (sid, matchId, decision) => api.post(`/sessions/${sid}/identity/decide`, { match_id: matchId, decision }).then(r => r.data);
export const identityUndo = (sid) => api.post(`/sessions/${sid}/identity/undo`).then(r => r.data);
export const identityReset = (sid) => api.post(`/sessions/${sid}/identity/reset`).then(r => r.data);

// Analysis
export const startAnalysis = (sid) => api.post(`/sessions/${sid}/analyze`).then(r => r.data);
export const getStatus = (sid) => api.get(`/sessions/${sid}/status`).then(r => r.data);

// Dashboard
export const getDashboard = (sid) => api.get(`/sessions/${sid}/dashboard`).then(r => r.data);

// Accounts
export const getAccounts = (sid, params = {}) => api.get(`/sessions/${sid}/accounts`, { params }).then(r => r.data);
export const getLineage = (sid, rsxId) => api.get(`/sessions/${sid}/accounts/${rsxId}`).then(r => r.data);

// Exclusions
export const getExclusions = (sid, reasonCode) => api.get(`/sessions/${sid}/exclusions`, { params: reasonCode ? { reason_code: reasonCode } : {} }).then(r => r.data);

// Export
export const exportAccountsUrl = (sid, vt) => `${API}/sessions/${sid}/export/accounts${vt ? '?variance_type=' + vt : ''}`;
export const exportLineageUrl = (sid, rsxId) => `${API}/sessions/${sid}/export/lineage/${rsxId}`;
export const exportExclusionsUrl = (sid) => `${API}/sessions/${sid}/export/exclusions`;
export const exportReportUrl = (sid) => `${API}/sessions/${sid}/export/report`;

// Templates
export const templateUrl = (ft) => `${API}/templates/${ft}`;
export const syntheticDownloadUrl = (ft) => `${API}/synthetic/download/${ft}`;

// Synthetic
export const generateSynthetic = () => api.post('/synthetic').then(r => r.data);
