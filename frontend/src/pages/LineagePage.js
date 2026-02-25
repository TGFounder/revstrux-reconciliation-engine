import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { useAppSession } from "@/App";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Download, ArrowLeft, Loader2, ChevronRight, Info } from "lucide-react";
import { getLineage, exportLineageUrl } from "@/lib/api";
import { VarianceBadge } from "@/pages/DashboardPage";

const fmt = (n) => '$' + Number(n || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function LineagePage() {
  const { rsxId } = useParams();
  const { sessionId } = useAppSession();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedSeg, setSelectedSeg] = useState(null);

  useEffect(() => {
    if (!sessionId || !rsxId) return;
    getLineage(sessionId, rsxId).then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, [sessionId, rsxId]);

  if (loading) return <div className="flex items-center justify-center py-20"><Loader2 className="spinner text-slate-400" size={24} /></div>;
  if (!data || data.error) return <div className="text-center py-20 text-slate-400">Lineage data not found.</div>;

  const { entity, subscriptions, subscription_data, total_expected, total_invoiced, total_variance } = data;

  return (
    <div className="space-y-5 fade-in" data-testid="lineage-page">
      {/* Breadcrumb */}
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem><BreadcrumbLink href="/dashboard">Dashboard</BreadcrumbLink></BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem><BreadcrumbLink href="/accounts">Accounts</BreadcrumbLink></BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem><span className="text-slate-900 font-medium">{entity.account_name}</span></BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {/* Entity header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 font-heading">{entity.account_name}</h1>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-xs font-mono text-slate-500">{entity.rsx_id}</span>
            <Badge variant="outline" className="text-[9px]">
              {entity.match_type === 'exact' ? 'Exact Match' : `Fuzzy ${Math.round(entity.confidence * 100)}%`}
            </Badge>
            <span className="text-xs text-slate-400">CRM: {entity.account_id} | Billing: {entity.customer_id}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <Link to="/accounts">
            <Button variant="ghost" size="sm" data-testid="back-btn"><ArrowLeft size={14} className="mr-1" /> Back</Button>
          </Link>
          <a href={exportLineageUrl(sessionId, rsxId)} download>
            <Button variant="outline" size="sm" data-testid="export-lineage-btn"><Download size={14} className="mr-1" /> Export CSV</Button>
          </a>
        </div>
      </div>

      {/* Account summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card>
          <CardContent className="py-3 px-4 text-center">
            <div className="text-lg font-bold font-mono tabular-nums">{fmt(total_expected)}</div>
            <div className="text-[10px] text-slate-500 uppercase">Expected</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-3 px-4 text-center">
            <div className="text-lg font-bold font-mono tabular-nums">{fmt(total_invoiced)}</div>
            <div className="text-[10px] text-slate-500 uppercase">Invoiced</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-3 px-4 text-center">
            <div className={`text-lg font-bold font-mono tabular-nums ${total_variance < 0 ? 'text-red-600' : total_variance > 0 ? 'text-blue-600' : 'text-emerald-600'}`}>
              {fmt(total_variance)}
            </div>
            <div className="text-[10px] text-slate-500 uppercase">Variance</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-3 px-4 text-center">
            <div className="text-lg font-bold font-mono tabular-nums">{subscriptions.length}</div>
            <div className="text-[10px] text-slate-500 uppercase">Subscriptions</div>
          </CardContent>
        </Card>
      </div>

      {/* Subscription tabs */}
      <Tabs defaultValue={subscriptions[0]} className="space-y-3">
        <TabsList data-testid="subscription-tabs">
          {subscriptions.map(sid => (
            <TabsTrigger key={sid} value={sid} className="text-xs font-mono">{sid}</TabsTrigger>
          ))}
        </TabsList>

        {subscriptions.map(sid => {
          const subData = subscription_data[sid];
          if (!subData) return null;
          return (
            <TabsContent key={sid} value={sid}>
              {/* Sub summary */}
              <div className="flex gap-4 mb-3 text-xs text-slate-500">
                <span>Expected: <strong className="text-slate-800">{fmt(subData.total_expected)}</strong></span>
                <span>Invoiced: <strong className="text-slate-800">{fmt(subData.total_invoiced)}</strong></span>
                <span>Credits: <strong className="text-slate-800">{fmt(subData.total_credit_notes)}</strong></span>
                <span>Collected: <strong className="text-slate-800">{fmt(subData.total_collected)}</strong></span>
                <span className={subData.total_variance < 0 ? 'text-red-600 font-bold' : subData.total_variance > 0 ? 'text-blue-600 font-bold' : ''}>
                  Variance: <strong>{fmt(subData.total_variance)}</strong>
                </span>
              </div>

              {/* Segment table */}
              <Card>
                <CardContent className="p-0">
                  <div className="overflow-auto">
                    <Table data-testid={`lineage-table-${sid}`}>
                      <TableHeader>
                        <TableRow className="bg-slate-50">
                          <TableHead className="text-[10px] uppercase tracking-wider">Period</TableHead>
                          <TableHead className="text-[10px] uppercase tracking-wider text-right">MRR</TableHead>
                          <TableHead className="text-[10px] uppercase tracking-wider text-right">Days</TableHead>
                          <TableHead className="text-[10px] uppercase tracking-wider text-right">Expected</TableHead>
                          <TableHead className="text-[10px] uppercase tracking-wider text-right">Invoiced</TableHead>
                          <TableHead className="text-[10px] uppercase tracking-wider text-right">Credits</TableHead>
                          <TableHead className="text-[10px] uppercase tracking-wider text-right">Collected</TableHead>
                          <TableHead className="text-[10px] uppercase tracking-wider text-right">Variance</TableHead>
                          <TableHead className="text-[10px] uppercase tracking-wider">Status</TableHead>
                          <TableHead className="w-8" />
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {subData.segments.map((seg, i) => (
                          <TableRow key={i} className={`hover:bg-slate-50 cursor-pointer ${seg.status !== 'CLEAN' ? 'bg-amber-50/30' : ''}`}
                                    onClick={() => setSelectedSeg(seg)} data-testid={`seg-row-${i}`}>
                            <TableCell className="text-xs font-mono">{seg.period}</TableCell>
                            <TableCell className="text-xs font-mono tabular-nums text-right">{fmt(seg.mrr)}</TableCell>
                            <TableCell className="text-xs font-mono tabular-nums text-right">
                              {seg.days_active}/{seg.total_days}
                              {seg.is_prorated && <Badge variant="outline" className="ml-1 text-[8px]">Prorated</Badge>}
                            </TableCell>
                            <TableCell className="text-xs font-mono tabular-nums text-right">{fmt(seg.expected_amount)}</TableCell>
                            <TableCell className="text-xs font-mono tabular-nums text-right">{fmt(seg.invoiced_amount)}</TableCell>
                            <TableCell className="text-xs font-mono tabular-nums text-right">{fmt(seg.credit_notes_amount)}</TableCell>
                            <TableCell className="text-xs font-mono tabular-nums text-right">{fmt(seg.collected_amount)}</TableCell>
                            <TableCell className={`text-xs font-mono tabular-nums text-right font-bold ${seg.variance < 0 ? 'text-red-600' : seg.variance > 0 ? 'text-blue-600' : ''}`}>
                              {fmt(seg.variance)}
                            </TableCell>
                            <TableCell><VarianceBadge type={seg.status} /></TableCell>
                            <TableCell><Info size={12} className="text-slate-300" /></TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          );
        })}
      </Tabs>

      {/* Drilldown drawer */}
      <Dialog open={!!selectedSeg} onOpenChange={() => setSelectedSeg(null)}>
        <DialogContent className="max-w-lg" data-testid="drilldown-dialog">
          <DialogHeader>
            <DialogTitle className="text-base">Segment Detail — {selectedSeg?.period}</DialogTitle>
          </DialogHeader>
          {selectedSeg && (
            <div className="space-y-4">
              {/* Calculation steps */}
              <div className="p-3 bg-slate-50 rounded-md font-mono text-xs space-y-1">
                <div className="text-slate-600">MRR = {fmt(selectedSeg.mrr)}</div>
                <div className="text-slate-600">Active Days = {selectedSeg.days_active} / {selectedSeg.total_days}</div>
                {selectedSeg.is_prorated ? (
                  <div className="text-blue-700 font-bold">
                    Prorated Expected = ({selectedSeg.days_active} / {selectedSeg.total_days}) x {fmt(selectedSeg.mrr)} = {fmt(selectedSeg.expected_amount)}
                  </div>
                ) : (
                  <div className="text-slate-800 font-bold">Expected = {fmt(selectedSeg.expected_amount)}</div>
                )}
                <Separator />
                <div className="text-slate-600">Invoiced = {fmt(selectedSeg.invoiced_amount)}</div>
                <div className="text-slate-600">Credit Notes = {fmt(selectedSeg.credit_notes_amount)}</div>
                <div className="text-slate-600">Effective Invoiced = {fmt(selectedSeg.effective_invoiced)}</div>
                <Separator />
                <div className={`font-bold ${Math.abs(selectedSeg.variance) <= 1 ? 'text-emerald-700' : selectedSeg.variance < 0 ? 'text-red-700' : 'text-blue-700'}`}>
                  Variance = {fmt(selectedSeg.effective_invoiced)} - {fmt(selectedSeg.expected_amount)} = {fmt(selectedSeg.variance)}
                </div>
                <div className="text-slate-500">Tolerance: $1.00</div>
              </div>

              {/* Invoices */}
              {selectedSeg.invoices?.length > 0 && (
                <div>
                  <div className="text-xs font-medium text-slate-600 mb-2">Invoices</div>
                  <div className="space-y-1">
                    {selectedSeg.invoices.map((inv, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs p-2 bg-slate-50 rounded">
                        <span className="font-mono text-slate-500">{inv.invoice_id}</span>
                        <span className="text-slate-400">{inv.invoice_date}</span>
                        <span className="font-mono tabular-nums ml-auto">{fmt(inv.allocated_amount)}</span>
                        <Badge variant="outline" className="text-[8px]">{inv.invoice_status}</Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Credit notes */}
              {selectedSeg.credit_notes?.length > 0 && (
                <div>
                  <div className="text-xs font-medium text-slate-600 mb-2">Credit Notes</div>
                  <div className="space-y-1">
                    {selectedSeg.credit_notes.map((cn, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs p-2 bg-amber-50 rounded">
                        <span className="font-mono text-slate-500">{cn.credit_note_id}</span>
                        <span className="text-slate-400">{cn.reason}</span>
                        <span className="font-mono tabular-nums ml-auto text-amber-700">-{fmt(cn.amount)}</span>
                        {cn.linked_invoice && <span className="text-[10px] text-slate-400">via {cn.linked_invoice}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="text-[10px] text-slate-400">All calculations are deterministic. No AI or ML is used.</div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
