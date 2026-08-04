// Package schema 定义推理观测事件的结构与校验规则。
// 字段与 ClickHouse vera.events 表一一对应，JSON 格式兼容 JSONEachRow。
package schema

import (
	"crypto/rand"
	"errors"
	"fmt"
	"strings"
	"time"
)

// NewEventID 生成 UUID v4。
func NewEventID() string {
	b := make([]byte, 16)
	rand.Read(b)
	b[6] = b[6]&0x0f | 0x40
	b[8] = b[8]&0x3f | 0x80
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:16])
}

// CHTime 毫秒精度时间戳，JSON 输出兼容 ClickHouse JSONEachRow 解析。
type CHTime time.Time

// MarshalJSON 输出 UTC 毫秒精度、空格分隔且无时区后缀的字符串。
func (t CHTime) MarshalJSON() ([]byte, error) {
	return []byte(`"` + time.Time(t).UTC().Format("2006-01-02 15:04:05.000") + `"`), nil
}

// UnmarshalJSON 解析对应格式的时间字符串。
func (t *CHTime) UnmarshalJSON(b []byte) error {
	ts, err := time.Parse("2006-01-02 15:04:05.000", strings.Trim(string(b), `"`))
	if err != nil {
		return err
	}
	*t = CHTime(ts)
	return nil
}

// Event 记录一次推理请求的观测数据。
// 隐私约定：只携带摘要与哈希，不携带原文。
type Event struct {
	EventID           string  `json:"event_id"`
	Timestamp         CHTime  `json:"timestamp"`
	RequestID         string  `json:"request_id"`
	ModelName         string  `json:"model_name"`
	ModelVersion      string  `json:"model_version"`
	Route             string  `json:"route"`
	ClientID          string  `json:"client_id"`
	InputSummaryHash  string  `json:"input_summary_hash"`
	InputFeatures     string  `json:"input_features,omitempty"`
	InputEmbeddingRef string  `json:"input_embedding_ref,omitempty"`
	Prediction        string  `json:"prediction"`
	Confidence        float64 `json:"confidence"`
	LatencyMs         float64 `json:"latency_ms"`
	ServerHostname    string  `json:"server_hostname"`
	ContainerID       string  `json:"container_id"`
	Label             *string `json:"label,omitempty"`
	LabelTimestamp    *CHTime `json:"label_timestamp,omitempty"`
	SamplingFlag      bool    `json:"sampling_flag"`
	PrivacyMaskLevel  string  `json:"privacy_mask_level"`
}

// 隐私脱敏级别。
const (
	MaskNone    = "none"
	MaskPartial = "partial"
	MaskFull    = "full"
)

// IsZero 判断时间是否为零值。
func (t CHTime) IsZero() bool {
	return time.Time(t).IsZero()
}

// Validate 校验必填字段与格式。
func (e *Event) Validate() error {
	switch {
	case !isUUID(e.EventID):
		return errors.New("event_id 必须为 UUID")
	case e.Timestamp.IsZero():
		return errors.New("timestamp 不能为空")
	case e.RequestID == "":
		return errors.New("request_id 不能为空")
	case e.ModelName == "":
		return errors.New("model_name 不能为空")
	case e.ModelVersion == "":
		return errors.New("model_version 不能为空")
	case e.Route == "":
		return errors.New("route 不能为空")
	case e.ClientID == "":
		return errors.New("client_id 不能为空")
	case !isSHA256(e.InputSummaryHash):
		return errors.New("input_summary_hash 必须为 sha256 十六进制")
	case e.ServerHostname == "":
		return errors.New("server_hostname 不能为空")
	case e.PrivacyMaskLevel != MaskNone && e.PrivacyMaskLevel != MaskPartial && e.PrivacyMaskLevel != MaskFull:
		return errors.New("privacy_mask_level 必须是 none/partial/full")
	}
	return nil
}

func isUUID(s string) bool {
	if len(s) != 36 {
		return false
	}
	for i, c := range s {
		switch i {
		case 8, 13, 18, 23:
			if c != '-' {
				return false
			}
		default:
			if !isHex(c) {
				return false
			}
		}
	}
	return true
}

func isSHA256(s string) bool {
	if len(s) != 64 {
		return false
	}
	for _, c := range s {
		if !isHex(c) {
			return false
		}
	}
	return true
}

func isHex(c rune) bool {
	return c >= '0' && c <= '9' || c >= 'a' && c <= 'f' || c >= 'A' && c <= 'F'
}

// String 返回事件摘要，用于日志。
func (e *Event) String() string {
	return fmt.Sprintf("%s model=%s@%s route=%s latency=%.1fms", e.RequestID, e.ModelName, e.ModelVersion, e.Route, e.LatencyMs)
}
