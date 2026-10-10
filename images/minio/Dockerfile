# Source: https://github.com/minio/minio/tree/9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a
# Build from that source checkout with this Dockerfile.
FROM golang:1.25-bookworm@sha256:3b4a11519ad929d1e1d261a12cff056f0c85b735253d7d861346b9c6f8b36437 AS build
WORKDIR /src
COPY . .
RUN CGO_ENABLED=0 GOMAXPROCS=2 go build -buildvcs=false -p 2 -trimpath -o /minio .
FROM gcr.io/distroless/static-debian12:nonroot@sha256:afa5c872c891853ca7fcf1f12c3edb23f7eeef36189728842dd51042ff57f7ab
COPY --from=build /minio /minio
USER 65532:65532
EXPOSE 9000 9001
ENTRYPOINT ["/minio"]
