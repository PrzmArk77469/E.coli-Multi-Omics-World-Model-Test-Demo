# 阿里云首月 GPU ECS 购买手把手

> 目标：购买一台按量付费 GPU ECS，用一个月验证 Codex 本地控制、SSH、Docker/CUDA、OSS、Codeup 和 GPU 任务的完整工作流。  
> 默认方案：`ecs.gn7i-c8g1.2xlarge`，8 vCPU / 30 GiB / 1 x A10 24GB。  
> 低成本备选：`ecs.gn6i-c4g1.xlarge`，4 vCPU / 15 GiB / 1 x T4 16GB。  
> 关键原则：按量付费、节省停机、自动释放、数据放 OSS、代码放 Codeup。

## 1. 购买前准备

### 1.1 账号

1. 登录阿里云中国站：<https://www.aliyun.com/>
2. 完成个人或企业实名认证。
3. 进入费用中心，确认账户余额充足。按量付费实例通常要求账户有可用余额。
4. 确认可以购买 GPU ECS；新账号或特殊账号可能需要申请 GPU 配额。
5. 不要在第一天购买包年包月、ACK、NAS 或数据库。

### 1.2 先确定四个值

```text
地域：华东 2（上海）
实例：ecs.gn7i-c8g1.2xlarge
付费：按量付费
用途：E. coli 最小 Demo 工作流验证
```

备选地域顺序：

1. 华东 2（上海）
2. 华东 1（杭州）
3. 华北 2（北京）

ECS、OSS、ACR 应尽量放在同一地域，避免跨地域流量费用和延迟。

## 2. 进入购买页面

推荐路径：

1. 登录 ECS 控制台：<https://ecs.console.aliyun.com/>
2. 左侧选择“实例与镜像” -> “实例”。
3. 单击右上角“创建实例”。
4. 如果出现“一键购买”和“自定义购买”，选择“自定义购买”。
5. 不要使用“快速购买”，它通常不方便精确选择 GPU 实例族和公网计费方式。

如果控制台入口发生变化，也可以直接打开 ECS 购买页，再按下面的选项配置。

## 3. 基础配置

### 3.1 付费模式

选择：

```text
按量付费
```

不要选择：

- 包年包月
- 抢占式实例

原因：

- 首月是工作流验证，使用时间不确定。
- 包年包月停机后仍继续计费。
- 抢占式适合已经支持 checkpoint 的正式任务，不适合第一次搭环境。

### 3.2 地域和可用区

选择：

```text
地域：华东 2（上海）或华东 1（杭州）
可用区：优先默认可用区
```

如果默认可用区没有 GPU 库存，依次尝试：

1. 同地域其他可用区。
2. 华东 1（杭州）。
3. 华北 2（北京）。

不要为了库存把计算、OSS 和 ACR 分散到不同地域。

### 3.3 资源组和标签

资源组：

```text
ecoli-demo
```

标签建议：

```text
project=ecoli-demo
env=trial
owner=<你的名字>
expires=2026-10-16
```

自动释放日期必须与标签中的 `expires` 保持一致。

## 4. 实例规格

### 4.1 首选 A10 24GB

在实例规格区域按以下顺序选择：

```text
架构：x86 计算
分类：GPU/异构计算
子类：GPU 计算型
实例规格：ecs.gn7i-c8g1.2xlarge
```

核对规格：

```text
vCPU：8
内存：30 GiB
GPU：1 x NVIDIA A10
显存：24 GB
```

也可以在实例搜索框中直接输入：

```text
gn7i-c8g1.2xlarge
```

### 4.2 低成本备选 T4 16GB

如果 A10 无库存或希望进一步压低成本，搜索：

```text
gn6i-c4g1.xlarge
```

核对规格：

```text
vCPU：4
内存：15 GiB
GPU：1 x NVIDIA T4
显存：16 GB
```

### 4.3 库存或配额报错

如果提示“库存不足”：

1. 换同地域其他可用区。
2. 换上海/杭州/北京地域。
3. 从 A10 切换为 T4。

如果提示“配额不足”：

1. 打开配额中心。
2. 搜索 GPU 或 ECS 按量付费相关配额。
3. 提交配额提升申请。
4. 等待审批后再重新购买。

## 5. 镜像配置

选择：

```text
镜像类型：公共镜像
操作系统：Ubuntu
版本：Ubuntu 22.04 LTS 64位
```

优先 Ubuntu 22.04，而不是最新的 Ubuntu 24.04。22.04 对 CUDA、PyTorch 和生物信息工具的兼容性更成熟。

如果购买页出现“自动安装 GPU 驱动”或“安装 GPU 驱动”：

```text
选中
驱动/CUDA：选择与当前 PyTorch 稳定版本兼容的默认版本
```

不要选择以下镜像：

- 带额外商业授权费的第三方 GPU 镜像
- Windows Server
- 你自己尚未验证的自定义镜像
- 已经带大型模型和不明启动脚本的云市场镜像

创建成功后再通过 SSH 检查：

```bash
nvidia-smi
```

如果 `nvidia-smi` 不存在，再安装 NVIDIA 驱动和 Docker GPU 支持。

## 6. 存储配置

### 6.1 系统盘

选择：

```text
云盘类型：ESSD PL1
容量：200 GiB
随实例释放：是
```

如果预算严格，可以改为：

```text
ESSD PL1 100 GiB
```

首月不建议购买数据盘。先使用系统盘，并把重要数据同步到 OSS。

### 6.2 快照

购买页如果默认勾选自动快照策略：

1. 首月可以先关闭自动快照。
2. 环境安装完成后手工创建一次快照。
3. 快照保留 7 天后删除，避免持续存储费。

数据和代码不要只依赖快照。

## 7. 网络和公网 IP

### 7.1 VPC

选择：

```text
网络：默认 VPC 或新建 VPC
交换机：默认 vSwitch
```

没有默认 VPC 时创建：

```text
VPC 网段：192.168.0.0/16
vSwitch 网段：192.168.1.0/24
```

### 7.2 公网 IP

选择：

```text
分配公网 IPv4 地址：是
计费方式：按使用流量
带宽峰值：10 Mbps
```

不要选择：

- 按固定带宽计费
- 100 Mbps 峰值
- 同时购买多个 EIP

SSH、Codeup 和软件安装会产生少量公网流量。OSS 和 ACR 使用同地域内网 endpoint，不占用公网带宽。

## 8. 安全组

创建新的安全组：

```text
安全组名称：sg-ecoli-demo
类型：普通安全组
```

入方向只保留：

| 协议 | 端口 | 授权对象 |
|---|---:|---|
| SSH | 22 | 你当前的公网 IP/32 |

不要开放：

- `0.0.0.0/0` 的 22 端口
- 8888/JupyterLab
- 5000/FastAPI
- 3306/MySQL
- 6379/Redis
- 2375/Docker remote API

需要在本地打开 Web UI 时，使用 SSH 端口转发：

```bash
ssh -L 8888:127.0.0.1:8888 <user>@<ECS公网IP>
```

## 9. 登录凭证

优先选择：

```text
登录凭证：密钥对
```

操作：

1. 创建密钥对 `ecoli-a10`。
2. 下载私钥文件，只下载一次。
3. 将私钥保存在 WSL 的 `~/.ssh/` 中。
4. 设置权限。

在 WSL 中：

```bash
mkdir -p ~/.ssh
mv /mnt/c/Users/<Windows用户>/Downloads/ecoli-a10.pem ~/.ssh/
chmod 600 ~/.ssh/ecoli-a10.pem
ssh -i ~/.ssh/ecoli-a10.pem <username>@<ECS公网IP>
```

登录用户名以购买页或实例详情的“远程连接”提示为准。不同镜像常见用户名为 `root`、`ubuntu` 或 `ecs-user`。不要把私钥提交到 Codeup、放到聊天中或复制到项目目录。

如果选择密码登录：

```text
密码长度至少 8 位
包含大小写字母、数字或特殊字符中的至少三类
```

密码登录没有密钥对安全，但可以用于首月验证。

## 10. 高级选项

购买页的“高级选项”中设置：

```text
实例名称：ecoli-demo-a10
主机名：ecoli-a10
资源组：ecoli-demo
标签：project=ecoli-demo, env=trial
```

如果有“停止模式”：

```text
节省停机模式
```

如果购买页没有该选项，创建完成后进入实例详情：

1. 找到“停止模式”或“实例属性”。
2. 修改为“节省停机模式”。
3. 确认修改成功。

如果有“自动释放时间”：

```text
设置为购买后第 31 天
```

如果没有自动释放选项，创建后在实例的“释放设置”中配置。

## 11. 确认订单

在确认页逐项检查：

| 项目 | 应为 |
|---|---|
| 付费模式 | 按量付费 |
| 地域 | 上海、杭州或北京 |
| 规格 | `gn7i-c8g1.2xlarge` 或 `gn6i-c4g1.xlarge` |
| GPU | 1 张 A10 24GB 或 T4 16GB |
| 镜像 | Ubuntu 22.04 |
| 系统盘 | ESSD PL1 100-200 GiB |
| 公网计费 | 按使用流量 |
| 峰值带宽 | 10 Mbps |
| 安全组 | SSH 仅你的 IP |
| 登录 | 密钥对 |
| 自动释放 | 31 天后 |
| 停止模式 | 节省停机模式 |

重点确认订单页的“预计费用”。如果显示的是长期包月总价，应立即返回修改付费模式。

单击创建实例。创建完成后：

1. 记录实例 ID。
2. 记录公网 IP。
3. 记录私网 IP。
4. 记录资源组和标签。
5. 等待实例状态变为“运行中”。

## 12. 首次登录后的 15 分钟检查

使用控制台“远程连接”或本地 SSH 登录。

执行：

```bash
uname -a
nvidia-smi
nvidia-smi -L
df -h
free -h
```

预期：

- 系统为 Ubuntu。
- 能看到 A10 或 T4。
- 系统盘约 100-200 GB。
- 内存约为 30 GiB 或 15 GiB。

然后安装基础工具：

```bash
sudo apt update
sudo apt install -y git curl wget unzip tmux jq rsync python3-pip python3-venv
```

检查 Docker：

```bash
docker --version
docker info
```

如果没有 Docker，安装 Docker Engine 和 NVIDIA Container Toolkit。最后验证：

```bash
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

验证成功后再继续安装 Codex、项目依赖和 OSS 工具。

## 13. 本地 Codex 接管

在 WSL Ubuntu 中创建或编辑：

```text
~/.ssh/config
```

填入：

```sshconfig
Host ecoli-a10
    HostName <ECS公网IP>
    User <登录用户名>
    IdentityFile ~/.ssh/ecoli-a10.pem
    ServerAliveInterval 30
    ServerAliveCountMax 6
```

在 Windows PowerShell 中通过 WSL 验证：

```powershell
wsl.exe -d Ubuntu -- ssh ecoli-a10 "nvidia-smi"
```

如果你直接在 WSL 终端中操作，也可以执行：

```bash
ssh ecoli-a10 "nvidia-smi"
```

之后本地 Codex 可以通过以下方式工作：

```powershell
wsl.exe -d Ubuntu -- ssh ecoli-a10 "cd ~/ecoli-demo && git pull --ff-only"
wsl.exe -d Ubuntu -- ssh ecoli-a10 "docker run --rm --gpus all ecoli-demo:test python -c 'import torch; print(torch.cuda.is_available())'"
wsl.exe -d Ubuntu -- ssh ecoli-a10 "tmux new -d -s train 'bash scripts/run_trial.sh'"
```

如果使用 Windows OpenSSH 而不使用 WSL，需要把私钥单独放在 Windows 的 `C:\Users\<用户>\.ssh\` 下，并限制文件 ACL。两个控制端不要共用同一份私钥副本；推荐统一通过 WSL 管理。

## 14. 首月工作流验收

按顺序完成：

1. 本地 Codex 通过 SSH查看系统信息和 GPU。
2. Docker GPU 透传成功。
3. PyTorch 输出 `torch.cuda.is_available() == True`。
4. 创建 OSS 桶并完成上传、下载。
5. 创建 Codeup 仓库并完成 clone、commit、push。
6. 运行 COBRApy/iML1515 的 FBA 基线。
7. 运行一个 2,000-20,000 质点的 GPU 小任务。
8. 保存 checkpoint 到 OSS。
9. 停止 ECS，再启动并从 checkpoint 恢复。
10. 确认节省停机期间未继续收取 vCPU 和内存费用。

## 15. 日常省钱操作

每次工作结束：

1. 停止远程训练任务或确认其已经完成。
2. 将 checkpoint 和日志同步到 OSS。
3. 执行 `sync` 并确认没有未上传的重要文件。
4. 在 ECS 控制台执行“停止”。
5. 选择“节省停机模式”。
6. 第二天检查实例状态和账单。

不要只执行远程 `shutdown`。必须在阿里云控制台或 API 中停止实例，确保触发节省停机模式。

## 16. 如果购买后发现选错

### 16.1 买成包年包月

谨慎处理。包年包月通常不能无损直接退订。先提交工单询问退款规则，不要直接释放或重建。

### 16.2 买成标准停机

进入实例详情修改停止模式为“节省停机模式”。如果无法修改，提交工单确认是否满足条件。

### 16.3 买成 T4 但显存不足

1. 把数据和 checkpoint 同步到 OSS。
2. 保存需要的容器镜像到 ACR。
3. 创建 A10 实例。
4. 按量释放 T4 实例。
5. 不要在两个实例之间复制系统盘。

### 16.4 公网 IP 变化

节省停机后公网 IP 可能改变。以 ECS 控制台显示的新 IP 更新本地 SSH 配置。

### 16.5 本地 IP 变化导致 SSH 失败

在安全组中把 SSH 授权对象改成新的公网 IP/32。不要把来源临时改成 `0.0.0.0/0`。
