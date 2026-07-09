// SDK:      github.com/alibabacloud-go/dyvmsapi-20170525/v4/client
// Operation: CreateCallTask — create and execute batch voice notification task (equivalent to BatchCallByVoice)
// Usage:
//   cd alicloud-voice-ops/assets/code-snippets
//   CALLED_NUMBERS='["13800138000","13800138001"]' VOICE_CODE=123456 SHOW_NUMBER=4008123123 go run batch-call-voice.go

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
	// Required params from env
	calledNumbers := os.Getenv("CALLED_NUMBERS")
	if calledNumbers == "" {
		log.Fatal("CALLED_NUMBERS is required (JSON array string)")
	}
	voiceCode := os.Getenv("VOICE_CODE")
	if voiceCode == "" {
		log.Fatal("VOICE_CODE is required")
	}
	showNumber := os.Getenv("SHOW_NUMBER")
	if showNumber == "" {
		log.Fatal("SHOW_NUMBER is required")
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

	// Build request using CreateCallTask for batch voice notifications
	// BizType: VMS_VOICE_CODE for voice notification files
	req := &dyvmsapi.CreateCallTaskRequest{
		BizType:      tea.String("VMS_VOICE_CODE"),
		DataType:     tea.String("LIST"),
		Data:         tea.String(calledNumbers),
		TemplateCode: tea.String(voiceCode),
		Resource:     tea.String(showNumber),
	}

	if v := os.Getenv("TASK_NAME"); v != "" {
		req.TaskName = tea.String(v)
	}
	if v := os.Getenv("FIRE_TIME"); v != "" {
		req.FireTime = tea.String(v)
	}

	// Execute
	resp, err := client.CreateCallTask(req)
	if err != nil {
		log.Fatalf("CreateCallTask failed: %v", err)
	}

	// Output as JSON
	out, _ := json.MarshalIndent(resp, "", "  ")
	fmt.Println(string(out))
}
