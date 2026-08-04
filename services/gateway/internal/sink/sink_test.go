package sink

import (
	"compress/gzip"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/sufengx/vera/gateway/internal/schema"
)

func validEvents(n int) []schema.Event {
	evs := make([]schema.Event, n)
	for i := range evs {
		evs[i] = schema.Event{
			EventID:          schema.NewEventID(),
			Timestamp:        time.Now(),
			RequestID:        "req",
			ModelName:        "ctr",
			ModelVersion:     "v1",
			Route:            "/v1/predict",
			ClientID:         "c",
			InputSummaryHash: strings.Repeat("a", 64),
			ServerHostname:   "h",
			PrivacyMaskLevel: schema.MaskFull,
		}
	}
	return evs
}

func TestFlushEncoding(t *testing.T) {
	ch := make(chan string, 8)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gz, err := gzip.NewReader(r.Body)
		if err != nil {
			t.Error(err)
			return
		}
		b, _ := io.ReadAll(gz)
		ch <- string(b)
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	queue := make(chan schema.Event, 64)
	w := New(srv.URL, "vera", "events", queue, 500, time.Hour, 0)
	w.flush(validEvents(3))
	body := <-ch
	lines := strings.Split(strings.TrimSpace(body), "\n")
	if len(lines) != 3 {
		t.Fatalf("期望 3 行 JSONEachRow, 得到 %d", len(lines))
	}
	var ev schema.Event
	if err := json.Unmarshal([]byte(lines[0]), &ev); err != nil {
		t.Fatalf("行解析失败: %v", err)
	}
	if ev.ModelName != "ctr" {
		t.Fatalf("内容不符: %+v", ev)
	}
}

func TestRetryThenSuccess(t *testing.T) {
	var n atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if n.Add(1) < 2 {
			w.WriteHeader(http.StatusInternalServerError)
			return
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	queue := make(chan schema.Event, 8)
	w := New(srv.URL, "vera", "events", queue, 500, time.Hour, 3)
	w.flush(validEvents(1))
	if n.Load() != 2 {
		t.Fatalf("期望 2 次尝试, 得到 %d", n.Load())
	}
	if wr, _, _ := w.Stats(); wr != 1 {
		t.Fatalf("期望写入 1, 得到 %d", wr)
	}
}

func TestFlushOnInterval(t *testing.T) {
	written := make(chan struct{}, 1)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		written <- struct{}{}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	queue := make(chan schema.Event, 8)
	New(srv.URL, "vera", "events", queue, 500, 50*time.Millisecond, 0)
	queue <- validEvents(1)[0]
	select {
	case <-written:
	case <-time.After(2 * time.Second):
		t.Fatal("定时刷新未触发")
	}
}
