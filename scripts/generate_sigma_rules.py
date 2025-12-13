#!/usr/bin/env python3
"""
Automatically generate Sigma rules based on att_sim.py attack patterns
"""

import re
import yaml
from pathlib import Path
from datetime import datetime

class SigmaRuleGenerator:
    def __init__(self):
        self.rule_counter = 1000
        
    def generate_rule_from_attack_pattern(self, attack_name, log_patterns, mitre_technique, severity="medium"):
        """Generate a Sigma rule from attack patterns"""
        
        rule_id = f"custom-{self.rule_counter:04d}-{attack_name.replace('_', '-')}"
        self.rule_counter += 1
        
        # Extract keywords from log patterns
        keywords = []
        for pattern in log_patterns:
            # Extract meaningful words/phrases
            words = re.findall(r'\\b[a-zA-Z_/][a-zA-Z0-9_/.]{3,}\\b', pattern.lower())
            keywords.extend(words)
        
        # Remove duplicates and filter
        keywords = list(set([k for k in keywords if len(k) > 3 and k not in ['server', 'system']]))
        
        rule = {
            'title': f"Custom Detection: {attack_name.replace('_', ' ').title()}",
            'id': rule_id,
            'level': severity,
            'status': 'experimental',
            'description': f"Detects {attack_name.replace('_', ' ')} attack pattern",
            'references': [
                f"https://attack.mitre.org/techniques/{mitre_technique}/",
                f"Internal research - att_sim.py {attack_name}"
            ],
            'author': 'RKSha - Automated Generation',
            'date': datetime.now().strftime('%Y/%m/%d'),
            'tags': [
                f'attack.{self._get_tactic(mitre_technique)}',
                f'attack.{mitre_technique.lower()}',
                f'custom.{attack_name}'
            ],
            'logsource': {
                'product': 'linux',
                'service': self._detect_service(log_patterns[0])
            },
            'detection': {
                'keywords': keywords[:8],  # Limit to 8 keywords
                'condition': 'keywords'
            },
            'falsepositives': [
                'Legitimate system activities',
                'Administrative tasks'
            ]
        }
        
        return rule
    
    def _get_tactic(self, technique):
        """Map MITRE technique to tactic"""
        tactic_map = {
            'T1110': 'credential_access',
            'T1548': 'privilege_escalation', 
            'T1083': 'discovery',
            'T1190': 'initial_access',
            'T1486': 'impact'
        }
        return tactic_map.get(technique, 'unknown')
    
    def _detect_service(self, log_sample):
        """Detect service from log sample"""
        if 'sshd' in log_sample:
            return 'sshd'
        elif 'sudo' in log_sample:
            return 'sudo'
        elif 'nginx' in log_sample:
            return 'nginx'
        else:
            return 'system'
    
    def generate_all_rules(self):
        """Generate rules for all known attack patterns"""
        
        attack_patterns = {
            'ssh_brute_force': {
                'patterns': [
                    'Failed password for admin from',
                    'Invalid user hacker from', 
                    'authentication failure'
                ],
                'mitre': 'T1110',
                'severity': 'high'
            },
            'privilege_escalation': {
                'patterns': [
                    'sudo: user : COMMAND=/bin/bash',
                    'USER=root ; COMMAND=',
                    'executed sudo command as root'
                ],
                'mitre': 'T1548', 
                'severity': 'critical'
            },
            'directory_traversal': {
                'patterns': [
                    'GET /../../../etc/passwd',
                    'directory traversal attempt',
                    '../../../etc/shadow'
                ],
                'mitre': 'T1083',
                'severity': 'high'
            }
        }
        
        rules = []
        for attack_name, config in attack_patterns.items():
            rule = self.generate_rule_from_attack_pattern(
                attack_name, 
                config['patterns'],
                config['mitre'],
                config['severity']
            )
            rules.append(rule)
        
        return rules
    
    def save_rules_to_file(self, rules, filename="custom-generated-rules.yml"):
        """Save generated rules to YAML file"""
        output_path = Path("sigma-rules/custom") / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            for i, rule in enumerate(rules):
                if i > 0:
                    f.write("\\n---\\n\\n")
                yaml.dump(rule, f, default_flow_style=False, sort_keys=False)
        
        print(f"Generated {len(rules)} rules saved to {output_path}")

if __name__ == "__main__":
    generator = SigmaRuleGenerator()
    rules = generator.generate_all_rules()
    generator.save_rules_to_file(rules)
