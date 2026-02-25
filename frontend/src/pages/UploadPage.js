import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAppSession } from "@/App";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Upload, CheckCircle2, AlertCircle, Download, FileText, Loader2, Zap, X } from "lucide-react";
import { createSession, uploadFile, validateFiles, generateSynthetic, templateUrl, updateSettings } from "@/lib/api";

const FILE_TYPES = [
  { key: 'accounts', label: 'accounts.csv', required: true },
  { key: 'customers', label: 'customers.csv', required: true },
  { key: 'subscriptions', label: 'subscriptions.csv', required: true },
  { key: 'invoices', label: 'invoices.csv', required: true },
  { key: 'payments', label: 'payments.csv', required: true },
  { key: 'credit_notes', label: 'credit_notes.csv', required: false },
];

const CURRENCIES = ['USD', 'GBP', 'EUR', 'INR', 'AUD', 'CAD', 'SGD', 'AED'];

function UploadZone({ fileType, label, required, status, onUpload }) {
  const [dragOver, setDragOver] = useState(false);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer?.files?.[0];
    if (file) onUpload(fileType, file);
  }, [fileType, onUpload]);

  const handleSelect = useCallback((e) => {
    const file = e.target.files?.[0];
    if (file) onUpload(fileType, file);
  }, [fileType, onUpload]);

  const uploaded = status?.uploaded;

  return (
    <div
      data-testid={`upload-zone-${fileType}`}
      className={`upload-zone ${uploaded ? 'uploaded' : ''} ${!required ? 'optional' : ''} ${dragOver ? 'border-blue-400 bg-blue-50' : 'border-slate-300'}`}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      onClick={() => document.getElementById(`file-${fileType}`)?.click()}
    >
      <input id={`file-${fileType}`} type="file" accept=".csv" className="hidden" onChange={handleSelect} />
      {uploaded ? (
        <div className="flex flex-col items-center gap-1">
          <CheckCircle2 size={24} className="text-emerald-600" />
          <span className="text-xs font-medium text-emerald-700">{status.filename}</span>
          <span className="text-[10px] text-emerald-600">{status.rows} rows</span>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-1">
          <Upload size={20} className="text-slate-400" />
          <span className="text-xs font-medium text-slate-700">{label}</span>
          {!required && <span className="text-[10px] text-slate-400">Optional</span>}
          <span className="text-[10px] text-slate-400">Drop CSV or click to browse</span>
        </div>
      )}
    </div>
  );
}

export default function UploadPage() {
  const navigate = useNavigate();
  const { sessionId, setSessionId, setSessionStatus } = useAppSession();
  const [uploads, setUploads] = useState({});
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState(null);
  const [currency, setCurrency] = useState('USD');
  const [periodStart, setPeriodStart] = useState('2024-01');
  const [periodEnd, setPeriodEnd] = useState('2024-12');
  const [loading, setLoading] = useState(false);
  const [syntheticLoading, setSyntheticLoading] = useState(false);

  const handleUpload = useCallback(async (fileType, file) => {
    try {
      let sid = sessionId;
      if (!sid) {
        const s = await createSession();
        sid = s.session_id;
        setSessionId(sid);
        setSessionStatus('created');
      }
      const result = await uploadFile(sid, fileType, file);
      setUploads(prev => ({ ...prev, [fileType]: { uploaded: true, rows: result.rows, filename: result.filename } }));
      toast.success(`${fileType}.csv uploaded (${result.rows} rows)`);
    } catch (e) {
      toast.error(`Upload failed: ${e.message}`);
    }
  }, [sessionId, setSessionId, setSessionStatus]);

  const handleValidate = async () => {
    if (!sessionId) return;
    setValidating(true);
    try {
      await updateSettings(sessionId, { currency, period_start: periodStart, period_end: periodEnd });
      const result = await validateFiles(sessionId);
      setValidationResult(result);
      if (result.valid) {
        setSessionStatus('identity_review');
        toast.success("All files validated successfully");
      } else {
        toast.error(`${result.errors.length} validation error(s) found`);
      }
    } catch (e) {
      toast.error(`Validation failed: ${e.message}`);
    }
    setValidating(false);
  };

  const handleSynthetic = async () => {
    setSyntheticLoading(true);
    try {
      const result = await generateSynthetic();
      setSessionId(result.session_id);
      setSessionStatus('created');
      const meta = result.metadata;
      setUploads({
        accounts: { uploaded: true, rows: meta.total_accounts, filename: 'accounts_synthetic.csv' },
        customers: { uploaded: true, rows: meta.total_customers, filename: 'customers_synthetic.csv' },
        subscriptions: { uploaded: true, rows: meta.total_subscriptions, filename: 'subscriptions_synthetic.csv' },
        invoices: { uploaded: true, rows: meta.total_invoices, filename: 'invoices_synthetic.csv' },
        payments: { uploaded: true, rows: meta.total_payments, filename: 'payments_synthetic.csv' },
        credit_notes: { uploaded: true, rows: meta.total_credit_notes, filename: 'credit_notes_synthetic.csv' },
      });
      toast.success("Synthetic dataset loaded");
    } catch (e) {
      toast.error(`Synthetic generation failed: ${e.message}`);
    }
    setSyntheticLoading(false);
  };

  const requiredUploaded = FILE_TYPES.filter(f => f.required).every(f => uploads[f.key]?.uploaded);
  const canProceed = validationResult?.valid;

  return (
    <div className="space-y-6 fade-in" data-testid="upload-page">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 font-heading">Data Upload</h1>
          <p className="text-sm text-slate-500 mt-1">Upload CSV exports from your CRM and billing systems</p>
        </div>
        <Button variant="outline" size="sm" onClick={handleSynthetic} disabled={syntheticLoading} data-testid="load-synthetic-btn">
          {syntheticLoading ? <Loader2 size={14} className="spinner mr-2" /> : <Zap size={14} className="mr-2" />}
          Load Synthetic Data
        </Button>
      </div>

      {/* Template downloads */}
      <Card>
        <CardHeader className="py-3 px-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium">Download Templates</CardTitle>
            <div className="flex gap-1 flex-wrap">
              {FILE_TYPES.map(f => (
                <a key={f.key} href={templateUrl(f.key)} download data-testid={`template-${f.key}`}>
                  <Badge variant="outline" className="cursor-pointer hover:bg-slate-50 text-[10px]">
                    <Download size={10} className="mr-1" />{f.key}
                  </Badge>
                </a>
              ))}
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Upload zones */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {FILE_TYPES.map(f => (
          <UploadZone
            key={f.key}
            fileType={f.key}
            label={f.label}
            required={f.required}
            status={uploads[f.key]}
            onUpload={handleUpload}
          />
        ))}
      </div>

      {/* Settings */}
      <Card>
        <CardContent className="py-4 px-4">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1">Display Currency</label>
              <Select value={currency} onValueChange={setCurrency}>
                <SelectTrigger className="w-28 h-8 text-xs" data-testid="currency-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CURRENCIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1">Period Start</label>
              <input type="month" value={periodStart} onChange={e => setPeriodStart(e.target.value)}
                     className="h-8 px-2 text-xs border rounded-md" data-testid="period-start" />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1">Period End</label>
              <input type="month" value={periodEnd} onChange={e => setPeriodEnd(e.target.value)}
                     className="h-8 px-2 text-xs border rounded-md" data-testid="period-end" />
            </div>
            <div className="flex gap-2 ml-auto">
              <Button size="sm" variant="outline" onClick={handleValidate} disabled={!requiredUploaded || validating} data-testid="validate-btn">
                {validating ? <Loader2 size={14} className="spinner mr-2" /> : <FileText size={14} className="mr-2" />}
                Validate Files
              </Button>
              <Button size="sm" onClick={() => navigate('/identity')} disabled={!canProceed} data-testid="proceed-btn">
                Proceed
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Validation results */}
      {validationResult && (
        <Card data-testid="validation-results">
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-sm flex items-center gap-2">
              {validationResult.valid ? (
                <><CheckCircle2 size={16} className="text-emerald-600" /> All files validated</>
              ) : (
                <><AlertCircle size={16} className="text-red-600" /> {validationResult.errors.length} error(s) found</>
              )}
            </CardTitle>
          </CardHeader>
          {!validationResult.valid && (
            <CardContent className="px-4 pb-4">
              <div className="max-h-60 overflow-auto space-y-1">
                {validationResult.errors.slice(0, 50).map((err, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs py-1 border-b border-slate-100">
                    <Badge variant="destructive" className="text-[9px] shrink-0">{err.file}</Badge>
                    {err.row > 0 && <span className="text-slate-400 shrink-0">Row {err.row}</span>}
                    {err.field && <span className="font-mono text-slate-500 shrink-0">{err.field}</span>}
                    <span className="text-slate-700">{err.message}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          )}
          {validationResult.warnings?.length > 0 && (
            <CardContent className="px-4 pb-4">
              {validationResult.warnings.map((w, i) => (
                <Alert key={i} className="mb-1">
                  <AlertDescription className="text-xs text-amber-700">{w.message}</AlertDescription>
                </Alert>
              ))}
            </CardContent>
          )}
        </Card>
      )}
    </div>
  );
}
