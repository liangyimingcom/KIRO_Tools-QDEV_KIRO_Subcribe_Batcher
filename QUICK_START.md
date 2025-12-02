# 快速开始指南

5分钟快速上手AWS IAM Identity Center用户订阅管理系统。

---

## 📋 前置条件

- ✅ Python 3.8+
- ✅ AWS账号
- ✅ AWS CLI工具
- ✅ IAM Identity Center访问权限

---

## 🚀 快速安装

### 1. 克隆项目

```bash
git clone https://github.com/your-username/aws-iam-identity-center-subscription-manager.git
cd aws-iam-identity-center-subscription-manager
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置AWS

```bash
aws configure --profile your-profile
```

输入你的AWS凭证：
- AWS Access Key ID
- AWS Secret Access Key
- Default region: `us-east-1`
- Default output format: `json`

### 4. 配置系统

```bash
# 复制配置文件
cp config.yaml.example config.yaml

# 编辑配置文件
nano config.yaml
```

修改以下内容：
```yaml
aws:
  profile: your-profile              # 你的AWS profile
  identity_center:
    instance_id: ssoins-xxxxxxxxxx   # 你的Identity Store ID

groups:
  kiro: Group_KIRO_eu-central-1      # 你的KIRO组名
  qdev: Group_QDEV_eu-central-1      # 你的QDEV组名
```

### 5. 准备数据

```bash
# 复制CSV示例
cp list.csv.example list.csv

# 编辑CSV文件
nano list.csv
```

CSV格式：
```csv
工号,姓名,邮箱,订阅项目
EMP001,张三,zhangsan@example.com,KIRO订阅
EMP002,李四,lisi@example.com,QDEV订阅
```

---

## 🎯 开始使用

### 测试连接

```bash
python3 main.py test --config config.yaml
```

预期输出：
```
✅ AWS连接测试成功
Profile: your-profile
Region: us-east-1
Identity Store ID: ssoins-xxxxxxxxxx
```

### 试运行（推荐）

```bash
python3 main.py process list.csv --syncusers --dry-run --config config.yaml
```

这会显示将要执行的操作，但不会实际修改数据。

### 正式运行

```bash
python3 main.py process list.csv --syncusers --config config.yaml
```

---

## 📊 查看结果

### 查看日志

```bash
# 实时查看
tail -f logs/subscription_manager.log

# 查看完整日志
cat logs/subscription_manager.log
```

### 查看报告

```bash
# 查看最新报告
ls -lt reports/ | head -5

# 查看执行记录
cat reports/execution_record_*.md
```

---

## 💡 常用命令

```bash
# 同步用户
python3 main.py process list.csv --syncusers --config config.yaml

# 详细日志模式
python3 main.py process list.csv --syncusers --verbose --config config.yaml

# 自定义并发数
python3 main.py process list.csv --syncusers --max-workers 8 --config config.yaml
```

---

## 🆘 遇到问题？

### 常见错误

**AWS凭证错误**:
```bash
aws configure --profile your-profile
```

**权限不足**:
检查AWS用户是否有IAM Identity Center权限

**组不存在**:
在AWS控制台创建相应的组

### 获取帮助

1. 查看 [用户使用手册](USER_MANUAL.md)
2. 查看 [故障排除](USER_MANUAL.md#8-故障排除)
3. 创建 [Issue](https://github.com/your-username/aws-iam-identity-center-subscription-manager/issues)

---

## 📚 下一步

- 📖 阅读 [完整用户手册](USER_MANUAL.md)
- 🏗️ 了解 [系统架构](PRODUCTION_STRUCTURE.md)
- 🤝 参与 [贡献](CONTRIBUTING.md)

---

**祝使用愉快！** 🎉
