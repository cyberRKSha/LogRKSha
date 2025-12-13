#!/usr/bin/env python3
"""
FIXED Comprehensive test runner
Tests only functions and endpoints that actually exist
"""

import subprocess
import sys
import time
from pathlib import Path
import os

def main():
    print("🧪 FIXED COMPREHENSIVE TEST SUITE")
    print("=" * 50)
    print("Testing only actual functions and endpoints!")
    
    os.chdir(Path(__file__).parent.parent)
    
    test_plan = [
        {
            'name': 'Original Working Tests',
            'command': 'python -m pytest tests/test_utils.py -v',
            'description': 'Your original auth tests (these work)'
        },
        {
            'name': 'Fixed Worker Tests', 
            'command': 'python -m pytest tests/test_worker_utils.py -v',
            'description': 'Fixed worker utility tests'
        },
        {
            'name': 'Fixed API Tests',
            'command': 'python -m pytest tests/test_api.py -v',
            'description': 'Fixed API endpoint tests'
        },
        {
            'name': 'Fixed Integration Tests',
            'command': 'python -m pytest tests/test_dashboard_integration.py -v',
            'description': 'Fixed integration tests'
        },
        {
            'name': 'Fixed Security Tests',
            'command': 'python -m pytest tests/test_security.py -v',
            'description': 'Fixed security tests'
        }
    ]
    
    results = []
    total_start = time.time()
    
    for test in test_plan:
        print(f"\n{'='*50}")
        print(f"🔧 {test['name']}")
        print(f"📝 {test['description']}")
        print(f"{'='*50}")
        
        start_time = time.time()
        result = subprocess.run(test['command'], shell=True, capture_output=False)
        duration = time.time() - start_time
        
        success = result.returncode == 0
        results.append({
            'name': test['name'],
            'success': success,
            'duration': duration
        })
        
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status} {test['name']} ({duration:.2f}s)")
    
    total_duration = time.time() - total_start
    
    # Summary
    print(f"\n{'='*50}")
    print("📊 FIXED TEST RESULTS")
    print(f"{'='*50}")
    
    passed = sum(1 for r in results if r['success'])
    total = len(results)
    
    for result in results:
        status = "✅ PASSED" if result['success'] else "❌ FAILED"
        print(f"{status} {result['name']} ({result['duration']:.2f}s)")
    
    print(f"\n🎯 Results:")
    print(f"   Success rate: {(passed/total)*100:.1f}%")
    print(f"   Total time: {total_duration:.2f} seconds")
    
    if passed == total:
        print(f"\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test suites need attention.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
