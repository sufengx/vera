// Package sink 批量写入事件到 ClickHouse。
package sink

import (
	"bytes"
	"compress/gzip"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"sync/atomic"
	"time"

	"github.com/sufengx/vera/gateway/internal/schema"
)

// Writer 聚合事件并按批写入 ClickHouse，写入与请求路径解耦。
type Writer struct {
	addr   string
	table  string
	auth   string // Basic 认证头，未配置时为空
	client *http.Client
	queue  <-chan schema.Event

	batchSize     int
	batchInterval time.Duration
	retryMax      int

	written atomic.Uint64 // 成功写入的事件数
	dropped atomic.Uint64 // 队列满丢弃数
	failed  atomic.Uint64 // 写入失败丢弃数
}

// New 创建写入器并启动后台协程。queue 满时由写入方负责丢弃策略。
func New(addr, db, table string, queue <-chan schema.Event, batchSize int, batchInterval time.Duration, retryMax int, user, pass string) *Writer {
	w := &Writer{
		addr:          addr,
		table:         db + "." + table,
		client:        &http.Client{Timeout: 10 * time.Second},
		queue:         queue,
		batchSize:     batchSize,
		batchInterval: batchInterval,
		retryMax:      retryMax,
	}
	if user != "" {
		w.auth = "Basic " + base64.StdEncoding.EncodeToString([]byte(user+":"+pass))
	}
	go w.loop()
	return w
}

// Stats 返回写入统计。
func (w *Writer) Stats() (written, dropped, failed uint64) {
	return w.written.Load(), w.dropped.Load(), w.failed.Load()
}

func (w *Writer) loop() {
	batch := make([]schema.Event, 0, w.batchSize)
	timer := time.NewTimer(w.batchInterval)
	defer timer.Stop()
	for {
		select {
		case ev := <-w.queue:
			batch = append(batch, ev)
			if len(batch) >= w.batchSize {
				w.flush(batch)
				batch = batch[:0]
				timer.Reset(w.batchInterval)
			}
		case <-timer.C:
			if len(batch) > 0 {
				w.flush(batch)
				batch = batch[:0]
			}
			timer.Reset(w.batchInterval)
		}
	}
}

// flush 编码、压缩并写入，失败按指数退避重试。
func (w *Writer) flush(batch []schema.Event) {
	body, err := encodeBatch(batch)
	if err != nil {
		log.Printf("事件编码失败: %v", err)
		w.failed.Add(uint64(len(batch)))
		return
	}
	q := url.Values{"query": {fmt.Sprintf("INSERT INTO %s FORMAT JSONEachRow", w.table)}}
	req, err := http.NewRequest(http.MethodPost, w.addr+"/?"+q.Encode(), body)
	if err != nil {
		w.failed.Add(uint64(len(batch)))
		return
	}
	req.Header.Set("Content-Encoding", "gzip")
	if w.auth != "" {
		req.Header.Set("Authorization", w.auth)
	}
	for i := 0; ; i++ {
		resp, err := w.client.Do(req)
		if err == nil {
			io.Copy(io.Discard, resp.Body)
			resp.Body.Close()
			if resp.StatusCode == http.StatusOK {
				w.written.Add(uint64(len(batch)))
				return
			}
			log.Printf("ClickHouse 写入失败 status=%d", resp.StatusCode)
		} else {
			log.Printf("ClickHouse 连接失败: %v", err)
		}
		if i >= w.retryMax {
			w.failed.Add(uint64(len(batch)))
			log.Printf("重试耗尽，丢弃 %d 条事件", len(batch))
			return
		}
		time.Sleep(time.Duration(1<<i) * 100 * time.Millisecond)
	}
}

// encodeBatch 序列化为 gzip 压缩的 JSONEachRow。
func encodeBatch(batch []schema.Event) (io.Reader, error) {
	var raw bytes.Buffer
	enc := json.NewEncoder(&raw)
	for i := range batch {
		if err := enc.Encode(&batch[i]); err != nil {
			return nil, err
		}
	}
	var buf bytes.Buffer
	gw := gzip.NewWriter(&buf)
	if _, err := gw.Write(raw.Bytes()); err != nil {
		return nil, err
	}
	if err := gw.Close(); err != nil {
		return nil, err
	}
	return &buf, nil
}
