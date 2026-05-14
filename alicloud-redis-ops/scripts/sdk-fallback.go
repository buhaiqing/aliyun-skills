package main

import (
	"encoding/json"
	"fmt"
	"os"
	"text/tabwriter"

	openapi "github.com/alibabacloud-go/darabonba-openapi/client"
	"github.com/alibabacloud-go/tea/tea"
	rkvstore "github.com/alibabacloud-go/r-kvstore-20150101/v2/client"
)

type InstanceInfo struct {
	InstanceId       string `json:"InstanceId"`
	InstanceName     string `json:"InstanceName"`
	InstanceStatus   string `json:"InstanceStatus"`
	InstanceClass    string `json:"InstanceClass"`
	EngineVersion    string `json:"EngineVersion"`
	Capacity         int64  `json:"Capacity"`
	Bandwidth        int64  `json:"Bandwidth"`
	Connections      int64  `json:"Connections"`
	QPS              int64  `json:"QPS"`
	NetworkType      string `json:"NetworkType"`
	ChargeType       string `json:"ChargeType"`
	ConnectionDomain string `json:"ConnectionDomain"`
	Port             int64  `json:"Port"`
	PrivateIp        string `json:"PrivateIp"`
	ZoneId           string `json:"ZoneId"`
	CreateTime       string `json:"CreateTime"`
	EndTime          string `json:"EndTime"`
}

func main() {
	fmt.Println("=== SDK Fallback Path for Redis/Tair Operations ===")
	fmt.Println("")

	credentials := loadCredentials()
	if credentials == nil {
		fmt.Fprintf(os.Stderr, "ERROR: Failed to load credentials\n")
		fmt.Fprintf(os.Stderr, "Suggestion: Create .env file or set environment variables\n")
		os.Exit(1)
	}

	config := &openapi.Config{
		AccessKeyId:     tea.String(credentials.AccessKeyId),
		AccessKeySecret: tea.String(credentials.AccessKeySecret),
		RegionId:        tea.String(credentials.RegionId),
		Endpoint:        tea.String("r-kvstore.aliyuncs.com"),
	}

	c, err := rkvstore.NewClient(config)
	if err != nil {
		handleError("Client creation failed", err, "Check credentials and network connectivity")
		os.Exit(1)
	}

	req := &rkvstore.DescribeInstancesRequest{
		RegionId: tea.String(credentials.RegionId),
	}

	resp, err := c.DescribeInstances(req)
	if err != nil {
		handleError("DescribeInstances failed", err, "Check region and credentials")
		os.Exit(1)
	}

	data, err := json.Marshal(resp.Body)
	if err != nil {
		handleError("JSON marshaling failed", err, "Internal error")
		os.Exit(1)
	}

	var result struct {
		Instances struct {
			KVStoreInstance []InstanceInfo `json:"KVStoreInstance"`
		} `json:"Instances"`
		TotalCount int `json:"TotalCount"`
	}

	if err := json.Unmarshal(data, &result); err != nil {
		handleError("JSON unmarshaling failed", err, "Internal error")
		os.Exit(1)
	}

	displayResults(result)
}

type Credentials struct {
	AccessKeyId     string
	AccessKeySecret string
	RegionId        string
}

func loadCredentials() *Credentials {
	cred := &Credentials{}

	cred.AccessKeyId = os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
	cred.AccessKeySecret = os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
	cred.RegionId = os.Getenv("ALIBABA_CLOUD_REGION_ID")

	if cred.AccessKeyId == "" || cred.AccessKeySecret == "" || cred.RegionId == "" {
		fmt.Fprintf(os.Stderr, "ERROR: Missing credentials\n")
		fmt.Fprintf(os.Stderr, "  ALIBABA_CLOUD_ACCESS_KEY_ID: %s\n", maskCredential(cred.AccessKeyId))
		fmt.Fprintf(os.Stderr, "  ALIBABA_CLOUD_ACCESS_KEY_SECRET: %s\n", maskCredential(cred.AccessKeySecret))
		fmt.Fprintf(os.Stderr, "  ALIBABA_CLOUD_REGION_ID: %s\n", cred.RegionId)
		return nil
	}

	return cred
}

func maskCredential(cred string) string {
	if cred == "" {
		return "<NOT SET>"
	}
	if len(cred) <= 8 {
		return "***"
	}
	return cred[:4] + "***" + cred[len(cred)-4:]
}

func handleError(context string, err error, suggestion string) {
	fmt.Fprintf(os.Stderr, "\nERROR: %s\n", context)
	fmt.Fprintf(os.Stderr, "Details: %v\n", err)
	fmt.Fprintf(os.Stderr, "Suggestion: %s\n", suggestion)
	fmt.Fprintf(os.Stderr, "\nTroubleshooting Steps:\n")
	fmt.Fprintf(os.Stderr, "1. Run pre-flight check: bash scripts/preflight-check.sh\n")
	fmt.Fprintf(os.Stderr, "2. Check .env file exists and contains valid credentials\n")
	fmt.Fprintf(os.Stderr, "3. Verify network connectivity to r-kvstore.aliyuncs.com\n")
	fmt.Fprintf(os.Stderr, "4. Check RAM permissions for r-kvstore:* actions\n")
}

func displayResults(result struct {
	Instances struct {
		KVStoreInstance []InstanceInfo `json:"KVStoreInstance"`
	} `json:"Instances"`
	TotalCount int `json:"TotalCount"`
}) {
	region := os.Getenv("ALIBABA_CLOUD_REGION_ID")
	fmt.Printf("\n=== Redis/Tair 实例列表 (区域: %s) ===\n", region)
	fmt.Printf("总计: %d 个实例\n\n", result.TotalCount)

	w := tabwriter.NewWriter(os.Stdout, 0, 0, 3, ' ', 0)
	fmt.Fprintln(w, "序号\t实例ID\t实例名称\t状态\t规格\t版本\t容量(MB)\t网络类型\t付费类型")
	fmt.Fprintln(w, "----\t--------\t----------\t----\t----\t----\t---------\t----------\t--------")

	for i, instance := range result.Instances.KVStoreInstance {
		fmt.Fprintf(w, "%d\t%s\t%s\t%s\t%s\t%s\t%d\t%s\t%s\n",
			i+1,
			instance.InstanceId,
			instance.InstanceName,
			instance.InstanceStatus,
			instance.InstanceClass,
			instance.EngineVersion,
			instance.Capacity,
			instance.NetworkType,
			instance.ChargeType,
		)
	}
	w.Flush()

	fmt.Println("\n详细信息:")
	fmt.Println("=====================================")
	for i, instance := range result.Instances.KVStoreInstance {
		fmt.Printf("\n[%d] %s (%s)\n", i+1, instance.InstanceName, instance.InstanceId)
		fmt.Printf("  状态: %s\n", instance.InstanceStatus)
		fmt.Printf("  规格: %s\n", instance.InstanceClass)
		fmt.Printf("  版本: Redis %s\n", instance.EngineVersion)
		fmt.Printf("  容量: %d MB\n", instance.Capacity)
		fmt.Printf("  带宽: %d MB/s\n", instance.Bandwidth)
		fmt.Printf("  最大连接数: %d\n", instance.Connections)
		fmt.Printf("  QPS: %d\n", instance.QPS)
		fmt.Printf("  网络类型: %s\n", instance.NetworkType)
		fmt.Printf("  付费类型: %s\n", instance.ChargeType)
		fmt.Printf("  连接地址: %s:%d\n", instance.ConnectionDomain, instance.Port)
		fmt.Printf("  私网IP: %s\n", instance.PrivateIp)
		fmt.Printf("  可用区: %s\n", instance.ZoneId)
		fmt.Printf("  创建时间: %s\n", instance.CreateTime)
		if instance.ChargeType == "PrePaid" {
			fmt.Printf("  到期时间: %s\n", instance.EndTime)
		}
	}

	fmt.Println("\n=== SDK Fallback Execution Successful ===")
}