# 首月 GPU 云低成本替代选择

> 适用对象：E. coli 频谱虚拟细胞最小 Demo。  
> 当前阿里云报价：`ecs.gn7i-c8g1.2xlarge` 按量约 `￥9.7426/小时`，对首月工作流验证偏贵。  
> 结论：首月不要购买阿里云 A10。优先 AutoDL，要求更稳定的国际环境时选 RunPod Secure A5000。  
> 首月目标：只租 20-50 GPU 小时，总预算控制在 100-300 元。

## 1. 为什么不需要立刻租 100 小时

第一版 E. coli Demo 中，大部分工作不需要 GPU：

| 工作 | 是否需要 GPU |
|---|---|
| 下载 NCBI/UniProt/iML1515/RegulonDB | 否 |
| 解析 SBML、建词表、生成图谱 | 否 |
| COBRApy FBA 基线 | 否 |
| 图傅里叶初始化 | 通常不需要 |
| 2,000-20,000 质点的小规模逻辑时间模拟 | 可以先在 CPU 验证 |
| PyTorch/CUDA 环境验证 | 需要 1-2 小时 |
| 小型频谱字典训练 | 需要 10-30 小时 |
| 扰动实验和消融 | 需要 20-50 小时 |

因此，首月可以先在本地 WSL 完成 CPU 流程，再把已经能运行的任务发到 GPU 云做烟测。GPU 只用于 CUDA 环境、频谱模型和小规模 GPU 质点实验。

## 2. 推荐顺序

### 首选：AutoDL

适合：

- 中国区注册、充值和使用。
- 希望人民币付款、中文控制台、SSH 简单。
- 首月只做 20-50 小时 GPU 验证。
- 可以接受平台化 GPU 服务，而不是标准公有云 IaaS。

选择：

```text
GPU：RTX 3090、RTX 4090 或 A5000，24GB 显存
计费：按量付费
CPU：8 vCPU 以上
内存：30 GB 以上，尽量 40-60 GB
系统盘：默认容量
数据盘：50-100 GB，按需
镜像：PyTorch 2.x + CUDA 12.x + Ubuntu 22.04
```

预算参考：

| 使用量 | GPU 费用估算 | 存储与杂项 | 月合计 |
|---|---:|---:|---:|
| 20 小时 | 40-60 元 | 20-40 元 | 60-100 元 |
| 50 小时 | 100-150 元 | 20-50 元 | 120-200 元 |
| 100 小时 | 200-300 元 | 30-60 元 | 230-360 元 |

实际单价和库存以 AutoDL 控制台为准。不要购买长期包月实例，首月使用按量计费。

### 次选：RunPod Secure A5000

适合：

- 有国际支付方式。
- 希望标准容器环境、可移植性更高。
- 需要比社区 GPU 更稳定的计算节点。

RunPod 官方价格页当前列出的按需价格为：

| GPU | 显存 | Community | Secure |
|---|---:|---:|---:|
| RTX A5000 | 24GB | `$0.16/小时` | `$0.27/小时` |
| A40 | 48GB | `$0.35/小时` | `$0.49/小时` |
| RTX 4090 | 24GB | `$0.34/小时` | `$0.74/小时` |

网络存储当前标价为：

```text
Standard Network Storage：100 GB 约 $7/月
```

推荐：

```text
GPU：A5000 24GB Secure
GPU 时间：20-50 小时
Network Volume：50-100 GB
镜像：PyTorch/CUDA 容器
```

50 小时 A5000 Secure 加 100GB 网络存储，粗略成本约：

```text
GPU：50 x $0.27 = $13.50
存储：约 $7
合计：约 $20.50/月，约 150 元
```

### 只追求最低价格：Vast.ai

Vast.ai 上常见 3090/4090 的成本更低，但：

- 主机质量差异较大。
- 库存和 IP 可能变化。
- 持久化存储、网络和稳定性需要自行验证。

它适合已经支持 checkpoint 的短任务，不适合作为首月唯一开发环境。

不建议：

- 阿里云 A10 按量运行整月。
- T4 16GB 长期作为主力训练卡。
- A100、A800、H100。
- 多卡或 Kubernetes。
- Google Colab 作为唯一长期工作区。

## 3. 最省钱的执行方式

推荐首月流程：

```text
本地 WSL
  -> 下载数据、建词表、建图、跑 FBA、写测试
  -> Git push

AutoDL 或 RunPod
  -> 只在需要时启动 GPU
  -> 拉取代码和数据
  -> 跑 CUDA 烟测、小型频谱训练、GPU 质点实验
  -> checkpoint 写回持久化存储
  -> 停止 GPU
```

首月预算目标：

| 项目 | 建议预算 |
|---|---:|
| 本地 CPU 开发 | 0 元 |
| GPU 20-50 小时 | 40-150 元 |
| 持久化存储 50-100GB | 20-50 元 |
| 公网流量和备份 | 10-30 元 |
| **合计** | **约 70-230 元** |

## 4. AutoDL 购买路径

1. 注册 AutoDL 并完成实名认证。
2. 充值 100-200 元，首月不要一次充值过多。
3. 进入“算力市场”或“GPU 租用”。
4. 筛选 24GB 显存。
5. 优先按价格和库存选择：
   - RTX 3090 24GB
   - RTX 4090 24GB
   - A5000 24GB
6. 地区优先选择：
   - 北京 B 区
   - 西北 B 区
   - 内蒙 B 区
   - 其他延迟和价格合适、库存充足的地区
7. 计费方式选择按量付费，不选择包日或包月。
8. 选择 Ubuntu 22.04 + PyTorch 2.x + CUDA 12.x 镜像。
9. 系统盘保持默认，另加 50-100GB 数据盘或持久化存储。
10. 开放 SSH，保存 SSH 地址、端口和密码/密钥。
11. 实例开机后先验证：

```bash
nvidia-smi
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

12. 用本地 Codex 通过 SSH 接管：

```powershell
wsl.exe -d Ubuntu -- ssh -p <端口> root@<地址> "nvidia-smi"
```

13. 完成任务后，把代码提交到 Git，把 checkpoint 和结果同步到持久化存储。
14. 在 AutoDL 控制台关机，不要在实例内部只执行 `shutdown`。

## 5. RunPod 购买路径

1. 注册 RunPod 并添加少量余额。
2. 进入 Pods，选择 On-Demand。
3. 选择 Secure Cloud A5000 24GB。
4. 选择 PyTorch 2.x CUDA 12.x 模板。
5. 创建 50-100GB Network Volume，并挂载到 Pod。
6. 配置 SSH public key。
7. 暴露 TCP 22，保存 SSH host、port 和 Pod ID。
8. 本地 Codex 通过 SSH 连接并执行 GPU 烟测。
9. 任务结束先上传 checkpoint，再停止 Pod。
10. Network Volume 保留数据，不保留运行中的 GPU 费用。

## 6. 首月烟测清单

只购买 20-50 GPU 小时，完成以下任务即可：

1. NVIDIA 驱动、CUDA、PyTorch 正常。
2. Docker GPU 透传可用。
3. iML1515/FBA CPU 基线可运行。
4. 40-80 个 token 的词表和频谱初始化可运行。
5. 2,000-20,000 质点的小规模模拟在 GPU 上运行。
6. 训练一个最小频谱字典或状态预测模型。
7. 保存 checkpoint，关机后重新启动并继续。
8. 从 Git 和持久化存储完整恢复一次环境。

完成这些验收后，再决定是否扩大 GPU 预算。

## 7. 最终建议

如果当前还没有购买阿里云实例：

```text
暂停阿里云 A10 下单
改用 AutoDL 24GB 按量 GPU
首月只运行 20-50 小时
代码用 Git，数据用持久化磁盘加异云备份
```

如果希望环境更接近标准云平台且可以国际付款：

```text
RunPod Secure A5000 24GB
50 小时 GPU + 100GB Network Volume
```

这两种方案都比阿里云当前 `￥9.7426/小时` 更适合首月工作流验证。

## 8. 参考

- AutoDL 计费规则：<https://www.autodl.com/docs/price/>
- AutoDL GPU 选型：<https://www.autodl.com/docs/gpu/>
- RunPod 当前价格：<https://www.runpod.io/pricing>
- RunPod Pod 计费：<https://docs.runpod.io/pods/pricing>
