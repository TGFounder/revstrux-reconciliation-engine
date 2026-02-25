# RevStrux - Revenue Reconciliation Engine v1.2

## Original Problem Statement
Build a production-ready SaaS web application for global RevOps and Order-to-Cash teams. The tool deterministically matches CRM bookings with billing data, calculates period overlap, applies day-count proration, surfaces mismatches, and provides CFO-grade reconciliation views. All logic is rule-based - NO AI.

## Architecture
- **Frontend**: React 18 + Tailwind CSS + shadcn/ui + react-router-dom v7
- **Backend**: FastAPI (Python) + Motor (async MongoDB driver)
- **Database**: MongoDB (sessions, session_data collections)
- **PDF**: ReportLab for score report generation

## User Personas
1. **RevOps Manager**: Uploads CRM and billing data, reviews identity matches, analyzes reconciliation results
2. **Revenue Accountant**: Reviews variance details, drills into lineage, exports for audit
3. **Finance Controller/CFO**: Reviews score dashboard, downloads PDF report

## Core Requirements
- Smart unified upload: multiple CSVs or single ZIP file
- Automatic file type detection from CSV headers
- Header normalization (alias mapping: acct_id -> account_id, etc.)
- Enum value normalization (posted -> unpaid, settled -> paid, etc.)
- Soft validation with warnings (not hard-blocking errors)
- Three-pass identity matching (exact -> fuzzy -> email signal)
- Revenue segment generation with day-count proration
- Period overlap invoice matching
- Credit note reconciliation (linked + standalone)
- Variance classification (CLEAN/MISSING_INVOICE/UNDER_BILLED/OVER_BILLED/UNPAID_AR)
- 4-component Structural Integrity Score
- Currency display using session currency symbol
- Custom date selection for analysis period
- CSV + PDF export

## What's Been Implemented

### V1.0 (Initial Build - Feb 2026)
- [x] Full 8-screen frontend (Upload, Identity, Processing, Dashboard, Accounts, Lineage, Exclusions, Export)
- [x] Complete backend with 20+ API endpoints
- [x] Deterministic reconciliation engine
- [x] Synthetic dataset generator
- [x] CSV upload with drag-and-drop + file validation
- [x] Three-pass identity matching with fuzzy match review queue
- [x] Revenue segment generation with flat + ramp + proration
- [x] Period overlap invoice matching with proportional allocation
- [x] Credit note reconciliation (linked and standalone)
- [x] 4-component scoring with color-coded bands
- [x] Score Dashboard with coverage metrics, revenue at risk, quick findings
- [x] Account table with sorting, filtering, searching
- [x] Lineage drill-down with subscription tabs
- [x] Exclusions log with reason codes
- [x] CSV export (accounts, lineage, exclusions)
- [x] PDF score report (ReportLab)
- [x] Template downloads for all 6 file types
- [x] Session-based (no auth, no data retention beyond session)

### V1.2 (US-ING-001: Smart Unified Upload - Feb 2026)
- [x] Smart upload endpoint (POST /api/sessions/{sid}/smart-upload)
- [x] Multi-CSV or ZIP file upload support
- [x] Automatic file type detection from headers with confidence scores
- [x] Header alias normalization (50+ aliases mapped to canonical names)
- [x] Enum value normalization for statuses
- [x] Soft validation (warnings for non-critical issues, block only showstoppers)
- [x] Smart validate endpoint with identity matching integration
- [x] Refactored UploadPage with single smart drop zone
- [x] Detection results UI showing types, confidence, normalization summary
- [x] Currency selector with multi-currency support (10 currencies)
- [x] Custom date selection with calendar date pickers
- [x] RevStrux logo in sidebar
- [x] Dashboard currency display using session currency symbol
- [x] Reset upload functionality

## Prioritized Backlog

### P1 (High value)
- Configurable tolerance (currently hardcoded at $1.00)
- Undo last reconciliation run (session history rollback)
- Multi-user authentication (JWT or OAuth)
- Performance testing with 10K+ records

### P2 (Nice to have)
- Pagination for accounts table
- Advanced search with field-specific queries
- Score trend tracking across sessions
- Email domain matching in identity pass 3

### P3 (Future)
- Deferred Revenue modeling
- Trend dashboards
- Multi-period forecasting
- FX rate modeling
- ERP integrations

## Key API Endpoints
- POST /api/sessions - Create session
- GET /api/sessions/{sid} - Get session info
- PUT /api/sessions/{sid}/settings - Update settings
- POST /api/sessions/{sid}/smart-upload - Smart multi-file upload
- POST /api/sessions/{sid}/smart-validate - Soft validation + identity
- POST /api/sessions/{sid}/upload/{file_type} - Legacy single file upload
- POST /api/sessions/{sid}/validate - Legacy strict validation
- GET /api/sessions/{sid}/identity - Get identity results
- POST /api/sessions/{sid}/identity/decide - Confirm/reject fuzzy match
- POST /api/sessions/{sid}/analyze - Start analysis
- GET /api/sessions/{sid}/status - Get processing status
- GET /api/sessions/{sid}/dashboard - Dashboard data
- GET /api/sessions/{sid}/accounts - Accounts list
- GET /api/sessions/{sid}/accounts/{rsx_id} - Lineage drill-down
- GET /api/sessions/{sid}/exclusions - Exclusions list
- GET /api/sessions/{sid}/export/* - CSV/PDF exports
- POST /api/synthetic - Generate synthetic test data

## Database Schema (MongoDB)
- **database**: from DB_NAME env var
- **collections**:
  - sessions: { session_id, status, settings, upload_status, validation_result, identity_result, ... }
  - session_data: { session_id, type, data } - stores raw files, segments, reconciliation results, etc.
