import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAppSession } from "@/App";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { CheckCircle2, XCircle, Undo2, RotateCcw, ArrowRight, Loader2, AlertTriangle, Users } from "lucide-react";
import { getIdentity, identityDecide, identityUndo, identityReset, startAnalysis } from "@/lib/api";

export default function IdentityPage() {
  const navigate = useNavigate();
  const { sessionId, setSessionStatus } = useAppSession();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showReset, setShowReset] = useState(false);
  const [deciding, setDeciding] = useState(false);

  const load = useCallback(async () => {
    if (!sessionId) return;
    try {
      const result = await getIdentity(sessionId);
      setData(result);
    } catch (e) {
      toast.error("Failed to load identity data");
    }
    setLoading(false);
  }, [sessionId]);

  useEffect(() => { load(); }, [load]);

  const handleDecide = async (matchId, decision) => {
    setDeciding(true);
    try {
      await identityDecide(sessionId, matchId, decision);
      await load();
      toast.success(decision === 'confirmed' ? 'Match confirmed' : 'Match rejected');
    } catch (e) {
      toast.error("Decision failed");
    }
    setDeciding(false);
  };

  const handleUndo = async () => {
    try {
      const result = await identityUndo(sessionId);
      if (result.error) { toast.error(result.error); return; }
      await load();
      toast.info("Last decision undone");
    } catch (e) {
      toast.error("Undo failed");
    }
  };

  const handleReset = async () => {
    try {
      await identityReset(sessionId);
      await load();
      setShowReset(false);
      toast.info("All decisions cleared");
    } catch (e) {
      toast.error("Reset failed");
    }
  };

  const handleRunAnalysis = async () => {
    try {
      setSessionStatus('processing');
      await startAnalysis(sessionId);
      navigate('/processing');
    } catch (e) {
      toast.error("Failed to start analysis");
    }
  };

  if (loading) return <div className="flex items-center justify-center py-20"><Loader2 className="spinner text-slate-400" size={24} /></div>;
  if (!data) return <div className="text-center py-20 text-slate-400">No identity data available. Go to Upload first.</div>;

  const { auto_matched = [], needs_review = [], pending_review = [], unmatched_accounts = [], decisions = [], all_reviewed } = data;
  const currentCard = pending_review[0];

  return (
    <div className="space-y-6 fade-in" data-testid="identity-page">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 font-heading">Identity Review</h1>
        <p className="text-sm text-slate-500 mt-1">Match CRM accounts to billing customers</p>
      </div>

      {/* Summary bar */}
      <div className="grid grid-cols-3 gap-3" data-testid="identity-summary">
        <Card className="bg-emerald-50 border-emerald-200">
          <CardContent className="py-3 px-4 text-center">
            <div className="text-2xl font-bold font-mono text-emerald-700 tabular-nums">{auto_matched.length}</div>
            <div className="text-xs text-emerald-600">Auto-matched</div>
          </CardContent>
        </Card>
        <Card className="bg-amber-50 border-amber-200">
          <CardContent className="py-3 px-4 text-center">
            <div className="text-2xl font-bold font-mono text-amber-700 tabular-nums">{needs_review.length}</div>
            <div className="text-xs text-amber-600">Needs Review</div>
          </CardContent>
        </Card>
        <Card className="bg-red-50 border-red-200">
          <CardContent className="py-3 px-4 text-center">
            <div className="text-2xl font-bold font-mono text-red-700 tabular-nums">{unmatched_accounts.length}</div>
            <div className="text-xs text-red-600">Unmatched</div>
          </CardContent>
        </Card>
      </div>

      {/* Review queue */}
      {currentCard ? (
        <Card data-testid="review-card">
          <CardHeader className="py-3 px-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">
                Reviewing {decisions.length + 1} of {needs_review.length}
              </CardTitle>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={handleUndo} disabled={decisions.length === 0} data-testid="undo-btn">
                  <Undo2 size={14} className="mr-1" /> Undo last decision
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setShowReset(true)} data-testid="reset-btn">
                  <RotateCcw size={14} className="mr-1" /> Reset All
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <div className="flex items-center gap-4">
              {/* CRM side */}
              <div className="flex-1 p-4 bg-slate-50 rounded-md border">
                <div className="text-[10px] text-slate-400 uppercase tracking-wider mb-1">CRM Account</div>
                <div className="text-base font-bold text-slate-900">{currentCard.account_name}</div>
                <div className="text-xs font-mono text-slate-500 mt-1">{currentCard.account_id}</div>
                <div className="text-[10px] text-slate-400 mt-1">{currentCard.source_account}</div>
              </div>

              {/* Confidence */}
              <div className="flex flex-col items-center px-3">
                <div className={`text-xl font-bold font-mono tabular-nums ${currentCard.confidence >= 0.85 ? 'text-amber-600' : 'text-orange-600'}`}>
                  {Math.round(currentCard.confidence * 100)}%
                </div>
                <div className="text-[10px] text-slate-400">confidence</div>
              </div>

              {/* Billing side */}
              <div className="flex-1 p-4 bg-slate-50 rounded-md border">
                <div className="text-[10px] text-slate-400 uppercase tracking-wider mb-1">Billing Customer</div>
                <div className="text-base font-bold text-slate-900">{currentCard.customer_name}</div>
                <div className="text-xs font-mono text-slate-500 mt-1">{currentCard.customer_id}</div>
                <div className="text-[10px] text-slate-400 mt-1">{currentCard.source_customer}</div>
              </div>
            </div>

            <div className="flex gap-3 mt-4 justify-center">
              <Button className="bg-emerald-600 hover:bg-emerald-700" onClick={() => handleDecide(currentCard.match_id, 'confirmed')} disabled={deciding} data-testid="confirm-match-btn">
                <CheckCircle2 size={16} className="mr-2" /> Confirm — Same Company
              </Button>
              <Button variant="destructive" onClick={() => handleDecide(currentCard.match_id, 'rejected')} disabled={deciding} data-testid="reject-match-btn">
                <XCircle size={16} className="mr-2" /> Different Companies
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : needs_review.length > 0 ? (
        <Card>
          <CardContent className="py-6 text-center">
            <CheckCircle2 size={32} className="text-emerald-600 mx-auto mb-2" />
            <p className="text-sm font-medium text-slate-700">All matches reviewed</p>
            <div className="flex gap-2 mt-3 justify-center">
              <Button variant="ghost" size="sm" onClick={handleUndo} disabled={decisions.length === 0} data-testid="undo-btn-final">
                <Undo2 size={14} className="mr-1" /> Undo last decision
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setShowReset(true)} data-testid="reset-btn-final">
                <RotateCcw size={14} className="mr-1" /> Reset All
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Alert>
          <AlertDescription className="text-sm">No manual review needed. All entities were auto-matched or unmatched.</AlertDescription>
        </Alert>
      )}

      {/* Unmatched entities */}
      {unmatched_accounts.length > 0 && (
        <Card data-testid="unmatched-section">
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-sm flex items-center gap-2">
              <AlertTriangle size={14} className="text-amber-500" />
              Unmatched Entities ({unmatched_accounts.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <p className="text-xs text-slate-500 mb-3">
              These accounts will be included as Unknown Exposure. Their subscription data cannot be reconciled against invoices.
            </p>
            <div className="space-y-1">
              {unmatched_accounts.map(a => (
                <div key={a.account_id} className="flex items-center gap-3 py-1.5 px-2 bg-slate-50 rounded text-xs">
                  <span className="font-mono text-slate-500">{a.account_id}</span>
                  <span className="font-medium text-slate-700">{a.account_name}</span>
                  <Badge variant="outline" className="text-amber-600 border-amber-300 text-[9px] ml-auto">Unknown Exposure</Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Run Analysis button */}
      <div className="flex justify-end">
        <Button size="lg" onClick={handleRunAnalysis}
                disabled={needs_review.length > 0 && !all_reviewed}
                data-testid="run-analysis-btn">
          Run Analysis <ArrowRight size={16} className="ml-2" />
        </Button>
      </div>

      {/* Reset dialog */}
      <Dialog open={showReset} onOpenChange={setShowReset}>
        <DialogContent data-testid="reset-dialog">
          <DialogHeader>
            <DialogTitle>Reset All Decisions?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-slate-600">This will clear all {decisions.length} review decisions. You will restart from the beginning.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowReset(false)}>Cancel</Button>
            <Button variant="destructive" onClick={handleReset} data-testid="confirm-reset-btn">Reset All</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
