import json
import logging
from typing import Tuple, Optional, List
from openai import AsyncOpenAI
import base64

logger = logging.getLogger("telegram_bot")


class SpamDetector:
    """LLM 垃圾訊息檢測器"""

    def __init__(self, openai_api_key: str, threshold: float = 9.0):
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
- 詢問 KryptoGO 產品功能或服務（如「電報推送資格怎麼領取」「會員怎麼開通」「VIP 怎麼加入」等，這些是用戶在詢問我們的產品，不是垃圾訊息）
- 提及 KryptoGO 相關的群組/頻道（如「KryptoGO VIP」「KryptoGO 官方」等是我們自己的群組，不是垃圾訊息）
- **KryptoGO 產品功能介紹或詢問**：如果訊息提到 PRO、吸籌、集群、信號、監控等功能描述，這是在介紹或詢問我們的產品功能，不是垃圾訊息。例如「全网集群吸筹监控，需要 PRO，当任何代币出现吸筹信号时立即通知您」這類訊息是 KryptoGO 的功能說明，應評為 0-3 分
- **分享合約地址/代幣地址**（如 Solana pump.fun 地址「2nP9yKQNSGQy851iyawDvBkzkK2R2aqKArQCKc2gpump」、ERC-20 地址「0xe0cd4cacddcbf4f36e845407ce53e87717b6601d」等區塊鏈合約地址，這是正常的代幣討論）

垃圾訊息定義：
1. **格式化交易信號**（直接提供進場點位和多個目標價位的格式化信號，例如「#BTC 2.25附近🈳 目標2.19—2.15—2.08」「進場50000 目標48000-46000-44000」等）
2. **交易信號推廣**（如「⬆️點擊上方加入頻道⬆️」「加入加密頻道」並附帶具體進場/止盈/止損點位的格式化信號）
3. **推廣其他群組/頻道**（包含 Telegram 群組連結或 handle，如「@某某群組」「t.me/xxx」「加入這個群組」「這個頻道不錯」「簡介掛的群組」等，目的是引導用戶加入其他群組或頻道。⚠️ 注意：只有 KryptoGO 相關的群組/頻道是白名單，其他所有群組推廣都是垃圾訊息）
4. **暗示性群組推廣**（沒有明確連結但暗示推薦某個群組，例如「這群真牛」「這個群不錯」「推薦給各位」「跟著這群」「這群很穩」等，通常會搭配「止盈單」「獲利」「收益」等詞彙來暗示跟著某群組可以賺錢）
5. **私下拉人的訊息**（如「加我 LINE」「私聊帶單」「聯繫我微信」「telegram 私訊」）
6. **過度推銷的訊息**（如「包賺不賠」「跟單保證獲利」「穩賺方法」「100% 勝率」「超賺」「爽收U」「拿下一套房」「輕鬆賺錢」「跟上就賺」等誇大收益、承諾暴利的話術）
7. **無關主題的廣告**（如賣產品、其他服務推銷、色情、賭博）
8. **跨群組回覆訊息**（訊息內容看起來像是在回覆某個不存在於本群組的訊息，例如 Ella 之類的人名但群組裡沒有這個人）
9. **惡意洗版、騷擾性訊息、辱罵**

⚠️ 特別注意：
- 格式化交易信號（包含具體進場點位和多個用破折號或其他符號分隔的目標價位）是明確的垃圾訊息，應評為 8-10 分
- 包含 Telegram 群組/頻道 handle（如 @xxx）或連結（t.me/xxx），並試圖引導用戶加入的訊息，是明確的垃圾訊息，應評為 8-10 分
- 暗示性群組推廣：即使沒有明確連結，如果訊息用「這群」「這個群」等詞彙暗示推薦某個外部群組，並搭配「止盈單」「獲利」「很穩」「真牛」「推薦給各位」等正面詞彙來暗示跟著可以賺錢，這是明確的垃圾訊息，應評為 8-10 分。例如「又又又來一張止盈單！這群真牛，推薦給各位」就是典型的暗示性群組推廣
  ⚠️ 例外：只有 KryptoGO 相關的群組（包含「KryptoGO」「Krypto GO」等字樣）是白名單，應評為 0-3 分
  ⚠️ 其他所有群組/頻道推廣（如 @BTC_crypto888、@xxx_trading 等）都是垃圾訊息，應評為 8-10 分
- 正常討論可能會提到「我在 X 價位進場」或「目標看到 Y」，但不會使用高度格式化的「進場點—目標1—目標2—目標3」這種信號格式
- 如果訊息同時包含「加入頻道」等引導文字和交易信號，更是明確的垃圾訊息
- **合約地址/代幣地址不是垃圾訊息**：像「2nP9yKQNSGQy851iyawDvBkzkK2R2aqKArQCKc2gpump」或「0xe0cd4cacddcbf4f36e845407ce53e87717b6601d」這類區塊鏈合約地址（包括 Solana pump.fun 地址、ERC-20 地址等）是正常的代幣討論，應評為 0-3 分

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

    async def check_image(self, image_data: bytes, caption: Optional[str] = None) -> Tuple[bool, float, str]:
        """
        檢查圖片是否包含垃圾訊息（如合約曬單）

        Args:
            image_data: 圖片的二進制數據
            caption: 圖片說明文字（可選）

        Returns:
            (is_spam, score, reasoning)
        """
        try:
            # 將圖片轉換為 base64
            base64_image = base64.b64encode(image_data).decode('utf-8')

            prompt = self._build_image_prompt(caption)
            response = await self._call_openai_vision(prompt, base64_image)
            score, reasoning = self._parse_response(response)

            is_spam = score >= self.threshold
            logger.info(f"Image checked: score={score:.1f}, is_spam={is_spam}")

            return (is_spam, score, reasoning)

        except Exception as e:
            logger.error(f"Error checking image: {e}", exc_info=True)
            # 發生錯誤時，返回安全的預設值（不判定為垃圾訊息）
            return (False, 0.0, f"圖片檢測錯誤: {str(e)}")

    def _build_image_prompt(self, caption: Optional[str] = None) -> str:
        """構建圖片檢測的 prompt"""
        base_prompt = """你是 KryptoGO 加密貨幣交易討論群的垃圾訊息檢測助手。

群組性質：這是一個專業的加密貨幣交易討論群。

請分析這張圖片，判斷是否為垃圾訊息。特別注意以下類型：

1. **交易信號推廣**：
   - 圖片中包含「加入頻道」「點擊上方」等引導文字
   - 提供格式化的交易信號（進場/止盈/止損點位）
   - 包含頻道連結、邀請連結的圖片
   - 目的是引導用戶加入其他頻道或群組

2. **合約曬單**：
   - 顯示交易盈虧的截圖（如 +685.54%、永續做空 35x 等）
   - 顯示高額收益的交易記錄
   - 顯示槓桿交易的盈利
   - 目的是炫耀收益或吸引他人跟單

3. **推銷廣告**：
   - 帶有邀請碼、推薦連結的圖片
   - 帶有 QR Code 並要求掃碼的圖片
   - 帶有「穩賺」「保證獲利」等字樣

4. **私下拉人**：
   - 要求加 LINE、微信、Telegram 私訊的圖片
   - 帶有聯繫方式的廣告圖

正常圖片包括：
- 價格走勢圖、K線圖、技術分析圖表
- 新聞截圖、項目資訊
- 純粹的技術討論圖片
- **來自 KryptoGO VIP 群組的圖片**（包含「KryptoGO VIP」「KryptoGO 會員」等字樣的圖片是我們自己的群組，應評為 0-3 分）
- **KryptoGO 產品功能介紹圖片**：如果圖片或說明文字提到 PRO、吸籌、集群、信號、監控等 KryptoGO 功能描述，這是產品功能介紹，不是垃圾訊息，應評為 0-3 分
- **包含合約地址/代幣地址的圖片**（如 Solana pump.fun 地址「2nP9yKQNSGQy851iyawDvBkzkK2R2aqKArQCKc2gpump」或 ERC-20 地址「0xe0cd4cacddcbf4f36e845407ce53e87717b6601d」等區塊鏈合約地址，這是正常的代幣討論）

⚠️ 特別注意：
- 如果圖片包含「KryptoGO VIP」「KryptoGO 會員」「KryptoGO 官方」等字樣，這是我們自己的群組內容，不是垃圾訊息，應評為 0-3 分
- 如果圖片或圖片說明文字包含「加入頻道」「點擊上方」等引導文字（但不是 KryptoGO 相關），且同時提供格式化的交易信號（進場/止盈/止損點位），這是明確的交易信號推廣垃圾訊息，應評為 8-10 分

請評估這張圖片，給出 0-10 分的垃圾訊息評分：
- 0-3 分：正常的技術分析或討論圖片
- 4-6 分：有點可疑但可能是正常分享
- 7 分：可疑
- 8-10 分：明確的垃圾訊息（交易信號推廣、合約曬單、推銷廣告等）
"""

        if caption:
            base_prompt += f"\n\n圖片說明文字：\n\"\"\"{caption}\"\"\"\n"

        base_prompt += """
請以 JSON 格式回應：
{
    "score": <0-10的數字>,
    "reasoning": "<簡短說明判斷理由，描述圖片內容，50字以內>"
}"""

        return base_prompt

    async def _call_openai_vision(self, prompt: str, base64_image: str) -> str:
        """呼叫 OpenAI Vision API"""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "你是一個專業的垃圾訊息檢測助手，只回應 JSON 格式。"
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.3,
                max_tokens=300,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            logger.debug(f"OpenAI Vision response: {content}")
            return content

        except Exception as e:
            logger.error(f"OpenAI Vision API error: {e}", exc_info=True)
            raise
