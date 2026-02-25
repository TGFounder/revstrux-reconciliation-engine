import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAppSession } from "@/App";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { CheckCircle2, Loader2, AlertCircle, Clock } from "lucide-react";
import { getStatus } from "@/lib/api";

const STEPS = [
  { key: 'ingestion', label: 'Ingestion', desc: 'Loading validated data' },
  { key: 'identity', label: 'Identity Spine', desc: 'Building entity crosswalk' },
  { key: 'lifecycle', label: 'Lifecycle', desc: 'Generating revenue segments' },
  { key: 'reconciliation', label: 'Reconciliation', desc: 'Matching invoices & calculating variance' },
  { key: 'scoring', label: 'Scoring', desc: 'Computing structural integrity score' },
];

export default function ProcessingPage() {
  const navigate = useNavigate();
  const { sessionId, setSessionStatus } = useAppSession();
  const [status, setStatus] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const startTime = useRef(Date.now());
  const pollRef = useRef(null);
  const timerRef = useRef(null);

  useEffect(() => {
    if (!sessionId) return;
    startTime.current = Date.now();

    pollRef.current = setInterval(async () => {
      try {
        const result = await getStatus(sessionId);
        setStatus(result);
        if (result.status === 'completed') {
          setSessionStatus('completed');
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
          setTimeout(() => navigate('/dashboard'), 2000);
        } else if (result.status === 'error') {
          setSessionStatus('error');
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
        }
      } catch (e) { /* ignore poll errors */ }
    }, 1000);

    timerRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime.current) / 1000));
    }, 1000);

    return () => {
      clearInterval(pollRef.current);
      clearInterval(timerRef.current);
    };
  }, [sessionId, navigate, setSessionStatus]);

  const steps = status?.processing_status?.steps || {};
  const log = status?.processing_status?.log || [];
  const currentStep = status?.processing_status?.current_step;
  const completed = status?.status === 'completed';
  const error = status?.status === 'error';

  const formatTime = (s) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;

  return (
    <div className="space-y-6 fade-in" data-testid="processing-page">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 font-heading">Processing Analysis</h1>
        <p className="text-sm text-slate-500 mt-1">Running deterministic reconciliation engine</p>
      </div>

      {/* Timer */}
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Clock size={14} />
        <span className="font-mono tabular-nums">{formatTime(elapsed)}</span>
        {completed && <span className="text-emerald-600 font-medium ml-2">Complete - redirecting to dashboard...</span>}
        {error && <span className="text-red-600 font-medium ml-2">Error occurred</span>}
      </div>

      {/* Step tracker */}
      <Card data-testid="step-tracker">
        <CardContent className="py-5 px-5">
          <div className="space-y-3">
            {STEPS.map((step, i) => {
              const stepStatus = steps[step.key]?.status;
              const isActive = currentStep === step.key && !completed;
              const isDone = stepStatus === 'complete' || (completed && true);
              const isPending = !stepStatus && !isActive && !completed;

              return (
                <div key={step.key} className="flex items-center gap-3" data-testid={`step-${step.key}`}>
                  <div className="w-7 h-7 flex items-center justify-center shrink-0">
                    {isDone ? (
                      <CheckCircle2 size={20} className="text-emerald-600" />
                    ) : isActive ? (
                      <Loader2 size={20} className="text-blue-600 spinner" />
                    ) : (
                      <div className="w-5 h-5 rounded-full border-2 border-slate-200" />
                    )}
                  </div>
                  <div className="flex-1">
                    <div className={`text-sm font-medium ${isDone ? 'text-emerald-700' : isActive ? 'text-blue-700' : 'text-slate-400'}`}>
                      {step.label}
                    </div>
                    <div className="text-[10px] text-slate-400">{step.desc}</div>
                  </div>
                  {isDone && steps[step.key]?.timestamp && (
                    <span className="text-[10px] text-slate-400 font-mono">done</span>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Processing log */}
      {log.length > 0 && (
        <Card data-testid="processing-log">
          <CardContent className="py-3 px-4">
            <div className="text-xs font-medium text-slate-500 mb-2">Processing Log</div>
            <ScrollArea className="h-40">
              <div className="space-y-1 font-mono text-[11px]">
                {log.map((entry, i) => (
                  <div key={i} className="flex gap-2 text-slate-600 py-0.5">
                    <span className="text-slate-400 shrink-0">[{entry.step}]</span>
                    <span>{entry.message}</span>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-md" data-testid="processing-error">
          <div className="flex items-center gap-2 text-red-700 text-sm">
            <AlertCircle size={16} />
            <span className="font-medium">Processing failed</span>
          </div>
          <p className="text-xs text-red-600 mt-1">{status?.processing_status?.error || 'Unknown error'}</p>
        </div>
      )}
    </div>
  );
}
