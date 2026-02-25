import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAppSession } from "@/App";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";
import { Separator } from "@/components/ui/separator";
import {
  Upload, CheckCircle2, AlertCircle, AlertTriangle, Download, FileText,
  Loader2, Zap, X, FileArchive, ArrowRight, Info, CalendarIcon
} from "lucide-react";
import {
  createSession, smartUpload, smartValidate, validateFiles,
  uploadFile, generateSynthetic, templateUrl, updateSettings
} from "@/lib/api";

const CURRENCIES = ['USD', 'GBP', 'EUR', 'INR', 'AUD', 'CAD', 'SGD', 'AED', 'JPY', 'CHF'];

const FILE_TYPE_LABELS = {
  accounts: 'Accounts',
  customers: 'Customers',
  subscriptions: 'Subscriptions',
  invoices: 'Invoices',
  payments: 'Payments',
  credit_notes: 'Credit Notes',
};

const CONFIDENCE_COLORS = {
  high: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  medium: 'bg-amber-50 text-amber-700 border-amber-200',
  low: 'bg-red-50 text-red-700 border-red-200',
};

function confidenceLevel(c) {
  if (c >= 0.8) return 'high';
  if (c >= 0.5) return 'medium';
  return 'low';
}

function formatMonthStr(d) {
  if (!d) return '';
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  return `${y}-${m}`;
}

function DatePicker({ label, value, onChange, testId }) {
  const dateObj = value ? new Date(value + '-01') : null;
  return (
    <div>
      <label className="text-xs font-medium text-slate-600 block mb-1">{label}</label>
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="w-40 justify-start text-left text-xs font-normal h-8" data-testid={testId}>
            <CalendarIcon size={14} className="mr-2 text-slate-400" />
            {value || 'Pick month'}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="single"
            selected={dateObj}
            onSelect={(d) => d && onChange(formatMonthStr(d))}
            initialFocus
          />
        </PopoverContent>
      </Popover>
    </div>
  );
}

function DetectedFileCard({ result, index }) {
  const hasError = result.error || result.validation?.errors?.length > 0;
  const hasWarnings = result.validation?.warnings?.length > 0;
  const conf = confidenceLevel(result.confidence || 0);

  if (result.error) {
    return (
      <div className="flex items-center gap-3 p-3 rounded-lg border border-red-200 bg-red-50" data-testid={`detected-file-${index}`}>
        <AlertCircle size={16} className="text-red-500 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-red-800 truncate">{result.filename}</div>
          <div className="text-xs text-red-600">{result.error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className={`p-3 rounded-lg border transition-all ${hasError ? 'border-red-200 bg-red-50/50' : 'border-slate-200 bg-white'}`}
         data-testid={`detected-file-${index}`}>
      <div className="flex items-center gap-3">
        <FileText size={16} className="text-slate-400 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-slate-800 truncate">{result.filename}</span>
            <Badge variant="outline" className="text-[10px] shrink-0">{result.rows} rows</Badge>
          </div>
          <div className="flex items-center gap-2 mt-1">
            {result.detected_type ? (
              <Badge variant="outline" className={`text-[10px] ${CONFIDENCE_COLORS[conf]}`}>
                {FILE_TYPE_LABELS[result.detected_type] || result.detected_type}
                <span className="ml-1 opacity-70">{Math.round((result.confidence || 0) * 100)}%</span>
              </Badge>
            ) : (
              <Badge variant="outline" className="text-[10px] bg-slate-100 text-slate-500">Unknown type</Badge>
            )}
            {result.header_mappings?.length > 0 && (
              <span className="text-[10px] text-blue-600">{result.header_mappings.length} header(s) normalized</span>
            )}
            {result.enum_normalizations?.length > 0 && (
              <span className="text-[10px] text-purple-600">{result.enum_normalizations.length} value(s) normalized</span>
            )}
          </div>
        </div>
        {!hasError && result.detected_type && (
          <CheckCircle2 size={16} className="text-emerald-500 shrink-0" />
        )}
      </div>

      {/* Normalization details */}
      {(result.header_mappings?.length > 0 || result.enum_normalizations?.length > 0) && (
        <div className="mt-2 pt-2 border-t border-slate-100">
          {result.header_mappings?.slice(0, 5).map((m, i) => (
            <div key={i} className="text-[10px] text-slate-500 flex gap-1">
              <span className="font-mono text-slate-400">{m.original}</span>
              <ArrowRight size={10} className="text-slate-300" />
              <span className="font-mono text-blue-600">{m.normalized}</span>
            </div>
          ))}
          {result.header_mappings?.length > 5 && (
            <div className="text-[10px] text-slate-400">+{result.header_mappings.length - 5} more</div>
          )}
          {result.enum_normalizations?.slice(0, 3).map((n, i) => (
            <div key={`e${i}`} className="text-[10px] text-slate-500 flex gap-1">
              <span className="font-mono text-slate-400">{n.field}: {n.original}</span>
              <ArrowRight size={10} className="text-slate-300" />
              <span className="font-mono text-purple-600">{n.normalized}</span>
            </div>
          ))}
        </div>
      )}

      {/* Validation warnings */}
      {hasWarnings && (
        <div className="mt-2 pt-2 border-t border-slate-100 space-y-1">
          {result.validation.warnings.slice(0, 3).map((w, i) => (
            <div key={i} className="flex items-start gap-1 text-[10px] text-amber-700">
              <AlertTriangle size={10} className="shrink-0 mt-0.5" />
              <span>{w.message}</span>
            </div>
          ))}
        </div>
      )}

      {/* Validation errors */}
      {hasError && result.validation?.errors?.length > 0 && (
        <div className="mt-2 pt-2 border-t border-red-100 space-y-1">
          {result.validation.errors.slice(0, 3).map((e, i) => (
            <div key={i} className="flex items-start gap-1 text-[10px] text-red-700">
              <AlertCircle size={10} className="shrink-0 mt-0.5" />
              <span>{e.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function UploadPage() {
  const navigate = useNavigate();
  const { sessionId, setSessionId, setSessionStatus } = useAppSession();
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadResults, setUploadResults] = useState(null);
  const [storedTypes, setStoredTypes] = useState([]);
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState(null);
  const [currency, setCurrency] = useState('USD');
  const [periodStart, setPeriodStart] = useState('2024-01');
  const [periodEnd, setPeriodEnd] = useState('2024-12');
  const [syntheticLoading, setSyntheticLoading] = useState(false);
  const [droppedFiles, setDroppedFiles] = useState([]);

  const handleFiles = useCallback(async (fileList) => {
    const files = Array.from(fileList).filter(f =>
      f.name.toLowerCase().endsWith('.csv') || f.name.toLowerCase().endsWith('.zip')
    );
    if (files.length === 0) {
      toast.error('Please upload .csv or .zip files');
      return;
    }

    setUploading(true);
    setDroppedFiles(files);
    setValidationResult(null);

    try {
      let sid = sessionId;
      if (!sid) {
        const s = await createSession();
        sid = s.session_id;
        setSessionId(sid);
        setSessionStatus('created');
      }

      const result = await smartUpload(sid, files);
      setUploadResults(result.results);
      setStoredTypes(result.stored_types || []);

      const errFiles = result.results.filter(r => r.error || r.validation?.errors?.length > 0);
      const okFiles = result.results.filter(r => !r.error && r.detected_type);

      if (okFiles.length > 0) {
        toast.success(`${okFiles.length} file(s) detected and normalized`);
      }
      if (errFiles.length > 0) {
        toast.error(`${errFiles.length} file(s) have issues`);
      }
    } catch (e) {
      toast.error(`Upload failed: ${e.message}`);
    }
    setUploading(false);
  }, [sessionId, setSessionId, setSessionStatus]);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  const handleFileSelect = useCallback((e) => {
    if (e.target.files?.length) handleFiles(e.target.files);
  }, [handleFiles]);

  const handleValidate = async () => {
    if (!sessionId) return;
    setValidating(true);
    try {
      await updateSettings(sessionId, { currency, period_start: periodStart, period_end: periodEnd });
      const result = await smartValidate(sessionId);
      setValidationResult(result);
      if (result.valid) {
        setSessionStatus('identity_review');
        toast.success("Validation passed. Ready to proceed.");
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
      const synTypes = ['accounts', 'customers', 'subscriptions', 'invoices', 'payments', 'credit_notes'];
      setStoredTypes(synTypes);
      setUploadResults(synTypes.map(ft => ({
        filename: `${ft}_synthetic.csv`,
        detected_type: ft,
        confidence: 1.0,
        rows: meta[`total_${ft}`] || 0,
        header_mappings: [],
        enum_normalizations: [],
        validation: { valid: true, errors: [], warnings: [] },
      })));
      toast.success("Synthetic dataset loaded");
    } catch (e) {
      toast.error(`Synthetic generation failed: ${e.message}`);
    }
    setSyntheticLoading(false);
  };

  const handleReset = () => {
    setUploadResults(null);
    setStoredTypes([]);
    setValidationResult(null);
    setDroppedFiles([]);
    setSessionId(null);
    setSessionStatus('');
  };

  const requiredTypes = ['accounts', 'customers', 'subscriptions', 'invoices'];
  const missingRequired = requiredTypes.filter(t => !storedTypes.includes(t));
  const canValidate = storedTypes.length > 0 && missingRequired.length === 0;
  const canProceed = validationResult?.valid;

  return (
    <div className="space-y-6 fade-in" data-testid="upload-page">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 font-heading">Data Upload</h1>
          <p className="text-sm text-slate-500 mt-1">
            Drop your CSV exports or a ZIP file. Headers are auto-detected and normalized.
          </p>
        </div>
        <div className="flex gap-2">
          {uploadResults && (
            <Button variant="ghost" size="sm" onClick={handleReset} data-testid="reset-upload-btn">
              <X size={14} className="mr-1" /> Reset
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={handleSynthetic} disabled={syntheticLoading} data-testid="load-synthetic-btn">
            {syntheticLoading ? <Loader2 size={14} className="spinner mr-2" /> : <Zap size={14} className="mr-2" />}
            Load Synthetic Data
          </Button>
        </div>
      </div>

      {/* Template downloads */}
      <Card>
        <CardHeader className="py-3 px-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <CardTitle className="text-sm font-medium">CSV Templates</CardTitle>
            <div className="flex gap-1 flex-wrap">
              {Object.entries(FILE_TYPE_LABELS).map(([key, label]) => (
                <a key={key} href={templateUrl(key)} download data-testid={`template-${key}`}>
                  <Badge variant="outline" className="cursor-pointer hover:bg-slate-50 text-[10px]">
                    <Download size={10} className="mr-1" />{key}
                  </Badge>
                </a>
              ))}
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Smart Drop Zone */}
      {!uploadResults && (
        <div
          data-testid="smart-drop-zone"
          className={`relative border-2 border-dashed rounded-lg transition-all duration-200 cursor-pointer
            ${dragOver ? 'border-blue-400 bg-blue-50/50 scale-[1.01]' : 'border-slate-300 hover:border-slate-400 hover:bg-slate-50/50'}
            ${uploading ? 'pointer-events-none opacity-60' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => document.getElementById('smart-file-input')?.click()}
        >
          <input
            id="smart-file-input"
            type="file"
            accept=".csv,.zip"
            multiple
            className="hidden"
            onChange={handleFileSelect}
          />
          <div className="flex flex-col items-center justify-center py-16 px-6">
            {uploading ? (
              <>
                <Loader2 size={32} className="spinner text-blue-500 mb-3" />
                <span className="text-sm font-medium text-blue-700">Processing files...</span>
                <span className="text-xs text-blue-500 mt-1">Detecting types, normalizing headers</span>
              </>
            ) : (
              <>
                <div className="flex items-center gap-3 mb-3">
                  <Upload size={28} className="text-slate-400" />
                  <FileArchive size={24} className="text-slate-300" />
                </div>
                <span className="text-sm font-medium text-slate-700">Drop CSV files or a ZIP archive</span>
                <span className="text-xs text-slate-400 mt-1">Headers are automatically detected, normalized, and validated</span>
                <div className="flex gap-2 mt-4">
                  <Badge variant="outline" className="text-[10px] text-slate-500">accounts.csv</Badge>
                  <Badge variant="outline" className="text-[10px] text-slate-500">invoices.csv</Badge>
                  <Badge variant="outline" className="text-[10px] text-slate-500">*.zip</Badge>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Detection Results */}
      {uploadResults && (
        <Card data-testid="detection-results">
          <CardHeader className="py-3 px-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm flex items-center gap-2">
                <Info size={14} className="text-slate-400" />
                Detected Files ({uploadResults.length})
              </CardTitle>
              <div className="flex gap-1">
                {storedTypes.map(t => (
                  <Badge key={t} variant="outline" className="text-[10px] bg-emerald-50 text-emerald-700 border-emerald-200">
                    <CheckCircle2 size={10} className="mr-1" />{FILE_TYPE_LABELS[t] || t}
                  </Badge>
                ))}
              </div>
            </div>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <div className="space-y-2">
              {uploadResults.map((result, i) => (
                <DetectedFileCard key={i} result={result} index={i} />
              ))}
            </div>

            {/* Missing required files warning */}
            {missingRequired.length > 0 && (
              <Alert className="mt-3 border-amber-200 bg-amber-50" data-testid="missing-files-alert">
                <AlertTriangle size={14} className="text-amber-600" />
                <AlertDescription className="text-xs text-amber-700">
                  Missing required: {missingRequired.map(t => FILE_TYPE_LABELS[t]).join(', ')}.
                  Upload additional files or use the drop zone above.
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {/* Settings: Currency + Date Selection */}
      {storedTypes.length > 0 && (
        <Card data-testid="settings-card">
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

              <DatePicker label="Period Start" value={periodStart} onChange={setPeriodStart} testId="period-start" />
              <DatePicker label="Period End" value={periodEnd} onChange={setPeriodEnd} testId="period-end" />

              <div className="flex gap-2 ml-auto">
                <Button size="sm" variant="outline" onClick={handleValidate}
                        disabled={!canValidate || validating} data-testid="validate-btn">
                  {validating ? <Loader2 size={14} className="spinner mr-2" /> : <FileText size={14} className="mr-2" />}
                  Validate & Match
                </Button>
                <Button size="sm" onClick={() => navigate('/identity')} disabled={!canProceed} data-testid="proceed-btn">
                  Proceed <ArrowRight size={14} className="ml-1" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Validation Results */}
      {validationResult && (
        <Card data-testid="validation-results">
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-sm flex items-center gap-2">
              {validationResult.valid ? (
                <><CheckCircle2 size={16} className="text-emerald-600" /> Validated — {validationResult.identity_summary?.auto_matched || 0} auto-matched, {validationResult.identity_summary?.needs_review || 0} need review</>
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
              <div className="space-y-1">
                {validationResult.warnings.map((w, i) => (
                  <div key={i} className="flex items-start gap-1 text-[10px] text-amber-700 py-0.5">
                    <AlertTriangle size={10} className="shrink-0 mt-0.5" />
                    <span>{w.message}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          )}
        </Card>
      )}
    </div>
  );
}
