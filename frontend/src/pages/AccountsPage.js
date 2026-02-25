import { useState, useEffect, useMemo } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { useAppSession } from "@/App";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { ArrowUpDown, Search, Download, X, Filter, Loader2, Info, ArrowRight } from "lucide-react";
import { getAccounts, exportAccountsUrl } from "@/lib/api";
import { VarianceBadge } from "@/pages/DashboardPage";

const fmt = (n) => '$' + Number(n || 0).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });

const VARIANCE_TYPES = ['CLEAN', 'MISSING_INVOICE', 'UNDER_BILLED', 'OVER_BILLED', 'UNPAID_AR', 'UNKNOWN'];

const VARIANCE_TOOLTIPS = {
  'CLEAN': 'Within $1.00 tolerance. No action needed.',
  'MISSING_INVOICE': 'Subscription active but no invoice found for this period.',
  'UNDER_BILLED': 'Invoice raised for less than expected amount.',
  'OVER_BILLED': 'Invoice raised for more than expected amount.',
  'UNPAID_AR': 'Invoice raised correctly but payment not received.',
  'UNKNOWN': 'No billing match exists for this account.'
};

export default function AccountsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { sessionId } = useAppSession();
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState([]);
  const [sortBy, setSortBy] = useState('total_variance');
  const [sortDir, setSortDir] = useState('desc');
  const [showLegend, setShowLegend] = useState(false);

  useEffect(() => {
    if (!sessionId) return;
    const cFilter = searchParams.get('component_filter');
    const params = {};
    if (cFilter) params.component_filter = cFilter;
    if (filters.length) params.variance_type = filters.join(',');
    if (search) params.search = search;
    params.sort_by = sortBy;
    params.sort_dir = sortDir;
    setLoading(true);
    getAccounts(sessionId, params).then(d => { setAccounts(d.accounts || []); setLoading(false); }).catch(() => setLoading(false));
  }, [sessionId, filters, search, sortBy, sortDir, searchParams]);

  const toggleFilter = (type) => {
    setFilters(prev => prev.includes(type) ? prev.filter(f => f !== type) : [...prev, type]);
  };

  const handleSort = (col) => {
    if (sortBy === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortBy(col); setSortDir('desc'); }
  };

  const componentFilter = searchParams.get('component_filter');

  return (
    <TooltipProvider>
      <div className="space-y-4 fade-in" data-testid="accounts-page">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 font-heading">Account Table</h1>
            {componentFilter && (
              <div className="flex items-center gap-2 mt-1">
                <Badge variant="outline" className="text-xs">Filtered by: {componentFilter.replace('_', ' ')}</Badge>
                <Link to="/accounts" className="text-xs text-blue-600 hover:underline">Clear filter</Link>
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowLegend(true)} data-testid="legend-btn">
              <Info size={14} className="mr-1" /> Legend
            </Button>
            <a href={exportAccountsUrl(sessionId, filters.join(','))} download>
              <Button variant="outline" size="sm" disabled={accounts.length === 0} data-testid="export-accounts-btn">
                <Download size={14} className="mr-1" /> Export CSV
              </Button>
            </a>
          </div>
        </div>

        {/* Search + filters */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-2.5 text-slate-400" />
            <Input placeholder="Search accounts..." value={search} onChange={e => setSearch(e.target.value)}
                   className="pl-8 h-9 w-64 text-xs" data-testid="search-accounts" />
          </div>
          <div className="flex gap-1 flex-wrap">
            {VARIANCE_TYPES.map(t => (
              <Badge key={t} variant={filters.includes(t) ? 'default' : 'outline'}
                     className={`cursor-pointer text-[10px] ${filters.includes(t) ? '' : 'hover:bg-slate-50'}`}
                     onClick={() => toggleFilter(t)} data-testid={`filter-${t}`}>
                {t.replace('_', ' ')}
                {filters.includes(t) && <X size={10} className="ml-1" />}
              </Badge>
            ))}
          </div>
          {filters.length > 0 && (
            <Button variant="ghost" size="sm" className="text-xs" onClick={() => setFilters([])} data-testid="clear-filters-btn">
              Clear all
            </Button>
          )}
        </div>

        {/* Table */}
        <Card>
          <CardContent className="p-0">
            {loading ? (
              <div className="flex items-center justify-center py-12"><Loader2 className="spinner text-slate-400" size={20} /></div>
            ) : accounts.length === 0 ? (
              <div className="text-center py-12 text-sm text-slate-400">No accounts match your search. Try a different name or clear filters.</div>
            ) : (
              <div className="overflow-auto">
                <Table data-testid="accounts-table">
                  <TableHeader>
                    <TableRow className="bg-slate-50">
                      {[
                        { key: 'account_name', label: 'Account' },
                        { key: 'match_type', label: 'Match' },
                        { key: 'subscriptions', label: 'Subs' },
                        { key: 'periods', label: 'Periods' },
                        { key: 'expected_total', label: 'Expected' },
                        { key: 'invoiced_total', label: 'Invoiced' },
                        { key: 'credit_notes_total', label: 'Credits' },
                        { key: 'total_variance', label: 'Variance' },
                        { key: 'primary_variance_type', label: 'Status' },
                      ].map(col => (
                        <TableHead key={col.key} className="text-[10px] uppercase tracking-wider cursor-pointer hover:bg-slate-100"
                                   onClick={() => handleSort(col.key)}>
                          <span className="flex items-center gap-1">
                            {col.label}
                            {sortBy === col.key && <ArrowUpDown size={10} />}
                          </span>
                        </TableHead>
                      ))}
                      <TableHead className="w-8" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {accounts.map((a, i) => (
                      <TableRow key={a.rsx_id} className="hover:bg-slate-50 cursor-pointer"
                                onClick={() => a.match_type !== 'unmatched' && navigate(`/accounts/${a.rsx_id}`)}
                                data-testid={`account-row-${i}`}>
                        <TableCell className="text-xs font-medium text-slate-800 max-w-[200px] truncate">{a.account_name}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-[9px]">
                            {a.match_type === 'exact' ? 'Exact' : a.match_type === 'fuzzy_confirmed' ? `Fuzzy ${Math.round(a.confidence * 100)}%` : a.match_type}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs font-mono tabular-nums text-right">{a.subscriptions}</TableCell>
                        <TableCell className="text-xs font-mono tabular-nums text-right">{a.periods}</TableCell>
                        <TableCell className="text-xs font-mono tabular-nums text-right">{fmt(a.expected_total)}</TableCell>
                        <TableCell className="text-xs font-mono tabular-nums text-right">{fmt(a.invoiced_total)}</TableCell>
                        <TableCell className="text-xs font-mono tabular-nums text-right">{fmt(a.credit_notes_total)}</TableCell>
                        <TableCell className={`text-xs font-mono tabular-nums text-right font-bold ${a.total_variance < 0 ? 'text-red-600' : a.total_variance > 0 ? 'text-blue-600' : 'text-slate-600'}`}>
                          {fmt(a.total_variance)}
                        </TableCell>
                        <TableCell><VarianceBadge type={a.primary_variance_type} /></TableCell>
                        <TableCell>{a.match_type !== 'unmatched' && <ArrowRight size={12} className="text-slate-300" />}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="text-xs text-slate-400">{accounts.length} account(s) shown</div>

        {/* Legend dialog */}
        <Dialog open={showLegend} onOpenChange={setShowLegend}>
          <DialogContent data-testid="legend-dialog">
            <DialogHeader><DialogTitle>Variance Type Legend</DialogTitle></DialogHeader>
            <div className="space-y-3">
              {Object.entries(VARIANCE_TOOLTIPS).map(([type, desc]) => (
                <div key={type} className="flex items-start gap-3">
                  <VarianceBadge type={type} />
                  <p className="text-sm text-slate-600">{desc}</p>
                </div>
              ))}
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </TooltipProvider>
  );
}
