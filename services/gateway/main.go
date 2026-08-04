// 网关入口：代理模型服务流量并异步上报观测事件。
package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"os/signal"
	"syscall"
	"time"

	"github.com/sufengx/vera/gateway/internal/config"
	"github.com/sufengx/vera/gateway/internal/gateway"
	"github.com/sufengx/vera/gateway/internal/schema"
	"github.com/sufengx/vera/gateway/internal/sink"
)

func main() {
	cfg := config.Load()
	queue := make(chan schema.Event, cfg.QueueSize)
	sw := sink.New(cfg.ClickHouse, cfg.DB, cfg.Table, queue, cfg.BatchSize, cfg.BatchInterval, cfg.RetryMax, cfg.ClickHouseUser, cfg.ClickHousePass)
	h, err := gateway.New(cfg, queue)
	if err != nil {
		log.Fatalf("初始化失败: %v", err)
	}
	srv := &http.Server{
		Addr:         cfg.Addr,
		Handler:      h,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
	}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	go func() {
		log.Printf("网关监听 %s，上报至 %s", cfg.Addr, cfg.ClickHouse)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("服务异常退出: %v", err)
		}
	}()
	<-ctx.Done()
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	srv.Shutdown(shutdownCtx)
	w, d, f := sw.Stats()
	log.Printf("网关退出，written=%d dropped=%d failed=%d", w, d, f)
}
