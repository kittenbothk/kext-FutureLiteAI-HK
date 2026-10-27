# KOIX 固件端结构化识别结果改造需求

## 1. 背景与目标

当前 KOIX 串口协议已经定义了通用指令、物体识别 `OBJECT` 事件和人脸识别
`FACE` 事件，但特征分类、手势、姿态、OCR 等 App 尚未完整定义结构化结果。

积木端计划按功能拆分为物体识别、人脸识别、特征分类等分栏。为了让积木能够稳定读取
目标数量、坐标、名称、ID 和置信度，固件端需要为每个 App 提供字段固定、可验证的结果帧。

本次改造目标：

- 统一所有识别 App 的多目标结果格式。
- 补齐特征分类结果和学习成功响应。
- 统一 `RESULT?` 查询结果与实时推流的行为。
- 为后续手势、姿态、OCR 等积木预留一致的扩展方式。

## 2. 通用结果帧

所有识别 App 使用以下格式：

```text
KOIX <EVENT> seq=<序号> index=<目标序号> total=<目标数量> [业务字段...] <CHK>\r\n
```

字段约束：

| 字段 | 类型 | 必选 | 说明 |
| --- | --- | --- | --- |
| `EVENT` | ASCII 字符串 | 是 | 当前 App 固定的事件名称 |
| `seq` | 非负整数 | 是 | 一次推理结果的唯一递增序号 |
| `index` | 非负整数 | 有目标时是 | 当前目标序号，从 `0` 开始 |
| `total` | 非负整数 | 是 | 本次实际返回的目标总数 |
| `CHK` | 两位十六进制 | 是 | 遵循现有 XOR8 校验规则 |

通用行为：

1. 同一次推理产生的所有目标必须使用相同的 `EVENT` 和 `seq`。
2. `index` 必须从 `0` 连续排列到 `total - 1`。
3. 没有识别结果时发送一条 `total=0` 事件，不携带 `index`。
4. 中文、空格、`%` 和非 ASCII 内容使用 UTF-8 百分号编码。
5. 字段名称和字段类型一经发布应保持兼容，不能随界面语言变化。
6. 坐标统一使用屏幕显示坐标系，字段固定为 `x/y/w/h`。
7. 置信度统一使用 `score`，数值范围为 `0` 到 `1`。

无结果示例：

```text
KOIX OBJECT seq=126 total=0 <CHK>\r\n
```

## 3. 各 App 结果定义

### 3.1 物体识别

事件名称：`OBJECT`

```text
KOIX OBJECT seq=125 index=0 total=2 class_id=0 name=person label=%E4%BA%BA score=0.932 x=32 y=70 w=144 h=310 <CHK>\r\n
```

业务字段：

| 字段 | 类型 | 必选 | 说明 |
| --- | --- | --- | --- |
| `class_id` | 整数 | 是 | 模型类别 ID |
| `name` | ASCII 字符串 | 是 | 稳定英文类别名，不随界面语言改变 |
| `label` | 编码字符串 | 是 | 界面显示名称 |
| `score` | 浮点数 | 是 | 检测置信度 |
| `x/y/w/h` | 整数 | 是 | 目标框坐标和尺寸 |

现有 `OBJECT` 格式可以保持不变。

### 3.2 人脸识别

事件名称：`FACE`

```text
KOIX FACE seq=126 index=0 total=1 face_id=face_003 label=%E5%BC%A0%E4%B8%89 score=0.89 x=86 y=120 w=138 h=166 emotion=happy emotion_score=0.91 <CHK>\r\n
```

业务字段：

| 字段 | 类型 | 必选 | 说明 |
| --- | --- | --- | --- |
| `face_id` | ASCII 字符串 | 是 | 已录入人脸 ID；未知人脸返回 `unknown` |
| `label` | 编码字符串 | 是 | 用户标签；未知人脸返回 `unknown` |
| `score` | 浮点数 | 是 | 人脸匹配置信度 |
| `x/y/w/h` | 整数 | 是 | 人脸框坐标和尺寸 |
| `emotion` | ASCII 字符串 | 否 | 表情名称 |
| `emotion_score` | 浮点数 | 否 | 表情置信度 |

现有 `FACE` 格式可以保持不变，但需要统一未知人脸的字段值。

### 3.3 特征分类

事件名称：`CLASS`

```text
KOIX CLASS seq=130 index=0 total=1 class_id=2 label=apple score=0.95 <CHK>\r\n
```

业务字段：

| 字段 | 类型 | 必选 | 说明 |
| --- | --- | --- | --- |
| `class_id` | 非负整数 | 是 | 稳定的分类 ID |
| `label` | 编码字符串 | 是 | 用户设置的分类标签 |
| `score` | 浮点数 | 是 | 分类置信度 |

没有可信分类结果时：

```text
KOIX CLASS seq=131 total=0 <CHK>\r\n
```

这是本次积木改造必须新增的结果事件。

### 3.4 手势识别（后续扩展）

事件名称：`GESTURE`

```text
KOIX GESTURE seq=140 index=0 total=1 gesture_id=gesture_001 label=open_hand score=0.92 x=20 y=30 w=100 h=120 <CHK>\r\n
```

固定字段为 `gesture_id`、`label`、`score` 和 `x/y/w/h`。

### 3.5 姿态识别（后续扩展）

事件名称：`POSE`

```text
KOIX POSE seq=150 index=0 total=1 pose_id=pose_001 label=standing score=0.91 x=20 y=30 w=160 h=300 <CHK>\r\n
```

固定字段为 `pose_id`、`label`、`score` 和 `x/y/w/h`。

如需返回关键点，应另外定义固定格式，不能使用数量和名称不确定的临时字段。

### 3.6 OCR（后续扩展）

事件名称：`OCR`

```text
KOIX OCR seq=160 index=0 total=1 text=%E4%BD%A0%E5%A5%BD score=0.96 x=10 y=20 w=200 h=40 <CHK>\r\n
```

固定字段为 `text`、`score` 和 `x/y/w/h`。

### 3.7 二维码与条形码（后续扩展）

```text
KOIX QRCODE seq=170 index=0 total=1 content=https%3A%2F%2Fexample.com x=10 y=20 w=100 h=100 <CHK>\r\n
KOIX BARCODE seq=171 index=0 total=1 content=6901234567890 format=EAN13 x=10 y=20 w=180 h=60 <CHK>\r\n
```

二维码固定字段为 `content` 和 `x/y/w/h`；条形码另外返回 `format`。

## 4. `RESULT?` 行为

执行 `RESULT?` 后，固件先发送摘要，再发送完整的结构化结果帧。

有结果示例：

```text
KOIX OK RESULT? app=self_learning event=CLASS seq=130 total=1 <CHK>\r\n
KOIX CLASS seq=130 index=0 total=1 class_id=2 label=apple score=0.95 <CHK>\r\n
```

无结果示例：

```text
KOIX OK RESULT? app=self_learning event=CLASS seq=131 total=0 <CHK>\r\n
KOIX CLASS seq=131 total=0 <CHK>\r\n
```

必须满足：

1. 摘要中的 `app/event/seq/total` 与后续事件完全一致。
2. 摘要必须先于对应的事件帧发送。
3. `RESULT?` 返回一次完整推理结果，不能混入不同 `seq` 的数据。
4. 查询结果不受实时推流最大目标数限制。
5. `total=N` 时必须恰好发送 `N` 条目标事件。
6. `total=0` 时仍必须发送一条对应事件，用于清除主控端上一帧数据。

## 5. 特征学习响应

学习成功响应必须返回最终生成或使用的 ID，积木端不能依赖本地推测 ID。

创建新分类：

```text
KOIX OK CLASS LEARN class_id=2 label=apple samples=1 <CHK>\r\n
```

向已有分类追加样本：

```text
KOIX OK CLASS LEARN class_id=2 label=apple samples=2 <CHK>\r\n
```

其他录入操作建议采用相同规则：

```text
KOIX OK FACE REGISTER face_id=face_003 label=%E5%BC%A0%E4%B8%89 <CHK>\r\n
KOIX OK GESTURE REGISTER gesture_id=gesture_002 label=open_hand <CHK>\r\n
KOIX OK POSE REGISTER pose_id=pose_004 label=standing <CHK>\r\n
```

失败时继续使用现有错误码，例如：

```text
KOIX ERR NOT_READY <CHK>\r\n
KOIX ERR REGISTER_FAILED <CHK>\r\n
KOIX ERR BAD_CLASS <CHK>\r\n
KOIX ERR BAD_LABEL <CHK>\r\n
```

## 6. `CAPS?` 能力声明

建议让当前 App 返回事件名称、结果字段和支持的指令：

```text
KOIX OK CAPS? app=object event=OBJECT fields=class_id%2Cname%2Clabel%2Cscore%2Cx%2Cy%2Cw%2Ch commands=RESULT%3F%2CPARAM%20LIST <CHK>\r\n
```

至少应包含：

- `app`：当前 App ID。
- `event`：当前 App 的结果事件名称。
- `fields`：该事件支持的业务字段。
- `commands`：当前 App 支持的特色指令。

如果暂时无法修改 `CAPS?`，不能影响本次最低范围交付，但后续增加 App 时建议补上。

## 7. 本次最低交付范围

固件端至少完成以下修改后，积木端才能可靠拆分为物体识别、人脸识别和特征分类分栏：

1. 保持并验证现有 `OBJECT` 结果格式。
2. 保持并验证现有 `FACE` 结果格式。
3. 新增 `CLASS` 结构化分类结果。
4. `CLASS LEARN` 成功响应返回 `class_id`、`label` 和 `samples`。
5. 统一 `RESULT?` 摘要与后续事件帧的 `event/seq/total`。
6. 无结果时发送 `total=0` 事件，确保主控端清除旧数据。
7. 更新 `UART_PROTOCOL.md`，明确上述字段、类型和响应顺序。

手势、姿态、OCR、二维码等结果可以后续按同一规范逐项实现。

## 8. 验收标准

### 8.1 物体识别

- 单目标返回一条 `OBJECT`，且 `index=0 total=1`。
- 多目标的 `seq` 相同，`index` 连续，帧数等于 `total`。
- 能稳定读取物体名称、置信度和坐标。
- 从有目标变为无目标时返回一次 `OBJECT ... total=0`。

### 8.2 人脸识别

- 已录入人脸返回稳定的 `face_id` 和用户标签。
- 未知人脸返回约定的 `unknown`，不返回空 ID。
- 表情未开启或无有效结果时，可以省略表情字段。

### 8.3 特征分类

- `CLASS LEARN NEW` 成功后返回固件实际分配的 `class_id`。
- 向已有分类学习时返回相同的 `class_id` 和更新后的 `samples`。
- 分类识别返回 `CLASS` 事件及 `class_id/label/score`。
- 无可信分类时返回 `CLASS ... total=0`。

### 8.4 `RESULT?`

- 摘要始终先于目标事件发送。
- 摘要和事件的 `event/seq/total` 完全一致。
- 连续快速查询时，不出现不同 `seq` 数据混合。
- 标签包含中文、空格和 `%` 时，可以正确编码并通过校验。

