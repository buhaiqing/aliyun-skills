// SDK:      github.com/alibabacloud-go/dyvmsapi-20170525/v4/client
// Operation: SingleCallByTts — send single TTS voice notification
// Usage:
//   cd alicloud-voice-ops/assets/code-snippets
//   CALLED_NUMBER=13800138000 TTS_CODE=TTS_123456 SHOW_NUMBER=4008123123 go run single-call-tts.go

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
	calledNumber := os.Getenv("CALLED_NUMBER")
	if calledNumber == "" {
		log.Fatal("CALLED_NUMBER is required")
	}
	ttsCode := os.Getenv("TTS_CODE")
	if ttsCode == "" {
		log.Fatal("TTS_CODE is required")
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

	// Build request
	req := &dyvmsapi.SingleCallByTtsRequest{
		CalledNumber: tea.String(calledNumber),
		TtsCode:      tea.String(ttsCode),
	}

	// Optional: calling number displayed to the called party
	if showNumber != "" {
		req.CalledShowNumber = tea.String(showNumber)
	}
	// TtsParam: JSON string of template variables, e.g. {"product":"Alibaba Cloud"}
	if v := os.Getenv("TTS_PARAM"); v != "" {
		req.TtsParam = tea.String(v)
	}
	if v := os.Getenv("PLAY_TIMES"); v != "" {
		req.PlayTimes = tea.Int32(atoi32(v))
	}
	if v := os.Getenv("VOLUME"); v != "" {
		req.Volume = tea.Int32(atoi32(v))
	}
	if v := os.Getenv("SPEED"); v != "" {
		req.Speed = tea.Int32(atoi32(v))
	}
	if v := os.Getenv("OUT_ID"); v != "" {
		req.OutId = tea.String(v)
	}

	// Execute
	resp, err := client.SingleCallByTts(req)
	if err != nil {
		log.Fatalf("SingleCallByTts failed: %v", err)
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
