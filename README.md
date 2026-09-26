# BakeOven

烘焙占炉排程：发酵+烘烤半开区间占用炉位，冲突检测与下一可开工窗口。

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4500 |
| API | http://localhost:9500 |
| API 文档 | http://localhost:9500/docs |
| Postgres | localhost:5446 |

健康检查：`GET http://localhost:9500/api/health`

## 页面

- `/products` — 产品
- `/ovens` — 炉位
- `/batches` — 批次
- `/gantt` — 甘特
- `/conflicts` — 冲突
- `/windows` — 可开工

## 使用说明

1. 查看产品配方时长与炉位。
2. 创建生产批次，系统按半开区间占炉并检测冲突。
3. 点“试算”只读预检：返回是否重叠、重叠阶段、对手批次及若排入后的发酵止/烘烤止；不新增批次、不写冲突日志。
4. 甘特查看占用；冲突与可开工窗口辅助排产。真正创建冲突时返回 409 并写入一条拒绝记录。

## 开发与测试

```bash
docker compose exec api pytest -q
```
