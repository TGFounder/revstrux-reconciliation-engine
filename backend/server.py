from fastapi import FastAPI, APIRouter, UploadFile, File, Form, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import csv
import json
import logging
import asyncio
import zipfile
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timezone

from engine import (validate_csv, run_identity_matching, build_rsx_entities,
                    generate_segments, match_invoices, reconcile, calculate_score,
                    get_template, r2, detect_file_type, normalize_headers,
                    normalize_enums, smart_validate)
from synthetic import generate_synthetic

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="RevStrux API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# HELPERS
# =============================================================================
async def get_session(session_id: str):
    doc = await db.sessions.find_one({'session_id': session_id}, {'_id': 0})
    return doc

async def update_session(session_id: str, data: dict):
    await db.sessions.update_one({'session_id': session_id}, {'$set': data})

async def get_data(session_id: str, dtype: str):
    doc = await db.session_data.find_one({'session_id': session_id, 'type': dtype}, {'_id': 0})
    return doc.get('data', []) if doc else []

async def set_data(session_id: str, dtype: str, data):
    await db.session_data.update_one(
        {'session_id': session_id, 'type': dtype},
        {'$set': {'session_id': session_id, 'type': dtype, 'data': data}},
        upsert=True)

# =============================================================================
# SESSION ENDPOINTS
# =============================================================================
@api.post("/sessions")
async def create_session():
    sid = str(uuid.uuid4())[:12]
    session = {
        'session_id': sid, 'status': 'created',
        'settings': {'currency': 'USD', 'period_start': '2024-01', 'period_end': '2024-12'},
        'upload_status': {t: {'uploaded': False, 'rows': 0, 'filename': ''} for t in ['accounts','customers','subscriptions','invoices','payments','credit_notes']},
        'validation_result': None, 'identity_result': None,
        'identity_decisions': [], 'decision_history': [],
        'processing_status': {'current_step': None, 'steps': {}, 'log': []},
        'created_at': datetime.now(timezone.utc).isoformat(), 'completed_at': None
    }
    await db.sessions.insert_one(dict(session))
    return session

@api.get("/sessions/{session_id}")
async def get_session_info(session_id: str):
    s = await get_session(session_id)
    if not s:
        return {"error": "Session not found"}
    return s

@api.put("/sessions/{session_id}/settings")
async def update_settings(session_id: str, settings: dict):
    await update_session(session_id, {'settings': settings})
    return {"ok": True}

# =============================================================================
# UPLOAD ENDPOINTS
# =============================================================================
@api.post("/sessions/{session_id}/upload/{file_type}")
async def upload_file(session_id: str, file_type: str, file: UploadFile = File(...)):
    valid_types = ['accounts','customers','subscriptions','invoices','payments','credit_notes']
    if file_type not in valid_types:
        return {"error": f"Invalid file type. Must be one of: {', '.join(valid_types)}"}

    content = await file.read()
    try:
        text = content.decode('utf-8')
    except UnicodeDecodeError:
        return {"error": "File encoding error. Re-save as UTF-8 CSV."}

    reader = csv.DictReader(io.StringIO(text))
    rows = [dict(row) for row in reader]

    await set_data(session_id, f'raw_{file_type}', rows)
    us = {f'upload_status.{file_type}': {'uploaded': True, 'rows': len(rows), 'filename': file.filename}}
    await update_session(session_id, us)

    return {"file_type": file_type, "rows": len(rows), "filename": file.filename}

# =============================================================================
# SMART UPLOAD ENDPOINT
# =============================================================================
def _process_csv_bytes(content_bytes, filename):
    """Parse CSV bytes into rows, detect type, normalize headers/enums."""
    try:
        text = content_bytes.decode('utf-8')
    except UnicodeDecodeError:
        try:
            text = content_bytes.decode('latin-1')
        except Exception:
            return {'filename': filename, 'error': 'Unreadable file encoding. Save as UTF-8 CSV.'}

    reader = csv.DictReader(io.StringIO(text))
    rows = [dict(row) for row in reader]
    if not rows:
        return {'filename': filename, 'error': 'No data rows found.'}

    headers = list(rows[0].keys())
    file_type, confidence, alias_applied = detect_file_type(headers)
    norm_rows, header_mappings = normalize_headers(rows)

    enum_normalizations = []
    if file_type:
        norm_rows, enum_normalizations = normalize_enums(file_type, norm_rows)

    validation = smart_validate(file_type, norm_rows) if file_type else {
        'valid': False, 'errors': [{'file': filename, 'row': 0, 'field': '',
                                     'message': 'Could not auto-detect file type from headers.'}], 'warnings': []}

    return {
        'filename': filename,
        'detected_type': file_type,
        'confidence': confidence,
        'rows': len(norm_rows),
        'original_headers': headers,
        'header_mappings': header_mappings[:30],
        'enum_normalizations': enum_normalizations[:30],
        'validation': validation,
        'data': norm_rows if file_type else None,
    }


@api.post("/sessions/{session_id}/smart-upload")
async def smart_upload(session_id: str, files: List[UploadFile] = File(...)):
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    file_results = []
    for uploaded in files:
        raw = await uploaded.read()

        if uploaded.filename.lower().endswith('.zip'):
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    for name in zf.namelist():
                        if name.lower().endswith('.csv') and not name.startswith('__MACOSX'):
                            csv_bytes = zf.read(name)
                            result = _process_csv_bytes(csv_bytes, name.split('/')[-1])
                            file_results.append(result)
            except zipfile.BadZipFile:
                file_results.append({'filename': uploaded.filename, 'error': 'Invalid ZIP file.'})
        elif uploaded.filename.lower().endswith('.csv'):
            result = _process_csv_bytes(raw, uploaded.filename)
            file_results.append(result)
        else:
            file_results.append({'filename': uploaded.filename, 'error': 'Unsupported file format. Use .csv or .zip.'})

    # Store successfully detected files
    stored_types = []
    for result in file_results:
        ft = result.get('detected_type')
        data = result.pop('data', None)
        if ft and data and result.get('validation', {}).get('valid', False):
            await set_data(session_id, f'raw_{ft}', data)
            await update_session(session_id, {
                f'upload_status.{ft}': {'uploaded': True, 'rows': len(data), 'filename': result['filename']}
            })
            stored_types.append(ft)
        elif ft and data:
            # Store even with warnings (soft validation means we proceed)
            has_blocking = any(e for e in result.get('validation', {}).get('errors', []))
            if not has_blocking:
                await set_data(session_id, f'raw_{ft}', data)
                await update_session(session_id, {
                    f'upload_status.{ft}': {'uploaded': True, 'rows': len(data), 'filename': result['filename']}
                })
                stored_types.append(ft)

    return {'results': file_results, 'stored_types': stored_types}


@api.post("/sessions/{session_id}/smart-validate")
async def smart_validate_endpoint(session_id: str):
    """Soft validation + identity matching for smart upload flow."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    all_errors, all_warnings = [], []
    for ft in ['accounts', 'customers', 'subscriptions', 'invoices', 'payments', 'credit_notes']:
        if not session['upload_status'].get(ft, {}).get('uploaded'):
            if ft in ('credit_notes', 'payments'):
                all_warnings.append({'file': ft, 'row': 0, 'field': '',
                                     'message': f'{ft} not uploaded. Analysis will proceed without it.'})
                continue
            all_errors.append({'file': ft, 'row': 0, 'field': '',
                              'message': f'{ft} is required but not uploaded.'})
            continue
        rows = await get_data(session_id, f'raw_{ft}')
        result = smart_validate(ft, rows)
        all_errors.extend(result['errors'])
        all_warnings.extend(result['warnings'])

    valid = len(all_errors) == 0
    vr = {'valid': valid, 'errors': all_errors, 'warnings': all_warnings}
    new_status = 'validated' if valid else 'created'
    await update_session(session_id, {'validation_result': vr, 'status': new_status})

    if valid:
        accounts = await get_data(session_id, 'raw_accounts')
        customers = await get_data(session_id, 'raw_customers')
        identity = run_identity_matching(accounts, customers)
        await update_session(session_id, {'identity_result': identity, 'status': 'identity_review'})
        return {**vr, 'identity_summary': {
            'auto_matched': len(identity['auto_matched']),
            'needs_review': len(identity['needs_review']),
            'unmatched_accounts': len(identity['unmatched_accounts']),
            'unmatched_customers': len(identity['unmatched_customers'])
        }}

    return vr


# =============================================================================
# VALIDATION ENDPOINT
# =============================================================================
@api.post("/sessions/{session_id}/validate")
async def validate_files(session_id: str):
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    all_errors, all_warnings = [], []
    for ft in ['accounts','customers','subscriptions','invoices','payments','credit_notes']:
        if not session['upload_status'][ft]['uploaded']:
            if ft == 'credit_notes':
                continue
            all_errors.append({'file': ft, 'row': 0, 'field': '', 'message': f'{ft}.csv is required but not uploaded.'})
            continue
        rows = await get_data(session_id, f'raw_{ft}')
        result = validate_csv(ft, rows)
        all_errors.extend(result['errors'])
        all_warnings.extend(result['warnings'])

    valid = len(all_errors) == 0
    vr = {'valid': valid, 'errors': all_errors, 'warnings': all_warnings}
    new_status = 'validated' if valid else 'created'
    await update_session(session_id, {'validation_result': vr, 'status': new_status})

    # Auto-run identity matching if valid
    if valid:
        accounts = await get_data(session_id, 'raw_accounts')
        customers = await get_data(session_id, 'raw_customers')
        identity = run_identity_matching(accounts, customers)
        await update_session(session_id, {'identity_result': identity, 'status': 'identity_review'})
        return {**vr, 'identity_summary': {
            'auto_matched': len(identity['auto_matched']),
            'needs_review': len(identity['needs_review']),
            'unmatched_accounts': len(identity['unmatched_accounts']),
            'unmatched_customers': len(identity['unmatched_customers'])
        }}

    return vr

# =============================================================================
# IDENTITY ENDPOINTS
# =============================================================================
@api.get("/sessions/{session_id}/identity")
async def get_identity(session_id: str):
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}
    ir = session.get('identity_result')
    if not ir:
        return {"error": "Identity matching not run yet"}
    # Apply decisions to needs_review
    decisions = session.get('identity_decisions', [])
    decided_ids = {d['match_id'] for d in decisions}
    pending = [m for m in ir['needs_review'] if m['match_id'] not in decided_ids]
    return {
        'auto_matched': ir['auto_matched'],
        'needs_review': ir['needs_review'],
        'pending_review': pending,
        'unmatched_accounts': ir['unmatched_accounts'],
        'unmatched_customers': ir['unmatched_customers'],
        'prospects': ir.get('prospects', []),
        'decisions': decisions,
        'all_reviewed': len(pending) == 0
    }

@api.post("/sessions/{session_id}/identity/decide")
async def identity_decide(session_id: str, body: dict):
    match_id = body.get('match_id')
    decision = body.get('decision')  # 'confirmed' or 'rejected'
    if not match_id or decision not in ['confirmed', 'rejected']:
        return {"error": "Invalid request. Need match_id and decision (confirmed/rejected)"}

    session = await get_session(session_id)
    decisions = session.get('identity_decisions', [])
    history = session.get('decision_history', [])
    # Remove existing decision for this match_id if any
    decisions = [d for d in decisions if d['match_id'] != match_id]
    decisions.append({'match_id': match_id, 'decision': decision, 'timestamp': datetime.now(timezone.utc).isoformat()})
    history.append({'action': 'decide', 'match_id': match_id, 'decision': decision, 'timestamp': datetime.now(timezone.utc).isoformat()})
    await update_session(session_id, {'identity_decisions': decisions, 'decision_history': history})
    return {"ok": True, "decisions_count": len(decisions)}

@api.post("/sessions/{session_id}/identity/undo")
async def identity_undo(session_id: str):
    session = await get_session(session_id)
    decisions = session.get('identity_decisions', [])
    history = session.get('decision_history', [])
    if not decisions:
        return {"error": "No decisions to undo"}
    removed = decisions.pop()
    history.append({'action': 'undo', 'match_id': removed['match_id'], 'timestamp': datetime.now(timezone.utc).isoformat()})
    await update_session(session_id, {'identity_decisions': decisions, 'decision_history': history})
    return {"ok": True, "undone": removed}

@api.post("/sessions/{session_id}/identity/reset")
async def identity_reset(session_id: str):
    session = await get_session(session_id)
    history = session.get('decision_history', [])
    count = len(session.get('identity_decisions', []))
    history.append({'action': 'reset', 'count': count, 'timestamp': datetime.now(timezone.utc).isoformat()})
    await update_session(session_id, {'identity_decisions': [], 'decision_history': history})
    return {"ok": True, "cleared": count}

# =============================================================================
# ANALYSIS PROCESSING
# =============================================================================
async def run_analysis(session_id: str):
    try:
        session = await get_session(session_id)
        settings = session['settings']

        async def log_step(step, status, message=""):
            steps = (await get_session(session_id)).get('processing_status', {}).get('steps', {})
            steps[step] = {'status': status, 'timestamp': datetime.now(timezone.utc).isoformat()}
            log = (await get_session(session_id)).get('processing_status', {}).get('log', [])
            if message:
                log.append({'step': step, 'message': message, 'timestamp': datetime.now(timezone.utc).isoformat()})
            await update_session(session_id, {'processing_status': {'current_step': step, 'steps': steps, 'log': log}})

        # Step 1: Ingestion
        await log_step('ingestion', 'running', 'Loading validated data...')
        accounts = await get_data(session_id, 'raw_accounts')
        customers = await get_data(session_id, 'raw_customers')
        subs = await get_data(session_id, 'raw_subscriptions')
        invs = await get_data(session_id, 'raw_invoices')
        pays = await get_data(session_id, 'raw_payments')
        cns = await get_data(session_id, 'raw_credit_notes')
        await log_step('ingestion', 'complete', f'Loaded {len(accounts)} accounts, {len(subs)} subscriptions, {len(invs)} invoices')

        # Step 2: Identity
        await log_step('identity', 'running', 'Building identity spine...')
        identity = session['identity_result']
        decisions = session.get('identity_decisions', [])
        rsx_entities = build_rsx_entities(identity, decisions)
        await set_data(session_id, 'rsx_entities', rsx_entities)
        await log_step('identity', 'complete', f'{len(rsx_entities)} RSX entities created')

        # Step 3: Lifecycle
        await log_step('lifecycle', 'running', 'Generating revenue segments...')
        seg_result = generate_segments(subs, rsx_entities, settings['period_start'], settings['period_end'])
        segments = seg_result['segments']
        all_exclusions = seg_result['exclusions']
        await set_data(session_id, 'segments', segments)
        await log_step('lifecycle', 'complete', f'{len(segments)} revenue segments generated, {len(all_exclusions)} excluded')

        # Step 4: Reconciliation
        await log_step('reconciliation', 'running', 'Matching invoices and reconciling...')
        inv_result = match_invoices(invs, segments, rsx_entities)
        all_exclusions.extend(inv_result['exclusions'])
        recon_result = reconcile(segments, inv_result['allocations'], pays, cns, rsx_entities)
        recon_results = recon_result['results']
        all_exclusions.extend(recon_result['exclusions'])
        await set_data(session_id, 'reconciliation', recon_results)
        await set_data(session_id, 'exclusions', all_exclusions)
        await log_step('reconciliation', 'complete', f'{len(recon_results)} segments reconciled, {len(all_exclusions)} total exclusions')

        # Step 5: Scoring
        await log_step('scoring', 'running', 'Calculating structural integrity score...')
        total_subs = len(subs)
        total_arr = sum(float(s.get('mrr', 0)) * 12 for s in subs)
        excl_sub_ids = {e['record_id'] for e in all_exclusions if e['record_type'] == 'subscription'}
        excl_subs = len(excl_sub_ids)
        excl_arr = sum(float(s.get('mrr', 0)) * 12 for s in subs if s['sub_id'] in excl_sub_ids)

        score = calculate_score(rsx_entities, identity, recon_results, total_subs, total_arr, excl_subs, excl_arr)
        await set_data(session_id, 'score', score)

        # Build account summaries
        account_map = {}
        for e in rsx_entities:
            account_map[e['rsx_id']] = {
                'rsx_id': e['rsx_id'], 'account_name': e['account_name'],
                'account_id': e['account_id'], 'customer_id': e['customer_id'],
                'match_type': e['match_type'], 'confidence': e['confidence'],
                'subscriptions': 0, 'periods': 0,
                'expected_total': 0, 'invoiced_total': 0,
                'credit_notes_total': 0, 'total_variance': 0,
                'primary_variance_type': 'CLEAN', 'lineage_status': 'Complete',
                'currency': 'USD'
            }

        for r in recon_results:
            acc = account_map.get(r['rsx_id'])
            if acc:
                acc['periods'] += 1
                acc['expected_total'] = r2(acc['expected_total'] + r['expected_amount'])
                acc['invoiced_total'] = r2(acc['invoiced_total'] + r['invoiced_amount'])
                acc['credit_notes_total'] = r2(acc['credit_notes_total'] + r['credit_notes_amount'])
                acc['total_variance'] = r2(acc['total_variance'] + r['variance'])
                acc['currency'] = r['currency']
                if r['status'] != 'CLEAN':
                    if acc['primary_variance_type'] == 'CLEAN' or r['abs_variance'] > abs(acc['total_variance']):
                        acc['primary_variance_type'] = r['status']
                    if r['status'] == 'MISSING_INVOICE':
                        acc['lineage_status'] = 'Incomplete'

        for e in rsx_entities:
            acc = account_map.get(e['rsx_id'])
            if acc:
                acc['subscriptions'] = len(set(r['sub_id'] for r in recon_results if r['rsx_id'] == e['rsx_id']))

        # Add unmatched accounts
        for ua in identity.get('unmatched_accounts', []):
            rid = f"UNM-{ua['account_id']}"
            account_map[rid] = {
                'rsx_id': rid, 'account_name': ua['account_name'],
                'account_id': ua['account_id'], 'customer_id': '',
                'match_type': 'unmatched', 'confidence': 0,
                'subscriptions': 0, 'periods': 0,
                'expected_total': 0, 'invoiced_total': 0,
                'credit_notes_total': 0, 'total_variance': 0,
                'primary_variance_type': 'UNKNOWN', 'lineage_status': 'Unknown',
                'currency': settings.get('currency', 'USD')
            }

        accounts_list = sorted(account_map.values(), key=lambda x: abs(x['total_variance']), reverse=True)
        await set_data(session_id, 'accounts_summary', accounts_list)

        await log_step('scoring', 'complete', f'Score: {score["score"]} ({score["band"]})')
        await update_session(session_id, {
            'status': 'completed',
            'completed_at': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        await update_session(session_id, {
            'status': 'error',
            'processing_status.error': str(e)
        })

@api.post("/sessions/{session_id}/analyze")
async def start_analysis(session_id: str, background_tasks: BackgroundTasks):
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}
    await update_session(session_id, {
        'status': 'processing',
        'processing_status': {'current_step': 'ingestion', 'steps': {}, 'log': []}
    })
    background_tasks.add_task(run_analysis, session_id)
    return {"ok": True, "status": "processing"}

@api.get("/sessions/{session_id}/status")
async def get_status(session_id: str):
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}
    return {
        'status': session['status'],
        'processing_status': session.get('processing_status', {}),
        'completed_at': session.get('completed_at')
    }

# =============================================================================
# DASHBOARD
# =============================================================================
@api.get("/sessions/{session_id}/dashboard")
async def get_dashboard(session_id: str):
    score = await get_data(session_id, 'score')
    if not score:
        return {"error": "Analysis not complete"}
    session = await get_session(session_id)
    recon = await get_data(session_id, 'reconciliation')
    exclusions = await get_data(session_id, 'exclusions')
    accounts = await get_data(session_id, 'accounts_summary')

    # Top 5 accounts by absolute variance
    top5 = sorted([a for a in accounts if a['primary_variance_type'] != 'CLEAN' and a['primary_variance_type'] != 'UNKNOWN'],
                   key=lambda x: abs(x['total_variance']), reverse=True)[:5]

    ambiguous = sum(1 for e in exclusions if e.get('reason_code') == 'ALLOCATION_AMBIGUOUS')

    return {
        'score': score,
        'top_findings': top5,
        'total_exclusions': len(exclusions),
        'ambiguous_allocations': ambiguous,
        'settings': session.get('settings', {}),
        'created_at': session.get('created_at'),
        'completed_at': session.get('completed_at')
    }

# =============================================================================
# ACCOUNTS
# =============================================================================
@api.get("/sessions/{session_id}/accounts")
async def get_accounts(session_id: str, variance_type: Optional[str] = None,
                       match_type: Optional[str] = None, search: Optional[str] = None,
                       sort_by: Optional[str] = None, sort_dir: Optional[str] = 'desc',
                       component_filter: Optional[str] = None):
    accounts = await get_data(session_id, 'accounts_summary')
    if not accounts:
        return {"accounts": [], "total": 0}

    # Filters
    if variance_type:
        types = variance_type.split(',')
        accounts = [a for a in accounts if a['primary_variance_type'] in types]
    if match_type:
        accounts = [a for a in accounts if a['match_type'] == match_type]
    if search:
        sl = search.lower()
        accounts = [a for a in accounts if sl in a['account_name'].lower() or sl in a.get('rsx_id', '').lower()]

    # Component filter for drill-down
    if component_filter == 'entity_match':
        accounts = [a for a in accounts if a['match_type'] in ['fuzzy_confirmed', 'fuzzy', 'unmatched']]
    elif component_filter == 'billing_coverage':
        accounts = [a for a in accounts if a['primary_variance_type'] == 'MISSING_INVOICE']
    elif component_filter == 'variance':
        accounts = [a for a in accounts if a['primary_variance_type'] not in ['CLEAN', 'UNKNOWN']]
    elif component_filter == 'lineage':
        accounts = [a for a in accounts if a['lineage_status'] != 'Complete']

    # Sort
    if sort_by:
        reverse = sort_dir == 'desc'
        accounts = sorted(accounts, key=lambda x: x.get(sort_by, 0) if isinstance(x.get(sort_by, 0), (int, float)) else str(x.get(sort_by, '')), reverse=reverse)

    return {"accounts": accounts, "total": len(accounts)}

# =============================================================================
# LINEAGE
# =============================================================================
@api.get("/sessions/{session_id}/accounts/{rsx_id}")
async def get_lineage(session_id: str, rsx_id: str):
    recon = await get_data(session_id, 'reconciliation')
    entities = await get_data(session_id, 'rsx_entities')
    entity = next((e for e in entities if e['rsx_id'] == rsx_id), None)
    if not entity:
        return {"error": "Entity not found"}

    segments = [r for r in recon if r['rsx_id'] == rsx_id]
    subs = list(set(r['sub_id'] for r in segments))
    sub_data = {}
    for sid in subs:
        sub_segs = sorted([r for r in segments if r['sub_id'] == sid], key=lambda x: x['period'])
        sub_data[sid] = {
            'segments': sub_segs,
            'total_expected': r2(sum(s['expected_amount'] for s in sub_segs)),
            'total_invoiced': r2(sum(s['invoiced_amount'] for s in sub_segs)),
            'total_credit_notes': r2(sum(s['credit_notes_amount'] for s in sub_segs)),
            'total_collected': r2(sum(s['collected_amount'] for s in sub_segs)),
            'total_variance': r2(sum(s['variance'] for s in sub_segs))
        }

    return {
        'entity': entity,
        'subscriptions': subs,
        'subscription_data': sub_data,
        'total_expected': r2(sum(s['expected_amount'] for s in segments)),
        'total_invoiced': r2(sum(s['invoiced_amount'] for s in segments)),
        'total_variance': r2(sum(s['variance'] for s in segments))
    }

# =============================================================================
# EXCLUSIONS
# =============================================================================
@api.get("/sessions/{session_id}/exclusions")
async def get_exclusions(session_id: str, reason_code: Optional[str] = None):
    exclusions = await get_data(session_id, 'exclusions')
    if reason_code:
        exclusions = [e for e in exclusions if e.get('reason_code') == reason_code]
    # Summary by reason code
    summary = {}
    for e in await get_data(session_id, 'exclusions'):
        rc = e.get('reason_code', 'UNKNOWN')
        summary[rc] = summary.get(rc, 0) + 1
    return {"exclusions": exclusions, "total": len(exclusions), "summary": summary}

# =============================================================================
# EXPORT
# =============================================================================
@api.get("/sessions/{session_id}/export/accounts")
async def export_accounts(session_id: str, variance_type: Optional[str] = None):
    accounts = await get_data(session_id, 'accounts_summary')
    if variance_type:
        types = variance_type.split(',')
        accounts = [a for a in accounts if a['primary_variance_type'] in types]

    output = io.StringIO()
    if accounts:
        writer = csv.DictWriter(output, fieldnames=['rsx_id','account_name','match_type','subscriptions','periods','expected_total','invoiced_total','credit_notes_total','total_variance','primary_variance_type','lineage_status','currency'])
        writer.writeheader()
        for a in accounts:
            writer.writerow({k: a.get(k, '') for k in writer.fieldnames})

    return StreamingResponse(io.BytesIO(output.getvalue().encode()),
                             media_type='text/csv',
                             headers={'Content-Disposition': f'attachment; filename=RevStrux_Accounts_{datetime.now().strftime("%Y-%m-%d")}.csv'})

@api.get("/sessions/{session_id}/export/lineage/{rsx_id}")
async def export_lineage(session_id: str, rsx_id: str):
    recon = await get_data(session_id, 'reconciliation')
    segments = sorted([r for r in recon if r['rsx_id'] == rsx_id], key=lambda x: x['period'])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Period','Sub ID','Expected','Invoiced','Credit Notes','Collected','Variance','Status','Prorated'])
    for s in segments:
        writer.writerow([s['period'], s['sub_id'], s['expected_amount'], s['invoiced_amount'],
                         s['credit_notes_amount'], s['collected_amount'], s['variance'], s['status'],
                         'Yes' if s['is_prorated'] else 'No'])

    return StreamingResponse(io.BytesIO(output.getvalue().encode()),
                             media_type='text/csv',
                             headers={'Content-Disposition': f'attachment; filename=RevStrux_Lineage_{rsx_id}_{datetime.now().strftime("%Y-%m-%d")}.csv'})

@api.get("/sessions/{session_id}/export/exclusions")
async def export_exclusions(session_id: str):
    exclusions = await get_data(session_id, 'exclusions')
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['record_type','record_id','reason_code','description','excluded_at','session_id'])
    for e in exclusions:
        writer.writerow([e.get('record_type',''), e.get('record_id',''), e.get('reason_code',''),
                         e.get('description',''), e.get('excluded_at',''), session_id])

    return StreamingResponse(io.BytesIO(output.getvalue().encode()),
                             media_type='text/csv',
                             headers={'Content-Disposition': f'attachment; filename=RevStrux_Exclusions_{session_id}_{datetime.now().strftime("%Y-%m-%d")}.csv'})

@api.get("/sessions/{session_id}/export/report")
async def export_report(session_id: str):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table as RLTable, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    score_data = await get_data(session_id, 'score')
    session = await get_session(session_id)
    if not score_data:
        return {"error": "Analysis not complete"}

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=20, spaceAfter=20)
    elements = []

    elements.append(Paragraph("RevStrux - Structural Integrity Report", title_style))
    elements.append(Paragraph(f"Analysis Period: {session['settings']['period_start']} to {session['settings']['period_end']}", styles['Normal']))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 20))

    cov = score_data.get('coverage', {})
    elements.append(Paragraph(f"<b>Coverage:</b> {cov.get('subscription_pct', 0)}% of subscriptions ({cov.get('subscription_count', 0)} of {cov.get('total_subscriptions', 0)})", styles['Normal']))
    elements.append(Paragraph(f"<b>ARR Coverage:</b> {cov.get('arr_pct', 0)}% (${cov.get('arr_covered', 0):,.0f} of ${cov.get('total_arr', 0):,.0f})", styles['Normal']))
    elements.append(Spacer(1, 15))

    elements.append(Paragraph(f"<b>Structural Integrity Score: {score_data['score']}</b> — {score_data['band']}", styles['Heading2']))
    elements.append(Paragraph(score_data['interpretation'], styles['Normal']))
    elements.append(Spacer(1, 15))

    comp_data = [['Component', 'Score', 'Weight']]
    for k, v in score_data.get('components', {}).items():
        comp_data.append([v['label'], f"{v['value']}%", f"{v['weight']}%"])
    t = RLTable(comp_data, colWidths=[250, 100, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.06, 0.09, 0.16)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 15))

    rar = score_data.get('revenue_at_risk', {})
    elements.append(Paragraph(f"<b>Revenue at Risk: ${rar.get('total', 0):,.2f}</b>", styles['Heading2']))
    risk_data = [['Type', 'Amount', 'Accounts']]
    risk_data.append(['Missing Invoice', f"${rar.get('missing_invoice', 0):,.2f}", str(rar.get('missing_invoice_accounts', 0))])
    risk_data.append(['Under-billed', f"${rar.get('under_billed', 0):,.2f}", str(rar.get('under_billed_accounts', 0))])
    risk_data.append(['Over-billed', f"${rar.get('over_billed', 0):,.2f}", str(rar.get('over_billed_accounts', 0))])
    risk_data.append(['Unpaid AR', f"${rar.get('unpaid_ar', 0):,.2f}", str(rar.get('unpaid_ar_accounts', 0))])
    t2 = RLTable(risk_data, colWidths=[200, 130, 100])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.06, 0.09, 0.16)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))
    elements.append(t2)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Deferred revenue modelling is not included in this analysis.", styles['Italic']))
    elements.append(Paragraph("All calculations are deterministic and rule-based. No AI or machine learning is used.", styles['Italic']))
    elements.append(Paragraph("Generated by RevStrux v1.1", styles['Normal']))

    doc.build(elements)
    buf.seek(0)
    return StreamingResponse(buf, media_type='application/pdf',
                             headers={'Content-Disposition': f'attachment; filename=RevStrux_Report_{datetime.now().strftime("%Y-%m-%d")}.pdf'})

# =============================================================================
# TEMPLATES
# =============================================================================
@api.get("/templates/{file_type}")
async def download_template(file_type: str):
    content = get_template(file_type)
    if not content:
        return {"error": "Unknown file type"}
    return StreamingResponse(io.BytesIO(content.encode()), media_type='text/csv',
                             headers={'Content-Disposition': f'attachment; filename={file_type}_template.csv'})

# =============================================================================
# SYNTHETIC DATA
# =============================================================================
@api.post("/synthetic")
async def generate_synthetic_data():
    try:
        data = generate_synthetic()
        # Create a session and populate it
        sid = str(uuid.uuid4())[:12]
        session = {
            'session_id': sid, 'status': 'created',
            'settings': {'currency': 'USD', 'period_start': data['period_start'], 'period_end': data['period_end']},
            'upload_status': {},
            'validation_result': None, 'identity_result': None,
            'identity_decisions': [], 'decision_history': [],
            'processing_status': {'current_step': None, 'steps': {}, 'log': []},
            'created_at': datetime.now(timezone.utc).isoformat(), 'completed_at': None
        }

        await db.sessions.insert_one(dict(session))

        for ft in ['accounts','customers','subscriptions','invoices','payments','credit_notes']:
            rows = data.get(ft, [])
            await set_data(sid, f'raw_{ft}', rows)
            await update_session(sid, {f'upload_status.{ft}': {'uploaded': True, 'rows': len(rows), 'filename': f'{ft}_synthetic.csv'}})

        return {"session_id": sid, "metadata": data['metadata']}
    except Exception as e:
        logger.error(f"Synthetic generation failed: {e}", exc_info=True)
        return {"error": str(e)}

@api.get("/synthetic/download/{file_type}")
async def download_synthetic(file_type: str):
    data = generate_synthetic()
    rows = data.get(file_type, [])
    if not rows:
        return {"error": "Unknown file type or no data"}

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(io.BytesIO(output.getvalue().encode()), media_type='text/csv',
                             headers={'Content-Disposition': f'attachment; filename={file_type}_synthetic.csv'})

# =============================================================================
# HEALTH
# =============================================================================
@api.get("/")
async def root():
    return {"message": "RevStrux API v1.1", "status": "running"}

# =============================================================================
# APP CONFIG
# =============================================================================
app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
