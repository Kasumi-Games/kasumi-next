# 货币系统数据回溯脚本

## 功能说明

`rollback_monetary_data.py` 脚本用于根据 transaction 数据库中的记录，将 data 数据库回溯到指定的 transaction ID 之前的状态。

## 工作原理

1. **备份当前数据库**：自动创建带时间戳的备份文件
2. **查找回溯交易**：从指定的 transaction ID 开始，获取所有需要回溯的交易记录
3. **反向执行操作**：
   - `INCOME`（收入）→ 减少用户余额
   - `EXPENSE`（支出）→ 增加用户余额
   - `SET`（设置）→ 需要手动处理
   - `TRANSFER`（转账）→ 需要手动处理
4. **删除交易记录**：可选择是否删除已回溯的交易记录

## 使用方法

### 基本用法

```bash
# 回溯到交易ID 178445（含）之前的状态
python scripts/rollback_monetary_data.py --target-id 178445
```

### 高级选项

```bash
# 仅模拟运行，不实际修改数据
python scripts/rollback_monetary_data.py --target-id 178445 --dry-run

# 回溯但保留交易记录
python scripts/rollback_monetary_data.py --target-id 178445 --keep-transactions

# 组合使用
python scripts/rollback_monetary_data.py --target-id 178445 --dry-run --keep-transactions
```

## 参数说明

- `--target-id`：必需参数，指定目标交易ID，脚本将回溯到此ID（含）之前的状态
- `--dry-run`：可选参数，仅模拟运行，显示将要执行的操作但不实际修改数据
- `--keep-transactions`：可选参数，保留已回溯的交易记录，不从transaction数据库中删除

## 安全特性

1. **自动备份**：每次执行都会自动创建数据库备份文件
2. **错误处理**：遇到复杂操作（如SET、TRANSFER）时会提示需要手动处理
3. **干运行模式**：可以先查看将要执行的操作
4. **详细日志**：显示每个操作的详细信息

## 注意事项

⚠️ **重要提醒**：

1. **执行前备份**：虽然脚本会自动备份，但建议手动备份重要数据
2. **复杂操作**：SET和TRANSFER操作可能需要手动处理
3. **测试环境**：建议先在测试环境中验证
4. **权限要求**：确保对数据库文件有读写权限

## 示例输出

```
🎯 开始回溯到交易ID 178445 之前的状态
✅ 数据库备份完成:
   数据库备份: /path/to/data_backup_1234567890.db
   交易记录备份: /path/to/transaction_backup_1234567890.db
📋 找到 15 条需要回溯的交易记录

📊 回溯统计:
   总交易数: 15
   涉及用户: 3
   交易ID范围: 178445 ~ 178459

🔄 回溯交易 ID:178459 - income - user123 - 金额:100
   收入回溯: 1500 - 100 = 1400
🔄 回溯交易 ID:178458 - expense - user123 - 金额:50
   支出回溯: 1400 + 50 = 1450

📈 回溯完成:
   成功回溯: 13 条
   失败/跳过: 2 条

⚠️  以下交易需要手动处理:
   ID:178450 - set - user456 - 1000
   ID:178447 - transfer - user789 - 200

🗑️  删除了 13 条交易记录

✅ 回溯操作完成!
💾 备份文件保存在:
   /path/to/data_backup_1234567890.db
   /path/to/transaction_backup_1234567890.db
```

## 恢复数据

如果需要恢复到回溯前的状态，可以使用自动创建的备份文件：

```bash
# 恢复主数据库
cp /path/to/data_backup_1234567890.db /path/to/data.db

# 恢复交易数据库
cp /path/to/transaction_backup_1234567890.db /path/to/transaction.db
```

## 故障排除

### 常见错误

1. **数据库文件不存在**
   - 检查数据库文件路径是否正确
   - 确保项目已正确初始化

2. **权限不足**
   - 检查对数据库文件的读写权限
   - 确保备份目录可写

3. **交易ID不存在**
   - 使用 `--dry-run` 模式检查是否有匹配的交易记录
   - 确认指定的交易ID是否正确

### 调试建议

1. 先使用 `--dry-run` 参数查看将要执行的操作
2. 对于复杂场景，使用 `--keep-transactions` 保留原始记录
3. 查看生成的备份文件确认数据安全