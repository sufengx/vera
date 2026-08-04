package gateway

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/sufengx/vera/gateway/internal/config"
	"github.com/sufengx/vera/gateway/internal/schema"
)

func mockUpstream(pred string, conf float64) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]any{"prediction": pred, "confidence": conf})
	}))
}

func newTestHandler(upstream string) (*Handler, chan schema.Event, error) {
	events := make(chan schema.Event, 16)
	cfg := config.Config{
		Upstream:     upstream,
		ModelName:    "ctr",
		ModelVersion: "v1",
	}
	h, err := New(cfg, events)
	return h, events, err
}

func TestProxyAndEvent(t *testing.T) {
	up := mockUpstream("0.85", 0.9)
	defer up.Close()
	h, events, err := newTestHandler(up.URL)
	if err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest(http.MethodPost, "http://gw.test/v1/predict",
		strings.NewReader(`{"user_id":"u1","price":9.9}`))
	req.Header.Set("X-Client-ID", "client-7")
	req.Header.Set("X-Request-ID", "req-42")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("转发失败: %d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), "0.85") {
		t.Fatalf("上游响应未透传: %s", rec.Body.String())
	}
	select {
	case ev := <-events:
		if err := ev.Validate(); err != nil {
			t.Fatalf("事件非法: %v", err)
		}
		if ev.RequestID != "req-42" || ev.ClientID != "client-7" {
			t.Fatalf("请求头未采集: %+v", ev)
		}
		if ev.Prediction != "0.85" || ev.Confidence != 0.9 {
			t.Fatalf("预测未解析: %+v", ev)
		}
		if ev.LatencyMs <= 0 {
			t.Fatal("延迟未记录")
		}
		if ev.InputSummaryHash == "" {
			t.Fatal("输入哈希缺失")
		}
		if ev.PrivacyMaskLevel != schema.MaskFull {
			t.Fatal("隐私级别不符")
		}
	case <-time.After(time.Second):
		t.Fatal("事件未入队")
	}
}

func TestUpstreamDown(t *testing.T) {
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {}))
	addr := up.URL
	up.Close()
	h, _, err := newTestHandler(addr)
	if err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest(http.MethodPost, "http://gw.test/v1/predict", strings.NewReader(`{}`))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusBadGateway {
		t.Fatalf("期望 502, 得到 %d", rec.Code)
	}
}

func TestClientIDFallback(t *testing.T) {
	up := mockUpstream("1", 1)
	defer up.Close()
	h, events, err := newTestHandler(up.URL)
	if err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest(http.MethodPost, "http://gw.test/v1/predict", strings.NewReader(`{}`))
	req.RemoteAddr = "10.0.0.1:12345"
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	select {
	case ev := <-events:
		if ev.ClientID == "" || ev.ClientID == "10.0.0.1:12345" {
			t.Fatalf("client_id 回退逻辑错误: %s", ev.ClientID)
		}
	case <-time.After(time.Second):
		t.Fatal("事件未入队")
	}
}
