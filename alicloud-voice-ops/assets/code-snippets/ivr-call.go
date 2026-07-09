// SDK:      github.com/alibabacloud-go/dyvmsapi-20170525/v4/client
// Operation: IvrCall — start interactive voice response call
// Usage:
//   cd alicloud-voice-ops/assets/code-snippets
//   CALLED_NUMBER=13800138000 SHOW_NUMBER=4008123123 START_CODE=123456 go run ivr-call.go

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
	req := &dyvmsapi.IvrCallRequest{
		CalledNumber: tea.String(calledNumber),
	}

	// Optional: calling number displayed to the called party
	if showNumber != "" {
		req.CalledShowNumber = tea.String(showNumber)
	}
	if v := os.Getenv("OUT_ID"); v != "" {
		req.OutId = tea.String(v)
	}
	if v := os.Getenv("START_CODE"); v != "" {
		req.StartCode = tea.String(v)
	}
	if v := os.Getenv("START_TTS_PARAMS"); v != "" {
		req.StartTtsParams = tea.String(v)
	}

	// Execute
	resp, err := client.IvrCall(req)
	if err != nil {
		log.Fatalf("IvrCall failed: %v", err)
	}

	// Output as JSON
	out, _ := json.MarshalIndent(resp, "", "  ")
	fmt.Println(string(out))
}
