#!/usr/bin/env python3
"""
货币系统数据回溯脚本

根据transaction数据库中的记录，将data数据库回溯到指定transaction ID之前的状态。
此脚本会从指定的transaction ID开始，反向执行所有操作以恢复之前的状态。

使用方法:
    python scripts/rollback_monetary_data.py --target-id 178445

注意事项:
- 脚本会自动备份当前数据库
- 所有操作都是可逆的
- 建议在执行前手动备份重要数据
"""

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any
import time
from enum import Enum

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TransactionCategory(Enum):
    """Transaction categories for monetary operations"""

    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    SET = "set"


class MonetaryDataRollback:
    """货币数据回溯处理器"""

    def __init__(
        self, target_transaction_id: int, data_db_path: Path, transaction_db_path: Path
    ):
        self.target_id = target_transaction_id
        self.data_db_path = data_db_path
        self.transaction_db_path = transaction_db_path

        # 验证数据库文件存在
        if not self.data_db_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {self.data_db_path}")
        if not self.transaction_db_path.exists():
            raise FileNotFoundError(f"交易数据库文件不存在: {self.transaction_db_path}")

    def backup_databases(self) -> Tuple[Path, Path]:
        """备份当前数据库文件"""
        timestamp = int(time.time())

        data_backup = self.data_db_path.parent / f"data_backup_{timestamp}.db"
        transaction_backup = (
            self.transaction_db_path.parent / f"transaction_backup_{timestamp}.db"
        )

        shutil.copy2(self.data_db_path, data_backup)
        shutil.copy2(self.transaction_db_path, transaction_backup)

        print("✅ 数据库备份完成:")
        print(f"   数据库备份: {data_backup}")
        print(f"   交易记录备份: {transaction_backup}")

        return data_backup, transaction_backup

    def get_transactions_to_rollback(self) -> List[Dict[str, Any]]:
        """获取需要回溯的交易记录（按ID降序）"""
        with sqlite3.connect(self.transaction_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 获取目标ID及之后的所有交易记录，按ID降序排列
            cursor.execute(
                """
                SELECT id, user_id, category, amount, time, description
                FROM transactions 
                WHERE id >= ?
                ORDER BY id DESC
            """,
                (self.target_id,),
            )

            transactions = [dict(row) for row in cursor.fetchall()]

        print(f"📋 找到 {len(transactions)} 条需要回溯的交易记录")
        return transactions

    def get_user_current_data(self, user_id: str) -> Dict[str, Any]:
        """获取用户当前数据"""
        with sqlite3.connect(self.data_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT user_id, balance, last_daily_time, level
                FROM users 
                WHERE user_id = ?
            """,
                (user_id,),
            )

            row = cursor.fetchone()
            if row:
                return dict(row)
            else:
                # 如果用户不存在，返回默认值
                return {
                    "user_id": user_id,
                    "balance": 0,
                    "last_daily_time": 0,
                    "level": 1,
                }

    def update_user_data(
        self, user_id: str, balance: int, level: int = None, last_daily_time: int = None
    ):
        """更新用户数据"""
        with sqlite3.connect(self.data_db_path) as conn:
            cursor = conn.cursor()

            # 检查用户是否存在
            cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
            user_exists = cursor.fetchone() is not None

            if user_exists:
                # 更新现有用户
                if level is not None and last_daily_time is not None:
                    cursor.execute(
                        """
                        UPDATE users 
                        SET balance = ?, level = ?, last_daily_time = ?
                        WHERE user_id = ?
                    """,
                        (balance, level, last_daily_time, user_id),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE users 
                        SET balance = ?
                        WHERE user_id = ?
                    """,
                        (balance, user_id),
                    )
            else:
                # 创建新用户（通常不会发生，因为回溯是删除操作）
                level = level or 1
                last_daily_time = last_daily_time or 0
                cursor.execute(
                    """
                    INSERT INTO users (user_id, balance, level, last_daily_time)
                    VALUES (?, ?, ?, ?)
                """,
                    (user_id, balance, level, last_daily_time),
                )

            conn.commit()

    def rollback_transaction(self, transaction: Dict[str, Any]) -> bool:
        """回溯单个交易记录"""
        user_id = transaction["user_id"]
        category = transaction["category"]
        amount = transaction["amount"]
        tx_id = transaction["id"]
        description = transaction["description"]

        print(f"🔄 回溯交易 ID:{tx_id} - {category} - 用户:{user_id} - 金额:{amount}")

        # 获取用户当前数据
        user_data = self.get_user_current_data(user_id)
        current_balance = user_data["balance"]
        current_level = user_data["level"]
        current_daily_time = user_data["last_daily_time"]

        # 根据交易类型执行反向操作
        new_balance = current_balance
        new_level = current_level

        if category == TransactionCategory.INCOME.value:
            # 收入 -> 减少余额
            new_balance = current_balance - amount
            print(f"   收入回溯: {current_balance} - {amount} = {new_balance}")

            # 检查是否是upgrade类型的收入（实际上是负数，表示花费）
            if description.startswith("upgrade_"):
                # 解析upgrade描述格式: upgrade_{old_level}_{levels}
                try:
                    parts = description.split("_")
                    if len(parts) == 3:
                        # {level}_{levels}
                        old_level = int(parts[1])
                        levels = int(parts[2])
                        # 回溯时需要将用户级别降回升级前的状态
                        new_level = old_level
                        print(
                            f"   🌟 升级回溯: 从等级 {current_level} 降回 {old_level} (降低了 {levels} 级)"
                        )
                    elif len(parts) == 2:
                        # {level+1}
                        old_level = int(parts[1])
                        levels = 1
                        new_level = old_level - levels
                        print(
                            f"   🌟 升级回溯: 从等级 {current_level} 降回 {new_level} (降低了 {levels} 级)"
                        )
                    else:
                        print(f"   ⚠️  升级描述格式不正确: {description}")
                except (ValueError, IndexError) as e:
                    print(f"   ⚠️  解析升级描述失败: {description}, 错误: {e}")

        elif category == TransactionCategory.EXPENSE.value:
            # 支出 -> 增加余额
            new_balance = current_balance + amount
            print(f"   支出回溯: {current_balance} + {amount} = {new_balance}")

        elif category == TransactionCategory.SET.value:
            # SET操作比较复杂，需要查找之前的余额
            print(f"   ⚠️  SET操作回溯: 当前余额 {current_balance}, 设置值 {amount}")
            print(f"   📝 描述: {description}")
            # 对于SET操作，我们需要手动处理或跳过
            print("   ⚠️  SET操作无法自动回溯，需要手动检查")
            return False

        elif category == TransactionCategory.TRANSFER.value:
            # 转账操作也比较复杂，通常涉及两个用户
            print(f"   ⚠️  转账操作回溯: {description}")
            print("   📝 这可能需要手动处理转账的双方")
            return False

        # 更新用户数据（包括余额和级别）
        self.update_user_data(user_id, new_balance, new_level, current_daily_time)

        return True

    def delete_transactions(self, transactions: List[Dict[str, Any]]):
        """删除已回溯的交易记录"""
        transaction_ids = [tx["id"] for tx in transactions]

        with sqlite3.connect(self.transaction_db_path) as conn:
            cursor = conn.cursor()

            # 批量删除交易记录
            placeholders = ",".join("?" * len(transaction_ids))
            cursor.execute(
                f"""
                DELETE FROM transactions 
                WHERE id IN ({placeholders})
            """,
                transaction_ids,
            )

            deleted_count = cursor.rowcount
            conn.commit()

        print(f"🗑️  删除了 {deleted_count} 条交易记录")

    def execute_rollback(self, delete_transactions: bool = True):
        """执行完整的回溯操作"""
        print(f"🎯 开始回溯到交易ID {self.target_id} 之前的状态")

        # 1. 备份数据库
        data_backup, tx_backup = self.backup_databases()

        try:
            # 2. 获取需要回溯的交易
            transactions = self.get_transactions_to_rollback()

            if not transactions:
                print("✅ 没有找到需要回溯的交易记录")
                return

            # 3. 统计信息
            user_transactions = {}
            for tx in transactions:
                user_id = tx["user_id"]
                if user_id not in user_transactions:
                    user_transactions[user_id] = []
                user_transactions[user_id].append(tx)

            print("📊 回溯统计:")
            print(f"   总交易数: {len(transactions)}")
            print(f"   涉及用户: {len(user_transactions)}")
            print(f"   交易ID范围: {transactions[-1]['id']} ~ {transactions[0]['id']}")

            # 4. 执行回溯
            failed_transactions = []
            successful_count = 0

            for transaction in transactions:
                try:
                    if self.rollback_transaction(transaction):
                        successful_count += 1
                    else:
                        failed_transactions.append(transaction)
                except Exception as e:
                    print(f"❌ 回溯交易 {transaction['id']} 失败: {e}")
                    failed_transactions.append(transaction)

            # 5. 报告结果
            print("\n📈 回溯完成:")
            print(f"   成功回溯: {successful_count} 条")
            print(f"   失败/跳过: {len(failed_transactions)} 条")

            if failed_transactions:
                print("\n⚠️  以下交易需要手动处理:")
                for tx in failed_transactions:
                    print(
                        f"   ID:{tx['id']} - {tx['category']} - {tx['user_id']} - {tx['amount']}"
                    )

            # 6. 删除已处理的交易记录
            if delete_transactions and successful_count > 0:
                successful_transactions = [
                    tx for tx in transactions if tx not in failed_transactions
                ]
                if successful_transactions:
                    self.delete_transactions(successful_transactions)

            print("\n✅ 回溯操作完成!")
            print("💾 备份文件保存在:")
            print(f"   {data_backup}")
            print(f"   {tx_backup}")

        except Exception as e:
            print(f"❌ 回溯过程中发生错误: {e}")
            print("💾 可以使用以下备份文件恢复:")
            print(f"   {data_backup}")
            print(f"   {tx_backup}")
            raise


def main():
    parser = argparse.ArgumentParser(description="回溯货币系统数据到指定交易ID之前")
    parser.add_argument(
        "--target-id",
        type=int,
        required=True,
        help="目标交易ID，将回溯到此ID（含）之前的状态",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="仅模拟运行，不实际修改数据"
    )
    parser.add_argument(
        "--keep-transactions",
        action="store_true",
        help="保留交易记录，不删除已回溯的记录",
    )

    args = parser.parse_args()

    try:
        rollback = MonetaryDataRollback(
            args.target_id,
            Path(".data/monetary/data.db"),
            Path(".data/monetary/transaction.db"),
        )

        if args.dry_run:
            print("🔍 模拟运行模式，不会实际修改数据")
            transactions = rollback.get_transactions_to_rollback()

            if transactions:
                print("📋 将会回溯以下交易:")
                for tx in transactions:
                    print(
                        f"   ID:{tx['id']} - {tx['category']} - {tx['user_id']} - {tx['amount']}"
                    )
            else:
                print("✅ 没有找到需要回溯的交易记录")
        else:
            rollback.execute_rollback(delete_transactions=not args.keep_transactions)

    except Exception as e:
        print(f"❌ 执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
