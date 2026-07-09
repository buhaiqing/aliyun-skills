// SDK:      github.com/alibabacloud-go/dyvmsapi-20170525/v4/client
// Operation: QueryCallDetailByCallId — query call detail record by call ID
// Usage:
//   cd alicloud-voice-ops/assets/code-snippets
//   CALL_ID=123456789^123456 QUERY_DATE=2026-06-15 go run query-call-detail.go

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
	callID := os.Getenv("CALL_ID")
	if callID == "" {
		log.Fatal("CALL_ID is required")
	}
	queryDate := os.Getenv("QUERY_DATE")
	if queryDate == "" {
		log.Fatal("QUERY_DATE is required (format: YYYY-MM-DD)")
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
	req := &dyvmsapi.QueryCallDetailByCallIdRequest{
		CallId:    tea.String(callID),
		QueryDate: tea.Int64(parseTimestamp(queryDate)),
	}

	// Optional: ProdId — product type (default 0 for voice)
	if v := os.Getenv("PROD_ID"); v != "" {
		req.ProdId = tea.Int64(atoi64(v))
	}

	// Execute
	resp, err := client.QueryCallDetailByCallId(req)
	if err != nil {
		log.Fatalf("QueryCallDetailByCallId failed: %v", err)
	}

	// Output as JSON
	out, _ := json.MarshalIndent(resp, "", "  ")
	fmt.Println(string(out))
}

func parseTimestamp(dateStr string) int64 {
	// Parse YYYY-MM-DD and return Unix timestamp
	var year, month, day int
	fmt.Sscanf(dateStr, "%d-%d-%d", &year, &month, &day)
	// Approximate timestamp for the start of the day
	t := int64(year-1970)*31536000 + int64((month-1))*2592000 + int64(day-1)*86400
	return t
}

func atoi64(s string) int64 {
	var n int64
	fmt.Sscanf(s, "%d", &n)
	return n
}
