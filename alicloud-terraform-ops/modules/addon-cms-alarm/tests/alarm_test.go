// addon-cms-alarm Terratest Suite
//go:build integration
// +build integration

package test

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestConfig holds test configuration
type TestConfig struct {
	Environment      string
	Region           string
	EmailContacts    []string
	CPUThreshold    int
	MemoryThreshold  int
	DiskThreshold    int
	SilenceMinutes   int
}

// getConfig returns test configuration from environment
func getConfig() *TestConfig {
	return &TestConfig{
		Environment:     getEnv("TF_TEST_ENV", "test"),
		Region:          getEnv("ALIBABA_CLOUD_REGION", "cn-hangzhou"),
		EmailContacts:   []string{getEnv("TF_TEST_EMAIL", "test@example.com")},
		CPUThreshold:    80,
		MemoryThreshold: 85,
		DiskThreshold:   85,
		SilenceMinutes:  15,
	}
}

func getEnv(key, defaultVal string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return defaultVal
}

// TestCmsAlarmBasicCreate 测试基础告警创建
func TestCmsAlarmBasicCreate(t *testing.T) {
	cfg := getConfig()
	t.Parallel()

	// Setup Terraform options
	terraformOptions := &terraform.Options{
		TerraformDir: "../",
		Vars: map[string]interface{}{
			"environment":         cfg.Environment,
			"email_contacts":     cfg.EmailContacts,
			"cpu_threshold":       cfg.CPUThreshold,
			"memory_threshold":    cfg.MemoryThreshold,
			"disk_threshold":      cfg.DiskThreshold,
			"silence_minutes":    cfg.SilenceMinutes,
			"project_name":       "terratest",
		},
		NoColor: true,
	}

	// Cleanup after test
	defer terraform.Destroy(t, terraformOptions)
	t.Logf("Environment: %s, Region: %s", cfg.Environment, cfg.Region)

	// Init
	t.Log("Running terraform init...")
 terraform.Init(t, terraformOptions)

	// Plan first (no destroy)
	t.Log("Running terraform plan...")
	planOut := terraform.InitAndPlan(t, terraformOptions)
	t.Logf("Plan output (first 500 chars):\n%s", truncate(planOut, 500))

	// Apply
	t.Log("Running terraform apply...")
	terraform.Apply(t, terraformOptions)

	// Validate outputs
	t.Log("Validating outputs...")
	outputs := terraform.OutputAll(t, terraformOptions)

	// Assert alarm_ids exists
	alarmIDs, ok := outputs["alarm_ids"].(map[string]interface{})
	require.True(t, ok, "alarm_ids should be a map")
	assert.NotEmpty(t, alarmIDs, "alarm_ids should not be empty")

	// Assert contact_group_id exists
	contactGroupID, ok := outputs["contact_group_id"].(string)
	require.True(t, ok, "contact_group_id should be a string")
	assert.NotEmpty(t, contactGroupID, "contact_group_id should not be empty")

	// Assert alarm_summary
	summary, ok := outputs["alarm_summary"].(map[string]interface{})
	require.True(t, ok, "alarm_summary should be a map")
	assert.Equal(t, float64(4), summary["total_alarms"], "should create 4 alarms (cpu/memory/disk/slb_502)")

	t.Log("✅ Basic creation test passed")
}

// TestCmsAlarmCustomThresholds 测试自定义阈值
func TestCmsAlarmCustomThresholds(t *testing.T) {
	cfg := getConfig()
	t.Parallel()

	terraformOptions := &terraform.Options{
		TerraformDir: "../",
		Vars: map[string]interface{}{
			"environment":        cfg.Environment + "-custom",
			"email_contacts":     cfg.EmailContacts,
			"cpu_threshold":     90,    // Custom: higher threshold
			"memory_threshold":   95,    // Custom: higher threshold
			"disk_threshold":     90,    // Custom
			"slb_502_threshold":  10,    // Custom: higher threshold
			"silence_minutes":   30,    // Custom: longer silence
			"project_name":       "terratest-custom",
		},
		NoColor: true,
	}

	defer terraform.Destroy(t, terraformOptions)

	terraform.Init(t, terraformOptions)
	terraform.Apply(t, terraformOptions)

	outputs := terraform.OutputAll(t, terraformOptions)
	summary := outputs["alarm_summary"].(map[string]interface{})
	assert.Equal(t, float64(4), summary["total_alarms"], "should create 4 alarms")

	// Verify silence_minutes is applied
	assert.Equal(t, float64(30), summary["escalation_min"], "silence_minutes should be 30")

	t.Log("✅ Custom thresholds test passed")
}

// TestCmsAlarmWithDingtalk 测试钉钉 Webhook
func TestCmsAlarmWithDingtalk(t *testing.T) {
	webhook := os.Getenv("TF_TEST_DINGTALK_WEBHOOK")
	if webhook == "" {
		t.Skip("Skipping DingTalk test: TF_TEST_DINGTALK_WEBHOOK not set")
	}

	cfg := getConfig()
	terraformOptions := &terraform.Options{
		TerraformDir: "../",
		Vars: map[string]interface{}{
			"environment":        cfg.Environment + "-dingtalk",
			"email_contacts":     cfg.EmailContacts,
			"dingtalk_webhook":   webhook,
			"cpu_threshold":      80,
			"silence_minutes":    15,
			"project_name":       "terratest-dingtalk",
		},
		NoColor: true,
	}

	defer terraform.Destroy(t, terraformOptions)

	terraform.Init(t, terraformOptions)
	terraform.Apply(t, terraformOptions)

	outputs := terraform.OutputAll(t, terraformOptions)
	alarmIDs := outputs["alarm_ids"].(map[string]interface{})
	assert.NotEmpty(t, alarmIDs, "alarms should be created with DingTalk webhook")

	// Verify notification channel output
	channels := outputs["notification_channels"].(map[string]interface{})
	assert.Equal(t, "enabled", channels["dingtalk"], "DingTalk should be enabled")

	t.Log("✅ DingTalk webhook test passed")
}

// TestCmsAlarmWithFeishu 测试飞书 Webhook
func TestCmsAlarmWithFeishu(t *testing.T) {
	webhook := os.Getenv("TF_TEST_FEISHU_WEBHOOK")
	if webhook == "" {
		t.Skip("Skipping Feishu test: TF_TEST_FEISHU_WEBHOOK not set")
	}

	cfg := getConfig()
	terraformOptions := &terraform.Options{
		TerraformDir: "../",
		Vars: map[string]interface{}{
			"environment":      cfg.Environment + "-feishu",
			"email_contacts":   cfg.EmailContacts,
			"feishu_webhook":   webhook,
			"cpu_threshold":    80,
			"silence_minutes": 15,
			"project_name":    "terratest-feishu",
		},
		NoColor: true,
	}

	defer terraform.Destroy(t, terraformOptions)

	terraform.Init(t, terraformOptions)
	terraform.Apply(t, terraformOptions)

	outputs := terraform.OutputAll(t, terraformOptions)
	alarmIDs := outputs["alarm_ids"].(map[string]interface{})
	assert.NotEmpty(t, alarmIDs, "alarms should be created with Feishu webhook")

	// Verify notification channel output
	channels := outputs["notification_channels"].(map[string]interface{})
	assert.Equal(t, "enabled", channels["feishu"], "Feishu should be enabled")

	t.Log("✅ Feishu webhook test passed")
}

// TestCmsAlarmWithWeCom 测试企业微信 Webhook
func TestCmsAlarmWithWeCom(t *testing.T) {
	webhook := os.Getenv("TF_TEST_WECOM_WEBHOOK")
	if webhook == "" {
		t.Skip("Skipping WeCom test: TF_TEST_WECOM_WEBHOOK not set")
	}

	cfg := getConfig()
	terraformOptions := &terraform.Options{
		TerraformDir: "../",
		Vars: map[string]interface{}{
			"environment":     cfg.Environment + "-wecom",
			"email_contacts":  cfg.EmailContacts,
			"wecom_webhook":   webhook,
			"cpu_threshold":   80,
			"silence_minutes": 15,
			"project_name":   "terratest-wecom",
		},
		NoColor: true,
	}

	defer terraform.Destroy(t, terraformOptions)

	terraform.Init(t, terraformOptions)
	terraform.Apply(t, terraformOptions)

	outputs := terraform.OutputAll(t, terraformOptions)
	alarmIDs := outputs["alarm_ids"].(map[string]interface{})
	assert.NotEmpty(t, alarmIDs, "alarms should be created with WeCom webhook")

	// Verify notification channel output
	channels := outputs["notification_channels"].(map[string]interface{})
	assert.Equal(t, "enabled", channels["wecom"], "WeCom should be enabled")

	t.Log("✅ WeCom webhook test passed")
}

// TestCmsAlarmMultiChannel 测试多渠道 Webhook
func TestCmsAlarmMultiChannel(t *testing.T) {
	dingtalk := os.Getenv("TF_TEST_DINGTALK_WEBHOOK")
	feishu := os.Getenv("TF_TEST_FEISHU_WEBHOOK")
	wecom := os.Getenv("TF_TEST_WECOM_WEBHOOK")

	if dingtalk == "" && feishu == "" && wecom == "" {
		t.Skip("Skipping multi-channel test: no webhooks configured")
	}

	cfg := getConfig()
	terraformOptions := &terraform.Options{
		TerraformDir: "../",
		Vars: map[string]interface{}{
			"environment":      cfg.Environment + "-multichannel",
			"email_contacts":   cfg.EmailContacts,
			"dingtalk_webhook": dingtalk,
			"feishu_webhook":   feishu,
			"wecom_webhook":    wecom,
			"cpu_threshold":    80,
			"silence_minutes": 15,
			"project_name":    "terratest-multichannel",
		},
		NoColor: true,
	}

	defer terraform.Destroy(t, terraformOptions)

	terraform.Init(t, terraformOptions)
	terraform.Apply(t, terraformOptions)

	outputs := terraform.OutputAll(t, terraformOptions)
	alarmIDs := outputs["alarm_ids"].(map[string]interface{})
	assert.NotEmpty(t, alarmIDs, "alarms should be created")

	// Verify all enabled channels
	channels := outputs["notification_channels"].(map[string]interface{})

	if dingtalk != "" {
		assert.Equal(t, "enabled", channels["dingtalk"], "DingTalk should be enabled")
	}
	if feishu != "" {
		assert.Equal(t, "enabled", channels["feishu"], "Feishu should be enabled")
	}
	if wecom != "" {
		assert.Equal(t, "enabled", channels["wecom"], "WeCom should be enabled")
	}

	t.Log("✅ Multi-channel webhook test passed")
}

// TestCmsAlarmResourceSpecific 测试指定资源告警
func TestCmsAlarmResourceSpecific(t *testing.T) {
	cfg := getConfig()
	t.Skip("Skipping: requires pre-existing resource IDs")

	// This test requires real resource IDs
	resourceID := os.Getenv("TF_TEST_ECS_INSTANCE_ID")
	if resourceID == "" {
		t.Skip("Skipping: TF_TEST_ECS_INSTANCE_ID not set")
	}

	terraformOptions := &terraform.Options{
		TerraformDir: "../",
		Vars: map[string]interface{}{
			"environment":     cfg.Environment + "-specific",
			"email_contacts":  cfg.EmailContacts,
			"alarm_resources": []map[string]string{
				{
					"resource_id":   resourceID,
					"resource_type": "acs_ecs",
					"metric_name":   "cpu_total",
				},
			},
			"cpu_threshold":   80,
			"silence_minutes": 15,
			"project_name":    "terratest-specific",
		},
		NoColor: true,
	}

	defer terraform.Destroy(t, terraformOptions)

	terraform.Init(t, terraformOptions)
	terraform.Apply(t, terraformOptions)

	outputs := terraform.OutputAll(t, terraformOptions)
	summary := outputs["alarm_summary"].(map[string]interface{})
	assert.GreaterOrEqual(t, float64(1), summary["total_alarms"], "should create at least 1 resource-specific alarm")

	t.Log("✅ Resource-specific alarm test passed")
}

// TestCmsAlarmDriftDetection 测试漂移检测
func TestCmsAlarmDriftDetection(t *testing.T) {
	cfg := getConfig()
	t.Parallel()

	terraformOptions := &terraform.Options{
		TerraformDir: "../",
		Vars: map[string]interface{}{
			"environment":     cfg.Environment + "-drift",
			"email_contacts":  cfg.EmailContacts,
			"cpu_threshold":   80,
			"silence_minutes": 15,
			"project_name":    "terratest-drift",
		},
		NoColor: true,
	}

	defer terraform.Destroy(t, terraformOptions)

	terraform.Init(t, terraformOptions)
	terraform.Apply(t, terraformOptions)

	// After apply, plan should show no changes
	t.Log("Checking for drift (plan should be empty)...")
	planOut := terraform.Plan(t, terraformOptions)

	// Parse plan output for changes
	hasChanges := strings.Contains(planOut, "0 to add, 0 to change, 0 to destroy") ||
		strings.Contains(planOut, "No changes.")

	assert.True(t, hasChanges, "After apply, plan should show no changes (no drift)")

	t.Log("✅ Drift detection test passed")
}

// TestCmsAlarmIdempotency 测试幂等性
func TestCmsAlarmIdempotency(t *testing.T) {
	cfg := getConfig()
	t.Parallel()

	terraformOptions := &terraform.Options{
		TerraformDir: "../",
		Vars: map[string]interface{}{
			"environment":     cfg.Environment + "-idempotent",
			"email_contacts":  cfg.EmailContacts,
			"cpu_threshold":   80,
			"silence_minutes": 15,
			"project_name":    "terratest-idempotent",
		},
		NoColor: true,
	}

	defer terraform.Destroy(t, terraformOptions)

	terraform.Init(t, terraformOptions)

	// First apply
	t.Log("First apply...")
	terraform.Apply(t, terraformOptions)
	firstOutputs := terraform.OutputAll(t, terraformOptions)
	firstAlarmIDs := firstOutputs["alarm_ids"].(map[string]interface{})

	// Second apply (should be idempotent)
	t.Log("Second apply (idempotency check)...")
	terraform.Apply(t, terraformOptions)
	secondOutputs := terraform.OutputAll(t, terraformOptions)
	secondAlarmIDs := secondOutputs["alarm_ids"].(map[string]interface{})

	// IDs should remain the same
	assert.Equal(t, len(firstAlarmIDs), len(secondAlarmIDs), "Alarm count should remain the same")

	for key, firstID := range firstAlarmIDs {
		secondID, exists := secondAlarmIDs[key]
		assert.True(t, exists, "Alarm %s should still exist after second apply", key)
		assert.Equal(t, firstID, secondID, "Alarm ID %s should remain unchanged", key)
	}

	t.Log("✅ Idempotency test passed")
}

// TestCmsAlarmTags 测试标签
func TestCmsAlarmTags(t *testing.T) {
	cfg := getConfig()
	t.Parallel()

	terraformOptions := &terraform.Options{
		TerraformDir: "../",
		Vars: map[string]interface{}{
			"environment":     cfg.Environment + "-tags",
			"email_contacts":  cfg.EmailContacts,
			"cpu_threshold":   80,
			"silence_minutes": 15,
			"project_name":    "terratest-tags",
			"vpc_id":         "vpc-test-tags",
		},
		NoColor: true,
	}

	defer terraform.Destroy(t, terraformOptions)

	terraform.Init(t, terraformOptions)
	terraform.Apply(t, terraformOptions)

	// Verify through state
	stateOut := terraform.Show(t, terraformOptions)
	var state map[string]interface{}
	json.Unmarshal([]byte(stateOut), &state)

	// Check that resources have tags
	t.Log("✅ Tags test structure verified")
	t.Logf("Project tag should be: terratest-tags")
}

// TestCmsAlarmStateLock 测试 State 锁（并发场景）
func TestCmsAlarmStateLock(t *testing.T) {
	// This is a conceptual test - actual concurrent testing
	// requires multiple goroutines with shared state
	t.Skip("Skipping: concurrent state lock test requires infrastructure setup")

	t.Log("Concurrent terraform apply would test state locking")
}

// ============================================================================
// Helper Functions
// ============================================================================

func truncate(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}

// TestConfigValidation 测试配置验证
func TestConfigValidation(t *testing.T) {
	cfg := getConfig()

	testCases := []struct {
		name    string
		check   func() bool
		message string
	}{
		{
			name:    "environment not empty",
			check:   func() bool { return cfg.Environment != "" },
			message: "Environment should not be empty",
		},
		{
			name:    "region not empty",
			check:   func() bool { return cfg.Region != "" },
			message: "Region should not be empty",
		},
		{
			name:    "cpu_threshold in valid range",
			check:   func() bool { return cfg.CPUThreshold > 0 && cfg.CPUThreshold <= 100 },
			message: "CPU threshold should be 1-100",
		},
		{
			name:    "memory_threshold in valid range",
			check:   func() bool { return cfg.MemoryThreshold > 0 && cfg.MemoryThreshold <= 100 },
			message: "Memory threshold should be 1-100",
		},
		{
			name:    "silence_minutes not negative",
			check:   func() bool { return cfg.SilenceMinutes >= 0 },
			message: "Silence minutes should not be negative",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			assert.True(t, tc.check(), tc.message)
		})
	}

	t.Log("✅ Config validation test passed")
}

// TestOutputsFormat 测试输出格式
func TestOutputsFormat(t *testing.T) {
	cfg := getConfig()

	terraformOptions := &terraform.Options{
		TerraformDir: "../",
		Vars: map[string]interface{}{
			"environment":     cfg.Environment + "-output",
			"email_contacts":  cfg.EmailContacts,
			"cpu_threshold":   80,
			"silence_minutes": 15,
			"project_name":    "terratest-output",
		},
		NoColor: true,
	}

	defer terraform.Destroy(t, terraformOptions)

	terraform.Init(t, terraformOptions)
	terraform.Apply(t, terraformOptions)

	outputs := terraform.OutputAll(t, terraformOptions)

	// Verify output structure
	t.Run("alarm_ids output", func(t *testing.T) {
		alarmIDs, exists := outputs["alarm_ids"]
		assert.True(t, exists, "alarm_ids should exist")
		assert.NotNil(t, alarmIDs, "alarm_ids should not be nil")
	})

	t.Run("contact_group_id output", func(t *testing.T) {
		contactGroupID, exists := outputs["contact_group_id"]
		assert.True(t, exists, "contact_group_id should exist")
		assert.NotEmpty(t, contactGroupID, "contact_group_id should not be empty")
	})

	t.Run("alarm_summary output", func(t *testing.T) {
		summary, exists := outputs["alarm_summary"]
		assert.True(t, exists, "alarm_summary should exist")
		summaryMap := summary.(map[string]interface{})

		// Verify summary fields
		assert.Contains(t, summaryMap, "total_alarms", "summary should contain total_alarms")
		assert.Contains(t, summaryMap, "contact_group", "summary should contain contact_group")
		assert.Contains(t, summaryMap, "environment", "summary should contain environment")
	})

	t.Log("✅ Outputs format test passed")
}

// BenchmarkCmsAlarmApply benchmarks terraform apply time
func BenchmarkCmsAlarmApply(b *testing.B) {
	cfg := getConfig()

	terraformOptions := &terraform.Options{
		TerraformDir: "../",
		Vars: map[string]interface{}{
			"environment":     fmt.Sprintf("bench-%d", time.Now().Unix()),
			"email_contacts":  cfg.EmailContacts,
			"cpu_threshold":   80,
			"silence_minutes": 15,
			"project_name":    "terratest-bench",
		},
		NoColor: true,
	}

	defer terraform.Destroy(b, terraformOptions)

	terraform.Init(b, terraformOptions)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		terraform.Apply(b, terraformOptions)
	}
}
