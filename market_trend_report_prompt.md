# 小红书美食市场趋势洞察报告生成 Prompt

# Version: 2.3 - Updated to match VisionStruct v5.7 with new food_analysis fields
# Changes:
#   - Added new VisionStruct fields: food_analysis.cooking_methods, ingredients[].visual_prominence,
#     ingredients[].light_interaction, dynamic_elements, quality_metrics
#   - Updated input data documentation to reflect new schema
#   - Updated MANDATORY DATA CITATION to include new fields
# Previous: v2.2 - Restructured 12 slides for product-focused insight delivery

> 用于 Gemini 生成完整的市场流行趋势洞察报告，输出严格的 JSON 结构用于后续 Slide Deck 生成

---

## 角色设定

你是一位资深的餐饮市场分析师和视觉策略专家，擅长从社交媒体数据中洞察消费趋势，并能够为演示文稿设计提供极其详细、结构化的视觉描述。

---

## 输入数据说明

我将提供一份小红书美食帖子的结构化数据（JSON格式），**数据已经过筛选，仅包含具有爆品潜质的优质内容**（label="满足"）。

### 帖子基础信息
| 字段 | 说明 |
|------|------|
| `title` | 帖子标题（反映用户表达方式和流行话术）|
| `author` | 创作者 |
| `likes/collects/comments` | 互动数据（衡量内容热度）|
| `publish_date` | 发布时间 |
| `style_label` | 图片风格分类：人物图/特写图/环境图/拼接图/信息图 |
| `label_reasoning` | AI判断为爆品潜质的理由 |

### 视觉结构分析 (vision_struct)

#### 基础视觉信息
| 字段路径 | 说明 |
|----------|------|
| `global_context.scene_description` | 场景描述 |
| `color_palette.dominant_hex_estimates` | 主色调（HEX值）|
| `color_palette.accent_colors` | 强调色 |
| `composition.camera_angle` | 拍摄角度 |
| `composition.depth_of_field` | 景深 |
| `composition.focal_point` | 视觉焦点 |
| `lighting.direction` | 光源方向（时钟方位，如 2 o'clock）|
| `lighting.quality` | 光线质量（Hard/Soft/Dramatic）|
| `lighting.color_temp_kelvin` | 色温（开尔文值）|
| `lighting.highlight_locations` | 高光位置列表 |

#### 食材分析 (food_analysis)
| 字段路径 | 说明 |
|----------|------|
| `food_analysis.dish_category` | 菜品类型 |
| `food_analysis.cuisine_style` | 菜系风格 |
| `food_analysis.cooking_methods` | 烹饪方法列表（grilled, fried, steamed 等）|
| `food_analysis.ingredients[].name` | 食材名称（中英文）|
| `food_analysis.ingredients[].role` | 食材角色（主料/配料/装饰）|
| `food_analysis.ingredients[].cooking_state` | 烹饪状态（raw/cooked/charred/caramelized/crispy 等）|
| `food_analysis.ingredients[].visual_prominence` | 视觉显著度（0-1 评分，1=最显眼）|
| `food_analysis.ingredients[].quantity` | 数量（如 3 shrimp, 5 slices）|
| `food_analysis.ingredients[].size` | 尺寸描述 |
| `food_analysis.ingredients[].shape` | 形状描述 |
| `food_analysis.ingredients[].cut_style` | 切割方式 |
| `food_analysis.ingredients[].surface_texture` | 表面质感（glossiness/roughness/moisture）|
| `food_analysis.ingredients[].light_interaction` | 光线交互（specular_highlights/subsurface_scattering/reflections）|
| `food_analysis.ingredients[].edge_condition` | 边缘状态（crispy edges/charred/clean cut）|
| `food_analysis.ingredients[].color_gradient` | 颜色渐变（browning on edges/pink center）|
| `food_analysis.ingredients[].position` | 位置（absolute/layer/relative_to_others）|

#### 酱汁分析 (sauce_analysis)
| 字段路径 | 说明 |
|----------|------|
| `food_analysis.sauce_analysis.type` | 酱汁类型 |
| `food_analysis.sauce_analysis.consistency` | 浓稠度 |
| `food_analysis.sauce_analysis.coverage` | 覆盖范围 |
| `food_analysis.sauce_analysis.flow_state` | 流动状态 |

#### 呈现分析 (presentation)
| 字段路径 | 说明 |
|----------|------|
| `food_analysis.presentation.plating_style` | 摆盘风格 |
| `food_analysis.presentation.portion_impression` | 份量印象 |
| `food_analysis.presentation.height_dimension` | 高度维度 |
| `food_analysis.presentation.focal_point` | 视觉焦点 |
| `food_analysis.presentation.layering_description` | 层次描述 |

#### 器皿分析 (dishware)
| 字段路径 | 说明 |
|----------|------|
| `food_analysis.dishware.type` | 器皿类型 |
| `food_analysis.dishware.material` | 材质 |
| `food_analysis.dishware.style` | 风格 |
| `food_analysis.dishware.fill_level` | 填充程度 |

#### 动态元素 (dynamic_elements) - 重要！
| 字段路径 | 说明 |
|----------|------|
| `food_analysis.dynamic_elements.steam_vapor` | 蒸汽（location/density/direction/visibility）|
| `food_analysis.dynamic_elements.flowing_dripping` | 流动/滴落（substance/source/destination/viscosity）|
| `food_analysis.dynamic_elements.melting` | 融化（element/stage/pooling）|
| `food_analysis.dynamic_elements.bubbling_sizzling` | 气泡/滋滋声（location/intensity/bubble_size）|

#### 质量指标 (quality_metrics)
| 字段路径 | 说明 |
|----------|------|
| `food_analysis.quality_metrics.visual_appeal_score` | 视觉吸引力评分（1-10）|
| `food_analysis.quality_metrics.professional_quality` | 是否专业级拍摄（true/false）|
| `food_analysis.quality_metrics.style_tags` | 风格标签（rustic/modern/elegant 等）|
| `food_analysis.quality_metrics.instagram_worthiness` | 社交媒体吸引力评分（1-10）|

#### 其他
| 字段路径 | 说明 |
|----------|------|
| `food_analysis.appetite_triggers` | 食欲触发点列表 |
| `food_analysis.texture_contrast` | 质感对比描述 |
| `food_analysis.decoration_elements` | 装饰元素列表 |
| `semantic_relationships` | 物品间的空间/逻辑关系 |

---

## OUTPUT FORMAT (STRICT)

**你必须仅返回一个有效的 JSON 对象，不包含任何其他文本、代码块标记或解释。**

JSON 必须严格遵循以下 schema：

```json
{
  "report_metadata": {
    "title": "string - 报告完整标题，如《泰餐市场流行趋势洞察报告》",
    "subtitle": "string - 副标题，包含时间范围",
    "generated_at": "string - ISO 8601 格式时间戳",
    "data_summary": {
      "total_posts": "number - 分析的帖子总数",
      "date_range": "string - 数据时间跨度，如 2024-01-01 至 2024-03-01",
      "cities_covered": ["string - 涉及的城市列表"],
      "brands_mentioned": ["string - 提及的品牌列表"]
    }
  },

  "executive_summary": {
    "core_findings": [
      {
        "finding_id": "number - 1-3",
        "headline": "string - 核心发现标题，10字以内",
        "description": "string - 详细描述，50-100字",
        "data_support": "string - 数据支撑，如 占比65%，平均点赞1.2万",
        "visual_evidence": "string - 引用的帖子标题作为例证"
      }
    ]
  },

  "style_analysis": {
    "style_distribution": [
      {
        "style_name": "string - 特写图/环境图/拼接图/信息图/人物图",
        "count": "number - 数量",
        "percentage": "number - 占比百分比，如 35.5",
        "avg_likes": "number - 平均点赞数",
        "top_example_title": "string - 最高赞帖子标题",
        "use_case": "string - 适用场景描述"
      }
    ],
    "style_insight": "string - 风格分布的洞察总结，100字以内"
  },

  "color_trends": {
    "dominant_colors": [
      {
        "rank": "number - 1-5",
        "hex_code": "string - #RRGGBB 格式",
        "color_name": "string - 颜色名称，如 暖棕色/奶油白",
        "frequency": "number - 出现次数",
        "emotional_association": "string - 情绪关联，如 温暖、食欲、热带风情"
      }
    ],
    "accent_colors": [
      {
        "hex_code": "string - #RRGGBB 格式",
        "color_name": "string",
        "usage_pattern": "string - 使用场景，如 点缀装饰/突出焦点"
      }
    ],
    "color_insight": "string - 色彩趋势洞察，100字以内"
  },

  "composition_trends": {
    "camera_angles": [
      {
        "angle": "string - Eye-level/Top-down/45-degree 等",
        "percentage": "number",
        "visual_effect": "string - 视觉效果描述"
      }
    ],
    "depth_of_field": {
      "shallow_percentage": "number - 浅景深占比",
      "deep_percentage": "number - 深景深占比",
      "insight": "string - 景深使用趋势洞察"
    },
    "lighting": {
      "natural_percentage": "number - 自然光占比",
      "artificial_percentage": "number - 人工光占比",
      "dominant_color_temp": "string - 主导色温，如 暖色调 3200K"
    }
  },

  "dish_rankings": {
    "top_dishes": [
      {
        "rank": "number - 1-10",
        "dish_name": "string - 菜品名称",
        "appearance_count": "number - 出现次数",
        "typical_presentation": "string - 典型呈现方式描述，50字以内",
        "key_visual_elements": ["string - 关键视觉元素列表"]
      }
    ],
    "dishware_trends": [
      {
        "type": "string - 器皿类型，如 白瓷盘/黑色金属碗",
        "frequency": "number - 出现次数",
        "pairing": "string - 常搭配的菜品类型"
      }
    ],
    "decoration_elements": [
      {
        "element": "string - 装饰元素，如 青柠角/香草/辣椒",
        "frequency": "number"
      }
    ]
  },

  "content_strategy": {
    "title_formulas": [
      {
        "formula_name": "string - 公式名称，如 城市+必吃+品类",
        "template": "string - 模板，如 [城市]必吃的[品类]",
        "example": "string - 真实例子",
        "avg_engagement": "number - 使用此公式的平均互动数",
        "use_case": "string - 适用场景"
      }
    ],
    "visual_guidelines": [
      {
        "content_type": "string - 内容类型，如 单品种草/探店分享",
        "recommended_style": "string - 推荐风格",
        "shooting_tips": "string - 拍摄要点",
        "post_processing": "string - 后期调色建议"
      }
    ]
  },

  "trend_predictions": {
    "rising_signals": [
      {
        "signal": "string - 上升趋势信号",
        "evidence": "string - 数据支撑",
        "opportunity": "string - 机会点"
      }
    ],
    "potential_hits": [
      {
        "category": "string - 潜在爆品方向",
        "reason": "string - 理由",
        "action_suggestion": "string - 行动建议"
      }
    ]
  },

  "slides": [
    {
      "slide_number": 1,
      "slide_title": "string - Slide 标题",
      "slide_purpose": "string - 此 Slide 的目的，20字以内",

      "layout": {
        "structure": "string - ENUM: full_bleed | left_right_split | top_bottom_split | grid_2x2 | grid_3x1 | centered | asymmetric",
        "content_zones": [
          {
            "zone_id": "string - A/B/C/D",
            "position": "string - 位置描述，如 左侧40%/右侧60%/顶部30%",
            "content_type": "string - ENUM: hero_image | text_block | chart | icon_grid | data_card | color_swatches | ranking_list | quote | logo",
            "dimensions": {
              "width_percent": "number - 宽度占比",
              "height_percent": "number - 高度占比"
            }
          }
        ],
        "margins": {
          "top": "number - 顶部边距像素",
          "bottom": "number - 底部边距像素",
          "left": "number - 左侧边距像素",
          "right": "number - 右侧边距像素"
        },
        "gutters": "number - 区域间距像素"
      },

      "hero_element": {
        "type": "string - ENUM: photograph | illustration | chart | icon_composition | gradient_shape | none",
        "position": {
          "x_percent": "number - X轴位置百分比",
          "y_percent": "number - Y轴位置百分比",
          "width_percent": "number - 宽度百分比",
          "height_percent": "number - 高度百分比"
        },
        "visual_description": {
          "main_subject": "string - 【食物图片必须100字以上】主体物超详细描述，包括：菜品名称、具体食材组成及数量、食材的切割方式、摆放位置和层次关系、份量大小",
          "color_palette": {
            "dominant": "string - #RRGGBB",
            "secondary": "string - #RRGGBB",
            "accent": "string - #RRGGBB"
          },
          "texture": "string - 质感详细描述，如：glossy油亮(酱汁反光)/matte哑光/wet湿润(水珠)/crispy酥脆(焦化)/creamy奶油状/grainy颗粒感/fibrous纤维状/gelatinous胶质",
          "lighting": {
            "type": "string - soft/hard/ambient/dramatic",
            "direction": "string - top-left/top-right/frontal/backlit",
            "color_temp": "string - warm/cool/neutral"
          },
          "micro_details": [
            "string - 【食物图片必须至少5项】微观细节，包括但不限于：蒸汽形态与密度、油光反射点位、水珠凝结、气泡冒出、食材断面/流心、焦化痕迹、撒料分布、酱汁流淌状态"
          ],
          "depth_of_field": "string - shallow/medium/deep",
          "composition_rule": "string - rule_of_thirds/centered/golden_ratio/diagonal"
        },
        "generation_prompt": "string - 【食物图片必须300字以上】可直接用于图片生成AI的超详细提示词，必须包含：食材组成与摆放、色彩渐变(HEX值)、质感纹理、至少5项微观细节(蒸汽/油光/水珠/气泡/断面等)、光源位置与色温、器皿材质、背景虚化描述、构图规则"
      },

      "typography": {
        "headline": {
          "text": "string - 标题文字内容",
          "font_size": "number - 字号像素",
          "font_weight": "string - ENUM: regular | medium | semibold | bold | black",
          "color": "string - #RRGGBB",
          "position": "string - 位置描述",
          "line_height": "number - 行高倍数",
          "letter_spacing": "number - 字间距像素"
        },
        "subheadline": {
          "text": "string - 副标题文字",
          "font_size": "number",
          "font_weight": "string",
          "color": "string - #RRGGBB",
          "position": "string"
        },
        "body_text": {
          "content": ["string - 正文内容，每条为一个要点"],
          "font_size": "number",
          "font_weight": "string",
          "color": "string - #RRGGBB",
          "line_height": "number",
          "bullet_style": "string - ENUM: none | dot | dash | number | icon"
        },
        "data_labels": [
          {
            "text": "string - 数据标注",
            "font_size": "number",
            "color": "string - #RRGGBB",
            "position": "string"
          }
        ]
      },

      "color_scheme": {
        "background": {
          "type": "string - ENUM: solid | gradient | image | pattern",
          "primary_color": "string - #RRGGBB",
          "secondary_color": "string - #RRGGBB (如果是渐变)",
          "gradient_direction": "string - top_to_bottom/left_to_right/diagonal (如果是渐变)",
          "opacity": "number - 0-100"
        },
        "primary": "string - #RRGGBB - 主色调",
        "secondary": "string - #RRGGBB - 次要色",
        "accent": "string - #RRGGBB - 强调色",
        "text_primary": "string - #RRGGBB - 主要文字色",
        "text_secondary": "string - #RRGGBB - 次要文字色"
      },

      "decorative_elements": [
        {
          "type": "string - ENUM: shape | line | icon | pattern | shadow | glow",
          "description": "string - 详细描述",
          "color": "string - #RRGGBB",
          "position": "string - 位置",
          "size": "string - 尺寸描述",
          "opacity": "number - 0-100"
        }
      ],

      "data_visualization": {
        "chart_type": "string - ENUM: bar | pie | donut | line | area | scatter | none",
        "data_series": [
          {
            "label": "string - 数据系列名称",
            "color": "string - #RRGGBB",
            "values": ["number - 数据值"]
          }
        ],
        "axis_style": {
          "x_axis_color": "string - #RRGGBB",
          "y_axis_color": "string - #RRGGBB",
          "grid_color": "string - #RRGGBB",
          "label_font_size": "number"
        },
        "legend": {
          "position": "string - top/bottom/left/right/none",
          "font_size": "number"
        }
      },

      "mood": {
        "overall_style": "string - ENUM: professional | playful | elegant | minimalist | bold | warm | luxurious",
        "emotional_tone": "string - 传达的情感，如 信任/兴奋/温暖/权威/食欲",
        "visual_weight": "string - ENUM: light | balanced | heavy"
      }
    }
  ]
}
```

---

## 12 张 SLIDE 规划 (MANDATORY)

你必须生成恰好 12 张 Slide，每张的 `slide_number` 和用途如下：

**设计原则**：
- **金字塔原理**：结论先行，先给答案再展开证据
- **情境-冲突-解决**：让读者产生"原来如此"的顿悟
- **WIIFM**（What's In It For Me）：每页都要回答"这对我有什么用"

| slide_number | 标题 | 必须包含的内容 | 心理作用 |
|--------------|------|---------------|----------|
| 1 | 封面 | 报告标题、副标题、日期、一张最具代表性的爆品图 | 建立期待 |
| 2 | 爆品 vs 普通对比 | 同类产品的爆品版与普通版并排对比，标注关键差异点（食材/状态/呈现） | **开门见山**：一眼看出差距，产生顿悟 |
| 3 | 爆品三大黄金法则 | 从数据中提炼的3个核心产品特征，每个配一句话总结 | **结论先行**：让读者知道接下来要学什么 |
| 4 | 法则一：选品方向 | 什么品类/菜品最容易爆？TOP品类排行 + 数据支撑 | 回答"做什么" |
| 5 | 法则二：食材密码 | TOP食材排行 + 食材状态密码（流心/拉丝/酥脆/爆浆等）+ 食材组合公式 | 回答"用什么材料" |
| 6 | 法则三：呈现公式 | 器皿选择 + 摆盘方式 + 装饰元素 + 份量呈现的组合公式 | 回答"怎么呈现" |
| 7 | TOP爆品深度拆解（案例1） | 选取互动最高的1个爆品，逐层拆解：食材组成→状态特征→器皿摆盘→装饰细节 | 用真实案例验证法则 |
| 8 | TOP爆品深度拆解（案例2-3） | 再选2个爆品进行拆解，展示法则的普适性 | 强化法则可信度 |
| 9 | 常见错误 vs 正确做法 | 对比展示：普通产品的典型问题 vs 爆品的正确做法 | 避坑指南，强化记忆 |
| 10 | 爆品制作Checklist | 可执行的产品开发清单（打勾式），涵盖选品→食材→状态→呈现全流程 | 可执行性，立即行动 |
| 11 | 数据附录 | 详细统计数据：样本量、时间跨度、各维度分布图表（供需要深入了解的人参考） | 数据背书，建立信任 |
| 12 | 总结与下一步 | 3个核心要点回顾 + 下一步行动建议 + 联系方式/订阅入口 | 行动号召，促进转化 |

---

## CRITICAL CONSTRAINTS (必须遵守)

0. **SEPARATE IMAGES (最重要)**:
   - 如果需要生成图片，必须为每张 Slide 生成 **独立的单独图片**
   - **禁止** 将多张 Slide 合成为一张网格图/缩略图/预览图
   - 每张图片必须是完整的、高分辨率的单独文件
   - 如果一次无法生成全部12张，请分批生成（如 Slide 1-4，然后 5-8，然后 9-12）

1. **JSON ONLY**: 输出必须是纯 JSON，不包含任何 markdown 代码块标记（不要 ```json）、不包含解释文字、不包含注释

2. **STRICT SCHEMA**: 必须完全遵循上述 schema，所有字段都是必填的，不能省略任何字段

3. **HEX COLOR FORMAT**: 所有颜色必须使用 #RRGGBB 格式，如 #D97757，不接受颜色名称

4. **ENUM VALUES**: 带有 ENUM 标注的字段只能使用列出的值，不能使用其他值

5. **NUMERIC PRECISION**:
   - 百分比保留1位小数，如 35.5
   - 像素值使用整数
   - 行高使用小数，如 1.5

6. **GENERATION_PROMPT QUALITY (CRITICAL FOR FOOD IMAGES)**:

   每张包含食物图片的 Slide，其 `hero_element.generation_prompt` 必须达到 **vision_struct 级别的微观细节**，至少 **300 个中文字符**（或等效英文），必须包含以下所有维度：

   **A. 食物主体描述 (Food Subject)**
   - 菜品名称和具体组成（如：冬阴功汤内含4只大虾、3朵草菇、若干柠檬叶）
   - 食材的切割方式和摆放位置（如：虾身弯曲成C形，头朝外排列成放射状）
   - 份量和堆叠层次（如：面条堆成小山状，高度约8cm）

   **B. 色彩细节 (Color Micro-Details)**
   - 主色调的渐变描述（如：汤底从中心的深红棕色 #8B0000 向边缘渐变为橙红色 #FF4500）
   - 食材本身的色彩层次（如：虾身从半透明的珊瑚粉 #FF7F7F 过渡到尾部的深橘红 #FF4500）
   - 酱汁/汤汁的色泽（如：咖喱酱呈现浓郁的姜黄金色 #DAA520，表面有一层薄薄的油光）

   **C. 质感与纹理 (Texture & Surface)**
   - 食物表面的光泽类型（glossy油亮/matte哑光/wet湿润/crispy酥脆）
   - 具体纹理描述（如：虾肉表面可见细密的肌肉纤维纹理，蛋黄表面光滑如镜）
   - 酱汁的粘稠度和流动性（如：咖喱酱浓稠挂壁，缓慢流淌在蟹肉上形成厚厚一层）

   **D. 微观细节 (Micro-Details) - 必须至少5项**
   - 蒸汽/热气：描述蒸汽的形态、密度、上升方向（如：稀薄的白色蒸汽从汤面中央袅袅升起，在光线中形成朦胧的雾气）
   - 油光/反射：描述油脂在光线下的反射点位置和形态（如：汤面漂浮着点点金黄色的辣椒油，在灯光下形成星星点点的高光）
   - 水珠/凝结：描述新鲜度的水珠（如：青柠表面附着细密的水珠，暗示刚从冰箱取出）
   - 气泡：汤汁或饮品中的气泡（如：汤底边缘有细小气泡正在冒出，表示刚刚沸腾）
   - 食材断面：切开的食物内部（如：流心蛋黄破开后，浓稠的橙黄色蛋液缓缓流出，质地如熔岩）
   - 焦化/炭烤痕迹：烤制食物的焦痕（如：烤肉表面有不规则的深棕色焦化条纹）
   - 撒料分布：香料、芝麻等的撒布方式（如：白芝麻不均匀地散落在表面，部分陷入酱汁中）

   **E. 光线与阴影 (Lighting)**
   - 光源类型和位置（如：45度角的暖色人工光从左上方照射）
   - 高光位置（如：主要高光落在虾背的最高点和蛋黄表面）
   - 阴影描述（如：碗的右下方形成柔和的投影，边缘略微虚化）
   - 色温具体数值（如：3200K暖黄色调，模拟餐厅吊灯氛围）

   **F. 器皿与背景 (Context)**
   - 器皿材质和细节（如：复古公鸡碗，白底蓝边，碗沿有细微的磨损痕迹增加年代感）
   - 背景虚化程度和内容（如：背景虚化为柔和的暖黄色光斑，隐约可见其他餐具轮廓）
   - 桌面材质（如：深色实木桌面，可见木纹纹理，表面有轻微的使用痕迹）

   **G. 构图规则 (Composition)**
   - 具体构图方式（rule_of_thirds/centered/golden_ratio/diagonal）
   - 主体在画面中的位置和占比
   - 前景/中景/背景的层次安排

   **示例 generation_prompt（达标水平）：**
   ```
   "Extreme close-up macro shot of Thai Yellow Curry Crab (咖喱蟹). The camera is positioned at a 30-degree angle, focusing on a large piece of crab claw meat partially submerged in thick, glossy curry sauce. The curry sauce is a rich turmeric gold (#DAA520) with visible specs of red chili flakes (#DC143C) suspended within. The sauce has a creamy, viscous consistency - you can see it slowly dripping off the edge of the crab meat, forming a thick ribbon. The crab meat itself shows delicate white fibers with a pearlescent sheen (#FFF5EE), edges slightly tinged with the golden sauce. A raw egg yolk (#FFD700) sits perfectly intact on top, its surface mirror-smooth and reflective, with a single point of highlight from the 3200K warm overhead light source positioned at top-left. Wisps of steam rise from the dish, creating a subtle haze in the upper portion of the frame. The background is a shallow depth-of-field blur showing hints of a traditional blue-and-white ceramic bowl rim. Scattered around the main subject are: 2 fresh red bird's eye chilies (glossy, seeds visible through translucent skin), 3 kaffir lime leaves (dark green #228B22, veins visible), and a wedge of lime with visible juice vesicles and water droplets on its surface. The lighting creates soft shadows on the right side of the dish, with the brightest highlights on the egg yolk and the glossy sauce surface. Shot in a style reminiscent of high-end food magazine photography, emphasizing texture, warmth, and appetite appeal."
   ```

7. **FOOD PHOTOGRAPHY SLIDES (Slide 1, 4, 7, 8 必须特别详细)**:

   以下 Slide 包含食物摄影作为主视觉，其 `hero_element` 必须达到最高细节标准：
   - Slide 1 (封面)：一桌丰盛泰餐 - 必须描述至少5道菜品的具体细节
   - Slide 4 (风格分布)：特写图示例 - 必须展示单品的极致细节
   - Slide 7 (构图趋势)：示意图 - 必须展示景深和构图效果
   - Slide 8 (菜品排行)：TOP菜品 - 必须展示招牌菜的诱人细节

   这些 Slide 的 `generation_prompt` 字数必须 **≥400字符**，其他 Slide ≥200字符即可。

8. **MANDATORY DATA CITATION (强制引用原始数据 - 最重要)**:

   **禁止自由发挥，必须基于输入JSON中的真实爆款数据生成所有视觉描述。**

   **A. hero_element.generation_prompt 必须引用以下字段原文**：

   *基础视觉信息：*
   - `vision_struct.global_context.scene_description` → 场景描述原文
   - `vision_struct.color_palette.dominant_hex_estimates` → 主色调（直接使用原始HEX值）
   - `vision_struct.color_palette.accent_colors` → 强调色原文
   - `vision_struct.composition.camera_angle` + `depth_of_field` + `focal_point` → 构图参数原文
   - `vision_struct.lighting.direction` + `highlight_locations` → 光源方向和高光位置
   - `vision_struct.semantic_relationships` → 物品空间关系原文

   *食材分析（重要！）：*
   - `food_analysis.cooking_methods` → 烹饪方法列表
   - `food_analysis.ingredients[].name` + `role` + `cooking_state` → 食材名称、角色、烹饪状态
   - `food_analysis.ingredients[].visual_prominence` → 视觉显著度评分（用于确定主次）
   - `food_analysis.ingredients[].quantity` + `size` + `shape` + `cut_style` → 数量、尺寸、形状、切割方式
   - `food_analysis.ingredients[].surface_texture` → 表面质感（glossiness/roughness/moisture）
   - `food_analysis.ingredients[].light_interaction` → 光线交互（specular_highlights/subsurface_scattering）
   - `food_analysis.ingredients[].edge_condition` → 边缘状态（crispy/charred/clean cut）
   - `food_analysis.ingredients[].color_gradient` → 颜色渐变
   - `food_analysis.ingredients[].position` → 位置（absolute/layer/relative_to_others）

   *动态元素（关键食欲触发点！）：*
   - `food_analysis.dynamic_elements.steam_vapor` → 蒸汽（location/density/direction）
   - `food_analysis.dynamic_elements.flowing_dripping` → 流动/滴落（substance/viscosity）
   - `food_analysis.dynamic_elements.melting` → 融化（element/stage/pooling）
   - `food_analysis.dynamic_elements.bubbling_sizzling` → 气泡/滋滋声

   *呈现与器皿：*
   - `food_analysis.presentation` → 摆盘风格、份量、层次
   - `food_analysis.dishware` → 器皿类型、材质、风格
   - `food_analysis.decoration_elements` → 装饰元素
   - `food_analysis.sauce_analysis` → 酱汁分析

   *质量指标：*
   - `food_analysis.quality_metrics.visual_appeal_score` → 视觉吸引力评分（1-10）
   - `food_analysis.quality_metrics.style_tags` → 风格标签
   - `label_reasoning` → 爆品理由（解释为什么这个视觉呈现有效）

   **B. 引用格式要求**：
   - 使用「」标注直接引用的原文
   - 示例：「汤面漂浮着点点金黄色的辣椒油，在灯光下形成星星点点的高光」（来自 note_id: xxx）
   - 每个 generation_prompt 必须包含至少 **5 处原文引用**
   - 引用时保留原始数据中的具体数值（HEX色值、visual_prominence评分、Kelvin色温）

   **C. 合成逻辑（当需要组合多个爆款特征时）**：
   - 从多个爆款帖子的 food_analysis 中提取 **高频出现的共性特征**
   - 优先引用 `visual_prominence` 评分高的食材
   - 优先引用 `visual_appeal_score` 评分高的帖子
   - 将这些共性特征组合成"理想爆款"的描述
   - 必须标注每个特征来源于哪个 note_id
   - 示例：「流心蛋黄，visual_prominence: 0.9」（出现于 note_id: A, B, C，占比 75%）

   **D. 禁止行为**：
   - ❌ 禁止完全重新编造视觉描述，必须基于原始数据
   - ❌ 禁止忽略 food_analysis 中已有的 dynamic_elements
   - ❌ 禁止使用与原始数据不符的颜色值（必须使用原始HEX）
   - ❌ 禁止编造原始数据中不存在的食材或物品
   - ❌ 禁止使用模糊描述替代原始数据中的精确描述
   - ❌ 禁止忽略 light_interaction 中的 specular_highlights 和 subsurface_scattering

   **E. 验证清单（生成前自检）**：
   - [ ] generation_prompt 中是否包含至少5处「」引用？
   - [ ] 所有HEX色值是否来自原始 color_palette？
   - [ ] 所有食材是否来自原始 food_analysis.ingredients[]？
   - [ ] dynamic_elements（蒸汽/流动/融化）是否直接引用原始数据？
   - [ ] light_interaction 是否被引用？
   - [ ] 是否标注了特征来源的 note_id？
   - [ ] 是否引用了 visual_appeal_score 和 visual_prominence？

9. **DATA-DRIVEN**: 所有数据（百分比、数量、排名）必须基于输入数据计算得出，不能编造

10. **12 SLIDES EXACTLY**: 必须生成恰好 12 张 Slide，slide_number 从 1 到 12

11. **NO NULL VALUES**: 如果某个字段不适用，使用空字符串 "" 或空数组 []，不使用 null

12. **CHINESE OUTPUT**: 所有文字内容使用中文，专业术语可保留英文（如 Eye-level、shallow depth of field）

---

## 开始任务

请仔细阅读以下数据（仅包含具有爆品潜质的优质内容），然后输出符合上述严格 schema 的 JSON：

```json
[在此处粘贴筛选后的 JSON 数据，仅保留 label="满足" 的帖子]
```
