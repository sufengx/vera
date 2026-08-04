// Package gateway 代理上游模型服务，为每个请求生成观测事件。
package gateway

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strconv"
	"time"

	"github.com/sufengx/vera/gateway/internal/config"
	"github.com/sufengx/vera/gateway/internal/schema"
)

// Handler 拦截并转发请求，构造事件后交给调用方。
type Handler struct {
	cfg    config.Config
	proxy  *httputil.ReverseProxy
	events chan<- schema.Event
	host   string
}

// New 创建处理器。
func New(cfg config.Config, events chan<- schema.Event) (*Handler, error) {
	target, err := url.Parse(cfg.Upstream)
	if err != nil {
		return nil, fmt.Errorf("解析上游地址: %w", err)
	}
	host, _ := os.Hostname()
	h := &Handler{cfg: cfg, events: events, host: host}
	h.proxy = &httputil.ReverseProxy{
		Rewrite: func(r *httputil.ProxyRequest) {
			r.SetURL(target)
		},
		ErrorHandler: func(w http.ResponseWriter, r *http.Request, err error) {
			log.Printf("上游转发失败 %s %s: %v", r.Method, r.URL.Path, err)
			http.Error(w, "upstream unavailable", http.StatusBadGateway)
		},
	}
	return h, nil
}

// ServeHTTP 转发请求并采集事件。
func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	start := time.Now()
	body, _ := io.ReadAll(r.Body)
	r.Body = io.NopCloser(bytes.NewReader(body))
	cw := &captureWriter{ResponseWriter: w}
	h.proxy.ServeHTTP(cw, r)
	ev := h.buildEvent(r, body, cw.body.Bytes(), time.Since(start))
	select {
	case h.events <- ev:
	default:
		// 队列已满则丢弃，保证请求路径不因上报而阻塞
		log.Printf("事件队列已满，丢弃 %s", ev.RequestID)
	}
}

// buildEvent 组装观测事件。
func (h *Handler) buildEvent(r *http.Request, in, out []byte, dur time.Duration) schema.Event {
	clientID := r.Header.Get("X-Client-ID")
	if clientID == "" {
		clientID = shortHash(r.RemoteAddr)
	}
	pred, conf := parsePrediction(out)
	ev := schema.Event{
		EventID:          schema.NewEventID(),
		Timestamp:        schema.CHTime(time.Now().UTC()),
		RequestID:        firstNonEmpty(r.Header.Get("X-Request-ID"), schema.NewEventID()),
		ModelName:        firstNonEmpty(r.Header.Get("X-Model-Name"), h.cfg.ModelName),
		ModelVersion:     firstNonEmpty(r.Header.Get("X-Model-Version"), h.cfg.ModelVersion),
		Route:            r.URL.Path,
		ClientID:         clientID,
		InputSummaryHash: hashHex(in),
		Prediction:       pred,
		Confidence:       conf,
		LatencyMs:        float64(dur.Microseconds()) / 1000,
		ServerHostname:   h.host,
		ContainerID:      h.cfg.ContainerID,
		SamplingFlag:     true,
		PrivacyMaskLevel: schema.MaskFull,
	}
	return ev
}

// parsePrediction 从模型响应提取预测结果与置信度，格式不匹配时留空。
func parsePrediction(body []byte) (string, float64) {
	var m map[string]any
	if json.Unmarshal(body, &m) != nil {
		return "", 0
	}
	var pred string
	switch v := m["prediction"].(type) {
	case string:
		pred = v
	case float64:
		pred = strconv.FormatFloat(v, 'f', -1, 64)
	}
	var conf float64
	if v, ok := m["confidence"].(float64); ok {
		conf = v
	}
	return pred, conf
}

// captureWriter 记录响应状态码与响应体。
type captureWriter struct {
	http.ResponseWriter
	status int
	body   bytes.Buffer
}

func (w *captureWriter) WriteHeader(code int) {
	w.status = code
	w.ResponseWriter.WriteHeader(code)
}

func (w *captureWriter) Write(b []byte) (int, error) {
	if w.status == 0 {
		w.status = http.StatusOK
	}
	w.body.Write(b)
	return w.ResponseWriter.Write(b)
}

func hashHex(b []byte) string {
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

func shortHash(s string) string {
	sum := sha256.Sum256([]byte(s))
	return hex.EncodeToString(sum[:8])
}

func firstNonEmpty(a, b string) string {
	if a != "" {
		return a
	}
	return b
}
