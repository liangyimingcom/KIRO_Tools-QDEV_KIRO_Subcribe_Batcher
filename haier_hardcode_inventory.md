# Haier 硬编码值清单

## 概述

本文档列出了代码库中所有与 "haier" 相关的硬编码内容，并提供了配置化方案。

**生成日期**: 2024年

**总计**: 27 处硬编码值

---

## 1. 用户名域名后缀硬编码

### 1.1 src/models.py

**位置**: 第 47 行

**当前硬编码值**:
```python
return f"{self.employee_id}@haier-saml.com"
```

**作用描述**:
- UserSubscription 类中的 get_username() 方法
- 用于生成 IAM Identity Center 用户名
- 当没有配置对象时的默认用户名格式

**建议配置方案**:
- 将用户名模板配置到 `config.yaml` 的 `user_format.username_template` 字段
- 配置项: `username_template: "{employee_id}@your-domain.com"`
- 优先使用配置，无配置时使用默认值确保向后兼容

**影响范围**: 中等 - 影响用户名生成逻辑

---

### 1.2 src/user_manager.py - 第 696 行

**位置**: 第 696 行

**当前硬编码值**:
```python
username = f"{employee_id}@haier-saml.com"
```

**作用描述**:
- UserManager 类的 get_user_by_employee_id() 方法
- 根据员工号查询 IAM 用户时构建用户名

**建议配置方案**:
- 使用配置中的 `user_format.username_template` 模板
- 通过 `template.format(employee_id=employee_id)` 动态生成用户名

**影响范围**: 高 - 影响用户查询功能

---

### 1.3 src/user_manager.py - 第 818-819 行

**位置**: 第 818-819 行

**当前硬编码值**:
```python
if not username.endswith('@haier-saml.com'):
    errors.append("用户名格式错误，应为员工号@haier-saml.com")
```

**作用描述**:
- UserManager 类的 _validate_user_data() 方法
- 验证用户名格式是否符合规范

**建议配置方案**:
- 从配置中提取域名后缀进行验证
- 使用正则表达式或字符串处理动态生成验证规则
- 错误消息也应基于配置动态生成

**影响范围**: 中等 - 影响用户数据验证

---

### 1.4 src/user_manager.py - 第 1178 行

**位置**: 第 1178 行

**当前硬编码值**:
```python
username.endswith('@haier-saml.com')
```

**作用描述**:
- UserManager 类的 generate_execution_plan() 方法
- 判断 IAM 中的用户是否属于需要管理的海尔域用户
- 用于决定是否删除不在 CSV 中的用户

**建议配置方案**:
- 新增配置项 `user_format.username_suffix` 用于判断可管理用户
- 或直接使用 `username_template` 提取后缀部分

**影响范围**: 高 - 影响用户同步和删除逻辑

---

### 1.5 src/user_manager.py - 第 215-217 行

**位置**: 第 215-217 行

**当前硬编码值**:
```python
# 新格式：工号@haier-saml.com, 工号_中文姓名
aws_user_data = {
    'UserName': username,  # 工号@haier-saml.com
```

**作用描述**:
- UserManager 类的 create_user() 方法中的注释
- 说明新用户格式的用户名规范

**建议配置方案**:
- 更新注释，使用通用描述或引用配置
- 示例: "工号@{domain}，根据 username_template 配置生成"

**影响范围**: 低 - 仅影响代码注释

---

### 1.6 src/report_generator.py - 第 366 行

**位置**: 第 366 行

**当前硬编码值**:
```python
report.append(f"- **Username**: 工号@haier-saml.com")
```

**作用描述**:
- ReportGenerator 类的 generate_upgrade_report() 方法
- 生成属性升级报告时的格式说明

**建议配置方案**:
- 从配置中读取 username_template 并在报告中使用
- 动态生成报告内容以反映实际配置

**影响范围**: 低 - 影响报告文档内容

---

### 1.7 src/report_generator.py - 第 381 行

**位置**: 第 381 行

**当前硬编码值**:
```python
report.append(f"  Username: 20117703@haier-saml.com")
```

**作用描述**:
- ReportGenerator 类的 generate_upgrade_report() 方法
- 升级示例中的用户名展示

**建议配置方案**:
- 使用配置模板生成示例用户名
- 示例: `template.format(employee_id="20117703")`

**影响范围**: 低 - 影响报告示例内容

---

### 1.8 main.py - 第 565 行

**位置**: 第 565 行

**当前硬编码值**:
```python
help='属性升级模式，将用户属性升级到新格式（工号@haier-saml.com）'
```

**作用描述**:
- 命令行参数 --update2ver0928 的帮助文本
- 说明属性升级模式的目标格式

**建议配置方案**:
- 使用更通用的描述，例如: "属性升级模式，将用户属性升级到配置的用户名格式"
- 或保持当前示例但注明可配置

**影响范围**: 低 - 影响命令行帮助信息

---

### 1.9 src/user_attribute_upgrader.py - 第 109 行

**位置**: 第 109 行

**当前硬编码值**:
```python
new_username = csv_user.get_username()  # 工号@haier-saml.com
```

**作用描述**:
- UserAttributeUpgrader 类的 generate_upgrade_plan() 方法中的注释
- 说明新用户名的格式

**建议配置方案**:
- 更新注释为通用描述
- 示例: "根据配置模板生成的用户名"

**影响范围**: 低 - 仅影响代码注释

---

### 1.10 src/user_attribute_upgrader.py - 第 230-231 行

**位置**: 第 230-231 行

**当前硬编码值**:
```python
# 匹配 工号@haier-saml.com 格式
match = re.match(r'^([A-Za-z0-9]+)@haier-saml\.com$', username)
```

**作用描述**:
- UserAttributeUpgrader 类的 _needs_upgrade() 方法
- 判断用户名是否已经是新格式

**建议配置方案**:
- 从配置中提取域名后缀构建动态正则表达式
- 新增辅助方法从 username_template 生成验证正则

**影响范围**: 中等 - 影响升级判断逻辑

---

## 2. 邮箱域名验证列表硬编码

### 2.1 src/data_validator.py - 第 204-216 行

**位置**: 第 204-216 行

**当前硬编码值**:
```python
haier_domains = [
    'haier.com',
    'haier1.com',
    'haier2.com',
    'haier3.com',
    'haier.com.new',
    'haier.com.new1',
    'haier.com.new2',
    'haier.com.new3',
    'haiergroup.com',
    'haier.net',
    'casarte.com',
    'leader.com.cn'
]
```

**作用描述**:
- DataValidator 类的 validate_email_domain() 方法
- 验证用户邮箱是否属于海尔认可的域名列表
- 用于数据验证时发出警告

**建议配置方案**:
- 新增配置节 `validation.allowed_email_domains` 存储允许的邮箱域名列表
- 配置格式:
```yaml
validation:
  allowed_email_domains:
    - haier.com
    - haier1.com
    - haier2.com
    - haier3.com
    - haier.com.new
    - haier.com.new1
    - haier.com.new2
    - haier.com.new3
    - haiergroup.com
    - haier.net
    - casarte.com
    - leader.com.cn
```

**影响范围**: 中等 - 影响邮箱验证功能

---

### 2.2 src/data_validator.py - 第 221 行

**位置**: 第 221 行

**当前硬编码值**:
```python
return any(domain.endswith(haier_domain) for haier_domain in haier_domains)
```

**作用描述**:
- 使用上述硬编码的域名列表进行验证
- 检查邮箱域名是否以任一允许的域名结尾

**建议配置方案**:
- 从配置读取 allowed_email_domains 列表
- 保持相同的验证逻辑

**影响范围**: 低 - 依赖于域名列表配置

---

## 3. 注释和文档中的硬编码

### 3.1 src/data_validator.py - 第 94 行

**位置**: 第 94 行

**当前硬编码值**:
```python
result.add_warning(f"{user_prefix}: 邮箱域名可能不是海尔域名 '{user.email}'")
```

**作用描述**:
- 邮箱域名验证失败时的警告消息
- 提示用户邮箱可能不是海尔域名

**建议配置方案**:
- 使用更通用的警告消息
- 示例: "邮箱域名可能不在允许的域名列表中"
- 或从配置中读取组织名称

**影响范围**: 低 - 影响警告消息内容

---

### 3.2 src/data_validator.py - 第 190 行

**位置**: 第 190 行 (实际是第 188-190 行的方法注释)

**当前硬编码值**:
```python
def validate_email_domain(self, email: str) -> bool:
    """
    验证邮箱域名是否为海尔域名
```

**作用描述**:
- 方法的文档字符串
- 说明方法用途

**建议配置方案**:
- 更新为通用描述: "验证邮箱域名是否在允许的域名列表中"

**影响范围**: 低 - 仅影响代码文档

---

### 3.3 src/data_validator.py - 第 203 行 (注释)

**位置**: 第 203 行

**当前硬编码值**:
```python
# 海尔相关域名
```

**作用描述**:
- 域名列表的注释说明

**建议配置方案**:
- 更新为: "允许的邮箱域名列表（从配置读取或使用默认值）"

**影响范围**: 低 - 仅影响代码注释

---

### 3.4 src/user_manager.py - 第 1162 行

**位置**: 第 1162 行

**当前硬编码值**:
```python
users_to_delete = []  # IAM中有，CSV中没有（仅海尔域用户）
```

**作用描述**:
- 变量声明的注释
- 说明仅删除海尔域用户

**建议配置方案**:
- 更新为: "仅删除配置域名下的用户"
- 或: "仅删除可管理域名下的用户"

**影响范围**: 低 - 仅影响代码注释

---

### 3.5 src/user_manager.py - 第 1175 行

**位置**: 第 1175 行

**当前硬编码值**:
```python
# 找出需要删除的用户（仅海尔域用户）
```

**作用描述**:
- 代码块的注释说明

**建议配置方案**:
- 更新为: "找出需要删除的用户（仅配置域名下的用户）"

**影响范围**: 低 - 仅影响代码注释

---

## 4. 配置文件中的硬编码

### 4.1 src/config.py - 第 28 行

**位置**: 第 28 行

**当前硬编码值**:
```python
username_template: str = "{employee_id}@haier-saml.com"
```

**作用描述**:
- UserFormatConfig 类的默认用户名模板
- 作为配置类的默认值

**建议配置方案**:
- 这是合理的默认值，提供向后兼容性
- 应通过 config.yaml 覆盖
- 在 config.yaml.example 中使用通用占位符

**影响范围**: 低 - 仅作为默认值，可被配置覆盖

---

### 4.2 src/config.py - 第 225 行

**位置**: 第 225 行

**当前硬编码值**:
```python
'username_template': '{employee_id}@haier-saml.com',
```

**作用描述**:
- ConfigManager 类的 create_default_config_file() 方法
- 创建默认配置文件时使用的值

**建议配置方案**:
- 使用通用占位符或示例域名
- 示例: `'{employee_id}@your-domain.com'`

**影响范围**: 低 - 仅影响生成的默认配置文件

---

## 配置化改造总结

### 新增配置项

需要在 `config.yaml` 和 `src/config.py` 中添加以下配置项：

```yaml
user_format:
  username_template: "{employee_id}@your-domain.com"  # 用户名模板
  username_suffix: "@your-domain.com"                 # 用户名后缀（用于验证）
  use_new_format: true

validation:
  allowed_email_domains:                              # 允许的邮箱域名列表
    - haier.com
    - haier1.com
    - haier2.com
    # ... 更多域名
  max_users_warning: 1000
```

### 代码修改优先级

**高优先级** (影响核心功能):
1. src/user_manager.py 第 696 行 - 用户查询
2. src/user_manager.py 第 1178 行 - 用户删除判断
3. src/user_manager.py 第 818-819 行 - 用户验证

**中优先级** (影响功能扩展):
4. src/data_validator.py 第 204-216 行 - 邮箱域名列表
5. src/models.py 第 47 行 - 用户名生成默认值
6. src/user_attribute_upgrader.py 第 230-231 行 - 升级判断

**低优先级** (注释和文档):
7. 所有注释和帮助文本中的硬编码
8. 报告生成中的示例和说明文本

### 向后兼容性保证

1. 配置项都提供合理的默认值
2. 未配置时使用原有的 haier-saml.com 逻辑
3. 现有部署无需立即修改配置即可正常运行
4. 建议在实施时提供配置迁移指南

---

## 修复进度

- [ ] 更新 config.yaml.example 添加新配置项
- [ ] 更新 src/config.py 添加配置类和加载逻辑
- [ ] 修复 src/models.py (已部分支持配置，需测试)
- [ ] 修复 src/user_manager.py 所有硬编码
- [ ] 修复 src/data_validator.py 邮箱域名列表
- [ ] 修复 src/user_attribute_upgrader.py 正则表达式
- [ ] 修复 src/report_generator.py 报告生成
- [ ] 更新 main.py 帮助文本
- [ ] 更新所有注释和文档字符串

---

**文档版本**: 1.0  
**最后更新**: 2024年
