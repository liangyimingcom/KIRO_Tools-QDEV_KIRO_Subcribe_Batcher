# 贡献指南

感谢你考虑为本项目做出贡献！

## 如何贡献

### 报告Bug

如果你发现了bug，请创建一个Issue，包含以下信息：

1. **Bug描述**: 清晰简洁的描述
2. **重现步骤**: 详细的重现步骤
3. **预期行为**: 你期望发生什么
4. **实际行为**: 实际发生了什么
5. **环境信息**: 
   - 操作系统
   - Python版本
   - AWS区域
6. **日志**: 相关的错误日志

### 提出新功能

如果你有新功能的想法，请创建一个Issue，包含：

1. **功能描述**: 清晰的功能说明
2. **使用场景**: 为什么需要这个功能
3. **实现建议**: 如果有的话

### 提交代码

1. **Fork仓库**
2. **创建分支**: `git checkout -b feature/your-feature-name`
3. **编写代码**: 
   - 遵循现有代码风格
   - 添加必要的注释
   - 更新文档
4. **测试**: 确保所有测试通过
5. **提交**: `git commit -m 'Add some feature'`
6. **推送**: `git push origin feature/your-feature-name`
7. **创建Pull Request**

## 代码规范

### Python代码风格

- 遵循PEP 8规范
- 使用4个空格缩进
- 函数和类添加文档字符串
- 变量名使用小写+下划线
- 类名使用驼峰命名

### 提交信息

- 使用清晰的提交信息
- 第一行简短描述（<50字符）
- 如需要，添加详细说明

示例：
```
Add user batch delete feature

- Implement batch delete functionality
- Add confirmation mechanism
- Update documentation
```

## 测试

在提交PR前，请确保：

1. 所有现有测试通过
2. 新功能有相应的测试
3. 代码覆盖率不降低

运行测试：
```bash
python -m pytest tests/ -v
```

## 文档

如果你的更改影响用户使用，请更新：

- README.md
- USER_MANUAL.md
- 相关的技术文档

## 问题

如有任何问题，请：

1. 查看现有Issues
2. 创建新Issue
3. 在PR中讨论

## 行为准则

- 尊重所有贡献者
- 保持友好和专业
- 接受建设性批评
- 关注项目目标

## 许可证

提交代码即表示你同意将代码以MIT许可证发布。

---

再次感谢你的贡献！🎉
