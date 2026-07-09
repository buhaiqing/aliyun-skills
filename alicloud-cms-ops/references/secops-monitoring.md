# Security Operations Monitoring Guide

Security operations monitoring reference for alicloud-cms-ops skill, covering threat detection, compliance monitoring, and incident response coordination.

## 1. Security Namespace Integration Guide

### SAS Namespace Mapping

| CMS Namespace | SAS Skill | Integration Type | Priority |
|---------------|-----------|------------------|----------|
| acs_sas_dashboard | alicloud-sas-ops | Primary Security Source | Critical |
| acs_sas_alert | alicloud-sas-ops | Real-time Alert Feed | High |
| acs_sas_vul | alicloud-sas-ops | Vulnerability Tracking | Medium |
| acs_sas_baseline | alicloud-sas-ops | Compliance Baseline | Medium |
| acs_sas_threat | alicloud-sas-ops | Threat Intelligence | High |

### Key Security Metrics

#### Critical Security Indicators

| Metric Name | Namespace | Description | Alert Threshold |
|-------------|-----------|-------------|-----------------|
| SuspiciousEventCount | acs_sas_dashboard | Suspicious event count | >5 events/hour |
| VulCount | acs_sas_vul | Vulnerability count | >10 high-risk vuls |
| RiskScore | acs_sas_dashboard | Security risk score | >70 (high risk) |
| BaselineRisk | acs_sas_baseline | Baseline compliance risk | >60% non-compliant |
| ThreatLevel | acs_sas_threat | Threat intelligence level | malicious/suspicious |

#### Security Event Categories

```yaml
security_event_categories:
  - category: intrusion_detection
    metrics:
      - SuspiciousProcessCount
      - AbnormalLoginCount
      - BruteForceAttemptCount
    threshold_multiplier: 1.5
    
  - category: vulnerability_management
    metrics:
      - HighRiskVulCount
      - MediumRiskVulCount
      - UnpatchedVulCount
    threshold_multiplier: 2.0
    
  - category: compliance_monitoring
    metrics:
      - BaselineCheckFailCount
      - SecurityGroupViolationCount
      - RAMPermissionRiskCount
    threshold_multiplier: 1.0
```

### Delegation Protocol: CMS → SAS Root Cause Analysis

```yaml
cms_to_sas_delegation:
  trigger:
    condition: "CMS security alert received"
    indicators:
      - namespace: "acs_sas_*"
      - metric_value: "exceeds threshold"
      - severity: "critical OR high"
  
  delegation_flow:
    - step: 1
      action: "CMS detects security anomaly"
      tool: "cms alarm trigger"
      
    - step: 2
      action: "Delegate to SAS for detailed analysis"
      skill: "alicloud-sas-ops"
      tool: "DescribeSuspEvents"
      parameters:
        - SuspiciousEventId
        - SourceIp
        - EventType
        
    - step: 3
      action: "Root cause identification"
      analysis:
        - event_source: "internal OR external"
        - attack_vector: "network OR application OR system"
        - impact_scope: "single_instance OR cluster OR account"
        
    - step: 4
      action: "Recommend remediation actions"
      output:
        - quarantine_instance
        - block_source_ip
        - patch_vulnerability
        - reset_credentials
```

## 2. Compliance Alarm Templates

### SecurityGroup Exposure Detection

#### Port Exposure Check Template

```yaml
alarm_template:
  name: "SecurityGroup_Port_Exposure"
  namespace: "acs_ecs_dashboard"
  metric: "SecurityGroupRiskCount"
  
  thresholds:
    - severity: critical
      condition: "> 0 high_risk_ports exposed"
      ports:
        - 22 (SSH)
        - 3389 (RDP)
        - 3306 (MySQL)
        - 6379 (Redis)
        - 27017 (MongoDB)
        
    - severity: high
      condition: "> 5 medium_risk_ports exposed"
      ports:
        - 80 (HTTP)
        - 443 (HTTPS)
        - 8080 (HTTP-Alt)
        
  delegation:
    skill: "alicloud-sas-ops"
    tool: "DescribeCheckWarningSummary"
    check_items:
      - "SecurityGroup_BroadScopeAccess"
      - "SecurityGroup_UnauthorizedPort"
      
  remediation:
    - action: "restrict_security_group_rules"
      priority: immediate
    - action: "enable_network_acl"
      priority: high
```

#### Rule Redundancy Check Template

```yaml
alarm_template:
  name: "SecurityGroup_Rule_Redundancy"
  namespace: "acs_ecs_dashboard"
  metric: "SecurityGroupRuleCount"
  
  thresholds:
    - severity: warning
      condition: "> 50 rules per security_group"
      risk: "configuration_complexity"
      
    - severity: high
      condition: "> 100 rules per security_group"
      risk: "performance_impact AND management_difficulty"
      
  analysis:
    redundant_rule_detection:
      - overlapping_cidr_blocks
      - duplicate_port_ranges
      - contradictory_permissions
      
  delegation:
    skill: "alicloud-sas-ops"
    tool: "DescribeCheckWarningSummary"
    focus: "SecurityGroup_Optimization"
```

### RAM Permission Anomaly Detection

```yaml
alarm_template:
  name: "RAM_Permission_Anomaly"
  namespace: "acs_ram_dashboard"
  metrics:
    - PermissionChangeRate
    - HighRiskPermissionCount
    - CrossAccountAccessCount
    
  thresholds:
    permission_change_rate:
      - severity: critical
        condition: "> 10 changes/hour"
        indicator: "potential_account_compromise"
        
      - severity: high
        condition: "> 5 changes/hour"
        indicator: "unusual_permission_activity"
        
    high_risk_permission:
      - severity: critical
        permissions:
          - "AdministratorAccess"
          - "AliyunECSFullAccess"
          - "AliyunRDSFullAccess"
          - "AliyunOSSFullAccess"
        condition: "new_assignment detected"
        
  delegation:
    skill: "alicloud-sas-ops"
    tool: "DescribeCheckWarningSummary"
    check_items:
      - "RAM_HighRiskPermission"
      - "RAM_CrossAccountAccess"
      
  integration:
    audit_trail:
      skill: "alicloud-actiontrail-ops"
      tool: "LookupEvents"
      event_types:
        - "CreateUser"
        - "AttachPolicyToUser"
        - "AttachPolicyToRole"
```

### AK Leak Detection Integration

```yaml
alarm_template:
  name: "AccessKey_Leak_Detection"
  namespace: "acs_sas_alert"
  metric: "AccessKeyLeakCount"
  
  thresholds:
    - severity: critical
      condition: "> 0 leak_detected"
      immediate_action: "disable_access_key"
      
  delegation_flow:
    primary:
      skill: "alicloud-sas-ops"
      tool: "DescribeAccesskeyLeakList"
      parameters:
        - Status: "LEAKED"
        - RiskLevel: "HIGH"
        
    secondary:
      skill: "alicloud-actiontrail-ops"
      tool: "LookupEvents"
      focus: "api_calls_with_leaked_ak"
      
  remediation_protocol:
    - step: 1
      action: "immediately_disable_leaked_ak"
      tool: "RAM DeleteAccessKey"
      
    - step: 2
      action: "rotate_credentials"
      scope: "all_affected_services"
      
    - step: 3
      action: "audit_recent_api_calls"
      skill: "alicloud-actiontrail-ops"
      
    - step: 4
      action: "notify_security_team"
      severity: "critical"
```

### Baseline Compliance Monitoring

```yaml
alarm_template:
  name: "Security_Baseline_Compliance"
  namespace: "acs_sas_baseline"
  metrics:
    - BaselineCheckFailCount
    - BaselineRiskScore
    - BaselineComplianceRate
    
  thresholds:
    compliance_rate:
      - severity: critical
        condition: "< 70% compliance"
        focus: "immediate_remediation"
        
      - severity: high
        condition: "< 85% compliance"
        focus: "planned_remediation"
        
    baseline_risk_score:
      - severity: critical
        condition: "> 80 risk_score"
        categories:
          - "account_security"
          - "network_security"
          - "instance_security"
          
  delegation:
    skill: "alicloud-sas-ops"
    tool: "DescribeCheckWarningSummary"
    
    check_categories:
      account_security:
        - "RAM_MFANotEnabled"
        - "RAM_PasswordPolicyWeak"
        - "RootAccountAKUsed"
        
      network_security:
        - "SecurityGroup_BroadScopeAccess"
        - "VPC_PublicSubnetExposure"
        - "EIP_UnrestrictedAccess"
        
      instance_security:
        - "ECS_UnpatchedVulnerability"
        - "ECS_PublicImageRisk"
        - "ECS_KeyPairNotUsed"
        
  remediation_priority:
    critical:
      - RootAccountAKUsed
      - RAM_MFANotEnabled
      - SecurityGroup_BroadScopeAccess
      
    high:
      - RAM_PasswordPolicyWeak
      - ECS_UnpatchedVulnerability
      - VPC_PublicSubnetExposure
```

## 3. Threat Intelligence Correlation Protocols

### Input Parameters

```yaml
threat_correlation_input:
  required_parameters:
    - source_ip:
        description: "Source IP address of suspicious activity"
        type: "string"
        validation: "IPv4 OR IPv6 format"
        
    - event_type:
        description: "Type of security event"
        enum:
          - "intrusion_attempt"
          - "brute_force"
          - "malware_detection"
          - "unauthorized_access"
          - "data_exfiltration"
          
    - time_range:
        description: "Time range for correlation analysis"
        format: "ISO8601"
        default: "last_24_hours"
        
  optional_parameters:
    - target_resource:
        description: "Affected resource identifier"
        type: "string"
        examples:
          - "i-ecs-xxx"
          - "rds-instance-xxx"
          - "oss-bucket-xxx"
          
    - user_identity:
        description: "RAM user or role involved"
        type: "string"
        
    - network_context:
        description: "Network flow context"
        fields:
          - source_port
          - destination_port
          - protocol
          - packet_count
```

### Output Fields

```yaml
threat_correlation_output:
  threat_level:
    values:
      - malicious:
          description: "Confirmed malicious activity"
          confidence: "> 90%"
          action: "immediate_block"
          
      - suspicious:
          description: "Potential threat requiring investigation"
          confidence: "70-90%"
          action: "monitor_and_analyze"
          
      - unknown:
          description: "Activity with insufficient context"
          confidence: "50-70%"
          action: "gather_more_evidence"
          
      - benign:
          description: "Activity confirmed as legitimate"
          confidence: "> 90%"
          action: "no_action_required"
          
  correlation_results:
    - related_events:
        description: "Historically related security events"
        count: "number_of_correlated_events"
        
    - threat_sources:
        description: "Identified threat sources"
        categories:
          - botnet
          - ddos
          - scan
          - brute_force
          - malware_c2
          
    - affected_resources:
        description: "Resources impacted by threat"
        scope: "single OR multiple OR account-wide"
        
    - attack_timeline:
        description: "Timeline of attack progression"
        stages:
          - reconnaissance
          - initial_access
          - execution
          - persistence
          - data_exfiltration
```

### Threat Source Classification

```yaml
threat_source_classification:
  botnet:
    indicators:
      - coordinated_ip_pattern
      - automated_request_sequence
      - distributed_attack_source
    confidence_threshold: 0.85
    recommended_action: "block_ip_range"
    
  ddos:
    indicators:
      - abnormal_traffic_volume
      - connection_rate_spike
      - resource_exhaustion_pattern
    confidence_threshold: 0.90
    recommended_action: "enable_ddos_protection"
    
  scan:
    indicators:
      - port_probe_sequence
      - service_fingerprinting
      - vulnerability_scanning_pattern
    confidence_threshold: 0.75
    recommended_action: "monitor_and_log"
    
  brute_force:
    indicators:
      - repeated_login_attempts
      - credential_testing_pattern
      - authentication_failure_spike
    confidence_threshold: 0.85
    recommended_action: "block_ip_and_notify"
    
  malware_c2:
    indicators:
      - known_c2_server_ip
      - abnormal_outbound_connection
      - payload_download_pattern
    confidence_threshold: 0.90
    recommended_action: "quarantine_instance"
```

### Recommended Actions Matrix

| Threat Level | Threat Source | Primary Action | Secondary Action | Escalation |
|--------------|---------------|----------------|------------------|------------|
| malicious | botnet | block_ip_range | update_waf_rules | security_team |
| malicious | ddos | enable_ddos_protection | scale_resources | security_team + ops |
| malicious | malware_c2 | quarantine_instance | forensic_analysis | security_team |
| suspicious | brute_force | block_ip | monitor_account | ops_team |
| suspicious | scan | monitor_and_log | update_firewall | ops_team |
| unknown | any | gather_evidence | extended_monitoring | ops_team |

### Delegation Path: CMS → SAS → ActionTrail

```yaml
threat_intelligence_delegation:
  stage_1_cms_detection:
    trigger: "Security metric anomaly"
    skill: "alicloud-cms-ops"
    action: "Initial alert generation"
    
  stage_2_sas_analysis:
    trigger: "CMS alert received"
    skill: "alicloud-sas-ops"
    tools:
      - DescribeSuspEvents:
          purpose: "Get detailed suspicious event information"
          
      - DescribeCheckWarningSummary:
          purpose: "Check baseline compliance status"
          
      - DescribeAccesskeyLeakList:
          purpose: "Check for AK leak incidents"
          
    analysis_output:
      - event_details
      - threat_classification
      - recommended_actions
      
  stage_3_actiontrail_audit:
    trigger: "SAS analysis completed"
    skill: "alicloud-actiontrail-ops"
    tools:
      - LookupEvents:
          parameters:
            - EventName: "relevant_operation"
            - ResourceName: "affected_resource"
            - TimeRange: "incident_period"
            
    audit_output:
      - operation_history
      - user_activity_timeline
      - api_call_patterns
      
  stage_4_integrated_response:
    coordination:
      - cms: "Update alarm status"
      - sas: "Execute remediation actions"
      - actiontrail: "Document incident timeline"
      
    reporting:
      - incident_summary
      - root_cause_analysis
      - remediation_steps_taken
      - lessons_learned
```

## Alarm-to-Diagnosis Delegation Matrix (Security)

| CMS Alarm Type | Primary SAS Tool | Secondary Integration | Diagnosis Focus | Response Priority |
|----------------|------------------|----------------------|-----------------|-------------------|
| SuspiciousEventCount | DescribeSuspEvents | ActionTrail LookupEvents | Intrusion detection | Critical (1h) |
| VulCount | DescribeVulList | - | Vulnerability patching | High (24h) |
| RiskScore | DescribeCheckWarningSummary | ActionTrail LookupEvents | Compliance remediation | Medium (72h) |
| AccessKeyLeakCount | DescribeAccesskeyLeakList | RAM DeleteAccessKey | Credential rotation | Critical (immediate) |
| BaselineCheckFailCount | DescribeCheckWarningSummary | - | Baseline compliance | Medium (7d) |
| SecurityGroupRiskCount | DescribeCheckWarningSummary | ECS DescribeSecurityGroups | Network security | High (24h) |
| RAMPermissionRiskCount | DescribeCheckWarningSummary | RAM ListPolicies | Permission cleanup | High (24h) |
| BruteForceAttemptCount | DescribeSuspEvents | ActionTrail LookupEvents | Account protection | Critical (1h) |
| MalwareDetectionCount | DescribeSuspEvents | ECS quarantine | Instance isolation | Critical (immediate) |
| DataExfiltrationIndicator | DescribeSuspEvents | OSS GetBucketLog | Data protection | Critical (immediate) |

## CLI Command Examples

### Security Event Query

```bash
# Query recent suspicious events
aliyun cms QueryMetricList \
  --Namespace acs_sas_dashboard \
  --MetricName SuspiciousEventCount \
  --StartTime "$(date -u -d '1 hour ago' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -v-1H '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null)" \
  --EndTime "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

# Query vulnerability status
aliyun cms QueryMetricList \
  --Namespace acs_sas_vul \
  --MetricName VulCount \
  --Dimensions '{"instanceId":"i-ecs-xxx"}'
```

### SAS Integration Commands

```bash
# Describe suspicious events (delegated from CMS)
aliyun sas DescribeSuspEvents \
  --SuspiciousEventId "event-xxx" \
  --SourceIp "192.168.1.100"

# Check baseline compliance warnings
aliyun sas DescribeCheckWarningSummary \
  --CheckType "SecurityGroup_BroadScopeAccess" \
  --Status "Failed"

# Check for AK leaks
aliyun sas DescribeAccesskeyLeakList \
  --Status "LEAKED" \
  --RiskLevel "HIGH"
```

### ActionTrail Correlation Commands

```bash
# Lookup events for security incident investigation
aliyun actiontrail LookupEvents \
  --EventName "AttachPolicyToUser" \
  --ResourceName "ram-user-xxx" \
  --StartTime "$(date -u -d '24 hours ago' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -v-24H '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null)" \
  --EndTime "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

# Query recent API calls with leaked AK
aliyun actiontrail LookupEvents \
  --EventName "ConsoleSignin" \
  --EventType "ConsoleSignin" \
  --StartTime "$(date -u -d '7 days ago' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -v-7d '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null)"
```

### Security Alarm Configuration

```bash
# Create security baseline compliance alarm
aliyun cms PutAlarmRule \
  --AlarmName "SecurityBaseline_Compliance_Alarm" \
  --Namespace acs_sas_baseline \
  --MetricName BaselineComplianceRate \
  --Threshold 70 \
  --ComparisonOperator "<=" \
  --Severity "Critical" \
  --ContactGroups "security_team"

# Create AK leak detection alarm
aliyun cms PutAlarmRule \
  --AlarmName "AccessKey_Leak_Alarm" \
  --Namespace acs_sas_alert \
  --MetricName AccessKeyLeakCount \
  --Threshold 0 \
  --ComparisonOperator ">" \
  --Severity "Critical" \
  --ContactGroups "security_team,ops_team"
```

## Integration Best Practices

### 1. Alarm Delegation Strategy

- **Critical Alerts**: Immediate delegation to SAS with parallel ActionTrail audit
- **High Alerts**: SAS analysis first, then ActionTrail correlation if needed
- **Medium Alerts**: Scheduled SAS check with optional ActionTrail verification

### 2. Threat Correlation Workflow

- **Stage 1**: CMS detects anomaly and triggers alert
- **Stage 2**: SAS provides detailed threat analysis
- **Stage 3**: ActionTrail provides context and audit trail
- **Stage 4**: Integrated response with cross-skill coordination

### 3. Compliance Monitoring Protocol

- **Daily**: Check baseline compliance rate and vulnerability count
- **Weekly**: Review security group rules and RAM permissions
- **Monthly**: Full security assessment with remediation planning

### 4. Incident Response Escalation

- **Level 1**: Automated remediation via SAS tools
- **Level 2**: Ops team intervention with ActionTrail audit
- **Level 3**: Security team escalation with full forensic analysis
- **Level 4**: Management escalation with business impact assessment