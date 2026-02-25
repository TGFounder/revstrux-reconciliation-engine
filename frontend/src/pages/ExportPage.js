import { useAppSession } from "@/App";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Download, FileText, Table2, FileWarning, FileOutput } from "lucide-react";
import { exportAccountsUrl, exportExclusionsUrl, exportReportUrl, syntheticDownloadUrl } from "@/lib/api";

const SYNTHETIC_FILES = ['accounts', 'customers', 'subscriptions', 'invoices', 'payments', 'credit_notes'];

export default function ExportPage() {
  const { sessionId } = useAppSession();
  const hasResults = !!sessionId;

  return (
    <div className="space-y-6 fade-in" data-testid="export-page">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 font-heading">Export</h1>
        <p className="text-sm text-slate-500 mt-1">Download reconciliation results and reports</p>
      </div>

      {/* Reconciliation Exports */}
      <Card>
        <CardHeader className="py-3 px-5">
          <CardTitle className="text-sm">Reconciliation Exports</CardTitle>
        </CardHeader>
        <CardContent className="px-5 pb-5 space-y-3">
          <a href={hasResults ? exportAccountsUrl(sessionId) : '#'} download>
            <Button variant="outline" className="w-full justify-start" disabled={!hasResults} data-testid="export-accounts-csv">
              <Table2 size={16} className="mr-3" />
              <div className="text-left">
                <div className="text-sm font-medium">Account Summary CSV</div>
                <div className="text-[10px] text-slate-400">All accounts with variance type, amounts, and status</div>
              </div>
              <Download size={14} className="ml-auto" />
            </Button>
          </a>

          <a href={hasResults ? exportExclusionsUrl(sessionId) : '#'} download>
            <Button variant="outline" className="w-full justify-start mt-2" disabled={!hasResults} data-testid="export-exclusions-csv">
              <FileWarning size={16} className="mr-3" />
              <div className="text-left">
                <div className="text-sm font-medium">Exclusions Log CSV</div>
                <div className="text-[10px] text-slate-400">All excluded records with reason codes and timestamps</div>
              </div>
              <Download size={14} className="ml-auto" />
            </Button>
          </a>

          <a href={hasResults ? exportReportUrl(sessionId) : '#'} download>
            <Button variant="outline" className="w-full justify-start mt-2" disabled={!hasResults} data-testid="export-pdf-report">
              <FileOutput size={16} className="mr-3" />
              <div className="text-left">
                <div className="text-sm font-medium">Score Report (PDF)</div>
                <div className="text-[10px] text-slate-400">1-page structural integrity report for CFO review</div>
              </div>
              <Download size={14} className="ml-auto" />
            </Button>
          </a>
        </CardContent>
      </Card>

      <Separator />

      {/* Synthetic Dataset */}
      <Card>
        <CardHeader className="py-3 px-5">
          <CardTitle className="text-sm flex items-center gap-2">
            Synthetic Test Dataset
            <Badge variant="outline" className="text-[9px]">60 accounts | 15 anomalies</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="px-5 pb-5">
          <p className="text-xs text-slate-500 mb-3">Download individual synthetic CSV files for testing</p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {SYNTHETIC_FILES.map(ft => (
              <a key={ft} href={syntheticDownloadUrl(ft)} download>
                <Button variant="outline" size="sm" className="w-full text-xs" data-testid={`download-synthetic-${ft}`}>
                  <FileText size={12} className="mr-2" />
                  {ft}.csv
                </Button>
              </a>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="text-[10px] text-slate-400 space-y-1">
        <p>All exports include session metadata. No data is retained beyond the session lifecycle.</p>
        <p>PDF report includes score, coverage metrics, revenue at risk breakdown, and component scores.</p>
      </div>
    </div>
  );
}
