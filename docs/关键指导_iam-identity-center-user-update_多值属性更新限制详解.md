## 多值属性更新限制详解

### 🚨 重要发现：多值属性的更新限制

在实际操作中发现，AWS Identity Store 对**多值属性**（Multi-Value Attributes）有特殊的更新限制：

#### ❌ 错误的更新方式

```bash
# 这种方式会失败！
aws identitystore update-user \
  --identity-store-id d-90678f2f6b \
  --user-id <USER_ID> \
  --operations '[{
    "AttributePath": "emails[0].value",
    "AttributeValue": "newemail@example.com"
  }]'
```

**错误信息:**

```
ValidationException: Unsupported update operation on multi-value attribute emails, 
please provide full replacement of Multi-Value attribute types
```

#### ✅ 正确的更新方式

```bash
# 必须完整替换整个数组！
aws identitystore update-user \
  --identity-store-id d-90678f2f6b \
  --user-id <USER_ID> \
  --operations '[{
    "AttributePath": "emails",
    "AttributeValue": [
      {
        "Value": "newemail@example.com",
        "Type": "work",
        "Primary": true
      }
    ]
  }]'
```

### 多值属性列表及更新方法

| 属性名           | 错误路径 ❌                   | 正确路径 ✅     | 完整替换示例 |
| ---------------- | ---------------------------- | -------------- | ------------ |
| **emails**       | `emails[0].value`            | `emails`       | 见下方示例   |
| **phoneNumbers** | `phoneNumbers[0].value`      | `phoneNumbers` | 见下方示例   |
| **addresses**    | `addresses[0].streetAddress` | `addresses`    | 见下方示例   |

### 完整的多值属性更新示例

#### 1. 更新邮箱地址

```bash
# 单个邮箱
aws identitystore update-user \
  --profile oversea1 \
  --region us-east-1 \
  --identity-store-id d-90678f2f6b \
  --user-id <USER_ID> \
  --operations '[{
    "AttributePath": "emails",
    "AttributeValue": [
      {
        "Value": "primary@company.com",
        "Type": "work",
        "Primary": true
      }
    ]
  }]'

# 多个邮箱
aws identitystore update-user \
  --profile oversea1 \
  --region us-east-1 \
  --identity-store-id d-90678f2f6b \
  --user-id <USER_ID> \
  --operations '[{
    "AttributePath": "emails",
    "AttributeValue": [
      {
        "Value": "work@company.com",
        "Type": "work", 
        "Primary": true
      },
      {
        "Value": "personal@gmail.com",
        "Type": "home",
        "Primary": false
      }
    ]
  }]'
```

#### 2. 更新电话号码

```bash
aws identitystore update-user \
  --profile oversea1 \
  --region us-east-1 \
  --identity-store-id d-90678f2f6b \
  --user-id <USER_ID> \
  --operations '[{
    "AttributePath": "phoneNumbers",
    "AttributeValue": [
      {
        "Value": "+86-138-0000-0000",
        "Type": "mobile",
        "Primary": true
      },
      {
        "Value": "+86-010-8888-8888", 
        "Type": "work",
        "Primary": false
      }
    ]
  }]'
```

#### 3. 更新地址信息

```bash
aws identitystore update-user \
  --profile oversea1 \
  --region us-east-1 \
  --identity-store-id d-90678f2f6b \
  --user-id <USER_ID> \
  --operations '[{
    "AttributePath": "addresses",
    "AttributeValue": [
      {
        "StreetAddress": "北京市朝阳区xxx路123号",
        "Locality": "北京",
        "Region": "北京",
        "PostalCode": "100000",
        "Country": "CN",
        "Type": "work",
        "Primary": true
      }
    ]
  }]'
```

### 混合更新策略

当需要同时更新单值和多值属性时，可以在一个操作中完成：

```bash
aws identitystore update-user \
  --profile oversea1 \
  --region us-east-1 \
  --identity-store-id d-90678f2f6b \
  --user-id <USER_ID> \
  --operations '[
    {
      "AttributePath": "displayName",
      "AttributeValue": "张三_高级工程师"
    },
    {
      "AttributePath": "title", 
      "AttributeValue": "高级软件工程师"
    },
    {
      "AttributePath": "emails",
      "AttributeValue": [
        {
          "Value": "zhangsan@company.com",
          "Type": "work",
          "Primary": true
        }
      ]
    },
    {
      "AttributePath": "phoneNumbers",
      "AttributeValue": [
        {
          "Value": "+86-138-0000-0000",
          "Type": "mobile", 
          "Primary": true
        }
      ]
    }
  ]'
```

### 实际案例：本次更新操作

在本次更新中，我们遇到了这个限制，采用了分步更新的方法：

#### 步骤1：更新单值属性

```bash
aws identitystore update-user \
  --profile oversea1 \
  --region us-east-1 \
  --identity-store-id d-90678f2f6b \
  --user-id 14f8f418-9011-7033-b50b-16d94f29469f \
  --operations '[
    {
      "AttributePath": "displayName",
      "AttributeValue": "21033151_吕成锋"
    },
    {
      "AttributePath": "name.givenName",
      "AttributeValue": "20023656new"
    },
    {
      "AttributePath": "name.familyName", 
      "AttributeValue": "吕成锋new"
    }
  ]'
```

#### 步骤2：更新多值属性（邮箱）

```bash
aws identitystore update-user \
  --profile oversea1 \
  --region us-east-1 \
  --identity-store-id d-90678f2f6b \
  --user-id 14f8f418-9011-7033-b50b-16d94f29469f \
  --operations '[{
    "AttributePath": "emails",
    "AttributeValue": [
      {
        "Value": "lvchengfeng2@haier.com.new2",
        "Type": "work",
        "Primary": true
      }
    ]
  }]'
```

### 最佳实践建议

1. **获取现有数据**: 更新多值属性前，先用 `describe-user` 获取现有的完整数据
2. **保留现有值**: 如果只想修改部分值，需要在新数组中包含所有要保留的现有值
3. **分步更新**: 复杂更新可以分为单值属性和多值属性两步进行
4. **验证结果**: 每次更新后验证结果，确保数据完整性

### 获取现有多值属性的脚本示例

```bash
# 获取用户当前的邮箱信息
current_emails=$(aws identitystore describe-user \
  --profile oversea1 \
  --region us-east-1 \
  --identity-store-id d-90678f2f6b \
  --user-id <USER_ID> \
  --query 'Emails' \
  --output json)

echo "当前邮箱: $current_emails"

# 基于现有数据构建新的邮箱数组
# 然后进行更新...
```

## 注意事项

1. **用户名不可更改**: `userName` 属性在用户创建后无法修改
2. **邮箱唯一性**: 邮箱地址在同一个 Identity Store 中必须唯一
3. **属性路径**: 使用正确的属性路径格式，区分大小写
4. **批量操作**: 可以在一次 API 调用中更新多个属性
5. **验证更新**: 建议更新后使用 `describe-user` 验证更改是否生效
6. **🚨 多值属性限制**: emails、phoneNumbers、addresses 等多值属性必须完整替换，不能使用数组索引更新
7. **数据完整性**: 更新多值属性时，必须包含所有要保留的现有值
8. **Console限制**: 某些敏感操作只能通过 AWS Console 进行，确保安全性