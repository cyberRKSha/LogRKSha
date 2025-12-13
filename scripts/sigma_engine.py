import os
import re
import yaml
import pathlib
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class SigmaEngine:
    def __init__(self, rules_path: str = "sigma-rules"):
        print("SIGMA ENGINE: Initializing...")
        self.rules_path = pathlib.Path(rules_path)
        self.rules = self._load_rules()
        print(f"SIGMA ENGINE: Successfully loaded {len(self.rules)} rules.")
        if self.rules:
            print("Sample rules loaded:")
            for rule in self.rules[:3]:
                print(f"  - {rule['title']} (Level: {rule['level']})")
        
    def _load_rules(self) -> List[Dict[str, Any]]:
        """Load rules with custom rules priority"""
        rules = []
        
        if not self.rules_path.exists():
            logger.warning(f"Sigma rules path does not exist: {self.rules_path}")
            return rules
        
        # PRIORITY 1: Load custom rules first
        custom_directories = [
            "custom",           # Your custom rules
            "custom/linux",
            "custom/web", 
            "custom/network"
        ]
        
        # PRIORITY 2: Load selected standard rules
        standard_directories = [
            "rules/linux/auditd",
            "rules/linux/auth",
            "rules-emerging-threats",
            "rules-threat-hunting"
        ]
        
        all_directories = custom_directories + standard_directories
        
        yaml_files = []
        for priority_dir in all_directories:
            priority_path = self.rules_path / priority_dir
            if priority_path.exists():
                print(f"Loading rules from: {priority_dir}")
                dir_files = list(priority_path.rglob("*.yml")) + list(priority_path.rglob("*.yaml"))
                yaml_files.extend(dir_files[:20])  # Limit per directory
        
        # Process files with custom rules getting priority
        for yaml_file in yaml_files:
            try:
                rules_from_file = self._load_rules_from_file(yaml_file)
                rules.extend(rules_from_file)
                
                if len(rules) > 100:  # Limit total rules
                    break
                    
            except Exception as e:
                logger.debug(f"Error loading {yaml_file}: {e}")
                continue
            
        # Quality filtering but prioritize custom rules
        quality_rules = []
        custom_rules = [r for r in rules if 'custom' in r.get('source_file', '')]
        standard_rules = [r for r in rules if 'custom' not in r.get('source_file', '')]
        
        # Always include custom rules
        quality_rules.extend(custom_rules)
        
        # Add best standard rules
        filtered_standard = [rule for rule in standard_rules if self._is_useful_rule(rule)]
        quality_rules.extend(filtered_standard[:30])  # Max 30 standard rules
        
        print(f"Loaded {len(custom_rules)} custom rules, {len(filtered_standard)} standard rules")
        
        return quality_rules[:50]  # Total limit

    
    def _load_rules_from_file(self, file_path: pathlib.Path) -> List[Dict[str, Any]]:
        """Load rules from a single YAML file"""
        rules = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Handle multiple documents in one file
            if '\n---\n' in content:
                documents = content.split('\n---\n')
            else:
                documents = [content]
            
            for doc in documents:
                if not doc.strip():
                    continue
                    
                try:
                    parsed_rule = yaml.safe_load(doc)
                    if parsed_rule and isinstance(parsed_rule, dict):
                        processed_rule = self._process_rule(parsed_rule, file_path.name)
                        if processed_rule:
                            rules.append(processed_rule)
                except yaml.YAMLError as e:
                    logger.debug(f"YAML error in {file_path}: {e}")
                    continue
                    
        except Exception as e:
            logger.debug(f"File error {file_path}: {e}")
        
        return rules
    
    def _process_rule(self, rule_data: Dict[str, Any], filename: str) -> Optional[Dict[str, Any]]:
        """Process rule with reasonable filtering"""
        try:
            title = rule_data.get('title', 'Unknown Rule')
            rule_id = rule_data.get('id', 'unknown')
            level = rule_data.get('level', 'medium').upper()
            
            # Skip obvious test/example rules but be less aggressive
            skip_terms = ['test rule', 'example rule', 'template rule']
            if any(term in title.lower() for term in skip_terms):
                return None
            
            detection = rule_data.get('detection', {})
            if not detection:
                return None
            
            # Extract keywords more liberally
            keywords = []
            field_conditions = {}
            
            for key, value in detection.items():
                if key in ['condition', 'timeframe']:
                    continue
                    
                self._extract_keywords_from_value(key, value, keywords, field_conditions)
            
            # Clean keywords but be less strict
            cleaned_keywords = []
            for keyword in keywords:
                if self._is_reasonable_keyword(str(keyword)):
                    cleaned_keywords.append(str(keyword).strip())
            
            # Remove duplicates
            cleaned_keywords = list(dict.fromkeys(cleaned_keywords))
            
            if not cleaned_keywords:
                return None
            
            return {
                'title': title,
                'id': rule_id,
                'level': level,
                'keywords': cleaned_keywords[:10],
                'field_conditions': field_conditions,
                'category': self._get_category(title),
                'source_file': filename
            }
            
        except Exception as e:
            logger.debug(f"Error processing rule: {e}")
            return None
    
    def _extract_keywords_from_value(self, key: str, value: Any, keywords: List[str], field_conditions: Dict):
        """Recursively extract keywords from detection values"""
        if isinstance(value, dict):
            for field, field_values in value.items():
                if isinstance(field_values, list):
                    keywords.extend([str(v) for v in field_values if v])
                    field_conditions[field] = field_values
                elif field_values:
                    keywords.append(str(field_values))
                    field_conditions[field] = [str(field_values)]
        elif isinstance(value, list):
            keywords.extend([str(v) for v in value if v])
        elif value:
            keywords.append(str(value))
    
    def _is_reasonable_keyword(self, keyword: str) -> bool:
        """More balanced keyword filtering"""
        if not keyword or len(keyword) < 3:
            return False
        
        keyword = keyword.lower().strip()
        
        # Remove only the most generic terms
        very_generic = {
            'true', 'false', 'null', 'none', '1', '0', 
            'a', 'an', 'the', 'and', 'or', 'not', 'is', 'was', 'are'
        }
        
        if keyword in very_generic:
            return False
        
        # Skip pure numbers and simple patterns
        if keyword.isdigit() or keyword in ['*', '.*', '?']:
            return False
        
        # Skip very long file paths
        if keyword.startswith('/') and keyword.count('/') > 4:
            return False
        
        return True
    
    def _is_useful_rule(self, rule: Dict[str, Any]) -> bool:
        """Less strict quality filtering"""
        # Must have a real title
        if not rule['title'] or len(rule['title']) < 10:
            return False
        
        # Must have some keywords
        if not rule['keywords']:
            return False
        
        # Allow more rule levels
        if rule['level'] not in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
            return False
        
        return True
    
    def _get_category(self, title: str) -> str:
        """Categorize rules"""
        title_lower = title.lower()
        
        if any(term in title_lower for term in ['ssh', 'brute', 'authentication', 'login', 'password']):
            return 'authentication'
        elif any(term in title_lower for term in ['sudo', 'privilege', 'escalation', 'root']):
            return 'privilege_escalation'
        elif any(term in title_lower for term in ['web', 'http', 'injection', 'xss', 'sql']):
            return 'web_attack'
        elif any(term in title_lower for term in ['network', 'connection', 'port', 'scan']):
            return 'network'
        else:
            return 'security'
    
    def check_log(self, log_line: str) -> Optional[Dict[str, Any]]:
        """Balanced log matching that will actually find matches"""
        if not log_line or not isinstance(log_line, str) or not self.rules:
            return None
        
        log_content = log_line.lower()
        original_log = log_line
        
        # Debug output
        logger.debug(f"Checking log: {log_line[:100]}...")
        
        best_match = None
        highest_score = 0
        
        for rule in self.rules:
            try:
                score = 0
                matched_keywords = []
                
                # Check each keyword
                for keyword in rule['keywords']:
                    keyword_lower = str(keyword).lower().strip()
                    
                    if keyword_lower in log_content:
                        matched_keywords.append(keyword)
                        # Score based on keyword length (longer = more specific)
                        score += max(len(keyword_lower) // 2, 1)
                
                # Check field conditions for bonus points
                for field, values in rule['field_conditions'].items():
                    for value in values:
                        if str(value).lower() in log_content:
                            score += 2
                
                # Lower thresholds for better matching
                min_keywords_required = 1
                min_score_required = 3
                
                # Adjust requirements based on rule level
                if rule['level'] == 'CRITICAL':
                    min_keywords_required = 1
                    min_score_required = 4
                elif rule['level'] == 'HIGH':
                    min_keywords_required = 1  
                    min_score_required = 3
                else:
                    min_keywords_required = 1
                    min_score_required = 2
                
                # Check if rule qualifies
                if len(matched_keywords) >= min_keywords_required and score >= min_score_required:
                    if score > highest_score:
                        highest_score = score
                        best_match = {
                            'title': rule['title'],
                            'id': rule['id'],
                            'level': rule['level'],
                            'category': rule['category'],
                            'matched_keywords': matched_keywords,
                            'confidence_score': score,
                            'source_file': rule['source_file'],
                            'log': original_log
                        }
                
            except Exception as e:
                logger.debug(f"Error checking rule {rule.get('title', 'unknown')}: {e}")
                continue
        
        if best_match:
            logger.info(f"✅ SIGMA MATCH: {best_match['title']}")
            logger.info(f"   Level: {best_match['level']}, Score: {best_match['confidence_score']}")
            logger.info(f"   Keywords: {best_match['matched_keywords']}")
        else:
            logger.debug("No Sigma rule matches found")
        
        return best_match
