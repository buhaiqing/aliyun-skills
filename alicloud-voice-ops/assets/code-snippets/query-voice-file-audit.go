// SDK:      github.com/alibabacloud-go/dyvmsapi-20170525/v4/client
// Operation: QueryVoiceFileAuditInfo — query voice file audit status
// Usage:
//   cd alicloud-voice-ops/assets/code-snippets
//   VOICE_CODES="voice_demo.wav" go run query-voice-file-audit.go

package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"

	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	dyvmsapi "github.com/alibabacloud-go/dyvmsapi-20170525/v4/client"
	"github.com/alibabacloud-go/tea/tea"
)

func main() {
	// Required: comma-separated voice file codes (max 10)
	voiceCodes := os.Getenv("VOICE_CODES")
	if voiceCodes == "" {
		log.Fatal("VOICE_CODES is required (comma-separated voice file codes)")
	}

	// Init SDK client from env: ALIBABA_CLOUD_ACCESS_KEY_ID, _SECRET, _REGION_ID
	client, err := dyvmsapi.NewClient(&openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
		RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	})
	if err != nil {
		log.Fatalf("client init: %v", err)
	}

	// Build request
	req := &dyvmsapi.QueryVoiceFileAuditInfoRequest{
		VoiceCodes: tea.String(voiceCodes),
	}

	// Optional: BusinessType — 0 (voice notification, default), 2 (recording file)
	if v := os.Getenv("BUSINESS_TYPE"); v != "" {
		req.BusinessType = tea.Int32(atoi32(v))
	}

	// Execute
	resp, err := client.QueryVoiceFileAuditInfo(req)
	if err != nil {
		log.Fatalf("QueryVoiceFileAuditInfo failed: %v", err)
	}

	// Output as JSON
	out, _ := json.MarshalIndent(resp, "", "  ")
	fmt.Println(string(out))
}

func atoi32(s string) int32 {
	var n int32
	fmt.Sscanf(s, "%d", &n)
	return n
}
