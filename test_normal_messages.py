#!/usr/bin/env python3
"""
測試正常訊息不會被誤判為垃圾訊息

這些都是來自真實交易討論群的正常對話，應該被評為低分（< 8.0）
"""

import asyncio
import sys
from pathlib import Path

# 添加專案根目錄到 path
sys.path.insert(0, str(Path(__file__).parent))

from bot.config import load_config
from core.spam_detector import SpamDetector
from utils.logger import setup_logger


# 測試訊息（來自真實討論群）
TEST_MESSAGES = [
    "总的一个意思就是，我发ca了，能查到有没有庄，是不是在吸筹，能不能买，能不能卖在最高位，如果能有这些分析网站来一个，不会缺人购买的，其他公司也会寻求你们合作，因为这块市场还是一片空白",
]


async def test_messages():
    """測試所有訊息"""
    # 載入配置
    config = load_config('config.yaml')

    # 設定日誌
    logger = setup_logger('test.log', 'INFO')

    # 初始化檢測器
    detector = SpamDetector(
        openai_api_key=config['openai_api_key'],
        threshold=config['spam_threshold']
    )

    print("=" * 80)
    print("開始測試正常訊息檢測")
    print(f"垃圾訊息門檻：{config['spam_threshold']}")
    print(f"測試訊息數量：{len(TEST_MESSAGES)}")
    print("=" * 80)
    print()

    results = []
    false_positives = []

    for i, message in enumerate(TEST_MESSAGES, 1):
        print(f"[{i}/{len(TEST_MESSAGES)}] 測試訊息:")
        print(f"  內容: {message[:60]}{'...' if len(message) > 60 else ''}")

        try:
            is_spam, score, reasoning = await detector.check_message(message)

            result = {
                'message': message,
                'score': score,
                'is_spam': is_spam,
                'reasoning': reasoning
            }
            results.append(result)

            # 判斷是否為誤判
            if is_spam:
                false_positives.append(result)
                print(f"  ❌ 誤判為垃圾！評分: {score:.1f}")
                print(f"  理由: {reasoning}")
            else:
                print(f"  ✅ 正確判斷為正常訊息，評分: {score:.1f}")
                print(f"  理由: {reasoning}")

            print()

            # 避免觸發 API rate limit
            await asyncio.sleep(1)

        except Exception as e:
            print(f"  ⚠️ 檢測錯誤: {e}")
            print()

    # 統計結果
    print("=" * 80)
    print("測試結果統計")
    print("=" * 80)
    print(f"總測試數: {len(TEST_MESSAGES)}")
    print(f"正確判斷: {len(TEST_MESSAGES) - len(false_positives)} ({(len(TEST_MESSAGES) - len(false_positives)) / len(TEST_MESSAGES) * 100:.1f}%)")
    print(f"誤判數量: {len(false_positives)} ({len(false_positives) / len(TEST_MESSAGES) * 100:.1f}%)")
    print()

    # 評分分布
    scores = [r['score'] for r in results]
    avg_score = sum(scores) / len(scores)
    max_score = max(scores)
    min_score = min(scores)

    print(f"平均評分: {avg_score:.2f}")
    print(f"最高評分: {max_score:.2f}")
    print(f"最低評分: {min_score:.2f}")
    print()

    # 顯示誤判詳情
    if false_positives:
        print("=" * 80)
        print("誤判訊息詳情")
        print("=" * 80)
        for i, fp in enumerate(false_positives, 1):
            print(f"\n[{i}] 評分: {fp['score']:.1f}")
            print(f"訊息: {fp['message']}")
            print(f"理由: {fp['reasoning']}")
    else:
        print("🎉 太好了！沒有誤判！")

    print()
    print("=" * 80)

    # 返回測試結果
    return len(false_positives) == 0


async def main():
    """主函數"""
    try:
        success = await test_messages()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n測試中斷")
        sys.exit(1)
    except Exception as e:
        print(f"\n測試失敗: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
