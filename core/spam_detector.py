import json
import logging
from typing import Tuple
from openai import AsyncOpenAI

logger = logging.getLogger("telegram_bot")


class SpamDetector:
    """LLM 垃圾訊息檢測器"""

    def __init__(self, openai_api_key: str, threshold: float = 8.0):
        """
        初始化檢測器

        Args:
            openai_api_key: OpenAI API 金鑰
            threshold: 垃圾訊息評分門檻 (0-10)
        """
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.threshold = threshold
        logger.info(f"SpamDetector initialized with threshold={threshold}")

    async def check_message(self, message_text: str) -> Tuple[bool, float, str]:
        """
        檢查訊息是否為垃圾訊息

        Args:
            message_text: 要檢查的訊息內容

        Returns:
            (is_spam, score, reasoning)
            - is_spam: 是否為垃圾訊息
            - score: LLM 評分 (0-10)
            - reasoning: 判斷理由
        """
        try:
            prompt = self._build_prompt(message_text)
            response = await self._call_openai(prompt)
            score, reasoning = self._parse_response(response)

            is_spam = score >= self.threshold
            logger.info(f"Message checked: score={score:.1f}, is_spam={is_spam}")

            return (is_spam, score, reasoning)

        except Exception as e:
            logger.error(f"Error checking message: {e}", exc_info=True)
            # 發生錯誤時，返回安全的預設值（不判定為垃圾訊息）
            return (False, 0.0, f"檢測錯誤: {str(e)}")

    def _build_prompt(self, message_text: str) -> str:
        """構建 LLM prompt"""
        return f"""你是 KryptoGO 加密貨幣交易討論群的垃圾訊息檢測助手。

群組性質：這是一個專業的加密貨幣交易討論群，成員會討論交易策略、技術分析、止盈止損等交易相關話題。

正常討論包括但不限於：
- 分享交易策略和技術分析
- 討論 BTC/ETH 等加密貨幣價格走勢
- 討論止盈止損點位、槓桿倍數等
- 分享交易心得和經驗
- 詢問技術問題或尋求建議

垃圾訊息定義：
1. 私下拉人的訊息（如「加我 LINE」「私聊帶單」「聯繫我微信」「telegram 私訊」）
2. 過度推銷的訊息（如「包賺不賠」「跟單保證獲利」「穩賺方法」「100% 勝率」）
3. 無關主題的廣告（如賣產品、其他服務推銷、色情、賭博）
4. 惡意洗版、騷擾性訊息、辱罵

請評估以下訊息，給出 0-10 分的垃圾訊息評分：
- 0-3 分：完全正常的交易討論
- 4-6 分：有點可疑但可能是正常討論
- 7 分：可疑，需要注意
- 8-10 分：明確的垃圾訊息

訊息內容：
\"\"\"{message_text}\"\"\"

請以 JSON 格式回應：
{{
    "score": <0-10的數字>,
    "reasoning": "<簡短說明判斷理由，50字以內>"
}}"""

    async def _call_openai(self, prompt: str) -> str:
        """呼叫 OpenAI API"""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "你是一個專業的垃圾訊息檢測助手，只回應 JSON 格式。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # 降低隨機性，提高一致性
                max_tokens=200,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            logger.debug(f"OpenAI response: {content}")
            return content

        except Exception as e:
            logger.error(f"OpenAI API error: {e}", exc_info=True)
            raise

    def _parse_response(self, response: str) -> Tuple[float, str]:
        """
        解析 LLM 回應

        Returns:
            (score, reasoning)
        """
        try:
            data = json.loads(response)
            score = float(data.get("score", 0))
            reasoning = data.get("reasoning", "無理由")

            # 確保評分在合理範圍內
            score = max(0.0, min(10.0, score))

            return (score, reasoning)

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to parse LLM response: {e}, response: {response}")
            # 解析失敗時返回安全的預設值
            return (0.0, "解析回應失敗")
