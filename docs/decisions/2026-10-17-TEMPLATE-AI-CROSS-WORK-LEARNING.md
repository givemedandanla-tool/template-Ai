# Template AI 產品定義：跨作品學習與條件式模板生成

{
  "id": "DEC-20261017-TEMPLATE-AI-CROSS-WORK-LEARNING",
  "status": "USER_PRODUCT_DEFINITION_CONFIRMED_ENGINEERING_DESIGN_PROPOSED",
  "user_sources": [
    {
      "quote": "匯入作品，學習規則，產出模板，根據輸入找出最佳模板或產出自動排版結果。",
      "meaning": "Learn shared design rules from many works; generate reusable and conditional layouts; select best validated candidate for current input."
    },
    {
      "quote": "我無法接受當前的一個作品就一個模板的模式",
      "meaning": "One work -> one template is not accepted as the learning/product goal."
    },
    {
      "quote": "同時請參照數學演算法、Ai訓練技術、商用方案還有開源專案的思路，來設計我需要的訓練方法還有參數設計",
      "meaning": "Explicit mathematical/training/commercial/open-source basis is required."
    }
  ],
  "old_scope": "CURRENT008 verifies existing registered workflow/constraint software only. It does not establish cross-work generative learning; retain immutable evidence without claiming product-goal completion.",
  "required_behavior": [
    "Many independent works -> versioned shared design family/rules, not one exported template per source",
    "New input -> retrieve suitable families, synthesize parameterized candidates when needed, solve and rank feasible outputs",
    "Learned data/statistics/preferences separated from hard geometry/font/rights policies",
    "Evaluation on lineage-disjoint unseen works/inputs with real authorized corpus; authored fixtures only validate mechanics",
    "Zero routine dialogue; durable GitHub checkpoints and resumable local work"
  ],
  "not_approved_by_this_decision": [
    "No paid services/GPU rental/cloud model APIs",
    "No claim that proposed numeric defaults have been measured or accepted",
    "No replacement of historical evidence or automatic completion of new capabilities"
  ],
  "design": "docs/dev/AI_CROSS_WORK_LEARNING_PLAN.md",
  "contract": "docs/dev/AI_CROSS_WORK_LEARNING_CONTRACT.json"
}
