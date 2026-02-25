import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAppSession } from "@/App";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { AlertTriangle, Download, ArrowRight, FileWarning, Loader2, Info, ExternalLink } from "lucide-react";
import { getDashboard, exportReportUrl } from "@/lib/api";

const fmt = (n) => {
  if (n == null) return '$0';
  return '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
};
const fmtPct = (n) => `${Number(n || 0).toFixed(1)}%`;

export default function DashboardPage() {
  const navigate = useNavigate();
  const { sessionId } = useAppSession();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!sessionId) return;
    getDashboard(sessionId).then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, [sessionId]);

  if (loading) return <div className="flex items-center justify-center py-20"><Loader2 className="spinner text-slate-400" size={24} /></div>;
  if (!data || data.error) return <div className="text-center py-20 text-slate-400">No dashboard data. Run analysis first.</div>;

  const { score, top_findings = [], total_exclusions, ambiguous_allocations, settings, completed_at } = data;
  const { coverage, components, revenue_at_risk: rar } = score;
  const colorClass = `score-${score.color}`;
  const bgClass = `score-bg-${score.color}`;

  return (
    <TooltipProvider>
      <div className="space-y-6 fade-in" data-testid="dashboard-page">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 font-heading">Score Dashboard</h1>
            <p className="text-xs text-slate-400 mt-1">
              {settings?.currency} | {settings?.period_start} to {settings?.period_end} | Run: {completed_at ? new Date(completed_at).toLocaleString() : '-'}
            </p>
          </div>
          <a href={exportReportUrl(sessionId)} download>
            <Button variant="outline" size="sm" data-testid="download-report-btn"><Download size={14} className="mr-2" />Download Score Report</Button>
          </a>
        </div>

        {/* Coverage Panel */}
        <Card className={coverage.arr_pct < 70 ? 'border-amber-300' : 'border-emerald-200'} data-testid="coverage-panel">
          <CardContent className="py-4 px-5">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Subscription Coverage</div>
                <div className="text-lg font-bold font-mono tabular-nums text-slate-900">{fmtPct(coverage.subscription_pct)}</div>
                <div className="text-xs text-slate-500">{coverage.subscription_count} of {coverage.total_subscriptions} subscriptions</div>
              </div>
              <div>
                <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">ARR Coverage</div>
                <div className="text-lg font-bold font-mono tabular-nums text-slate-900">{fmtPct(coverage.arr_pct)}</div>
                <div className="text-xs text-slate-500">{fmt(coverage.arr_covered)} of {fmt(coverage.total_arr)} ARR</div>
              </div>
            </div>
            {coverage.arr_pct < 70 && (
              <div className="mt-3 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700 flex items-center gap-2" data-testid="coverage-warning">
                <AlertTriangle size={14} />
                Coverage Warning: Score may not reflect full revenue exposure.
              </div>
            )}
            {coverage.arr_pct >= 90 && (
              <div className="mt-3 p-2 bg-emerald-50 border border-emerald-200 rounded text-xs text-emerald-700">
                High coverage. Score reflects the majority of subscription value.
              </div>
            )}
          </CardContent>
        </Card>

        {/* Score + Revenue at Risk grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Score Panel */}
          <Card className="lg:col-span-2" data-testid="score-panel">
            <CardContent className="py-6 px-6">
              <div className="flex items-start gap-6">
                <div className={`text-center p-6 rounded-lg border-2 ${bgClass}`}>
                  <div className={`text-5xl font-extrabold font-mono tabular-nums ${colorClass}`}>{score.score}</div>
                  <div className={`text-sm font-bold uppercase tracking-wider mt-1 ${colorClass}`}>{score.band}</div>
                </div>
                <div className="flex-1">
                  <p className="text-sm text-slate-700 mb-4">{score.interpretation}</p>
                  <div className="space-y-3">
                    {Object.entries(components).map(([key, comp]) => (
                      <div key={key}>
                        <div className="flex justify-between text-xs mb-1">
                          <Link to={`/accounts?component_filter=${key.replace('_rate', '').replace('_completeness', '')}`}
                                className="text-slate-600 hover:text-slate-900 hover:underline cursor-pointer" data-testid={`component-${key}`}>
                            {comp.label} ({comp.weight}%)
                          </Link>
                          <span className="font-mono tabular-nums text-slate-700">{comp.value.toFixed(1)}%</span>
                        </div>
                        <Progress value={comp.value} className="h-2" />
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center gap-3 mt-4 text-[10px] text-slate-400">
                    <span>{total_exclusions} records excluded</span>
                    <Link to="/exclusions" className="text-blue-600 hover:underline flex items-center gap-0.5">
                      view Exclusions Log <ExternalLink size={10} />
                    </Link>
                    {ambiguous_allocations > 0 && (
                      <span className="text-amber-600">{ambiguous_allocations} ambiguous allocations</span>
                    )}
                  </div>
                  <Dialog>
                    <DialogTrigger asChild>
                      <Button variant="ghost" size="sm" className="mt-2 text-xs" data-testid="methodology-btn">
                        <Info size={12} className="mr-1" /> How is this calculated?
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader><DialogTitle>Scoring Methodology</DialogTitle></DialogHeader>
                      <div className="text-sm space-y-3">
                        <p className="font-medium text-slate-900">All calculations are deterministic and rule-based. No AI or machine learning is used.</p>
                        {Object.entries(components).map(([key, comp]) => (
                          <div key={key} className="p-3 bg-slate-50 rounded">
                            <div className="font-medium">{comp.label} (Weight: {comp.weight}%)</div>
                            <div className="text-xs text-slate-500 mt-1">Current: {comp.value.toFixed(1)}%</div>
                          </div>
                        ))}
                        <p className="text-xs text-slate-400">Deferred revenue modelling is not included in this analysis.</p>
                      </div>
                    </DialogContent>
                  </Dialog>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Revenue at Risk */}
          <Card data-testid="revenue-at-risk-panel">
            <CardHeader className="py-3 px-4">
              <CardTitle className="text-sm">Revenue at Risk</CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              <div className="text-2xl font-bold font-mono tabular-nums text-slate-900 mb-4">{fmt(rar.total)}</div>
              <div className="space-y-2">
                {[
                  { label: 'Missing Invoice', value: rar.missing_invoice, count: rar.missing_invoice_accounts, cls: 'text-red-600 bg-red-50' },
                  { label: 'Under-billed', value: rar.under_billed, count: rar.under_billed_accounts, cls: 'text-amber-600 bg-amber-50' },
                  { label: 'Over-billed', value: rar.over_billed, count: rar.over_billed_accounts, cls: 'text-blue-600 bg-blue-50' },
                  { label: 'Unpaid AR', value: rar.unpaid_ar, count: rar.unpaid_ar_accounts, cls: 'text-orange-600 bg-orange-50' },
                ].map(item => (
                  <div key={item.label} className={`flex items-center justify-between p-2 rounded ${item.cls}`}>
                    <div>
                      <div className="text-xs font-medium">{item.label}</div>
                      <div className="text-[10px] opacity-70">{item.count} account(s)</div>
                    </div>
                    <div className="text-sm font-mono tabular-nums font-bold">{fmt(item.value)}</div>
                  </div>
                ))}
              </div>
              <Button variant="ghost" size="sm" className="w-full mt-3 text-xs" onClick={() => navigate('/accounts')} data-testid="view-all-accounts-btn">
                View All Accounts <ArrowRight size={12} className="ml-1" />
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Quick Findings */}
        {top_findings.length > 0 && (
          <Card data-testid="quick-findings">
            <CardHeader className="py-3 px-4">
              <CardTitle className="text-sm">Quick Findings — Top {top_findings.length} by Variance</CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-3">
              <div className="space-y-1">
                {top_findings.map((a, i) => (
                  <Link key={a.rsx_id} to={`/accounts/${a.rsx_id}`}
                        className="flex items-center gap-3 py-2 px-2 rounded hover:bg-slate-50 transition-colors"
                        data-testid={`finding-${i}`}>
                    <span className="text-xs font-medium text-slate-700 flex-1">{a.account_name}</span>
                    <VarianceBadge type={a.primary_variance_type} />
                    <span className="text-xs font-mono tabular-nums text-slate-900 font-bold">{fmt(Math.abs(a.total_variance))}</span>
                    <ArrowRight size={12} className="text-slate-400" />
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Footer disclaimers */}
        <div className="text-[10px] text-slate-400 space-y-1 pt-2">
          <p>Deferred revenue modelling is not included in this analysis.</p>
          <p>Analysis covers {fmtPct(coverage.arr_pct)} of subscription value (ARR). {total_exclusions} records excluded — see Exclusions Log.</p>
        </div>
      </div>
    </TooltipProvider>
  );
}

export function VarianceBadge({ type }) {
  const map = {
    'CLEAN': { label: 'Clean', cls: 'badge-clean' },
    'MISSING_INVOICE': { label: 'Missing Invoice', cls: 'badge-missing' },
    'UNDER_BILLED': { label: 'Under-billed', cls: 'badge-under' },
    'OVER_BILLED': { label: 'Over-billed', cls: 'badge-over' },
    'UNPAID_AR': { label: 'Unpaid AR', cls: 'badge-unpaid' },
    'UNKNOWN': { label: 'Unknown', cls: 'badge-unknown' },
  };
  const { label, cls } = map[type] || map['UNKNOWN'];
  return <Badge variant="outline" className={`text-[9px] ${cls}`} data-testid={`badge-${type}`}>{label}</Badge>;
}
