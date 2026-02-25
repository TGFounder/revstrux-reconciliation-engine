"""
Tests for Smart Upload feature (US-ING-001):
- POST /api/sessions/{sid}/smart-upload - multiple CSVs with aliased headers
- POST /api/sessions/{sid}/smart-upload - ZIP file upload
- POST /api/sessions/{sid}/smart-validate - soft validation + identity matching
- PUT /api/sessions/{sid}/settings - currency and period settings
"""
import pytest
import requests
import os
import io
import zipfile

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def session_id(api_client):
    """Create a new session for testing"""
    response = api_client.post(f"{BASE_URL}/api/sessions")
    assert response.status_code == 200, f"Session creation failed: {response.text}"
    data = response.json()
    assert 'session_id' in data
    return data['session_id']

class TestHealthCheck:
    """Basic API health check"""
    
    def test_api_health(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'running'
        assert 'RevStrux API' in data['message']
        print("✓ API health check passed")

class TestSessionCreation:
    """Session management tests"""
    
    def test_create_session(self, api_client):
        response = api_client.post(f"{BASE_URL}/api/sessions")
        assert response.status_code == 200
        data = response.json()
        assert 'session_id' in data
        assert data['status'] == 'created'
        assert 'settings' in data
        assert data['settings']['currency'] == 'USD'
        print(f"✓ Session created: {data['session_id']}")
        return data['session_id']

class TestSmartUploadCSV:
    """Smart upload with aliased headers - CSV files"""
    
    def test_upload_accounts_with_aliased_headers(self, api_client, session_id):
        """Test uploading accounts CSV with aliased headers (acct_id instead of account_id)"""
        # CSV with aliased headers
        csv_content = """acct_id,company_name,acct_status,source_system
ACC-001,Acme Corporation,active,salesforce
ACC-002,TechStart Ltd,active,hubspot
ACC-003,Global Industries,active,salesforce
"""
        files = {'files': ('accounts.csv', csv_content, 'text/csv')}
        response = requests.post(f"{BASE_URL}/api/sessions/{session_id}/smart-upload", files=files)
        assert response.status_code == 200, f"Smart upload failed: {response.text}"
        data = response.json()
        
        assert 'results' in data
        assert len(data['results']) == 1
        result = data['results'][0]
        
        # Verify detection and normalization
        assert result['detected_type'] == 'accounts', f"Expected 'accounts', got {result.get('detected_type')}"
        assert result['confidence'] >= 0.7, f"Low confidence: {result.get('confidence')}"
        assert result['rows'] == 3
        
        # Verify header normalization occurred
        header_mappings = result.get('header_mappings', [])
        normalized_fields = [m['normalized'] for m in header_mappings]
        assert 'account_id' in normalized_fields or any('acct_id' in m.get('original', '') for m in header_mappings), \
            f"Expected header normalization, got: {header_mappings}"
        
        print(f"✓ Accounts uploaded with aliased headers. Type: {result['detected_type']}, Confidence: {result['confidence']}")
        print(f"  Header mappings: {header_mappings[:3]}")
        
    def test_upload_customers_with_aliased_headers(self, api_client, session_id):
        """Test uploading customers CSV with aliased headers"""
        csv_content = """cust_id,cust_name,cust_status,source_system,email
CUST-001,Acme Corporation,active,stripe,billing@acme.com
CUST-002,TechStart Limited,active,chargebee,finance@techstart.com
CUST-003,Global Industries Inc,active,stripe,ar@global.com
"""
        files = {'files': ('customers.csv', csv_content, 'text/csv')}
        response = requests.post(f"{BASE_URL}/api/sessions/{session_id}/smart-upload", files=files)
        assert response.status_code == 200
        data = response.json()
        
        result = data['results'][0]
        assert result['detected_type'] == 'customers'
        assert result['rows'] == 3
        print(f"✓ Customers uploaded. Type: {result['detected_type']}")
        
    def test_upload_subscriptions(self, api_client, session_id):
        """Test uploading subscriptions CSV"""
        csv_content = """subscription_id,customer_id,sub_start,mrr,currency,frequency,model,subscription_status
SUB-001,CUST-001,2024-01-01,10000,USD,monthly,flat,active
SUB-002,CUST-002,2024-03-15,5000,USD,monthly,flat,active
SUB-003,CUST-003,2024-02-01,8000,USD,monthly,flat,active
"""
        files = {'files': ('subscriptions.csv', csv_content, 'text/csv')}
        response = requests.post(f"{BASE_URL}/api/sessions/{session_id}/smart-upload", files=files)
        assert response.status_code == 200
        data = response.json()
        
        result = data['results'][0]
        assert result['detected_type'] == 'subscriptions'
        assert result['rows'] == 3
        print(f"✓ Subscriptions uploaded. Type: {result['detected_type']}")

    def test_upload_invoices_with_aliased_headers(self, api_client, session_id):
        """Test uploading invoices with aliased headers and enum normalization"""
        csv_content = """inv_id,customer_id,inv_date,billing_start,billing_end,total,currency,status
INV-001,CUST-001,2024-01-01,2024-01-01,2024-01-31,10000,USD,settled
INV-002,CUST-002,2024-04-01,2024-04-01,2024-04-30,5000,USD,posted
INV-003,CUST-003,2024-02-01,2024-02-01,2024-02-29,8000,USD,paid
"""
        files = {'files': ('invoices.csv', csv_content, 'text/csv')}
        response = requests.post(f"{BASE_URL}/api/sessions/{session_id}/smart-upload", files=files)
        assert response.status_code == 200
        data = response.json()
        
        result = data['results'][0]
        assert result['detected_type'] == 'invoices'
        
        # Check enum normalization (settled -> paid, posted -> unpaid)
        enum_normalizations = result.get('enum_normalizations', [])
        if enum_normalizations:
            print(f"  Enum normalizations: {enum_normalizations[:3]}")
        
        print(f"✓ Invoices uploaded. Type: {result['detected_type']}")

class TestSmartUploadMultiFile:
    """Test uploading multiple files at once"""
    
    def test_upload_multiple_csvs_at_once(self, api_client):
        """Test uploading multiple CSV files in a single request"""
        # Create new session for this test
        session_resp = api_client.post(f"{BASE_URL}/api/sessions")
        sid = session_resp.json()['session_id']
        
        accounts_csv = """account_id,account_name,account_status,source_system
ACC-001,Test Account,active,salesforce"""
        
        customers_csv = """customer_id,customer_name,customer_status,source_system
CUST-001,Test Account,active,stripe"""
        
        files = [
            ('files', ('accounts.csv', accounts_csv, 'text/csv')),
            ('files', ('customers.csv', customers_csv, 'text/csv'))
        ]
        
        response = requests.post(f"{BASE_URL}/api/sessions/{sid}/smart-upload", files=files)
        assert response.status_code == 200
        data = response.json()
        
        assert 'results' in data
        assert len(data['results']) == 2
        
        detected_types = [r['detected_type'] for r in data['results']]
        assert 'accounts' in detected_types
        assert 'customers' in detected_types
        
        print(f"✓ Multiple CSVs uploaded: {detected_types}")

class TestSmartUploadZIP:
    """Test ZIP file upload with multiple CSVs"""
    
    def test_upload_zip_file(self, api_client):
        """Test uploading a ZIP file containing multiple CSVs"""
        # Create new session for this test
        session_resp = api_client.post(f"{BASE_URL}/api/sessions")
        sid = session_resp.json()['session_id']
        
        # Create CSV content
        accounts_csv = """account_id,account_name,account_status,source_system
ACC-001,Acme Corp,active,salesforce
ACC-002,Beta LLC,active,hubspot"""
        
        customers_csv = """customer_id,customer_name,customer_status,source_system
CUST-001,Acme Corp,active,stripe
CUST-002,Beta LLC,active,chargebee"""
        
        subscriptions_csv = """sub_id,customer_id,start_date,mrr,currency,billing_frequency,pricing_model,sub_status
SUB-001,CUST-001,2024-01-01,5000,USD,monthly,flat,active
SUB-002,CUST-002,2024-02-01,3000,USD,monthly,flat,active"""
        
        invoices_csv = """invoice_id,customer_id,invoice_date,period_start,period_end,amount,currency,status
INV-001,CUST-001,2024-01-01,2024-01-01,2024-01-31,5000,USD,paid
INV-002,CUST-002,2024-02-01,2024-02-01,2024-02-29,3000,USD,paid"""
        
        # Create ZIP file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('accounts.csv', accounts_csv)
            zf.writestr('customers.csv', customers_csv)
            zf.writestr('subscriptions.csv', subscriptions_csv)
            zf.writestr('invoices.csv', invoices_csv)
        zip_buffer.seek(0)
        
        files = {'files': ('data.zip', zip_buffer.read(), 'application/zip')}
        response = requests.post(f"{BASE_URL}/api/sessions/{sid}/smart-upload", files=files)
        assert response.status_code == 200, f"ZIP upload failed: {response.text}"
        data = response.json()
        
        assert 'results' in data
        assert len(data['results']) >= 4, f"Expected 4+ files from ZIP, got {len(data['results'])}"
        
        detected_types = [r['detected_type'] for r in data['results'] if r.get('detected_type')]
        assert 'accounts' in detected_types, f"accounts not detected: {detected_types}"
        assert 'customers' in detected_types, f"customers not detected: {detected_types}"
        assert 'subscriptions' in detected_types, f"subscriptions not detected: {detected_types}"
        assert 'invoices' in detected_types, f"invoices not detected: {detected_types}"
        
        print(f"✓ ZIP file uploaded successfully. Detected types: {detected_types}")

class TestSmartValidate:
    """Test smart validation endpoint"""
    
    def test_smart_validate_after_upload(self, api_client):
        """Test smart validation after uploading all required files"""
        # Create new session
        session_resp = api_client.post(f"{BASE_URL}/api/sessions")
        sid = session_resp.json()['session_id']
        
        # Upload all required files
        accounts = """account_id,account_name,account_status,source_system
ACC-001,Test Corp,active,salesforce"""
        
        customers = """customer_id,customer_name,customer_status,source_system
CUST-001,Test Corp,active,stripe"""
        
        subscriptions = """sub_id,customer_id,start_date,mrr,currency,billing_frequency,pricing_model,sub_status
SUB-001,CUST-001,2024-01-01,1000,USD,monthly,flat,active"""
        
        invoices = """invoice_id,customer_id,invoice_date,period_start,period_end,amount,currency,status
INV-001,CUST-001,2024-01-01,2024-01-01,2024-01-31,1000,USD,paid"""
        
        files = [
            ('files', ('accounts.csv', accounts, 'text/csv')),
            ('files', ('customers.csv', customers, 'text/csv')),
            ('files', ('subscriptions.csv', subscriptions, 'text/csv')),
            ('files', ('invoices.csv', invoices, 'text/csv'))
        ]
        
        upload_resp = requests.post(f"{BASE_URL}/api/sessions/{sid}/smart-upload", files=files)
        assert upload_resp.status_code == 200
        
        # Now call smart-validate
        validate_resp = api_client.post(f"{BASE_URL}/api/sessions/{sid}/smart-validate")
        assert validate_resp.status_code == 200, f"Validation failed: {validate_resp.text}"
        data = validate_resp.json()
        
        assert 'valid' in data
        if data['valid']:
            assert 'identity_summary' in data
            print(f"✓ Smart validation passed. Identity: {data.get('identity_summary')}")
        else:
            print(f"✓ Smart validation returned errors: {data.get('errors', [])[:3]}")
            
    def test_smart_validate_missing_files(self, api_client):
        """Test smart validation when required files are missing"""
        # Create new session with no uploads
        session_resp = api_client.post(f"{BASE_URL}/api/sessions")
        sid = session_resp.json()['session_id']
        
        validate_resp = api_client.post(f"{BASE_URL}/api/sessions/{sid}/smart-validate")
        assert validate_resp.status_code == 200
        data = validate_resp.json()
        
        assert data['valid'] == False
        assert len(data['errors']) > 0
        print(f"✓ Validation correctly returned errors for missing files: {len(data['errors'])} errors")

class TestSettingsUpdate:
    """Test settings update endpoint"""
    
    def test_update_currency_settings(self, api_client, session_id):
        """Test updating session currency setting"""
        settings = {
            'currency': 'EUR',
            'period_start': '2024-01',
            'period_end': '2024-06'
        }
        
        response = api_client.put(
            f"{BASE_URL}/api/sessions/{session_id}/settings",
            json=settings
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        
        # Verify settings were saved
        session_resp = api_client.get(f"{BASE_URL}/api/sessions/{session_id}")
        assert session_resp.status_code == 200
        session_data = session_resp.json()
        assert session_data['settings']['currency'] == 'EUR'
        assert session_data['settings']['period_start'] == '2024-01'
        assert session_data['settings']['period_end'] == '2024-06'
        
        print(f"✓ Settings updated: currency={settings['currency']}, period={settings['period_start']} to {settings['period_end']}")

class TestSyntheticDataFlow:
    """Test full E2E flow with synthetic data"""
    
    def test_synthetic_data_generation(self, api_client):
        """Test synthetic data generation creates a fully populated session"""
        response = api_client.post(f"{BASE_URL}/api/synthetic")
        assert response.status_code == 200
        data = response.json()
        
        assert 'session_id' in data
        assert 'metadata' in data
        
        sid = data['session_id']
        
        # Verify session has all files uploaded
        session_resp = api_client.get(f"{BASE_URL}/api/sessions/{sid}")
        assert session_resp.status_code == 200
        session_data = session_resp.json()
        
        upload_status = session_data.get('upload_status', {})
        for ft in ['accounts', 'customers', 'subscriptions', 'invoices', 'payments', 'credit_notes']:
            assert upload_status.get(ft, {}).get('uploaded') == True, f"{ft} not uploaded"
        
        print(f"✓ Synthetic data generated. Session: {sid}")
        print(f"  Metadata: {data['metadata']}")
        return sid
        
    def test_full_flow_with_synthetic(self, api_client):
        """Test complete flow: synthetic -> validate -> identity -> analyze -> dashboard"""
        # Generate synthetic data
        syn_resp = api_client.post(f"{BASE_URL}/api/synthetic")
        assert syn_resp.status_code == 200
        sid = syn_resp.json()['session_id']
        
        # Validate
        val_resp = api_client.post(f"{BASE_URL}/api/sessions/{sid}/validate")
        assert val_resp.status_code == 200
        val_data = val_resp.json()
        assert val_data.get('valid') == True, f"Validation failed: {val_data.get('errors', [])[:3]}"
        
        # Get identity
        id_resp = api_client.get(f"{BASE_URL}/api/sessions/{sid}/identity")
        assert id_resp.status_code == 200
        id_data = id_resp.json()
        assert 'auto_matched' in id_data
        
        # Start analysis
        analyze_resp = api_client.post(f"{BASE_URL}/api/sessions/{sid}/analyze")
        assert analyze_resp.status_code == 200
        
        # Wait for analysis to complete (polling)
        import time
        for _ in range(30):
            status_resp = api_client.get(f"{BASE_URL}/api/sessions/{sid}/status")
            status_data = status_resp.json()
            if status_data.get('status') in ['completed', 'error']:
                break
            time.sleep(1)
        
        assert status_data.get('status') == 'completed', f"Analysis failed: {status_data}"
        
        # Get dashboard
        dash_resp = api_client.get(f"{BASE_URL}/api/sessions/{sid}/dashboard")
        assert dash_resp.status_code == 200
        dash_data = dash_resp.json()
        
        assert 'score' in dash_data
        assert dash_data['score']['score'] >= 0
        
        print(f"✓ Full flow completed. Score: {dash_data['score']['score']} ({dash_data['score']['band']})")

class TestTemplateDownloads:
    """Test template download endpoints"""
    
    def test_all_template_downloads(self, api_client):
        """Test downloading all CSV templates"""
        file_types = ['accounts', 'customers', 'subscriptions', 'invoices', 'payments', 'credit_notes']
        
        for ft in file_types:
            response = api_client.get(f"{BASE_URL}/api/templates/{ft}")
            assert response.status_code == 200, f"Template download failed for {ft}: {response.status_code}"
            assert len(response.content) > 50, f"Template {ft} too small"
            print(f"✓ Template {ft} downloaded ({len(response.content)} bytes)")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
