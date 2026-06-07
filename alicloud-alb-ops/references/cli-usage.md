# CLI Usage — ALB (`aliyun alb`)

> Version: 1.0.0 | Last Updated: 2026-06-07

## Command Map

### Load Balancer Operations

| Goal | Example |
|------|---------|
| List ALBs | `aliyun alb ListLoadBalancers --RegionId {{user.region}}` |
| Get ALB | `aliyun alb GetLoadBalancerAttribute --LoadBalancerId {{lb_id}}` |
| Extract fields | `aliyun alb ListLoadBalancers --RegionId {{user.region}} --output cols=LoadBalancerId,Status rows=LoadBalancers[].{id:LoadBalancerId,status:LoadBalancerStatus}` |
| Create ALB | `aliyun alb CreateLoadBalancer --LoadBalancerName "my-alb" --AddressType Intranet --VpcId {{vpc_id}} --ZoneMappings "[{\\"VSwitchId\\":\\"{{vswitch_id}}\\"}]"` |
| Delete ALB | `aliyun alb DeleteLoadBalancer --LoadBalancerId {{lb_id}}` **Destructive** |
| Update name | `aliyun alb UpdateLoadBalancerAttribute --LoadBalancerId {{lb_id}} --LoadBalancerName "new-name"` |
| Enable del protection | `aliyun alb EnableDeletionProtection --ResourceId {{lb_id}} --RegionId {{user.region}}` |
| Disable del protection | `aliyun alb DisableDeletionProtection --ResourceId {{lb_id}} --RegionId {{user.region}}` |
| Enable access log | `aliyun alb EnableLoadBalancerAccessLog --LoadBalancerId {{lb_id}} --LogProject {{project}} --LogStore {{store}}` |
| Disable access log | `aliyun alb DisableLoadBalancerAccessLog --LoadBalancerId {{lb_id}}` |
| Update address type | `aliyun alb UpdateLoadBalancerAddressTypeConfig --LoadBalancerId {{lb_id}} --AddressType Internet` |
| Update zones | `aliyun alb UpdateLoadBalancerZones --LoadBalancerId {{lb_id}} --ZoneMappings "[{\\"VSwitchId\\":\\"{{vswitch_id}}\\"}]"` |
| Update edition | `aliyun alb UpdateLoadBalancerEdition --LoadBalancerId {{lb_id}} --LoadBalancerEdition Standard` |
| Join security group | `aliyun alb LoadBalancerJoinSecurityGroup --LoadBalancerId {{lb_id}} --SecurityGroupIds "[\\"{{sg_id}}\\"]"` |
| Leave security group | `aliyun alb LoadBalancerLeaveSecurityGroup --LoadBalancerId {{lb_id}} --SecurityGroupIds "[\\"{{sg_id}}\\"]"` |

### Listener Operations

| Goal | Example |
|------|---------|
| List listeners | `aliyun alb ListListeners --LoadBalancerId {{lb_id}}` |
| Get listener | `aliyun alb GetListenerAttribute --ListenerId {{listener_id}}` |
| Create HTTP | `aliyun alb CreateListener --ListenerProtocol HTTP --ListenerPort 80 --LoadBalancerId {{lb_id}} --DefaultActions "[{\\"Type\\":\\"ForwardGroup\\",\\"ForwardGroupConfig\\":{\\"ServerGroupTuples\\":[{\\"ServerGroupId\\":\\"{{sg_id}}\\"}]}}]"` |
| Create HTTPS | `aliyun alb CreateListener --ListenerProtocol HTTPS --ListenerPort 443 --LoadBalancerId {{lb_id}} --DefaultActions "[...]" --Certificates "[{\\"CertificateId\\":\\"{{cert_id}}\\"}]"` |
| Update listener | `aliyun alb UpdateListenerAttribute --ListenerId {{listener_id}} --ListenerDescription "new desc"` |
| Start listener | `aliyun alb StartListener --ListenerId {{listener_id}}` |
| Stop listener | `aliyun alb StopListener --ListenerId {{listener_id}}` |
| Delete listener | `aliyun alb DeleteListener --ListenerId {{listener_id}}` **Destructive** |

### Server Group Operations

| Goal | Example |
|------|---------|
| Create SG | `aliyun alb CreateServerGroup --ServerGroupName "my-sg" --VpcId {{vpc_id}} --Protocol HTTP` |
| List SGs | `aliyun alb ListServerGroups --VpcId {{vpc_id}}` |
| Get SG | `aliyun alb GetServerGroupAttribute --ServerGroupId {{sg_id}}` |
| Add servers | `aliyun alb AddServersToServerGroup --ServerGroupId {{sg_id}} --Servers "[{\\"ServerId\\":\\"{{ecs_id}}\\",\\"ServerType\\":\\"Ecs\\",\\"Port\\":80,\\"Weight\\":100}]"` |
| Remove servers | `aliyun alb RemoveServersFromServerGroup --ServerGroupId {{sg_id}} --Servers "[{\\"ServerId\\":\\"{{ecs_id}}\\",\\"ServerType\\":\\"Ecs\\"}]"` |
| List servers | `aliyun alb ListServerGroupServers --ServerGroupId {{sg_id}}` |
| Delete SG | `aliyun alb DeleteServerGroup --ServerGroupId {{sg_id}}` **Destructive** |

### Forwarding Rule Operations

| Goal | Example |
|------|---------|
| Create rule | `aliyun alb CreateRule --ListenerId {{listener_id}} --Priority 10 --RuleConditions "[{\\"Type\\":\\"Host\\",\\"HostConfig\\":{\\"Values\\":[\\"example.com\\"]}}]" --RuleActions "[{\\"Type\\":\\"ForwardGroup\\",\\"ForwardGroupConfig\\":{\\"ServerGroupTuples\\":[{\\"ServerGroupId\\":\\"{{sg_id}}\\"}]},\\"Order\\":1}]"` |
| List rules | `aliyun alb ListRules --ListenerId {{listener_id}}` |
| Delete rule | `aliyun alb DeleteRule --RuleId {{rule_id}}` |

### ACL Operations

| Goal | Example |
|------|---------|
| Create ACL | `aliyun alb CreateAcl --AclName "my-acl"` |
| List ACLs | `aliyun alb ListAcls` |
| Add entries | `aliyun alb AddEntriesToAcl --AclId {{acl_id}} --AclEntries "[{\\"Entry\\":\\"192.168.1.0/24\\",\\"EntryDescription\\":\\"office\\"}]"` |
| Associate ACL | `aliyun alb AssociateAclsWithListener --ListenerId {{listener_id}} --AclIds "[\\"{{acl_id}}\\"]" --AclType Black` |
| Dissociate ACL | `aliyun alb DissociateAclsFromListener --ListenerId {{listener_id}} --AclIds "[\\"{{acl_id}}\\"]"` |
| Delete ACL | `aliyun alb DeleteAcl --AclId {{acl_id}}` **Destructive** |

### Security Policy / Health Check / AScript

| Goal | Example |
|------|---------|
| Create HC template | `aliyun alb CreateHealthCheckTemplate --HealthCheckTemplateName "my-hc" --HealthCheckProtocol HTTP --HealthCheckPath "/"` |
| Create security policy | `aliyun alb CreateSecurityPolicy --SecurityPolicyName "my-policy" --TLSVersion "TLSv1.2" --Ciphers "[\\"ECDHE-RSA-AES128-GCM-SHA256\\"]"` |
| Create AScript | `aliyun alb CreateAScripts --ListenerId {{listener_id}} --AScripts "[{\\"AScriptName\\":\\"my-script\\",\\"ScriptContent\\":\\"if (http.request.method == ...)\\",\\"Enabled\\":true}]"` |

### Infrastructure

| Goal | Example |
|------|---------|
| Regions | `aliyun alb DescribeRegions` |
| Zones | `aliyun alb DescribeZones --RegionId {{user.region}}` |
| Async jobs | `aliyun alb ListAsynJobs --JobId {{job_id}}` |
| Tag | `aliyun alb TagResources --ResourceType "loadbalancer" --ResourceIds "[\\"{{lb_id}}\\"]" --Tag "[{\\"Key\\":\\"Environment\\",\\"Value\\":\\"prod\\"}]"` |

## CLI vs API Coverage

ALB's `aliyun alb` CLI covers **all** major CRUD operations. No significant coverage gaps.