"""
RevStrux Reconciliation Engine v1.1
Deterministic, rule-based revenue reconciliation.
No AI, no ML, no probabilistic logic.
"""
import re
import uuid
import json
import io
import csv
from datetime import date, datetime, timedelta, timezone
from calendar import monthrange
from difflib import SequenceMatcher
from collections import defaultdict

# =============================================================================
# CONSTANTS
# =============================================================================
SUFFIXES = ['inc', 'incorporated', 'ltd', 'limited', 'corp', 'corporation',
            'pvt', 'private', 'llc', 'plc', 'gmbh', 'sas', 'bv', 'ag', 'co', 'company']

VALID_CURRENCIES = ['USD','GBP','EUR','INR','AUD','CAD','SGD','AED','JPY','CHF','HKD','NZD','SEK','NOK','DKK','ZAR']
VALID_ACCOUNT_STATUSES = ['active', 'churned', 'prospect']
VALID_CUSTOMER_STATUSES = ['active', 'cancelled', 'paused']
VALID_SUB_STATUSES = ['active', 'cancelled', 'paused', 'expired']
VALID_BILLING_FREQ = ['monthly', 'quarterly', 'annual']
VALID_PRICING_MODELS = ['flat', 'ramp', 'usage']
VALID_INVOICE_STATUSES = ['paid', 'unpaid', 'void', 'draft']

TOLERANCE = 1.00
WEIGHTS = {'entity_match': 0.25, 'billing_coverage': 0.35, 'variance': 0.25, 'lineage': 0.15}

REQUIRED_FIELDS = {
    'accounts': ['account_id', 'account_name', 'account_status', 'source_system'],
    'customers': ['customer_id', 'customer_name', 'customer_status', 'source_system'],
    'subscriptions': ['sub_id', 'customer_id', 'start_date', 'mrr', 'currency', 'billing_frequency', 'pricing_model', 'sub_status'],
    'invoices': ['invoice_id', 'customer_id', 'invoice_date', 'period_start', 'period_end', 'amount', 'currency', 'status'],
    'payments': ['payment_id', 'invoice_id', 'payment_date', 'amount', 'currency'],
    'credit_notes': ['credit_note_id', 'customer_id', 'issue_date', 'amount', 'currency']
}

ID_FIELDS = {
    'accounts': 'account_id', 'customers': 'customer_id', 'subscriptions': 'sub_id',
    'invoices': 'invoice_id', 'payments': 'payment_id', 'credit_notes': 'credit_note_id'
}

# =============================================================================
# HELPERS
# =============================================================================
def r2(v):
    return round(float(v), 2)

def normalize(name):
    if not name:
        return ""
    n = re.sub(r'[.,;:!?]', '', str(name).lower().strip())
    for s in SUFFIXES:
        n = re.sub(r'\b' + s + r'\.?\b', '', n).strip()
    return re.sub(r'\s+', ' ', n).strip()

def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def parse_date(s):
    if not s or str(s).strip() == '':
        return None
    if isinstance(s, date) and not isinstance(s, datetime):
        return s
    if isinstance(s, datetime):
        return s.date()
    try:
        return datetime.strptime(str(s).strip(), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None

def month_range(start_ym, end_ym):
    sy, sm = map(int, start_ym.split('-'))
    ey, em = map(int, end_ym.split('-'))
    result = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        result.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return result

def now_iso():
    return datetime.now(timezone.utc).isoformat()

# =============================================================================
# CSV VALIDATION
# =============================================================================
def validate_csv(file_type, rows):
    errors, warnings = [], []
    if file_type not in REQUIRED_FIELDS:
        errors.append({'file': file_type, 'row': 0, 'field': '', 'message': f'Unknown file type: {file_type}'})
        return {'valid': False, 'errors': errors, 'warnings': warnings}

    required = REQUIRED_FIELDS[file_type]
    if not rows:
        if file_type == 'credit_notes':
            warnings.append({'file': file_type, 'row': 0, 'field': '', 'message': 'No data rows. Credit note analysis will be skipped.'})
            return {'valid': True, 'errors': errors, 'warnings': warnings}
        errors.append({'file': file_type, 'row': 0, 'field': '', 'message': 'No data rows found.'})
        return {'valid': False, 'errors': errors, 'warnings': warnings}

    # Check headers
    headers = set(rows[0].keys())
    for f in required:
        if f not in headers:
            errors.append({'file': file_type, 'row': 0, 'field': f, 'message': f'Missing required column: {f}'})

    seen_ids = set()
    pk = ID_FIELDS.get(file_type)

    for i, row in enumerate(rows):
        rn = i + 2
        # Required fields
        for f in required:
            if f in headers and (row.get(f) is None or str(row.get(f, '')).strip() == ''):
                errors.append({'file': file_type, 'row': rn, 'field': f, 'message': f'Missing required field: {f}'})

        # Unique IDs
        if pk and row.get(pk):
            if row[pk] in seen_ids:
                errors.append({'file': file_type, 'row': rn, 'field': pk, 'message': f'Duplicate {pk}: {row[pk]}'})
            seen_ids.add(row[pk])

        # Type validations
        if file_type == 'accounts' and row.get('account_status') and row['account_status'] not in VALID_ACCOUNT_STATUSES:
            errors.append({'file': file_type, 'row': rn, 'field': 'account_status', 'message': f"Invalid value '{row['account_status']}'. Allowed: {', '.join(VALID_ACCOUNT_STATUSES)}"})

        elif file_type == 'customers' and row.get('customer_status') and row['customer_status'] not in VALID_CUSTOMER_STATUSES:
            errors.append({'file': file_type, 'row': rn, 'field': 'customer_status', 'message': f"Invalid value '{row['customer_status']}'. Allowed: {', '.join(VALID_CUSTOMER_STATUSES)}"})

        elif file_type == 'subscriptions':
            if row.get('sub_status') and row['sub_status'] not in VALID_SUB_STATUSES:
                errors.append({'file': file_type, 'row': rn, 'field': 'sub_status', 'message': f"Invalid value. Allowed: {', '.join(VALID_SUB_STATUSES)}"})
            if row.get('billing_frequency') and row['billing_frequency'] not in VALID_BILLING_FREQ:
                errors.append({'file': file_type, 'row': rn, 'field': 'billing_frequency', 'message': f"Invalid value. Allowed: {', '.join(VALID_BILLING_FREQ)}"})
            if row.get('pricing_model') and row['pricing_model'] not in VALID_PRICING_MODELS:
                errors.append({'file': file_type, 'row': rn, 'field': 'pricing_model', 'message': f"Invalid value. Allowed: {', '.join(VALID_PRICING_MODELS)}"})
            sd = parse_date(row.get('start_date'))
            if row.get('start_date') and sd is None:
                errors.append({'file': file_type, 'row': rn, 'field': 'start_date', 'message': 'Invalid date format. Use YYYY-MM-DD'})
            ed = parse_date(row.get('end_date'))
            if row.get('end_date') and str(row['end_date']).strip() and ed is None:
                errors.append({'file': file_type, 'row': rn, 'field': 'end_date', 'message': 'Invalid date format. Use YYYY-MM-DD'})
            if sd and ed and ed <= sd:
                errors.append({'file': file_type, 'row': rn, 'field': 'end_date', 'message': 'end_date must be after start_date'})
            try:
                mrr = float(row.get('mrr', 0))
                if mrr < 0:
                    errors.append({'file': file_type, 'row': rn, 'field': 'mrr', 'message': 'MRR must be positive'})
            except (ValueError, TypeError):
                errors.append({'file': file_type, 'row': rn, 'field': 'mrr', 'message': 'Invalid amount format'})

        elif file_type == 'invoices':
            if row.get('status') and row['status'] not in VALID_INVOICE_STATUSES:
                errors.append({'file': file_type, 'row': rn, 'field': 'status', 'message': f"Invalid value. Allowed: {', '.join(VALID_INVOICE_STATUSES)}"})
            for df in ['invoice_date', 'period_start', 'period_end']:
                if row.get(df) and parse_date(row[df]) is None:
                    errors.append({'file': file_type, 'row': rn, 'field': df, 'message': 'Invalid date format. Use YYYY-MM-DD'})
            ps, pe = parse_date(row.get('period_start')), parse_date(row.get('period_end'))
            if ps and pe and pe <= ps:
                errors.append({'file': file_type, 'row': rn, 'field': 'period_end', 'message': 'period_end must be after period_start'})

        elif file_type == 'credit_notes':
            if row.get('issue_date') and parse_date(row['issue_date']) is None:
                errors.append({'file': file_type, 'row': rn, 'field': 'issue_date', 'message': 'Invalid date format. Use YYYY-MM-DD'})
            try:
                amt = float(row.get('amount', 0))
                if amt <= 0:
                    errors.append({'file': file_type, 'row': rn, 'field': 'amount', 'message': 'Credit note amount must be a positive number'})
            except (ValueError, TypeError):
                errors.append({'file': file_type, 'row': rn, 'field': 'amount', 'message': 'Invalid amount format'})

        # Amount validation for invoices/payments
        if file_type in ['invoices', 'payments']:
            try:
                float(row.get('amount', 0))
            except (ValueError, TypeError):
                errors.append({'file': file_type, 'row': rn, 'field': 'amount', 'message': 'Invalid amount format'})

        # Currency
        if 'currency' in row and row.get('currency') and row['currency'] not in VALID_CURRENCIES:
            errors.append({'file': file_type, 'row': rn, 'field': 'currency', 'message': f"Invalid currency code: {row['currency']}"})

        if len(errors) >= 500:
            errors.append({'file': '', 'row': 0, 'field': '', 'message': 'Showing first 500 errors. Fix these and re-validate.'})
            break

    return {'valid': len(errors) == 0, 'errors': errors, 'warnings': warnings}

# =============================================================================
# IDENTITY MATCHING (3-Pass)
# =============================================================================
def run_identity_matching(accounts, customers):
    auto, review = [], []
    matched_aids, matched_cids = set(), set()
    anorm = {a['account_id']: normalize(a['account_name']) for a in accounts}
    cnorm = {c['customer_id']: normalize(c['customer_name']) for c in customers}

    # Pass 1: Exact
    for a in accounts:
        if a.get('account_status') == 'prospect':
            continue
        an = anorm[a['account_id']]
        if not an:
            continue
        for c in customers:
            cn = cnorm[c['customer_id']]
            if an == cn and a['account_id'] not in matched_aids and c['customer_id'] not in matched_cids:
                auto.append({
                    'rsx_id': f"RSX-{uuid.uuid4().hex[:5].upper()}",
                    'account_id': a['account_id'], 'account_name': a['account_name'],
                    'customer_id': c['customer_id'], 'customer_name': c['customer_name'],
                    'confidence': 1.0, 'match_type': 'exact',
                    'source_account': a.get('source_system', ''), 'source_customer': c.get('source_system', '')
                })
                matched_aids.add(a['account_id'])
                matched_cids.add(c['customer_id'])
                break

    # Pass 2: Fuzzy
    for a in accounts:
        if a['account_id'] in matched_aids or a.get('account_status') == 'prospect':
            continue
        an = anorm[a['account_id']]
        if not an:
            continue
        best, best_r = None, 0
        for c in customers:
            if c['customer_id'] in matched_cids:
                continue
            r = similarity(an, cnorm[c['customer_id']])
            if r > best_r:
                best, best_r = c, r
        if best and best_r >= 0.70:
            review.append({
                'match_id': uuid.uuid4().hex[:8],
                'account_id': a['account_id'], 'account_name': a['account_name'],
                'customer_id': best['customer_id'], 'customer_name': best['customer_name'],
                'confidence': r2(best_r), 'match_type': 'fuzzy',
                'source_account': a.get('source_system', ''), 'source_customer': best.get('source_system', ''),
                'status': 'pending'
            })
            matched_aids.add(a['account_id'])
            matched_cids.add(best['customer_id'])

    review_aids = {m['account_id'] for m in review}
    review_cids = {m['customer_id'] for m in review}
    unmatched_a = [a for a in accounts if a['account_id'] not in matched_aids and a['account_id'] not in review_aids and a.get('account_status') != 'prospect']
    unmatched_c = [c for c in customers if c['customer_id'] not in matched_cids and c['customer_id'] not in review_cids]
    prospects = [a for a in accounts if a.get('account_status') == 'prospect']

    return {
        'auto_matched': auto, 'needs_review': review,
        'unmatched_accounts': unmatched_a, 'unmatched_customers': unmatched_c,
        'prospects': prospects
    }

# =============================================================================
# BUILD RSX ENTITIES
# =============================================================================
def build_rsx_entities(identity_result, decisions):
    entities = list(identity_result['auto_matched'])
    for match in identity_result['needs_review']:
        dec = next((d for d in decisions if d['match_id'] == match['match_id']), None)
        if dec and dec['decision'] == 'confirmed':
            entities.append({
                'rsx_id': f"RSX-{uuid.uuid4().hex[:5].upper()}",
                'account_id': match['account_id'], 'account_name': match['account_name'],
                'customer_id': match['customer_id'], 'customer_name': match['customer_name'],
                'confidence': match['confidence'], 'match_type': 'fuzzy_confirmed',
                'source_account': match.get('source_account', ''), 'source_customer': match.get('source_customer', '')
            })
    return entities

# =============================================================================
# REVENUE SEGMENT GENERATION
# =============================================================================
def generate_segments(subscriptions, rsx_entities, period_start, period_end):
    segments, exclusions = [], []
    cid_to_rsx = {e['customer_id']: e for e in rsx_entities}
    months = month_range(period_start, period_end)

    for sub in subscriptions:
        if sub.get('pricing_model') == 'usage':
            exclusions.append({
                'record_type': 'subscription', 'record_id': sub['sub_id'],
                'reason_code': 'UNSUPPORTED_STRUCTURE',
                'description': f"Usage-based subscription excluded. Only flat and ramp supported.",
                'excluded_at': now_iso()
            })
            continue

        rsx = cid_to_rsx.get(sub['customer_id'])
        if not rsx:
            continue

        sub_start = parse_date(sub['start_date'])
        sub_end = parse_date(sub.get('end_date')) if sub.get('end_date') and str(sub.get('end_date', '')).strip() else None
        mrr = float(sub.get('mrr', 0))
        if not sub_start:
            continue

        ramp_schedule = None
        if sub.get('pricing_model') == 'ramp' and sub.get('ramp_schedule'):
            try:
                ramp_schedule = json.loads(sub['ramp_schedule']) if isinstance(sub['ramp_schedule'], str) else sub['ramp_schedule']
            except Exception:
                ramp_schedule = None

        for y, m in months:
            ms = date(y, m, 1)
            me = date(y, m, monthrange(y, m)[1])
            if sub_start > me:
                continue
            if sub_end and sub_end < ms:
                continue
            if sub.get('sub_status') in ['cancelled', 'expired'] and sub_end and sub_end < ms:
                continue

            active_start = max(sub_start, ms)
            active_end = min(sub_end, me) if sub_end else me
            days_active = (active_end - active_start).days + 1
            total_days = monthrange(y, m)[1]

            month_mrr = mrr
            if ramp_schedule:
                for stage in ramp_schedule:
                    ss = parse_date(stage.get('stage_start'))
                    se = parse_date(stage.get('stage_end'))
                    if ss and se and ss <= ms <= se:
                        month_mrr = float(stage.get('mrr', mrr))
                        break

            is_prorated = days_active < total_days
            expected = r2((days_active / total_days) * month_mrr) if is_prorated else r2(month_mrr)

            segments.append({
                'rsx_id': rsx['rsx_id'], 'sub_id': sub['sub_id'],
                'customer_id': sub['customer_id'], 'period': f"{y:04d}-{m:02d}",
                'expected_amount': expected, 'mrr': r2(month_mrr),
                'days_active': days_active, 'total_days': total_days,
                'is_prorated': is_prorated, 'currency': sub.get('currency', 'USD'),
                'billing_frequency': sub.get('billing_frequency', 'monthly')
            })

    return {'segments': segments, 'exclusions': exclusions}

# =============================================================================
# INVOICE MATCHING (Period Overlap)
# =============================================================================
def match_invoices(invoices, segments, rsx_entities):
    allocations, exclusions = [], []
    cid_to_rsx = {e['customer_id']: e for e in rsx_entities}
    seg_by_rsx = defaultdict(list)
    for s in segments:
        seg_by_rsx[s['rsx_id']].append(s)

    for inv in invoices:
        if inv.get('status') == 'void':
            continue
        rsx = cid_to_rsx.get(inv['customer_id'])
        if not rsx:
            continue
        inv_start = parse_date(inv.get('period_start'))
        inv_end = parse_date(inv.get('period_end'))
        inv_amount = float(inv.get('amount', 0))
        if not inv_start or not inv_end:
            continue
        total_inv_days = (inv_end - inv_start).days + 1
        if total_inv_days <= 0:
            continue

        entity_segs = seg_by_rsx.get(rsx['rsx_id'], [])
        target_segs = entity_segs
        if inv.get('sub_id') and str(inv['sub_id']).strip():
            filtered = [s for s in entity_segs if s['sub_id'] == inv['sub_id']]
            if filtered:
                target_segs = filtered

        matched_any = False
        for seg in target_segs:
            y, m = map(int, seg['period'].split('-'))
            ms = date(y, m, 1)
            me = date(y, m, monthrange(y, m)[1])
            os_date = max(inv_start, ms)
            oe_date = min(inv_end, me)
            if os_date <= oe_date:
                overlap = (oe_date - os_date).days + 1
                allocated = r2(inv_amount * (overlap / total_inv_days))
                allocations.append({
                    'invoice_id': inv['invoice_id'], 'rsx_id': rsx['rsx_id'],
                    'sub_id': seg['sub_id'], 'period': seg['period'],
                    'allocated_amount': allocated, 'overlap_days': overlap,
                    'total_inv_days': total_inv_days, 'invoice_amount': inv_amount,
                    'invoice_date': str(inv.get('invoice_date', '')),
                    'invoice_status': inv.get('status', ''), 'currency': inv.get('currency', 'USD')
                })
                matched_any = True

        if not inv.get('sub_id') and matched_any:
            periods = set(a['period'] for a in allocations if a['invoice_id'] == inv['invoice_id'])
            for period in periods:
                matching = [s for s in entity_segs if s['period'] == period]
                if len(matching) > 1:
                    exclusions.append({
                        'record_type': 'invoice', 'record_id': inv['invoice_id'],
                        'reason_code': 'ALLOCATION_AMBIGUOUS',
                        'description': f"Invoice {inv['invoice_id']} has no sub_id and multiple segments exist for {period}.",
                        'excluded_at': now_iso()
                    })
                    break

    return {'allocations': allocations, 'exclusions': exclusions}

# =============================================================================
# RECONCILIATION
# =============================================================================
def reconcile(segments, allocations, payments, credit_notes, rsx_entities):
    results, exclusions = [], []
    payment_by_inv = defaultdict(float)
    for p in payments:
        payment_by_inv[p['invoice_id']] += float(p.get('amount', 0))

    cn_by_inv = defaultdict(list)
    cn_standalone = defaultdict(list)
    cid_to_rsx = {e['customer_id']: e for e in rsx_entities}

    for cn in credit_notes:
        if cn.get('invoice_id') and str(cn['invoice_id']).strip():
            cn_by_inv[cn['invoice_id']].append(cn)
        else:
            issue_date = parse_date(cn.get('issue_date'))
            if issue_date:
                period = f"{issue_date.year:04d}-{issue_date.month:02d}"
                rsx = cid_to_rsx.get(cn['customer_id'])
                if rsx:
                    cn_standalone[(rsx['rsx_id'], period)].append(cn)
                else:
                    exclusions.append({
                        'record_type': 'credit_note', 'record_id': cn['credit_note_id'],
                        'reason_code': 'CREDIT_NOTE_UNALLOCATED',
                        'description': f"Credit note for unmatched customer {cn['customer_id']}.",
                        'excluded_at': now_iso()
                    })

    alloc_by_seg = defaultdict(list)
    for a in allocations:
        alloc_by_seg[(a['rsx_id'], a['sub_id'], a['period'])].append(a)

    for seg in segments:
        key = (seg['rsx_id'], seg['sub_id'], seg['period'])
        seg_allocs = alloc_by_seg.get(key, [])

        invoiced = r2(sum(a['allocated_amount'] for a in seg_allocs))
        credit_total = 0.0
        cn_applied = []

        for a in seg_allocs:
            for cn in cn_by_inv.get(a['invoice_id'], []):
                amt = float(cn.get('amount', 0))
                # Proportionally allocate credit note to this segment
                if a['invoice_amount'] > 0:
                    proportion = a['allocated_amount'] / a['invoice_amount']
                else:
                    proportion = 1.0
                seg_cn_amt = r2(amt * proportion)
                credit_total += seg_cn_amt
                cn_applied.append({
                    'credit_note_id': cn['credit_note_id'], 'amount': seg_cn_amt,
                    'reason': cn.get('reason', ''), 'issue_date': str(cn.get('issue_date', '')),
                    'linked_invoice': a['invoice_id']
                })

        standalone = cn_standalone.get((seg['rsx_id'], seg['period']), [])
        for cn in standalone:
            amt = float(cn.get('amount', 0))
            if invoiced > 0:
                credit_total += amt
                cn_applied.append({
                    'credit_note_id': cn['credit_note_id'], 'amount': amt,
                    'reason': cn.get('reason', ''), 'issue_date': str(cn.get('issue_date', '')),
                    'linked_invoice': None
                })
            else:
                exclusions.append({
                    'record_type': 'credit_note', 'record_id': cn['credit_note_id'],
                    'reason_code': 'CREDIT_NOTE_UNALLOCATED',
                    'description': f"No invoice for customer in {seg['period']}.",
                    'excluded_at': now_iso()
                })

        collected = 0.0
        for a in seg_allocs:
            paid = payment_by_inv.get(a['invoice_id'], 0)
            inv_total = float(a.get('invoice_amount', 0))
            if inv_total > 0:
                collected += r2(paid * (a['allocated_amount'] / inv_total))

        effective_invoiced = r2(invoiced - credit_total)
        variance = r2(effective_invoiced - seg['expected_amount'])

        if invoiced == 0 and not seg_allocs:
            status = 'MISSING_INVOICE'
        elif abs(variance) <= TOLERANCE:
            status = 'CLEAN'
        elif variance < -TOLERANCE:
            status = 'UNDER_BILLED'
        elif variance > TOLERANCE:
            status = 'OVER_BILLED'
        else:
            status = 'CLEAN'

        has_unpaid = False
        if invoiced > 0 and collected < invoiced * 0.99:
            has_unpaid = True
            inv_statuses = set(a.get('invoice_status', '') for a in seg_allocs)
            if 'unpaid' in inv_statuses and status == 'CLEAN':
                status = 'UNPAID_AR'

        results.append({
            'rsx_id': seg['rsx_id'], 'sub_id': seg['sub_id'], 'period': seg['period'],
            'expected_amount': seg['expected_amount'], 'invoiced_amount': invoiced,
            'credit_notes_amount': r2(credit_total), 'effective_invoiced': effective_invoiced,
            'collected_amount': r2(collected), 'variance': variance,
            'abs_variance': abs(variance), 'status': status, 'has_unpaid_ar': has_unpaid,
            'is_prorated': seg.get('is_prorated', False), 'mrr': seg.get('mrr', 0),
            'days_active': seg.get('days_active', 0), 'total_days': seg.get('total_days', 0),
            'currency': seg.get('currency', 'USD'),
            'invoices': [{'invoice_id': a['invoice_id'], 'allocated_amount': a['allocated_amount'],
                          'invoice_amount': a['invoice_amount'], 'invoice_date': a['invoice_date'],
                          'invoice_status': a['invoice_status'], 'overlap_days': a['overlap_days']} for a in seg_allocs],
            'credit_notes': cn_applied
        })

    return {'results': results, 'exclusions': exclusions}

# =============================================================================
# SCORING
# =============================================================================
def calculate_score(rsx_entities, identity_result, recon_results, total_subs, total_arr, excl_subs, excl_arr):
    total_entities = len(identity_result.get('auto_matched', [])) + len(identity_result.get('needs_review', [])) + len(identity_result.get('unmatched_accounts', [])) + len(identity_result.get('unmatched_customers', []))
    matched = len(rsx_entities)
    emr = (matched / max(total_entities, 1)) * 100

    total_segs = len(recon_results)
    segs_inv = sum(1 for r in recon_results if r['invoiced_amount'] > 0)
    bcr = (segs_inv / max(total_segs, 1)) * 100

    clean = sum(1 for r in recon_results if r['status'] == 'CLEAN')
    vr = (clean / max(total_segs, 1)) * 100

    full_chain = sum(1 for r in recon_results if r['invoiced_amount'] > 0 and r['collected_amount'] > 0)
    lc = (full_chain / max(total_segs, 1)) * 100

    score = round(WEIGHTS['entity_match'] * emr + WEIGHTS['billing_coverage'] * bcr + WEIGHTS['variance'] * vr + WEIGHTS['lineage'] * lc)

    sup_subs = total_subs - excl_subs
    sup_arr = total_arr - excl_arr
    sub_cov = r2((sup_subs / max(total_subs, 1)) * 100)
    arr_cov = r2((sup_arr / max(total_arr, 1)) * 100)

    if score >= 90: band, color = 'Coherent', 'green'
    elif score >= 75: band, color = 'Drifting', 'amber'
    elif score >= 60: band, color = 'At Risk', 'orange'
    else: band, color = 'Breakdown', 'red'

    interp = {'green': 'Structure is coherent. Spot-check recommended.',
              'amber': 'Moderate drift detected. Review flagged accounts.',
              'orange': 'Significant gaps. Investigate before month-end close.',
              'red': 'Structural breakdown. Do not rely on current revenue reporting.'}

    rar = {
        'total': r2(sum(abs(r['variance']) for r in recon_results if r['status'] != 'CLEAN')),
        'missing_invoice': r2(sum(r['expected_amount'] for r in recon_results if r['status'] == 'MISSING_INVOICE')),
        'under_billed': r2(sum(abs(r['variance']) for r in recon_results if r['status'] == 'UNDER_BILLED')),
        'over_billed': r2(sum(r['variance'] for r in recon_results if r['status'] == 'OVER_BILLED')),
        'unpaid_ar': r2(sum(r['invoiced_amount'] - r['collected_amount'] for r in recon_results if r['has_unpaid_ar'])),
        'missing_invoice_accounts': len(set(r['rsx_id'] for r in recon_results if r['status'] == 'MISSING_INVOICE')),
        'under_billed_accounts': len(set(r['rsx_id'] for r in recon_results if r['status'] == 'UNDER_BILLED')),
        'over_billed_accounts': len(set(r['rsx_id'] for r in recon_results if r['status'] == 'OVER_BILLED')),
        'unpaid_ar_accounts': len(set(r['rsx_id'] for r in recon_results if r['has_unpaid_ar']))
    }

    return {
        'score': score, 'band': band, 'color': color, 'interpretation': interp[color],
        'components': {
            'entity_match_rate': {'value': r2(emr), 'weight': 25, 'label': 'Entity Match Rate'},
            'billing_coverage_rate': {'value': r2(bcr), 'weight': 35, 'label': 'Billing Coverage Rate'},
            'variance_rate': {'value': r2(vr), 'weight': 25, 'label': 'Variance Rate'},
            'lineage_completeness': {'value': r2(lc), 'weight': 15, 'label': 'Lineage Completeness'}
        },
        'coverage': {
            'subscription_count': sup_subs, 'total_subscriptions': total_subs, 'subscription_pct': sub_cov,
            'arr_covered': r2(sup_arr), 'total_arr': r2(total_arr), 'arr_pct': arr_cov
        },
        'revenue_at_risk': rar
    }

# =============================================================================
# CSV TEMPLATES
# =============================================================================
def get_template(file_type):
    templates = {
        'accounts': {
            'headers': ['account_id', 'account_name', 'account_status', 'source_system', 'account_owner'],
            'rows': [
                ['ACC-001', 'Acme Corporation', 'active', 'salesforce', 'John Smith'],
                ['ACC-002', 'TechStart Ltd', 'active', 'hubspot', 'Jane Doe'],
            ]
        },
        'customers': {
            'headers': ['customer_id', 'customer_name', 'customer_status', 'source_system', 'billing_email'],
            'rows': [
                ['CUST-001', 'Acme Corporation', 'active', 'stripe', 'billing@acme.com'],
                ['CUST-002', 'TechStart Limited', 'active', 'chargebee', 'finance@techstart.com'],
            ]
        },
        'subscriptions': {
            'headers': ['sub_id', 'customer_id', 'start_date', 'end_date', 'mrr', 'currency', 'billing_frequency', 'pricing_model', 'ramp_schedule', 'sub_status'],
            'rows': [
                ['SUB-001', 'CUST-001', '2024-01-01', '2024-12-31', '10000', 'USD', 'monthly', 'flat', '', 'active'],
                ['SUB-002', 'CUST-002', '2024-03-15', '', '5000', 'USD', 'monthly', 'ramp', '[{"stage_start":"2024-03-15","stage_end":"2024-06-30","mrr":5000},{"stage_start":"2024-07-01","stage_end":"2025-12-31","mrr":8000}]', 'active'],
            ]
        },
        'invoices': {
            'headers': ['invoice_id', 'customer_id', 'sub_id', 'invoice_date', 'period_start', 'period_end', 'amount', 'currency', 'status'],
            'rows': [
                ['INV-001', 'CUST-001', 'SUB-001', '2024-01-01', '2024-01-01', '2024-01-31', '10000', 'USD', 'paid'],
                ['INV-002', 'CUST-002', 'SUB-002', '2024-04-01', '2024-04-01', '2024-04-30', '5000', 'USD', 'paid'],
            ]
        },
        'payments': {
            'headers': ['payment_id', 'invoice_id', 'payment_date', 'amount', 'currency', 'payment_method'],
            'rows': [
                ['PAY-001', 'INV-001', '2024-01-15', '10000', 'USD', 'bank_transfer'],
                ['PAY-002', 'INV-002', '2024-04-10', '5000', 'USD', 'card'],
            ]
        },
        'credit_notes': {
            'headers': ['credit_note_id', 'invoice_id', 'customer_id', 'issue_date', 'amount', 'currency', 'reason'],
            'rows': [
                ['CN-001', 'INV-001', 'CUST-001', '2024-02-01', '2000', 'USD', 'billing error correction'],
                ['CN-002', '', 'CUST-002', '2024-05-15', '500', 'USD', 'goodwill credit - no linked invoice'],
            ]
        }
    }
    t = templates.get(file_type)
    if not t:
        return None
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(t['headers'])
    for row in t['rows']:
        writer.writerow(row)
    return output.getvalue()
