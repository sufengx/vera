package schema

import (
	"encoding/json"
	"strings"
	"testing"
	"time"
)

func validEvent() Event {
	return Event{
		EventID:          NewEventID(),
		Timestamp:        CHTime(time.Now()),
		RequestID:        "req-1",
		ModelName:        "ctr",
		ModelVersion:     "v1",
		Route:            "/v1/predict",
		ClientID:         "client-1",
		InputSummaryHash: strings.Repeat("a", 64),
		ServerHostname:   "host-1",
		PrivacyMaskLevel: MaskFull,
	}
}

func TestValidateOK(t *testing.T) {
	e := validEvent()
	if err := e.Validate(); err != nil {
		t.Fatalf("合法事件被拒绝: %v", err)
	}
}

func TestValidateMissingField(t *testing.T) {
	cases := []struct {
		name   string
		mutate func(*Event)
	}{
		{"event_id 为空", func(e *Event) { e.EventID = "" }},
		{"event_id 非 UUID", func(e *Event) { e.EventID = "x" }},
		{"timestamp 为空", func(e *Event) { e.Timestamp = CHTime{} }},
		{"request_id 为空", func(e *Event) { e.RequestID = "" }},
		{"model_name 为空", func(e *Event) { e.ModelName = "" }},
		{"model_version 为空", func(e *Event) { e.ModelVersion = "" }},
		{"route 为空", func(e *Event) { e.Route = "" }},
		{"client_id 为空", func(e *Event) { e.ClientID = "" }},
		{"hash 长度不足", func(e *Event) { e.InputSummaryHash = strings.Repeat("a", 63) }},
		{"hash 非法字符", func(e *Event) { e.InputSummaryHash = strings.Repeat("z", 64) }},
		{"hostname 为空", func(e *Event) { e.ServerHostname = "" }},
		{"mask 非法", func(e *Event) { e.PrivacyMaskLevel = "bad" }},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			e := validEvent()
			c.mutate(&e)
			if err := e.Validate(); err == nil {
				t.Fatal("期望校验失败")
			}
		})
	}
}

func TestMarshalJSON(t *testing.T) {
	ts := time.Date(2026, 8, 4, 12, 34, 56, 789000000, time.UTC)
	e := validEvent()
	e.Timestamp = CHTime(ts)
	b, err := json.Marshal(e)
	if err != nil {
		t.Fatal(err)
	}
	s := string(b)
	if !strings.Contains(s, `"timestamp":"2026-08-04 12:34:56.789"`) {
		t.Fatalf("时间格式不符: %s", s)
	}
	if !strings.Contains(s, `"privacy_mask_level":"full"`) {
		t.Fatalf("字段缺失: %s", s)
	}
}

func TestNewEventID(t *testing.T) {
	a, b := NewEventID(), NewEventID()
	if a == b {
		t.Fatal("UUID 重复")
	}
	if !isUUID(a) {
		t.Fatalf("生成的不是合法 UUID: %s", a)
	}
}
