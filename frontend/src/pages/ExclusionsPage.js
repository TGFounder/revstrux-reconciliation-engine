import { useState, useEffect } from "react";
import { useAppSession } from "@/App";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Download, Loader2, FileWarning, Filter, X } from "lucide-react";
import { getExclusions, exportExclusionsUrl } from "@/lib/api";

const REASON_LABELS = {
  'UNSUPPORTED_STRUCTURE': 'Unsupported Structure',
  'ALLOCATION_AMBIGUOUS': 'Ambiguous Allocation',
  'CREDIT_NOTE_UNALLOCATED': 'Unallocated Credit Note',
};

export default function ExclusionsPage() {
  const { sessionId } = useAppSession();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState(null);

  useEffect(() => {
    if (!sessionId) return;
    getExclusions(sessionId, filter).then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, [sessionId, filter]);

  if (loading) return <div className="flex items-center justify-center py-20"><Loader2 className="spinner text-slate-400" size={24} /></div>;
  if (!data) return <div className="text-center py-20 text-slate-400">No exclusions data available.</div>;

  const { exclusions, total, summary } = data;

  return (
    <div className="space-y-5 fade-in" data-testid="exclusions-page">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 font-heading">Exclusions Log</h1>
          <p className="text-sm text-slate-500 mt-1">Records excluded from reconciliation with reason codes</p>
        </div>
        <a href={exportExclusionsUrl(sessionId)} download>
          <Button variant="outline" size="sm" data-testid="export-exclusions-btn">
            <Download size={14} className="mr-1" /> Export CSV
          </Button>
        </a>
      </div>

      {/* Summary by reason code */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3" data-testid="exclusion-summary">
        {Object.entries(summary || {}).map(([code, count]) => (
          <Card key={code} className={`cursor-pointer transition-all ${filter === code ? 'ring-2 ring-slate-900' : 'hover:border-slate-400'}`}
                onClick={() => setFilter(filter === code ? null : code)}>
            <CardContent className="py-3 px-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-lg font-bold font-mono tabular-nums text-slate-900">{count}</div>
                  <div className="text-xs text-slate-500">{REASON_LABELS[code] || code}</div>
                </div>
                <FileWarning size={18} className="text-slate-300" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {filter && (
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs">Filtered: {REASON_LABELS[filter] || filter}</Badge>
          <Button variant="ghost" size="sm" className="text-xs" onClick={() => setFilter(null)} data-testid="clear-exclusion-filter">
            <X size={12} className="mr-1" /> Clear
          </Button>
        </div>
      )}

      {/* Exclusions table */}
      <Card>
        <CardContent className="p-0">
          {exclusions.length === 0 ? (
            <div className="text-center py-12 text-sm text-slate-400">No exclusions recorded.</div>
          ) : (
            <div className="overflow-auto">
              <Table data-testid="exclusions-table">
                <TableHeader>
                  <TableRow className="bg-slate-50">
                    <TableHead className="text-[10px] uppercase tracking-wider">Record Type</TableHead>
                    <TableHead className="text-[10px] uppercase tracking-wider">Record ID</TableHead>
                    <TableHead className="text-[10px] uppercase tracking-wider">Reason Code</TableHead>
                    <TableHead className="text-[10px] uppercase tracking-wider">Description</TableHead>
                    <TableHead className="text-[10px] uppercase tracking-wider">Excluded At</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {exclusions.map((e, i) => (
                    <TableRow key={i} data-testid={`exclusion-row-${i}`}>
                      <TableCell>
                        <Badge variant="outline" className="text-[9px]">{e.record_type}</Badge>
                      </TableCell>
                      <TableCell className="text-xs font-mono text-slate-700">{e.record_id}</TableCell>
                      <TableCell>
                        <Badge className="text-[9px] bg-slate-100 text-slate-700 hover:bg-slate-100">
                          {REASON_LABELS[e.reason_code] || e.reason_code}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-slate-600 max-w-[300px]">{e.description}</TableCell>
                      <TableCell className="text-[10px] font-mono text-slate-400">
                        {e.excluded_at ? new Date(e.excluded_at).toLocaleString() : '-'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="text-xs text-slate-400">{total} exclusion(s) total. Exclusion log is immutable and included in all exports.</div>
    </div>
  );
}
