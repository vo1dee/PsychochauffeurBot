#!/usr/bin/env python3
"""
Demo script to test the test recommendation engine components.

This script demonstrates the functionality of:
1. Critical functionality analyzer
2. Test case generator  
3. Edge case analyzer
"""

import asyncio
import sys
from pathlib import Path

# Add the test_suite_optimizer to the path
sys.path.insert(0, str(Path(__file__).parent))

from test_suite_optimizer.critical_functionality_analyzer import CriticalFunctionalityAnalyzer
from test_suite_optimizer.test_case_generator import TestCaseGenerator
from test_suite_optimizer.edge_case_analyzer import EdgeCaseAnalyzer


async def demo_critical_functionality_analyzer():
    """Demo the critical functionality analyzer."""
    print("=" * 60)
    print("CRITICAL FUNCTIONALITY ANALYZER DEMO")
    print("=" * 60)
    
    analyzer = CriticalFunctionalityAnalyzer()
    
    # Analyze current project
    critical_paths = await analyzer.analyze(".")
    
    print(f"Found {len(critical_paths)} critical paths")
    print("\nTop 5 most critical paths:")
    
    for i, path in enumerate(critical_paths[:5]):
        print(f"\n{i+1}. {path.module}.{path.function_or_method}")
        print(f"   Criticality Score: {path.criticality_score:.3f}")
        print(f"   Risk Factors: {', '.join(path.risk_factors)}")
        print(f"   Recommended Tests: {[t.value for t in path.recommended_test_types]}")
    
    if analyzer.has_warnings():
        print(f"\nWarnings: {len(analyzer.get_warnings())}")
        for warning in analyzer.get_warnings()[:3]:
            print(f"  - {warning}")
    
    return critical_paths


async def demo_test_case_generator():
    """Demo the test case generator."""
    print("\n" + "=" * 60)
    print("TEST CASE GENERATOR DEMO")
    print("=" * 60)
    
    generator = TestCaseGenerator()
    
    # Generate recommendations for current project
    recommendations = await generator.analyze(".")
    
    print(f"Generated {len(recommendations)} test recommendations")
    print("\nTop 5 highest priority recommendations:")
    
    for i, rec in enumerate(recommendations[:5]):
        print(f"\n{i+1}. {rec.module}.{rec.functionality}")
        print(f"   Priority: {rec.priority.value}")
        print(f"   Test Type: {rec.test_type.value}")
        print(f"   Description: {rec.description}")
        print(f"   Rationale: {rec.rationale}")
        print(f"   Effort: {rec.estimated_effort}")
    
    if generator.has_warnings():
        print(f"\nWarnings: {len(generator.get_warnings())}")
        for warning in generator.get_warnings()[:3]:
            print(f"  - {warning}")
    
    return recommendations


async def demo_edge_case_analyzer():
    """Demo the edge case analyzer."""
    print("\n" + "=" * 60)
    print("EDGE CASE ANALYZER DEMO")
    print("=" * 60)
    
    analyzer = EdgeCaseAnalyzer()
    
    # Analyze current project for edge cases
    edge_recommendations = await analyzer.analyze(".")
    
    print(f"Found {len(edge_recommendations)} edge case recommendations")
    print("\nTop 5 edge case recommendations:")
    
    for i, rec in enumerate(edge_recommendations[:5]):
        print(f"\n{i+1}. {rec.module}.{rec.functionality}")
        print(f"   Priority: {rec.priority.value}")
        print(f"   Test Type: {rec.test_type.value}")
        print(f"   Description: {rec.description}")
        print(f"   Rationale: {rec.rationale}")
    
    if analyzer.has_warnings():
        print(f"\nWarnings: {len(analyzer.get_warnings())}")
        for warning in analyzer.get_warnings()[:3]:
            print(f"  - {warning}")
    
    return edge_recommendations


async def demo_integration():
    """Demo integration between components."""
    print("\n" + "=" * 60)
    print("INTEGRATION DEMO")
    print("=" * 60)
    
    # Use critical paths to generate targeted recommendations
    critical_analyzer = CriticalFunctionalityAnalyzer()
    generator = TestCaseGenerator()
    
    critical_paths = await critical_analyzer.analyze(".")
    targeted_recommendations = await generator.generate_recommendations_from_critical_paths(
        critical_paths[:10]  # Top 10 critical paths
    )
    
    print(f"Generated {len(targeted_recommendations)} targeted recommendations from critical paths")
    print("\nTop 3 targeted recommendations:")
    
    for i, rec in enumerate(targeted_recommendations[:3]):
        print(f"\n{i+1}. {rec.module}.{rec.functionality}")
        print(f"   Priority: {rec.priority.value}")
        print(f"   Test Type: {rec.test_type.value}")
        print(f"   Description: {rec.description}")
        print(f"   Implementation Example:")
        # Show first few lines of implementation example
        example_lines = rec.implementation_example.strip().split('\n')[:5]
        for line in example_lines:
            print(f"     {line}")
        if len(rec.implementation_example.strip().split('\n')) > 5:
            print("     ...")


async def main():
    """Run all demos."""
    print("Test Recommendation Engine Demo")
    print("This demo shows the functionality of the test recommendation system")
    
    try:
        # Run individual component demos
        critical_paths = await demo_critical_functionality_analyzer()
        recommendations = await demo_test_case_generator()
        edge_recommendations = await demo_edge_case_analyzer()
        
        # Run integration demo
        await demo_integration()
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Critical Paths Found: {len(critical_paths)}")
        print(f"Test Recommendations: {len(recommendations)}")
        print(f"Edge Case Recommendations: {len(edge_recommendations)}")
        print(f"Total Recommendations: {len(recommendations) + len(edge_recommendations)}")
        
        print("\nTest recommendation engine demo completed successfully!")
        
    except Exception as e:
        print(f"Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)