"""
RevStrux Synthetic Dataset Generator
Generates test data with 15 ground truth anomalies per PRD v1.1
"""
import random
import json
from datetime import date, timedelta
from calendar import monthrange

random.seed(42)

COMPANIES = [
    "NovaTech Solutions", "Meridian Digital", "Apex Global Partners", "CloudBridge Systems",
    "DataVault Analytics", "Zenith Platforms", "Summit Software", "Pinnacle AI Labs",
    "Horizon Networks", "Quantum Logic", "Atlas Dynamics", "Velocity SaaS",
    "Fusion Collaborative", "Nexus Intelligence", "Prism Analytics",
    "ClearPath Software", "Matrix Operations", "Forge Automation", "Signal Processing Co",
    "Blueprint Tech", "Cascade Data", "Ironclad Security", "Lighthouse Labs",
    "Pioneer Digital", "Sterling Analytics", "TrueNorth Consulting", "Vanguard Systems",
    "WavePoint Tech", "Axiom Software", "BrightEdge Solutions", "Cobalt Platforms",
    "Dreamscape AI", "EchoBase Systems", "Frontier Logic", "GreenField SaaS",
    "HexaCore Computing", "InfiniteLoop Tech", "JadeStone Analytics", "Keystone Digital",
    "LaunchPad Ventures", "MoonRise Software", "NorthStar Data", "OmniStack Solutions",
    "Polaris Systems", "QuickSilver Tech", "RedShift Analytics", "SkyVault Cloud",
    "TerraFlow Data", "UltraViolet Labs", "VectorSpace AI", "Windmill Software",
    "XenonByte Systems", "YieldMax Analytics", "ZeroGravity Tech", "AlphaWave Digital",
    "BetaForge Solutions", "TechFlow Inc", "Apex Systems", "CoreSync Ltd", "DataPrime Corp"
]

def gen_id(prefix, num):
    return f"{prefix}-{num:03d}"

def gen_date(y, m, d):
    return f"{y:04d}-{m:02d}-{d:02d}"

def generate_synthetic():
    accounts, customers, subscriptions, invoices, payments, credit_notes_list = [], [], [], [], [], []

    # Analysis period: Jan 2024 - Dec 2024
    period_start, period_end = "2024-01", "2024-12"

    # Generate 60 accounts
    for i in range(60):
        aid = f"SYNTH-{i+1:03d}"
        name = COMPANIES[i] if i < len(COMPANIES) else f"Company {i+1}"
        status = 'active'
        if i in [58, 59]:  # SYNTH-059, SYNTH-060 are prospects
            status = 'prospect'
        if i == 25:  # One churned
            status = 'churned'
        accounts.append({
            'account_id': aid, 'account_name': name, 'account_status': status,
            'source_system': 'salesforce', 'account_owner': f"Owner {i % 10 + 1}"
        })

    # Anomaly 7: SYNTH-033 -> fuzzy match name (index 32 = SYNTH-033)
    accounts[32]['account_name'] = 'TechFlow Inc'

    # Anomaly 8: SYNTH-041 -> fuzzy match name (index 40 = SYNTH-041)
    accounts[40]['account_name'] = 'Apex Systems'

    # Anomaly 4: SYNTH-019 unmatched (index 18 = SYNTH-019)
    accounts[18]['account_name'] = 'Pioneer Digital'

    # Anomaly 5: SYNTH-052 unmatched (index 51 = SYNTH-052)
    accounts[51]['account_name'] = 'XenonByte Systems'

    # Generate 55 billing customers - match 50 exactly, 2 fuzzy, 3 unmatched billing
    cust_idx = 0
    matched_account_indices = set()
    for i in range(60):
        if accounts[i]['account_status'] == 'prospect':
            continue
        if accounts[i]['account_id'] in ['SYNTH-019', 'SYNTH-052']:
            continue  # These accounts have no billing match
        if cust_idx >= 55:
            break

        aid = accounts[i]['account_id']
        aname = accounts[i]['account_name']
        cid = f"CUST-{cust_idx+1:03d}"

        # Fuzzy matches
        if aid == 'SYNTH-033':
            cname = 'Techflow Incorporated'  # Fuzzy match for TechFlow Inc
        elif aid == 'SYNTH-041':
            cname = 'Apex System Solutions'  # Fuzzy match for Apex Systems
        else:
            cname = aname  # Exact match

        customers.append({
            'customer_id': cid, 'customer_name': cname,
            'customer_status': 'active' if accounts[i]['account_status'] == 'active' else 'cancelled',
            'source_system': 'stripe', 'billing_email': f"billing@{aname.lower().replace(' ', '')}.com"
        })
        matched_account_indices.add(i)
        cust_idx += 1

    # Add 3 unmatched billing customers
    for j in range(3):
        customers.append({
            'customer_id': f"CUST-{55+j+1:03d}", 'customer_name': f"Orphan Billing Co {j+1}",
            'customer_status': 'active', 'source_system': 'stripe',
            'billing_email': f"billing@orphan{j+1}.com"
        })

    # Build customer_id lookup by account_id for subscriptions
    acc_to_cust = {}
    for i, acc in enumerate(accounts):
        if i < len(customers) and acc['account_id'] not in ['SYNTH-019', 'SYNTH-052']:
            # Find customer with matching name
            for c in customers:
                from engine import normalize, similarity
                if normalize(acc['account_name']) == normalize(c['customer_name']) or similarity(normalize(acc['account_name']), normalize(c['customer_name'])) >= 0.70:
                    acc_to_cust[acc['account_id']] = c['customer_id']
                    break

    # Generate 70 subscriptions
    sub_idx = 0
    for cust in customers[:55]:
        cid = cust['customer_id']
        # Most get 1 subscription, some get 2
        num_subs = 2 if sub_idx % 8 == 0 and sub_idx < 60 else 1
        for _ in range(num_subs):
            if sub_idx >= 70:
                break
            sid = f"SUB-{sub_idx+1:03d}"
            mrr = random.choice([5000, 8000, 10000, 12000, 15000, 20000])
            start_month = random.randint(1, 6)
            start_day = 1

            pricing = 'flat'
            ramp = ''

            # Anomaly 9: SYNTH-028 usage-based (find its customer)
            acct_for_cust = None
            for aid, c in acc_to_cust.items():
                if c == cid:
                    acct_for_cust = aid
                    break

            # 5 usage-based subs for exclusion testing
            if sub_idx in [27, 28, 29, 30, 31]:
                pricing = 'usage'

            # 5 ramp subs
            if sub_idx in [60, 61, 62, 63, 64] and sub_idx < 70:
                pricing = 'ramp'
                ramp = json.dumps([
                    {"stage_start": f"2024-{start_month:02d}-01", "stage_end": "2024-06-30", "mrr": mrr},
                    {"stage_start": "2024-07-01", "stage_end": "2024-12-31", "mrr": int(mrr * 1.5)}
                ])

            # Anomaly 11: SYNTH-058 mid-month start (March 15)
            if acct_for_cust == 'SYNTH-058' or (sub_idx == 57 and acct_for_cust is None):
                start_month = 3
                start_day = 15
                mrr = 10000

            subscriptions.append({
                'sub_id': sid, 'customer_id': cid,
                'start_date': gen_date(2024, start_month, start_day),
                'end_date': gen_date(2024, 12, 31),
                'mrr': str(mrr), 'currency': 'USD',
                'billing_frequency': 'monthly', 'pricing_model': pricing,
                'ramp_schedule': ramp, 'sub_status': 'active'
            })
            sub_idx += 1

    # Generate invoices and payments
    inv_idx = 0
    pay_idx = 0

    for sub in subscriptions:
        if sub['pricing_model'] == 'usage':
            continue
        cid = sub['customer_id']
        sub_start = date(int(sub['start_date'][:4]), int(sub['start_date'][5:7]), int(sub['start_date'][8:10]))
        sub_end = date(2024, 12, 31)
        mrr = float(sub['mrr'])

        # Find account for this customer
        acct_id = None
        for aid, c in acc_to_cust.items():
            if c == cid:
                acct_id = aid
                break

        # Anomaly 12: SYNTH-062 annual invoice
        if acct_id == 'SYNTH-062' or (inv_idx > 400 and sub['sub_id'] == 'SUB-062'):
            inv_idx += 1
            invoices.append({
                'invoice_id': f"INV-{inv_idx:04d}", 'customer_id': cid,
                'sub_id': sub['sub_id'], 'invoice_date': '2024-01-01',
                'period_start': '2024-01-01', 'period_end': '2024-12-31',
                'amount': str(mrr * 12), 'currency': 'USD', 'status': 'paid'
            })
            pay_idx += 1
            payments.append({
                'payment_id': f"PAY-{pay_idx:04d}", 'invoice_id': f"INV-{inv_idx:04d}",
                'payment_date': '2024-01-15', 'amount': str(mrr * 12),
                'currency': 'USD', 'payment_method': 'bank_transfer'
            })
            continue

        # Generate monthly invoices
        m = sub_start.month
        while m <= 12:
            ms = date(2024, m, 1)
            me = date(2024, m, monthrange(2024, m)[1])

            inv_amount = mrr

            # Anomaly 1: SYNTH-012 missing invoices Aug, Sep
            if acct_id == 'SYNTH-012' and m in [8, 9]:
                m += 1
                continue

            # Anomaly 2: SYNTH-031 under-billing Jul
            if acct_id == 'SYNTH-031' and m == 7:
                inv_amount = 7500  # vs expected 10000

            # Anomaly 3: SYNTH-044 under-billing May, Jun, Jul
            if acct_id == 'SYNTH-044' and m in [5, 6, 7]:
                inv_amount = mrr - 7333.33  # Underbill

            # Anomaly 6: SYNTH-007 over-billing
            if acct_id == 'SYNTH-007' and m == 6:
                inv_amount = 15000  # vs expected 12000

            # Anomaly 15: SYNTH-039 rounding tolerance
            if acct_id == 'SYNTH-039' and m == 4:
                inv_amount = mrr - 0.87  # $0.87 under - within tolerance

            inv_idx += 1
            inv_status = 'paid'

            # Anomaly 10: SYNTH-015 unpaid AR
            if acct_id == 'SYNTH-015' and m >= 10:
                inv_status = 'unpaid'

            invoices.append({
                'invoice_id': f"INV-{inv_idx:04d}", 'customer_id': cid,
                'sub_id': sub['sub_id'], 'invoice_date': gen_date(2024, m, 1),
                'period_start': gen_date(2024, m, 1),
                'period_end': gen_date(2024, m, monthrange(2024, m)[1]),
                'amount': str(round(inv_amount, 2)), 'currency': 'USD', 'status': inv_status
            })

            # Generate payment if paid
            if inv_status == 'paid':
                pay_idx += 1
                payments.append({
                    'payment_id': f"PAY-{pay_idx:04d}", 'invoice_id': f"INV-{inv_idx:04d}",
                    'payment_date': gen_date(2024, m, min(15, monthrange(2024, m)[1])),
                    'amount': str(round(inv_amount, 2)),
                    'currency': 'USD', 'payment_method': random.choice(['bank_transfer', 'card'])
                })

            m += 1

    # Anomaly 13: SYNTH-034 credit note linked to invoice
    # Find an invoice for the customer associated with SYNTH-034
    synth034_cust = acc_to_cust.get('SYNTH-034')
    if synth034_cust:
        target_inv = next((inv for inv in invoices if inv['customer_id'] == synth034_cust), None)
        if target_inv:
            credit_notes_list.append({
                'credit_note_id': 'CN-001', 'invoice_id': target_inv['invoice_id'],
                'customer_id': synth034_cust, 'issue_date': '2024-03-15',
                'amount': '2000', 'currency': 'USD', 'reason': 'billing error correction'
            })

    # Anomaly 14: SYNTH-047 standalone credit note unallocated
    synth047_cust = acc_to_cust.get('SYNTH-047')
    if synth047_cust:
        credit_notes_list.append({
            'credit_note_id': 'CN-002', 'invoice_id': '',
            'customer_id': synth047_cust, 'issue_date': '2025-06-15',
            'amount': '1500', 'currency': 'USD', 'reason': 'goodwill credit'
        })

    # Additional credit notes
    for j in range(6):
        cid = customers[j * 5 + 3]['customer_id'] if j * 5 + 3 < len(customers) else customers[0]['customer_id']
        target_inv = next((inv for inv in invoices if inv['customer_id'] == cid), None)
        credit_notes_list.append({
            'credit_note_id': f'CN-{j+3:03d}',
            'invoice_id': target_inv['invoice_id'] if target_inv and j < 3 else '',
            'customer_id': cid, 'issue_date': f'2024-{(j+1)*2:02d}-10',
            'amount': str(random.choice([500, 1000, 1500, 2000])),
            'currency': 'USD', 'reason': random.choice(['billing error', 'goodwill', 'dispute resolution'])
        })

    return {
        'accounts': accounts, 'customers': customers, 'subscriptions': subscriptions,
        'invoices': invoices, 'payments': payments, 'credit_notes': credit_notes_list,
        'period_start': period_start, 'period_end': period_end,
        'metadata': {
            'total_accounts': len(accounts), 'total_customers': len(customers),
            'total_subscriptions': len(subscriptions), 'total_invoices': len(invoices),
            'total_payments': len(payments), 'total_credit_notes': len(credit_notes_list)
        }
    }
