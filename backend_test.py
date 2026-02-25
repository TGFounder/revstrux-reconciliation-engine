#!/usr/bin/env python3
"""
RevStrux Backend API Testing Suite
Tests all API endpoints systematically
"""
import requests
import sys
import time
import json
from datetime import datetime

class RevStruxAPITester:
    def __init__(self, base_url="https://rre-reconcile.preview.emergentagent.com"):
        self.base_url = base_url
        self.session_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
        
        result = {
            "test": name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
        if details:
            print(f"    {details}")
        return success

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=30):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}" if not endpoint.startswith('/') else f"{self.base_url}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=timeout)
            else:
                return self.log_test(name, False, f"Unsupported method: {method}")

            success = response.status_code == expected_status
            details = f"Status: {response.status_code}"
            
            if success:
                try:
                    resp_data = response.json()
                    if 'session_id' in resp_data:
                        self.session_id = resp_data['session_id']
                    return self.log_test(name, True, f"{details}, Response OK"), resp_data
                except:
                    return self.log_test(name, True, details), {}
            else:
                try:
                    error_text = response.text[:200]
                except:
                    error_text = "Could not read response"
                return self.log_test(name, False, f"{details}, Expected {expected_status}. Error: {error_text}"), {}

        except requests.exceptions.Timeout:
            return self.log_test(name, False, f"Request timeout after {timeout}s"), {}
        except Exception as e:
            return self.log_test(name, False, f"Request failed: {str(e)}"), {}

    def test_health_check(self):
        """Test API health endpoint"""
        print("\n🔍 Testing API Health...")
        return self.run_test("API Health Check", "GET", "", 200)

    def test_session_creation(self):
        """Test session creation"""
        print("\n🔍 Testing Session Management...")
        success, data = self.run_test("Create Session", "POST", "sessions", 200)
        if success and self.session_id:
            self.run_test("Get Session Info", "GET", f"sessions/{self.session_id}", 200)
            return True
        return False

    def test_synthetic_data_generation(self):
        """Test synthetic data generation"""
        print("\n🔍 Testing Synthetic Data Generation...")
        success, data = self.run_test("Generate Synthetic Data", "POST", "synthetic", 200)
        if success and self.session_id:
            # Test file validation after synthetic load
            time.sleep(2)  # Allow synthetic data to populate
            self.run_test("Validate Synthetic Files", "POST", f"sessions/{self.session_id}/validate", 200)
            return True
        return False

    def test_identity_endpoints(self):
        """Test identity matching endpoints"""
        if not self.session_id:
            return False
            
        print("\n🔍 Testing Identity Matching...")
        
        # Get identity data
        success, data = self.run_test("Get Identity Data", "GET", f"sessions/{self.session_id}/identity", 200)
        if not success:
            return False
            
        # Test decision making if fuzzy matches exist
        needs_review = data.get('needs_review', [])
        if needs_review:
            match_id = needs_review[0].get('match_id')
            if match_id:
                decision_data = {"match_id": match_id, "decision": "confirmed"}
                self.run_test("Make Identity Decision", "POST", f"sessions/{self.session_id}/identity/decide", 200, decision_data)
                
                # Test undo
                self.run_test("Undo Identity Decision", "POST", f"sessions/{self.session_id}/identity/undo", 200)
        
        return True

    def test_analysis_processing(self):
        """Test analysis processing"""
        if not self.session_id:
            return False
            
        print("\n🔍 Testing Analysis Processing...")
        
        # Start analysis
        success, _ = self.run_test("Start Analysis", "POST", f"sessions/{self.session_id}/analyze", 200)
        if not success:
            return False
            
        # Poll status until completion (with timeout)
        max_polls = 30
        for i in range(max_polls):
            time.sleep(2)
            success, data = self.run_test(f"Check Status (poll {i+1})", "GET", f"sessions/{self.session_id}/status", 200)
            if success and data.get('status') == 'completed':
                print(f"    Analysis completed after {i+1} polls")
                return True
            elif success and data.get('status') == 'error':
                self.log_test("Analysis Processing", False, f"Analysis failed: {data.get('processing_status', {}).get('error', 'Unknown error')}")
                return False
                
        self.log_test("Analysis Processing", False, "Analysis did not complete within timeout")
        return False

    def test_dashboard_endpoints(self):
        """Test dashboard and results endpoints"""
        if not self.session_id:
            return False
            
        print("\n🔍 Testing Dashboard & Results...")
        
        # Test dashboard
        success, _ = self.run_test("Get Dashboard Data", "GET", f"sessions/{self.session_id}/dashboard", 200)
        if not success:
            return False
            
        # Test accounts endpoint
        self.run_test("Get Accounts List", "GET", f"sessions/{self.session_id}/accounts", 200)
        
        # Test accounts with filters
        self.run_test("Get Accounts (with filters)", "GET", f"sessions/{self.session_id}/accounts?variance_type=MISSING_INVOICE&sort_by=total_variance", 200)
        
        # Test exclusions
        self.run_test("Get Exclusions", "GET", f"sessions/{self.session_id}/exclusions", 200)
        
        return True

    def test_lineage_endpoints(self):
        """Test lineage (account detail) endpoints"""
        if not self.session_id:
            return False
            
        print("\n🔍 Testing Lineage Endpoints...")
        
        # Get accounts to find a real RSX ID
        success, data = self.run_test("Get Accounts for Lineage", "GET", f"sessions/{self.session_id}/accounts", 200)
        if success and data.get('accounts'):
            rsx_id = data['accounts'][0].get('rsx_id')
            if rsx_id:
                self.run_test("Get Account Lineage", "GET", f"sessions/{self.session_id}/accounts/{rsx_id}", 200)
                return True
        
        return False

    def test_export_endpoints(self):
        """Test export endpoints"""
        if not self.session_id:
            return False
            
        print("\n🔍 Testing Export Endpoints...")
        
        # Test CSV exports (these return files, so 200 status is success)
        self.run_test("Export Accounts CSV", "GET", f"sessions/{self.session_id}/export/accounts", 200)
        self.run_test("Export Exclusions CSV", "GET", f"sessions/{self.session_id}/export/exclusions", 200)
        
        # Test PDF report
        self.run_test("Export PDF Report", "GET", f"sessions/{self.session_id}/export/report", 200)
        
        return True

    def test_template_downloads(self):
        """Test template download endpoints"""
        print("\n🔍 Testing Template Downloads...")
        
        file_types = ['accounts', 'customers', 'subscriptions', 'invoices', 'payments', 'credit_notes']
        
        for file_type in file_types:
            self.run_test(f"Download {file_type} template", "GET", f"templates/{file_type}", 200)
            
        return True

    def run_comprehensive_test_suite(self):
        """Run the complete test suite"""
        print("🚀 Starting RevStrux API Comprehensive Test Suite")
        print(f"🎯 Testing against: {self.base_url}")
        print("=" * 60)
        
        # Test sequence - order matters for state dependencies
        test_sequence = [
            ("API Health Check", self.test_health_check),
            ("Session Creation", self.test_session_creation),
            ("Synthetic Data Generation", self.test_synthetic_data_generation),
            ("Identity Matching", self.test_identity_endpoints),
            ("Analysis Processing", self.test_analysis_processing),
            ("Dashboard & Results", self.test_dashboard_endpoints),
            ("Lineage Details", self.test_lineage_endpoints),
            ("Export Functions", self.test_export_endpoints),
            ("Template Downloads", self.test_template_downloads),
        ]
        
        failed_sections = []
        
        for section_name, test_func in test_sequence:
            try:
                success = test_func()
                if not success:
                    failed_sections.append(section_name)
                    # Don't continue if critical early tests fail
                    if section_name in ["API Health Check", "Session Creation"]:
                        print(f"\n💥 Critical failure in {section_name}. Stopping test suite.")
                        break
            except Exception as e:
                print(f"\n💥 Exception in {section_name}: {str(e)}")
                failed_sections.append(section_name)
        
        # Print final results
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/max(self.tests_run,1)*100):.1f}%")
        
        if failed_sections:
            print(f"\n❌ Failed Sections: {', '.join(failed_sections)}")
        else:
            print("\n✅ All sections completed successfully!")
            
        # Return success if most tests passed and no critical failures
        success_rate = (self.tests_passed / max(self.tests_run, 1)) * 100
        return success_rate >= 80 and "API Health Check" not in failed_sections

def main():
    tester = RevStruxAPITester()
    success = tester.run_comprehensive_test_suite()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())