#!/usr/bin/env python3
"""
Mobile UI Integration Test
Tests basic functionality and responsiveness of the mobile dashboard
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestMobileIntegration(unittest.TestCase):
    """Test mobile dashboard integration"""
    
    def setUp(self):
        """Set up test client"""
        # Mock the config to avoid dependency issues
        with patch('config.settings.Config') as mock_config:
            mock_config.validate.return_value = []
            mock_config.SECRET_KEY = 'test-key'
            mock_config.DEFAULT_SWITCHES = []
            mock_config.FLASK_DEBUG = False
            
            # Mock inventory
            with patch('config.switch_inventory.inventory') as mock_inventory:
                mock_inventory.add_switch.return_value = True
                
                from app import app
                self.app = app
                self.app.config['TESTING'] = True
                self.client = self.app.test_client()
    
    def test_mobile_route_exists(self):
        """Test that mobile route is accessible"""
        response = self.client.get('/mobile')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'AOS-CX Automation', response.data)
    
    def test_mobile_detection_redirect(self):
        """Test mobile device detection and redirect"""
        # Test with mobile user agent
        response = self.client.get('/', headers={'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'})
        self.assertEqual(response.status_code, 302)  # Redirect
        self.assertIn('/mobile', response.location)
    
    def test_desktop_override(self):
        """Test desktop override parameter"""
        # Test mobile UA with desktop override
        response = self.client.get('/?desktop=true', headers={'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Enhanced PyAOS-CX Automation Toolkit', response.data)
    
    def test_mobile_override(self):
        """Test mobile override parameter"""
        # Test desktop UA with mobile override
        response = self.client.get('/?mobile=true', headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        self.assertEqual(response.status_code, 302)  # Redirect to mobile
        self.assertIn('/mobile', response.location)
    
    def test_desktop_route_exists(self):
        """Test that desktop route still works"""
        response = self.client.get('/', headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Enhanced PyAOS-CX Automation Toolkit', response.data)
    
    def test_api_endpoints_still_work(self):
        """Test that API endpoints are still functional"""
        with patch('app.inventory') as mock_inventory:
            mock_inventory.get_all_switches.return_value = []
            mock_inventory.get_switch_count.return_value = 0
            
            response = self.client.get('/api/switches')
            self.assertEqual(response.status_code, 200)
            
            data = response.get_json()
            self.assertIn('switches', data)
            self.assertIn('count', data)
    
    def test_mobile_template_structure(self):
        """Test mobile template contains required elements"""
        response = self.client.get('/mobile')
        self.assertEqual(response.status_code, 200)
        
        # Check for mobile-specific elements
        self.assertIn(b'nav-tab', response.data)  # Bottom navigation
        self.assertIn(b'tab-content', response.data)  # Tab content areas
        self.assertIn(b'mobile_dashboard.css', response.data)  # Mobile CSS
        self.assertIn(b'mobile_dashboard.js', response.data)  # Mobile JS
        self.assertIn(b'manifest.json', response.data)  # PWA manifest
    
    def test_responsive_meta_tags(self):
        """Test that mobile template has proper responsive meta tags"""
        response = self.client.get('/mobile')
        self.assertEqual(response.status_code, 200)
        
        # Check for mobile viewport and PWA meta tags
        self.assertIn(b'width=device-width', response.data)
        self.assertIn(b'user-scalable=no', response.data)
        self.assertIn(b'apple-mobile-web-app-capable', response.data)
        self.assertIn(b'theme-color', response.data)

class TestFileStructure(unittest.TestCase):
    """Test that all required files exist"""
    
    def test_mobile_template_exists(self):
        """Test mobile template file exists"""
        self.assertTrue(os.path.exists('templates/mobile_dashboard.html'))
    
    def test_mobile_css_exists(self):
        """Test mobile CSS file exists"""
        self.assertTrue(os.path.exists('static/css/mobile_dashboard.css'))
    
    def test_mobile_js_exists(self):
        """Test mobile JavaScript file exists"""
        self.assertTrue(os.path.exists('static/js/mobile_dashboard.js'))
    
    def test_manifest_exists(self):
        """Test PWA manifest file exists"""
        self.assertTrue(os.path.exists('static/manifest.json'))
    
    def test_original_files_preserved(self):
        """Test that original dashboard files are preserved"""
        self.assertTrue(os.path.exists('templates/dashboard.html'))
        self.assertTrue(os.path.exists('static/css/dashboard.css'))
        self.assertTrue(os.path.exists('static/js/dashboard.js'))

class TestContentValidation(unittest.TestCase):
    """Test content validation"""
    
    def test_mobile_css_responsive(self):
        """Test mobile CSS contains responsive breakpoints"""
        with open('static/css/mobile_dashboard.css', 'r') as f:
            css_content = f.read()
        
        # Check for mobile-first responsive design patterns
        self.assertIn('@media (min-width: 640px)', css_content)
        self.assertIn('@media (min-width: 768px)', css_content)
        self.assertIn('@media (min-width: 1024px)', css_content)
        self.assertIn('min-height: 44px', css_content)  # Touch targets
        self.assertIn('touch-action', css_content)  # Touch optimization
    
    def test_mobile_js_functionality(self):
        """Test mobile JavaScript contains required functionality"""
        with open('static/js/mobile_dashboard.js', 'r') as f:
            js_content = f.read()
        
        # Check for mobile-specific features
        self.assertIn('MobileDashboard', js_content)
        self.assertIn('showTab', js_content)
        self.assertIn('setupMobileNavigation', js_content)
        self.assertIn('setupPullToRefresh', js_content)
        self.assertIn('touchstart', js_content)
        self.assertIn('haptic', js_content)  # Haptic feedback
    
    def test_pwa_manifest_structure(self):
        """Test PWA manifest has required structure"""
        import json
        
        with open('static/manifest.json', 'r') as f:
            manifest = json.load(f)
        
        # Check required PWA fields
        self.assertIn('name', manifest)
        self.assertIn('short_name', manifest)
        self.assertIn('start_url', manifest)
        self.assertIn('display', manifest)
        self.assertIn('theme_color', manifest)
        self.assertIn('icons', manifest)
        
        # Check mobile-specific configuration
        self.assertEqual(manifest['display'], 'standalone')
        self.assertEqual(manifest['start_url'], '/mobile')
        self.assertEqual(manifest['theme_color'], '#01A982')

if __name__ == '__main__':
    print("🧪 Running Mobile UI Integration Tests...")
    print("=" * 50)
    
    # Run tests
    unittest.main(verbosity=2, exit=False)
    
    print("\n✅ Mobile UI Integration Tests Complete!")
    print("\n📱 Mobile Dashboard Features:")
    print("• Responsive design with mobile-first approach")
    print("• Touch-optimized navigation and interactions")
    print("• Progressive Web App (PWA) capabilities")
    print("• Automatic device detection and routing")
    print("• Pull-to-refresh functionality")
    print("• Haptic feedback support")
    print("• All existing API functionality preserved")
    print("\n🌐 Access URLs:")
    print("• Desktop: http://localhost:5001/")
    print("• Mobile: http://localhost:5001/mobile")
    print("• Force Desktop: http://localhost:5001/?desktop=true")
    print("• Force Mobile: http://localhost:5001/?mobile=true")