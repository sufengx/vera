FROM golang:1.26-alpine AS build
WORKDIR /src
COPY . .
RUN CGO_ENABLED=0 go build -o /out/gateway .

FROM alpine:3.21
RUN adduser -D -u 10001 vera
COPY --from=build /out/gateway /usr/local/bin/gateway
USER vera
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/gateway"]
