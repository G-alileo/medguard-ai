#!/usr/bin/env python3
import os
import sys
import argparse
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medguard_project.settings')
    django.setup()

    from medguard_app.orchestrator.decision_pipeline import DecisionPipeline
except ImportError as e:
    print(f"Error importing Django/MedGuard modules: {e}")
    sys.exit(1)

class ManualTester:
    def __init__(self):
        self.pipeline = DecisionPipeline()

    def test_scenario(self, symptoms, drug, existing_drugs=None):
        """Test a specific scenario and print detailed results."""
        if existing_drugs is None:
            existing_drugs = []

        print("\\n" + "="*60)
        print("              MEDGUARD EVALUATION")
        print("="*60)
        print(f"Symptoms:          {', '.join(symptoms)}")
        print(f"Proposed Drug:     {drug}")
        print(f"Current Medications: {', '.join(existing_drugs) if existing_drugs else 'None'}")
        print("-"*60)

        try:
            result = self.pipeline.evaluate(symptoms, drug, existing_drugs)

            # Display key results
            print(f"\\nRISK ASSESSMENT:")
            print(f"  Risk Level:      {result.get('risk_level', 'Unknown')}")
            print(f"  Risk Score:      {result.get('risk_score', 'Unknown')}/100")
            print(f"  Recommendation:  {result.get('recommendation', {}).get('action', 'Unknown')}")

            # Display findings
            findings = result.get('findings', {})
            print(f"\\nFINDINGS:")
            print(f"  Drug Found:      {findings.get('drug_found', 'Unknown')}")
            print(f"  Treats Symptoms: {findings.get('treats_symptom', 'Unknown')}")
            print(f"  Interactions:    {findings.get('interactions_found', 0)}")
            print(f"  Interaction Risk: {findings.get('interaction_risk_level', 'None')}")

            # Display warnings
            warnings = findings.get('side_effect_warnings', [])
            if warnings:
                print(f"\\nWARNINGS:")
                for warning in warnings:
                    print(f"  • {warning}")

            # Display risk factors
            risk_factors = result.get('risk_factors', [])
            if risk_factors:
                print(f"\\nRISK FACTORS:")
                for factor in risk_factors:
                    print(f"  • {factor}")

            # Display recommendation message
            recommendation = result.get('recommendation', {})
            if recommendation.get('message'):
                print(f"\\nRECOMMENDATION:")
                print(f"  {recommendation['message']}")
                if recommendation.get('consult_required'):
                    print("  ⚠️  Professional consultation recommended")

            # Display alternatives
            alternatives = result.get('alternatives', [])
            if alternatives:
                print(f"\\nALTERNATIVE MEDICATIONS:")
                for alt in alternatives[:3]:  # Show top 3
                    print(f"  • {alt.get('name', 'Unknown')}")
                    print(f"    Reason: {alt.get('reason', 'N/A')}")
                    if alt.get('advantages'):
                        advantages = alt['advantages']
                        if isinstance(advantages, list):
                            print(f"    Advantages: {', '.join(advantages)}")
                        else:
                            print(f"    Advantages: {advantages}")

            # Display score breakdown
            breakdown = result.get('score_breakdown', {})
            if any(breakdown.values()):
                print(f"\\nSCORE BREAKDOWN:")
                for component, score in breakdown.items():
                    if score > 0:
                        print(f"  {component.replace('_', ' ').title()}: +{score} points")

            # Display metadata
            metadata = result.get('metadata', {})
            print(f"\\nEVALUATION METADATA:")
            print(f"  Processing Time: {metadata.get('processing_time_seconds', 'Unknown'):.2f}s")
            print(f"  Evaluation ID:   {metadata.get('evaluation_id', 'Unknown')}")

            print("="*60)
            return result

        except Exception as e:
            print(f"\\nERROR: {e}")
            print("="*60)
            return None

    def interactive_mode(self):
        """Run interactive testing mode."""
        print("\\n🏥 MedGuard Interactive Testing Mode")
        print("Enter 'quit' at any time to exit\\n")

        while True:
            try:
                # Get symptoms
                symptoms_input = input("Enter symptoms (comma-separated): ").strip()
                if symptoms_input.lower() == 'quit':
                    break

                symptoms = [s.strip() for s in symptoms_input.split(',') if s.strip()]
                if not symptoms:
                    print("Please enter at least one symptom.\\n")
                    continue

                # Get proposed drug
                drug = input("Enter proposed medication: ").strip()
                if drug.lower() == 'quit':
                    break
                if not drug:
                    print("Please enter a medication name.\\n")
                    continue

                # Get existing medications (optional)
                existing_input = input("Enter current medications (comma-separated, or press Enter for none): ").strip()
                if existing_input.lower() == 'quit':
                    break

                existing_drugs = []
                if existing_input:
                    existing_drugs = [s.strip() for s in existing_input.split(',') if s.strip()]

                # Run test
                self.test_scenario(symptoms, drug, existing_drugs)

                # Ask if user wants to continue
                continue_input = input("\\nTest another scenario? (y/n): ").strip().lower()
                if continue_input in ['n', 'no', 'quit']:
                    break
                print()

            except KeyboardInterrupt:
                print("\\n\\nExiting...")
                break

        print("Thank you for using MedGuard Interactive Testing!")

def get_predefined_scenarios():
    """Return a set of predefined test scenarios."""
    return {
        'basic': {
            'symptoms': ['headache'],
            'drug': 'ibuprofen',
            'existing_drugs': []
        },
        'moderate': {
            'symptoms': ['back pain'],
            'drug': 'ibuprofen',
            'existing_drugs': ['lisinopril']
        },
        'high_risk': {
            'symptoms': ['headache'],
            'drug': 'aspirin',
            'existing_drugs': ['warfarin']
        },
        'complex': {
            'symptoms': ['anxiety', 'insomnia'],
            'drug': 'alprazolam',
            'existing_drugs': ['oxycodone', 'zolpidem']
        },
        'allergy': {
            'symptoms': ['sneezing', 'runny nose', 'itchy eyes'],
            'drug': 'cetirizine',
            'existing_drugs': []
        },
        'fever': {
            'symptoms': ['fever', 'body aches'],
            'drug': 'acetaminophen',
            'existing_drugs': ['vitamin c']
        },
        'mismatch': {
            'symptoms': ['fever', 'cough'],
            'drug': 'amoxicillin',
            'existing_drugs': []
        }
    }

def main():
    parser = argparse.ArgumentParser(description="Manual testing for MedGuard")
    parser.add_argument("--scenario", choices=list(get_predefined_scenarios().keys()),
                       help="Run a predefined scenario")
    parser.add_argument("--symptoms", type=str, help="Symptoms (space or comma separated)")
    parser.add_argument("--drug", type=str, help="Proposed drug")
    parser.add_argument("--existing", type=str, help="Existing drugs (space or comma separated)")
    parser.add_argument("--list-scenarios", action="store_true", help="List available scenarios")

    args = parser.parse_args()
    tester = ManualTester()

    if args.list_scenarios:
        scenarios = get_predefined_scenarios()
        print("\\nAvailable predefined scenarios:")
        print("-" * 40)
        for name, scenario in scenarios.items():
            print(f"{name}:")
            print(f"  Symptoms: {', '.join(scenario['symptoms'])}")
            print(f"  Drug: {scenario['drug']}")
            print(f"  Existing: {', '.join(scenario['existing_drugs']) if scenario['existing_drugs'] else 'None'}")
            print()
        return

    if args.scenario:
        # Run predefined scenario
        scenarios = get_predefined_scenarios()
        scenario = scenarios[args.scenario]
        print(f"\\nRunning predefined scenario: {args.scenario}")
        tester.test_scenario(
            scenario['symptoms'],
            scenario['drug'],
            scenario['existing_drugs']
        )

    elif args.symptoms and args.drug:
        # Run custom scenario from command line
        symptoms = [s.strip() for s in args.symptoms.replace(',', ' ').split() if s.strip()]
        existing_drugs = []
        if args.existing:
            existing_drugs = [s.strip() for s in args.existing.replace(',', ' ').split() if s.strip()]

        tester.test_scenario(symptoms, args.drug, existing_drugs)

    else:
        # Run interactive mode
        tester.interactive_mode()

if __name__ == "__main__":
    main()